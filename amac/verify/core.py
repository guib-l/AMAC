"""Core checks: Python version, mandatory dependencies, configuration."""

from __future__ import annotations

import importlib
import platform
import sys

from amac.verify.report import Report
from amac.verify.software import check_software

PYTHON_MIN = (3, 12)
DEPENDENCIES = ("numpy", "ase", "pip", "amac", "h5py")


def check_core(report: Report, config: dict) -> None:
    """Run the checks that do not depend on a particular software."""
    check_python(report)
    dependencies_ok = check_dependencies(report)
    check_schema(report, config, dependencies_ok)


def check_python(report: Report) -> None:
    """Check the Python version."""
    ok = sys.version_info >= PYTHON_MIN
    report.add("core", "python", "ok" if ok else "fail", platform.python_version())


def check_dependencies(report: Report) -> bool:
    """Import the mandatory dependencies and report their version.

    Returns:
        True when every dependency is importable.
    """
    ok = True
    for name in DEPENDENCIES:
        try:
            module = importlib.import_module(name)
        except ImportError as error:
            report.add("core", name, "fail", f"not importable ({error})")
            ok = False
        else:
            report.add("core", name, "ok", getattr(module, "__version__", "unknown version"))
    return ok


def check_schema(report: Report, config: dict, dependencies_ok: bool) -> None:
    """Check the structure of the configuration (roadmap 1.2).

    Unknown keys are ignored: only the keys AMAC actually reads matter.
    """
    if "software" not in config:
        report.add("core", "config", "fail", "missing 'software' section")
        return
    sections = config["software"]
    if not isinstance(sections, dict):
        report.add("core", "config", "fail", "'software' must be a JSON object")
        return
    if not dependencies_ok:
        report.add("core", "config", "skip", "software names not checked (missing dependency)")
        return
    check_sections(report, sections)


def check_sections(report: Report, sections: dict) -> None:
    """Check each ``software.<name>`` section against the registered assets."""
    # Importing amac.asset registers every asset; it needs numpy and ase.
    from amac.asset import Software

    seen: dict[str, str] = {}
    for key, section in sections.items():
        soft = Software._registry.get(key.upper())
        if soft is None:
            report.add(key, "software", "fail", "unknown software")
            continue
        if soft.name in seen:
            report.add(soft.name, "config", "warn", f"duplicate section {seen[soft.name]!r}")
            continue
        seen[soft.name] = key
        if not isinstance(section, dict):
            report.add(soft.name, "config", "fail", "section must be a JSON object")
            continue

        check_software(report, soft, section)
