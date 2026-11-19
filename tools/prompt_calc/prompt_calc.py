#!/usr/bin/env python3
"""prompt_calc: turn a free-text prompt or a spec file into an AMAC calculation.

Pipeline (design doc ``docs/prompt_calc_design.md``):

    transcribe -> validate -> resolve -> build image -> execute -> report

Stage 1 (transcribe, N LLM draws + vote) is the only non-deterministic step;
stages 2-6 are deterministic, pure functions, importable and unit-testable
without the CLI. Same resolved spec -> byte-identical inputs, same workdir.

Exit codes (design doc, section 8): 0 ok, 1 RUNTIME_FAILURE,
2 INVALID_SPEC/AMBIGUOUS, 3 UNSUPPORTED_CATALOG/UNSUPPORTED_SOFTWARE/
MISSING_DATA, 4 USER_ABORT.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core import (
    CODES,
    EXIT_OK,
    EXIT_RUNTIME_FAILURE,
    Failure,
    _Context,
    canon_software,
    load_defaults,
    load_schema,
    spec_hash,
)
from execute import build_image, execute
from report import make_report, write_llm_samples, write_report
from resolve import resolve
from validate import validate
from vote import _llm_stage


def _pipeline(args) -> dict:
    """Run validate -> resolve -> build image -> execute -> report."""
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    schema = load_schema()
    defaults = load_defaults()
    ctx = _Context()
    try:
        if args.spec:
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                raise Failure("INVALID_SPEC", "the spec file must hold a JSON object")
            ctx.spec = spec
        else:
            _llm_stage(args, schema, ctx)

        software = args.software or ctx.spec.get("software")
        if software is None:
            software = defaults["software"]
            ctx.injected.append("software")
        ctx.spec["software"] = canon_software(software, schema)

        errors = validate(ctx.spec, schema, ctx.spec["software"], defaults, config)
        if errors:
            raise Failure(
                errors[0].code, "; ".join(e.message for e in errors), field=errors[0].field
            )

        resolved = resolve(ctx.spec, defaults, config, schema["aliases"])
        ctx.injected.extend(resolved.injected)
        ctx.spec_hash = spec_hash(resolved.spec)
        image = build_image(resolved.spec.get("structure") or {}, defaults.get("molecule-aliases"))
        execution = execute(
            resolved,
            image,
            config,
            run_root=Path(".run"),
            fresh=args.fresh,
            dry_run=args.dry_run,
        )
        ctx.workdir = execution.workdir
        report = make_report(
            "succeeded",
            vote=ctx.vote,
            ambiguities=ctx.ambiguities,
            injected=ctx.injected,
            spec_hash_value=ctx.spec_hash,
            workdir=execution.workdir,
            products=execution.products,
        )
    except Failure as failure:
        report = make_report(
            failure.code,
            code=failure.code,
            message=failure.message,
            vote=ctx.vote,
            ambiguities=ctx.ambiguities,
            injected=ctx.injected,
            spec_hash_value=ctx.spec_hash,
            workdir=failure.workdir or ctx.workdir,
        )
    except Exception as error:  # last resort: a failure is never a traceback
        report = make_report(
            "RUNTIME_FAILURE",
            code="RUNTIME_FAILURE",
            message=f"unexpected {type(error).__name__}: {error}",
            vote=ctx.vote,
            ambiguities=ctx.ambiguities,
            injected=ctx.injected,
            spec_hash_value=ctx.spec_hash,
            workdir=ctx.workdir,
        )
    if ctx.raw:
        if report["workdir"] is not None:
            write_llm_samples(ctx.raw, report["workdir"])
        else:
            # The vote failed before any workdir existed: keep the samples
            # in the report (the abort message).
            report["llm_samples"] = ctx.raw
    # The report is written for every terminal status (design doc,
    # section 8) — whenever a workdir holds it.
    write_report(report, report["workdir"])
    return report


def _print_report(report: dict, dry_run: bool) -> None:
    """Stdout: the report JSON, the composed inputs (dry run), product values."""
    if report["workdir"] is None:
        if "llm_samples" in report:
            # The vote failed before a workdir existed: print the full report
            # so the raw samples (provenance) survive the abort.
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"prompt_calc: {report['code']}: {report['message']}")
        return
    print(json.dumps(report, indent=2, default=str))
    if dry_run:
        # Design doc, section 7: a dry run prints the composed inputs.
        print(f"\n(dry run: nothing was launched; inputs composed in {report['workdir']}):")
        workdir = Path(report["workdir"])
        for path in sorted(workdir.iterdir()):
            if not path.is_file() or path.name in (
                "spec.json",
                "products.json",
                "llm_samples.json",
            ):
                continue
            print(f"--- {path.name} ---")
            print(path.read_text(encoding="utf-8"))
    for name, value in report["products"].items():
        if name == "lowest-energy" and isinstance(value, (int, float)):
            print(f"{name}: {value:.8f} Hartree ({value * 627.509:.2f} kcal/mol)")
        else:
            print(f"{name}: {value}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Command line of prompt_calc (design doc, section 10)."""
    parser = argparse.ArgumentParser(
        prog="prompt_calc",
        description="Turn a prompt or a spec file into an AMAC calculation.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="free-text request, translated by an LLM (N draws + vote)")
    source.add_argument("--spec", help="JSON spec file (deterministic entry point, no LLM)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compose the inputs, write them to the workdir, launch nothing",
    )
    parser.add_argument(
        "--yes", action="store_true", help="never ask; an ambiguous vote is a hard failure"
    )
    parser.add_argument("--config", default="config-amac.json", help="AMAC configuration file")
    parser.add_argument("--software", help="software override (dftb+, deMonNano)")
    parser.add_argument(
        "--fresh", action="store_true", help="new timestamped workdir even if the spec hash exists"
    )
    parser.add_argument("--llm-url", help="OpenAI-compatible /chat/completions endpoint (--prompt)")
    parser.add_argument("--api-key", help="API key of the LLM endpoint")
    parser.add_argument(
        "--api-key-env", metavar="VARNAME", help="read the API key from this environment variable"
    )
    parser.add_argument("--llm-model", help="model name sent to the endpoint (optional)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: run the pipeline and return the typed exit code."""
    args = _parse_args(argv)
    report = _pipeline(args)
    _print_report(report, args.dry_run)
    if report["status"] == "succeeded":
        return EXIT_OK
    return CODES.get(report["code"], EXIT_RUNTIME_FAILURE)


if __name__ == "__main__":
    sys.exit(main())
