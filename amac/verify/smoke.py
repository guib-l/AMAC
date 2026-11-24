"""Smoke runs: one tiny single point per software (``amac-check --run``)."""

from __future__ import annotations

import copy
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from amac.verify.report import Report

# Wall time given to a smoke job when a scheduler is configured.
RUN_WALL_TIME = "00:10:00"


def _dftb_basis(key: str, **extra) -> Callable[[dict], dict]:
    """Parameters of a DFTB-2 run whose Slater-Koster directory is ``section[key]``."""

    def build(section: dict) -> dict:
        if not section.get(key):
            raise ValueError(f"no {key!r} in the configuration section")
        return {
            "method": "dftb-2",
            "method_args": {"basis": {"directory": section[key], **extra}},
            "module": "single-point",
        }

    return build


def _hf(basis: str) -> Callable[[dict], dict]:
    """Parameters of an HF run in ``basis``."""
    return lambda section: {
        "method": "hf",
        "method_args": {"basis": basis},
        "module": "single-point",
    }


# Software name -> parameters built from its configuration section
# (the same settings as examples/<software>/01_*.py, on H2).
SMOKE_RUNS: dict[str, Callable[[dict], dict]] = {
    "dftb+": _dftb_basis("basis"),
    "deMonNano": _dftb_basis("basis", ptype="BIO"),
    "orca": _hf("def2-svp"),
    "pyscf": _hf("sto-3g"),
    "openmolcas": _hf("cc-pvdz"),
}


def runnable(report: Report, soft: type) -> str | None:
    """Return why ``soft`` cannot be run, or None when it can.

    A software is run only when none of its static checks failed and, if it
    needs a binary, its executable check passed.
    """
    checks = [check for check in report.checks if check.scope == soft.name]
    if any(check.status == "fail" for check in checks):
        return "static checks failed"
    if soft.requires_executable and not any(
        check.name == "executable" and check.status == "ok" for check in checks
    ):
        return "no executable"
    if soft.name not in SMOKE_RUNS:
        return "no smoke run defined"
    return None


def smoke_config(config: dict) -> dict:
    """Copy of ``config`` where each software gets a short scheduler wall time.

    The wall time only matters when the effective ``hpc`` block of the
    software enables a scheduler; otherwise it is ignored.
    """
    config = copy.deepcopy(config)
    for section in config.get("software", {}).values():
        if not isinstance(section, dict):
            continue
        override = section.get("hpc")
        if override is not None and not isinstance(override, dict):
            continue  # Malformed: reported by the static checks.
        override = dict(override or {})
        defaults = override.get("defaults")
        override["defaults"] = {
            **(defaults if isinstance(defaults, dict) else {}),
            "time": RUN_WALL_TIME,
        }
        section["hpc"] = override
    return config


def run_smoke(report: Report, config: dict, *, workdir: str | Path | None = None) -> None:
    """Run one H2 single point per configured software and report the energy.

    The process-wide configuration is replaced during the runs and restored
    afterwards. Each run works in its own directory under ``workdir``
    (default: a new hidden directory in the current one, so that it is on a
    filesystem shared with the compute nodes when a scheduler is used). The
    directories of successful runs are removed; failed ones are kept.

    Args:
        report: Report holding the static checks; the ``run`` lines are added.
        config: The AMAC configuration.
        workdir: Parent directory of the runs.
    """
    from ase.build import molecule

    from amac import config as amac_config
    from amac.amac import AMAC
    from amac.asset import Software

    sections = config.get("software")
    if not isinstance(sections, dict):
        return

    root = Path(workdir) if workdir is not None else None
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix=".amac-check-", dir=root or Path.cwd()))

    previous = amac_config.CONFIGURE
    amac_config.configure(config=smoke_config(config))
    try:
        for key, section in sections.items():
            soft = Software._registry.get(key.upper())
            if soft is None or not isinstance(section, dict):
                continue
            reason = runnable(report, soft)
            if reason is not None:
                report.add(soft.name, "run", "skip", reason)
                continue
            run_dir = base / soft.name
            start = time.perf_counter()
            try:
                parameters = SMOKE_RUNS[soft.name](section)
                calc = AMAC(software=soft.name, workdir=run_dir, label="amac-check")
                calc.handler_register("lowest-energy")
                calc.parameters_register(**parameters)
                calc.run(molecule("H2"))
                energy = calc.instance.res.product["lowest-energy"]
            except Exception as error:  # noqa: BLE001  any failure is reported
                first = (str(error).strip().splitlines() or [""])[0]
                kept = f" (kept in {run_dir})" if run_dir.exists() else ""
                report.add(soft.name, "run", "fail", f"{type(error).__name__}: {first}{kept}")
                continue
            elapsed = time.perf_counter() - start
            report.add(soft.name, "run", "ok", f"H2 E = {float(energy):.6f} Ha in {elapsed:.1f} s")
            shutil.rmtree(run_dir, ignore_errors=True)
    finally:
        amac_config.configure(config=previous)
        if not any(base.iterdir()):
            base.rmdir()
