from __future__ import annotations

import copy
import os
import sys

from core import Failure, Vote, _Context, canonical_json

# ----------------------------------------------------------------------
# Stage 1 — TRANSCRIBE (voting, design doc, section 3.3)
# ----------------------------------------------------------------------


def _drop_empty(obj):
    """Recursively drop None, empty dicts and empty lists."""
    if isinstance(obj, dict):
        return {k: _drop_empty(v) for k, v in obj.items() if v not in (None, [], {})}
    if isinstance(obj, list):
        return [_drop_empty(v) for v in obj]
    return obj


def _normalize_spec(spec: dict) -> dict:
    """Canonicalize known tokens of a spec for voting (case, handlers)."""
    for key in ("software", "method", "module"):
        value = spec.get(key)
        if isinstance(value, str):
            spec[key] = value.strip().lower()
    structure = spec.get("structure")
    if isinstance(structure, dict) and isinstance(structure.get("name"), str):
        structure["name"] = structure["name"].strip().upper()  # "H2O" vs "h2o"
    handlers = spec.get("handlers")
    if isinstance(handlers, list):
        spec["handlers"] = [str(h).strip().lower().replace("_", "-") for h in handlers]
    args = spec.get("method_args")
    if isinstance(args, dict) and isinstance(args.get("dispersion"), str):
        args["dispersion"] = args["dispersion"].strip().lower()
    return _drop_empty(spec)


def _canonical_spec(spec: dict) -> str:
    """Canonical JSON of a spec: sort keys, drop empties, normalize tokens."""
    return canonical_json(_normalize_spec(copy.deepcopy(spec)))


def _disagree_fields(a: dict, b: dict) -> list[str]:
    """Dotted paths where two specs differ (one level into method_args)."""
    diffs = []
    for key in sorted(set(a) | set(b)):
        if key == "method_args" and isinstance(a.get(key), dict) and isinstance(b.get(key), dict):
            for sub in sorted(set(a[key]) | set(b[key])):
                if a[key].get(sub) != b[key].get(sub):
                    diffs.append(f"method_args.{sub}")
        elif a.get(key) != b.get(key):
            diffs.append(key)
    return diffs


def _field_value(spec: dict, dotted: str):
    """The value of a dotted path (one level into method_args)."""
    if dotted.startswith("method_args."):
        return (spec.get("method_args") or {}).get(dotted.removeprefix("method_args."))
    return spec.get(dotted)


def vote_samples(samples: list[tuple[dict, dict]]) -> Vote:
    """Vote on the canonical hash of the N transcribed specs.

    Unanimous -> high confidence; strict majority -> majority (minority
    fields appended to ambiguities); tie -> spec None (the caller runs the
    tie-break round or presents the candidates).
    """
    total = len(samples)
    groups: dict[str, list[dict]] = {}
    for spec, _raw in samples:
        groups.setdefault(_canonical_spec(spec), []).append(spec)
    ambiguities: list[str] = []
    for spec, _raw in samples:
        for note in spec.get("ambiguities") or []:
            if note not in ambiguities:
                ambiguities.append(note)
    variants = [group[0] for group in groups.values()]
    best = max(groups.values(), key=len)
    count = f"{len(best)}/{total}"
    if len(best) == total:
        return Vote(best[0], count, "high", [], variants, ambiguities)
    fields = []
    for variant in variants:
        if variant is not best[0]:
            fields = sorted(set(fields) | set(_disagree_fields(best[0], variant)))
    if len(best) > total / 2:
        # Name the conflicting values per disagreed field (design doc,
        # section 3.3: "'d4' instead of 'd3-bj'").
        for variant in variants:
            if variant is best[0]:
                continue
            minority = len(groups[_canonical_spec(variant)])
            for field in sorted(set(_disagree_fields(best[0], variant))):
                note = (
                    f"{minority}/{total} samples mapped {field} to "
                    f"{_field_value(variant, field)!r} instead of {_field_value(best[0], field)!r}"
                )
                if note not in ambiguities:
                    ambiguities.append(note)
        return Vote(best[0], count, "majority", fields, variants, ambiguities)
    return Vote(None, count, "tie", fields, variants, ambiguities)


# ----------------------------------------------------------------------
# CLI glue (LLM stage, interaction, pipeline, entry point)
# ----------------------------------------------------------------------


def _tie_break(args, schema: dict, url: str, api_key: str, vote: Vote, raw: list[dict]) -> Vote:
    """One tie-break round: re-prompt with the distinct candidates."""
    from llm import transcribe

    candidates = "\n".join(canonical_json(v) for v in vote.variants)
    prompt = (
        f"{args.prompt}\n\n"
        f"Independent readings of the request produced these candidate JSON specs:\n"
        f"{candidates}\n\n"
        "Pick the one that matches the request best, or report which fields are ambiguous."
    )
    samples = transcribe(prompt, schema, api_key, url, n=1, model=args.llm_model)
    if samples:
        raw.extend(payload for _spec, payload in samples)
        tie = vote_samples(samples)
        if tie.spec is not None and any(
            _canonical_spec(tie.spec) == _canonical_spec(v) for v in vote.variants
        ):
            return Vote(
                tie.spec, vote.count, "tie-break", vote.fields, vote.variants, vote.ambiguities
            )
    return vote


def _ask_candidate(variants: list[dict]) -> dict | None:
    """Present the distinct candidates and return the chosen one (or None)."""
    print("No stable vote. Distinct candidate specs:")
    for index, variant in enumerate(variants):
        print(f"  [{index}] {canonical_json(variant)}")
    try:
        answer = input("choose an index, or 'q' to abort: ").strip()
    except EOFError:
        return None
    if answer.isdigit() and 0 <= int(answer) < len(variants):
        return variants[int(answer)]
    return None


def _confirm(message: str) -> bool:
    """Ask the user to proceed; refuse when not on a TTY (no silent guess)."""
    if not sys.stdin.isatty():
        return False
    print(message)
    return input("proceed? [y/N] ").strip().lower() in ("y", "yes")


def _llm_stage(args, schema: dict, ctx: _Context) -> None:
    """Stage 1: N transcribed draws, vote, tie-break, ambiguities confirm."""
    api_key = args.api_key
    if args.api_key_env:
        api_key = os.environ.get(args.api_key_env) or api_key
    if not args.llm_url:
        raise Failure(
            "INVALID_SPEC",
            "--prompt needs --llm-url (an OpenAI-compatible /chat/completions endpoint)",
        )
    if not api_key:
        raise Failure("INVALID_SPEC", "--prompt needs --api-key or --api-key-env VARNAME")

    from llm import transcribe

    samples = transcribe(args.prompt, schema, api_key, args.llm_url, model=args.llm_model)
    if not samples:
        raise Failure("INVALID_SPEC", "the LLM returned no parseable spec (all attempts failed)")
    ctx.raw.extend(payload for _spec, payload in samples)
    vote = vote_samples(samples)
    if vote.spec is None:
        vote = _tie_break(args, schema, args.llm_url, api_key, vote, ctx.raw)
        if vote.spec is None:
            if args.yes:
                raise Failure(
                    "AMBIGUOUS",
                    f"no stable vote ({vote.count}); distinct candidates: {vote.variants} — "
                    "rephrase the prompt",
                )
            chosen = _ask_candidate(vote.variants)
            if chosen is None:
                raise Failure("USER_ABORT", "no candidate chosen")
            vote = Vote(chosen, vote.count, "user", [], vote.variants, vote.ambiguities)
    ctx.spec = vote.spec
    ctx.vote = {"count": vote.count, "confidence": vote.confidence, "fields": vote.fields}
    ctx.ambiguities.extend(vote.ambiguities)
    if ctx.ambiguities and not args.yes:
        summary = "; ".join(ctx.ambiguities[:5])
        if not _confirm(f"Interpretation notes: {summary}"):
            raise Failure("USER_ABORT", "user declined to proceed")
