"""Write the ORCA input file and read the ORCA text output."""

import re
from pathlib import Path
from typing import Any

import numpy as np
from ase import Atoms

from amac.utils.exception import OutputParseError

_NUMBER = r"-?\d+\.\d+(?:[eE][-+]?\d+)?"


def _value(value: Any) -> str:
    """Format a value for an ORCA block."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_value(item) for item in value)
    return str(value)


def _block_lines(block: dict, indent: str = "  ") -> list[str]:
    """Lines of a ``%block``; a nested dict becomes a sub-block closed by ``end``."""
    lines = []
    for key, value in block.items():
        if isinstance(value, dict):
            lines += [f"{indent}{key}", *_block_lines(value, indent + "  "), f"{indent}end"]
        elif key.endswith("]"):
            lines.append(f"{indent}{key} = {_value(value)}")
        else:
            lines.append(f"{indent}{key} {_value(value)}")
    return lines


def to_inp(params: dict, image: Atoms) -> str:
    """Build the ORCA input: ``!`` line, ``%`` blocks, then the coordinates.

    Args:
        params: Translated parameters (``"!"``, ``"%name"`` and ``"*"`` keys).
        image: Geometry (Angstrom).
    """
    keywords = [str(word) for word in params.get("!", {}).values() if word]
    lines = ["! " + " ".join(keywords)]
    for name, block in params.items():
        if name.startswith("%"):
            lines += [name, *_block_lines(block), "end"]
    coords = params["*"]
    lines.append(f"* xyz {coords['charge']} {coords['mult']}")
    for symbol, (x, y, z) in zip(image.get_chemical_symbols(), image.positions):
        lines.append(f"{symbol:2s} {x:16.10f} {y:16.10f} {z:16.10f}")
    lines.append("*")
    return "\n".join(lines) + "\n"


def _last_block(lines: list[str], title: str, pattern: str, skip: int) -> list[re.Match]:
    """Matches of ``pattern`` in the last block headed by ``title``.

    The block starts ``skip`` lines after the title and ends at the first
    line that does not match.
    """
    starts = [i for i, line in enumerate(lines) if title in line]
    if not starts:
        return []
    matches = []
    for line in lines[starts[-1] + skip:]:
        match = re.match(pattern, line)
        if match is None:
            break
        matches.append(match)
    return matches


def _excited_states(text: str) -> dict[str, dict] | None:
    """TD-DFT/CIS states by spin symmetry: ``w`` (eV) and ``oscillator``.

    Energies come from the ``STATE n: E= ... au ... eV`` lines of the
    SINGLETS/TRIPLETS sections; oscillator strengths from the absorption
    spectrum rows ``0-1A -> n-1A  eV  cm-1  nm  fosc`` (0.0 if absent).
    """
    states: dict[str, dict] = {}
    symmetry = None
    for line in text.splitlines():
        if "EXCITED STATES" in line:
            symmetry = "triplet" if "TRIPLETS" in line else "singlet"
        match = re.match(rf"\s*STATE\s+(\d+):\s+E=\s+{_NUMBER}\s+au\s+({_NUMBER})\s+eV", line)
        if match and symmetry:
            index = int(match.group(1)) - 1
            states.setdefault(symmetry, {})[f"state_{index}"] = {
                "w": float(match.group(2)),
                "oscillator": 0.0,
            }
    rows = re.findall(
        rf"\s*0-\S+\s+->\s+(\d+)-(\d)\S*\s+{_NUMBER}\s+{_NUMBER}\s+{_NUMBER}\s+({_NUMBER})", text
    )
    for number, mult, fosc in rows:
        symmetry = "triplet" if mult == "3" else "singlet"
        state = states.get(symmetry, {}).get(f"state_{int(number) - 1}")
        if state is not None:
            state["oscillator"] = float(fosc)
    return states or None


def read_output(path: str | Path, image: Atoms) -> dict[str, Any]:
    """Read the ORCA text output (energy in Hartree, gradient in Hartree/Bohr).

    Raises:
        OutputParseError: If the file is missing, ORCA did not terminate
            normally or no final energy is found.
    """
    path = Path(path)
    if not path.is_file():
        raise OutputParseError(f"Missing ORCA output file: {path}")
    text = path.read_text()
    if "ORCA TERMINATED NORMALLY" not in text:
        raise OutputParseError(f"ORCA did not terminate normally (see {path})")
    energies = re.findall(rf"FINAL SINGLE POINT ENERGY\s+({_NUMBER})", text)
    if not energies:
        raise OutputParseError(f"No final energy in {path}")
    lines = text.splitlines()

    gradient = _last_block(
        lines, "CARTESIAN GRADIENT", rf"\s*\d+\s+\S+\s*:\s*({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})", 3
    )
    charges = _last_block(lines, "MULLIKEN ATOMIC CHARGES", rf"\s*\d+\s+\S+\s*:\s*({_NUMBER})", 2)
    coords = _last_block(
        lines, "CARTESIAN COORDINATES (ANGSTROEM)", rf"\s*(\S+)\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})", 2
    )
    dipole = re.findall(rf"Total Dipole Moment\s*:\s*({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})", text)

    # IR SPECTRUM rows: "  6:   1623.45   0.0123   62.39 ..." (cm-1, eps, km/mol)
    infrared = _last_block(
        lines, "IR SPECTRUM", rf"\s*\d+:\s+({_NUMBER})\s+{_NUMBER}\s+({_NUMBER})", 6
    )

    final = image.copy()
    if len(coords) == len(image):
        final.positions = [[float(value) for value in match.groups()[1:]] for match in coords]
    return {
        "errors": [],
        "energy": {"energy": float(energies[-1])},
        "forces": -np.array([[float(v) for v in m.groups()] for m in gradient]) if gradient else None,
        "charges": [float(m.group(1)) for m in charges] or None,
        "dipole": [float(value) for value in dipole[-1]] if dipole else None,
        "frequencies": np.array([[float(v) for v in m.groups()] for m in infrared]) if infrared else None,
        "excited-states": _excited_states(text),
        "input_geometry": image.copy(),
        "output_geometry": final,
    }


def read_md_trajectory(path: str | Path, image: Atoms, time_step: float) -> list[Atoms]:
    """Read the ``Dump Position`` xyz trajectory of an ORCA MD run.

    ``info["time"]`` is ``index * time_step`` (fs); ``epot`` comes from the
    ``E_Pot=`` field of the comment line (Hartree), ``ekin`` from ``E_Kin=``,
    both None when absent.

    Raises:
        OutputParseError: If the trajectory file is missing.
    """
    path = Path(path)
    if not path.is_file():
        raise OutputParseError(f"Missing ORCA MD trajectory: {path}")
    lines = path.read_text().splitlines()
    natoms = len(image)
    frames = []
    for index, start in enumerate(range(0, len(lines) - natoms - 1, natoms + 2)):
        comment = lines[start + 1]
        epot = re.search(rf"E_Pot\s*=\s*({_NUMBER})", comment)
        ekin = re.search(rf"E_Kin\s*=\s*({_NUMBER})", comment)
        atoms = image.copy()
        atoms.positions = [[float(v) for v in line.split()[1:4]] for line in lines[start + 2 : start + 2 + natoms]]
        atoms.info.update(
            time=index * time_step,
            epot=float(epot.group(1)) if epot else None,
            ekin=float(ekin.group(1)) if ekin else None,
        )
        frames.append(atoms)
    return frames
