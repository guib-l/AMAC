"""Checks of the ``hpc`` section: job scheduler executables."""

from __future__ import annotations

import os
from pathlib import Path

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
    if scheduler != "slurm":
        report.add("core", "hpc", "fail", f"unknown scheduler {scheduler!r} (supported: slurm)")
        return
    report.add("core", "hpc", "ok", f"scheduler: {scheduler}")
    if check_scheduler_executable(report, "sbatch", hpc.get("sbatch"), required=True):
        check_scheduler_executable(report, "squeue", hpc.get("squeue"), required=False)


def check_scheduler_executable(report: Report, name: str, value: object, *, required: bool) -> bool:
    """Check one scheduler executable: configured, absolute, existing, executable.

    Returns:
        True when checking may continue to the next executable (an
        optional executable that is not configured included).
    """
    if value is None:
        if required:
            report.add("core", name, "fail", "not configured")
            return False
        report.add("core", name, "warn", "not configured (only needed for asynchronous mode)")
        return True
    if not isinstance(value, str):
        report.add("core", name, "fail", f"must be a string, got {value!r}")
        return False
    path = Path(value)
    if not path.is_absolute():
        report.add("core", name, "fail", f"must be absolute, got {path}")
        return False
    if not path.is_file():
        report.add("core", name, "fail", f"not found: {path}")
        return False
    if not os.access(path, os.X_OK):
        report.add("core", name, "fail", f"not executable: {path}")
        return False
    report.add("core", name, "ok", str(path))
    return True
