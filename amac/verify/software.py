"""Per-software checks: executable and Python library."""

from __future__ import annotations

import importlib
import importlib.metadata
import os

from amac.engine.profile import checked_executable
from amac.verify.report import Report

# Software that also needs a Python library, checked by importing it.
PYTHON_MODULES = {
    "pyscf": "pyscf", 
    "deMonNano": "deMonPy"
}


def check_software(report: Report, soft: type, section: dict) -> None:
    """Run every per-software check on one configuration section."""
    check_executable(report, soft, section)
    check_module(report, soft)
    check_env(report, soft, section)


def check_executable(report: Report, soft: type, section: dict) -> None:
    """Check the executable: configured, absolute, existing, executable.

    A software that needs a binary but has no ``executable`` is only a
    warning: the software is unavailable, the configuration is not broken.
    """
    value = section.get("executable")
    if value is None:
        if soft.requires_executable:
            report.add(soft.name, "executable", "warn", "not configured")
        return
    try:
        path = checked_executable(soft.name, value, soft.requires_executable)
    except ValueError as error:
        report.add(soft.name, "executable", "fail", str(error).removeprefix(f"{soft.name}: "))
        return
    if not path.is_file():
        report.add(soft.name, "executable", "fail", f"not found: {path}")
    elif not os.access(path, os.X_OK):
        report.add(soft.name, "executable", "fail", f"not executable: {path}")
    else:
        report.add(soft.name, "executable", "ok", str(path))


def check_module(report: Report, soft: type) -> None:
    """Check the Python library of software that runs in process."""
    module = PYTHON_MODULES.get(soft.name)
    if module is None:
        return
    try:
        importlib.import_module(module)
    except ImportError as error:
        report.add(soft.name, "module", "fail", f"{module} not importable ({error})")
        return
    try:
        version = importlib.metadata.version(module)
    except importlib.metadata.PackageNotFoundError:
        version = "unknown version"
    report.add(soft.name, "module", "ok", f"{module} {version}")


def check_env(report: Report, soft: type, section: dict) -> None:
    """Check that the ``env`` values are strings (never searches the filesystem)."""
    env = section.get("env")
    if env is None:
        return
    if not isinstance(env, dict):
        report.add(soft.name, "env", "fail", "must be a JSON object")
        return
    problems = 0
    for key, value in env.items():
        if not isinstance(value, str):
            report.add(soft.name, "env", "warn", f"{key}: value is not a string ({value!r})")
            problems += 1
    if not problems:
        report.add(soft.name, "env", "ok", f"{len(env)} variables")
