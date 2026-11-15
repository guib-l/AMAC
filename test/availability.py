"""Detect which quantum chemistry software can run the ``real`` tests.

Everything comes from the AMAC configuration dict (``config-amac.json``):
no environment variable is read and no executable is searched in ``PATH``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Requirement:
    """What a software needs to run.

    Attributes:
        aliases: Other names of the software section in the configuration.
        executable: True if an absolute executable is required.
        basis: True if the ``basis`` option must be an existing directory.
        modules: Python modules that must be importable.
    """

    aliases: tuple[str, ...] = ()
    executable: bool = False
    basis: bool = False
    modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Availability:
    """Whether a software can run, and why not.

    Attributes:
        name: Software name (``Software.name``).
        available: True if every requirement is met.
        reason: First requirement not met; empty if available.
    """

    name: str
    available: bool
    reason: str = ""


# Requirements of each AMAC asset, by ``Software.name``.
REQUIREMENTS: dict[str, Requirement] = {
    "deMonNano": Requirement(
        aliases=("demonano", "demon_nano", "demon-nano"),
        executable=True,
        basis=True,
        modules=("deMonPy",),
    ),
    "dftb+": Requirement(
        aliases=("dftbplus", "DFTB+", "DFTBplus"),
        executable=True,
        basis=True,
    ),
    "orca": Requirement(aliases=("ORCA",), executable=True),
    "pyscf": Requirement(aliases=("PySCF",), modules=("pyscf",)),
}


def config_section(config: Mapping[str, Any], name: str, aliases: tuple[str, ...]) -> dict | None:
    """Return the software section of ``config`` (name or alias), None if absent."""
    softwares = config.get("software") or {}
    for key in (name, *aliases):
        if key in softwares:
            return dict(softwares[key])
    return None


def executable_problem(path: Any) -> str:
    """Return why ``path`` is not a usable executable, empty if it is."""
    if not path:
        return "executable not configured"
    path = Path(path)
    if not path.is_absolute():
        return f"executable is not an absolute path: {path}"
    if not path.is_file():
        return f"executable not found: {path}"
    if not os.access(path, os.X_OK):
        return f"executable is not executable: {path}"
    return ""


def smoke_problem(path: str | Path, timeout: float = 10.0) -> str:
    """Start ``path`` without argument; return why it failed, empty if it started.

    The return code is not checked: most programs exit with an error
    without input file. Only a failure to start or a hang is reported.
    """
    with tempfile.TemporaryDirectory() as workdir:
        try:
            subprocess.run(
                [str(path)],
                cwd=workdir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"executable did not answer within {timeout} s: {path}"
        except OSError as error:
            return f"executable cannot start ({error.strerror}): {path}"
    return ""


def check_software(
    name: str,
    config: Mapping[str, Any],
    requirement: Requirement | None = None,
    smoke: bool = False,
) -> Availability:
    """Check every requirement of the software ``name``.

    Args:
        name: Software name, a key of :data:`REQUIREMENTS`.
        config: AMAC configuration dict.
        requirement: Requirements to check; those of :data:`REQUIREMENTS`
            if None.
        smoke: If True, also start the executable once.

    Returns:
        The availability, with the first requirement not met as reason.
    """
    requirement = requirement or REQUIREMENTS[name]
    for module in requirement.modules:
        if importlib.util.find_spec(module) is None:
            return Availability(name, False, f"Python module {module} not importable")

    if not (requirement.executable or requirement.basis):
        return Availability(name, True)

    section = config_section(config, name, requirement.aliases)
    if section is None:
        return Availability(name, False, "no section in the configuration")
    if requirement.executable:
        problem = executable_problem(section.get("executable"))
        if problem:
            return Availability(name, False, problem)
    if requirement.basis:
        basis = section.get("basis")
        if not basis or not Path(basis).is_dir():
            return Availability(name, False, f"basis directory not found: {basis}")
    if smoke and requirement.executable:
        problem = smoke_problem(section["executable"])
        if problem:
            return Availability(name, False, problem)
    return Availability(name, True)


def check_all(config: Mapping[str, Any], smoke: bool = False) -> dict[str, Availability]:
    """Return the availability of every software of :data:`REQUIREMENTS`."""
    return {name: check_software(name, config, smoke=smoke) for name in REQUIREMENTS}
