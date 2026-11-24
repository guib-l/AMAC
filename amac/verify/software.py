"""Per-software checks: executable and Python library."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import re
import shlex
import string
import sys
from pathlib import Path

from amac.engine.profile import checked_executable
from amac.verify.report import Report

# Placeholders replaced in the ``launcher`` by amac.engine.profile.Program.
LAUNCHER_FIELDS = {"process_unit"}

# Section keys holding a path to a resource (file or directory).
RESOURCE_KEYS = ("basis",)

# Software that also needs a Python library, checked by importing it.
PYTHON_MODULES = {
    "pyscf": "pyscf", 
    "deMonNano": "deMonPy"
}

# Software whose Python library is installed by an amac extra (pyproject.toml).
EXTRAS = {"pyscf": "pyscf"}


def extra_requirements(extra: str) -> list[str]:
    """Requirements of an amac extra, read from the installed amac metadata.

    Returns:
        The requirement strings, empty when amac is not installed or its
        metadata does not declare the extra (e.g. not reinstalled yet).
    """
    try:
        requires = importlib.metadata.requires("amac") or []
    except importlib.metadata.PackageNotFoundError:
        return []
    marker = re.compile(rf"""extra\s*==\s*["']{re.escape(extra)}["']""")
    return [req.split(";")[0].strip() for req in requires if marker.search(req)]


def install_hint(package: str, extra: str | None = None) -> str:
    """Command installing ``package`` with the running interpreter (never run).

    The requirements of the amac ``extra`` are used when known, else the
    bare package name.
    """
    requirements = (extra_requirements(extra) if extra else []) or [package]
    return f"{sys.executable} -m pip install " + " ".join(shlex.quote(r) for r in requirements)


def check_software(report: Report, soft: type, section: dict) -> None:
    """Run every per-software check on one configuration section."""
    check_executable(report, soft, section)
    check_launcher(report, soft, section)
    check_module(report, soft)
    check_env(report, soft, section)
    check_resources(report, soft, section)


def check_executable(report: Report, soft: type, section: dict) -> None:
    """Check the executable: configured, absolute, existing, executable.

    A software that needs a binary but has no ``executable`` (or an empty
    one) is only a warning: the software is unavailable, the configuration
    is not broken.
    """
    value = section.get("executable")
    if value is None or (isinstance(value, str) and not value.strip()):
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


def check_launcher(report: Report, soft: type, section: dict) -> None:
    """Check the MPI ``launcher``: a non-empty list of strings whose first
    element is an absolute executable, using only known placeholders.
    """
    launcher = section.get("launcher")
    if launcher is None:
        return
    if (
        not isinstance(launcher, list)
        or not launcher
        or not all(isinstance(part, str) for part in launcher)
    ):
        report.add(soft.name, "launcher", "fail", "must be a non-empty list of strings")
        return

    for part in launcher:
        try:
            fields = {name for _, name, _, _ in string.Formatter().parse(part) if name is not None}
        except ValueError as error:
            report.add(soft.name, "launcher", "fail", f"{part!r}: {error}")
            return
        unknown = fields - LAUNCHER_FIELDS
        if unknown:
            report.add(
                soft.name,
                "launcher",
                "fail",
                f"{part!r}: unknown placeholder {sorted(unknown)} "
                f"(known: {sorted(LAUNCHER_FIELDS)})",
            )
            return

    path = Path(launcher[0])
    if not path.is_absolute():
        report.add(soft.name, "launcher", "fail", f"must be absolute, got {path}")
    elif not path.is_file():
        report.add(soft.name, "launcher", "fail", f"not found: {path}")
    elif not os.access(path, os.X_OK):
        report.add(soft.name, "launcher", "fail", f"not executable: {path}")
    else:
        report.add(soft.name, "launcher", "ok", " ".join(launcher))


def check_resources(report: Report, soft: type, section: dict) -> None:
    """Check the resource paths (``basis``...): they must exist.

    A relative path is only a warning: it depends on the current directory.
    """
    for key in RESOURCE_KEYS:
        value = section.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            report.add(soft.name, key, "fail", f"must be a non-empty path, got {value!r}")
            continue
        path = Path(value)
        if not path.exists():
            report.add(soft.name, key, "fail", f"not found: {path}")
        elif not path.is_absolute():
            report.add(soft.name, key, "warn", f"relative path, depends on the current directory: {path}")
        else:
            report.add(soft.name, key, "ok", str(path))


def check_module(report: Report, soft: type) -> None:
    """Check the Python library of software that runs in process."""
    module = PYTHON_MODULES.get(soft.name)
    if module is None:
        return
    try:
        importlib.import_module(module)
    except ImportError as error:
        extra = EXTRAS.get(soft.name)
        hint = (
            install_hint(module, extra)
            if extra
            else f"no amac extra: install {module} by hand"
        )
        report.add(soft.name, "module", "fail", f"{module} not importable ({error}) → {hint}")
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
