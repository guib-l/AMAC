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

    final = image.copy()
    if len(coords) == len(image):
        final.positions = [[float(value) for value in match.groups()[1:]] for match in coords]
    return {
        "errors": [],
        "energy": {"energy": float(energies[-1])},
        "forces": -np.array([[float(v) for v in m.groups()] for m in gradient]) if gradient else None,
        "charges": [float(m.group(1)) for m in charges] or None,
        "dipole": [float(value) for value in dipole[-1]] if dipole else None,
        "input_geometry": image.copy(),
        "output_geometry": final,
    }
