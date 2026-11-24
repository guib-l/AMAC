"""Checks of the ``hpc`` section: job scheduler executables."""

from __future__ import annotations

import os
from pathlib import Path

from amac.engine.execute import merge_hpc
from amac.verify.report import Report


def check_hpc(report: Report, config: dict) -> None:
    """Check the scheduler configured in the ``hpc`` section, if any.

    A configuration without ``hpc`` prints nothing, like every other check.
    """
    hpc = config.get("hpc")
    if hpc is None:
        return
    if not isinstance(hpc, dict):
        report.add("core", "hpc", "fail", "hpc must be a JSON object")
        return
    scheduler = hpc.get("scheduler")
    if scheduler in (None, "local"):
        report.add("core", "hpc", "warn", "no scheduler (local execution)")
        return
    check_scheduler(report, "core", hpc)


def check_software_hpc(report: Report, soft: type, config: dict, section: dict) -> None:
    """Check the effective ``hpc`` block of one software (global + its own).

    Without a software ``hpc`` key, only the compatibility with the global
    block is checked: the global block itself is reported under ``core``.
    """
    override = section.get("hpc")
    base = config.get("hpc")
    if override is None and base is None:
        return
    try:
        hpc = merge_hpc(base, override, name=soft.name) or {}
    except ValueError as error:
        report.add(soft.name, "hpc", "fail", str(error))
        return
    if not isinstance(hpc, dict):
        return  # Malformed global block: already reported under "core".
    scheduler = hpc.get("scheduler")
    if scheduler in (None, "local"):
        if override is not None:
            report.add(soft.name, "hpc", "ok", "local execution")
        return
    if soft.execute_library:
        report.add(
            soft.name,
            "hpc",
            "fail",
            f"runs through a Python library, cannot be submitted to {scheduler!r}; "
            'add "hpc": {"scheduler": "local"} to its section',
        )
        return
    if override is not None:
        check_scheduler(report, soft.name, hpc)


def check_scheduler(report: Report, scope: str, hpc: dict) -> None:
    """Check a block that enables a scheduler: its name and its executables."""
    scheduler = hpc.get("scheduler")
    if scheduler != "slurm":
        report.add(scope, "hpc", "fail", f"unknown scheduler {scheduler!r} (supported: slurm)")
        return
    report.add(scope, "hpc", "ok", f"scheduler: {scheduler}")
    if check_scheduler_executable(report, "sbatch", hpc.get("sbatch"), required=True, scope=scope):
        check_scheduler_executable(
            report, "squeue", hpc.get("squeue"), required=False, scope=scope
        )


def check_scheduler_executable(
    report: Report, name: str, value: object, *, required: bool, scope: str = "core"
) -> bool:
    """Check one scheduler executable: configured, absolute, existing, executable.

    Returns:
        True when checking may continue to the next executable (an
        optional executable that is not configured included).
    """
    if value is None:
        if required:
            report.add(scope, name,"fail", "not configured")
            return False
        report.add(scope, name,"warn", "not configured (only needed for asynchronous mode)")
        return True
    if not isinstance(value, str):
        report.add(scope, name,"fail", f"must be a string, got {value!r}")
        return False
    path = Path(value)
    if not path.is_absolute():
        report.add(scope, name,"fail", f"must be absolute, got {path}")
        return False
    if not path.is_file():
        report.add(scope, name,"fail", f"not found: {path}")
        return False
    if not os.access(path, os.X_OK):
        report.add(scope, name,"fail", f"not executable: {path}")
        return False
    report.add(scope, name,"ok", str(path))
    return True
