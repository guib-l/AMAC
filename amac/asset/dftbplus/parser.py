import re
from pathlib import Path
from typing import Any

import ase.io
import numpy as np

from amac.utils.exception import OutputParseError

# Header of a results.tag entry: "name :type:rank:shape"
_TAG_HEADER = re.compile(r"^(\S+)\s*:(real|integer|logical|complex):(\d+):(.*)$")
_CONVERT = {
    "real": float,
    "integer": int,
    "logical": lambda token: token.upper().startswith("T"),
    "complex": complex,
}


def read_results_tag(path: str | Path) -> dict[str, Any]:
    """Read a DFTB+ ``results.tag`` file.

    Scalars (rank 0) are returned as Python numbers, arrays as NumPy
    arrays in C order (Fortran shape reversed).

    Raises:
        OutputParseError: If the file is missing or malformed.
    """
    path = Path(path)
    if not path.is_file():
        raise OutputParseError(f"Missing DFTB+ results file: {path}")

    entries: dict[str, Any] = {}
    header = None
    tokens: list[str] = []

    def flush() -> None:
        if header is None:
            return
        name, kind, rank, shape = header
        values = [_CONVERT[kind](token) for token in tokens]
        if rank == 0:
            entries[name] = values[0]
        else:
            dims = [int(dim) for dim in shape.split(",") if dim]
            entries[name] = np.array(values).reshape(dims[::-1])

    for line in path.read_text().splitlines():
        match = _TAG_HEADER.match(line.strip())
        if match:
            flush()
            name, kind, rank, shape = match.groups()
            header = (name, kind, int(rank), shape)
            tokens = []
        elif header is not None:
            tokens.extend(line.split())
        elif line.strip():
            raise OutputParseError(f"Unexpected line in {path}: {line!r}")
    flush()
    return entries


# Energy line of detailed.out: "Repulsive energy:   0.0718034081 H   1.9539 eV"
_DETAILED_LINE = re.compile(r"^([^:]+):\s+(\S+)\s+H\b")
# detailed.out label -> key of results["energy"].
_DETAILED_ENERGIES = {
    "Band energy": "band_energy",
    "Energy H0": "h0_energy",
    "Energy SCC": "scc_energy",
    "Total Electronic energy": "electronic_energy",
    "Repulsive energy": "repulsive_energy",
}


def read_detailed_out(path: str | Path) -> dict[str, float]:
    """Read the energies (Hartree) of a DFTB+ ``detailed.out`` file.

    Args:
        path: Path to the detailed.out file.

    Returns:
        The energies of :data:`_DETAILED_ENERGIES`, by key; empty if the
        file does not exist.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    energies = {}
    for line in path.read_text().splitlines():
        match = _DETAILED_LINE.match(line.strip())
        if match and match.group(1) in _DETAILED_ENERGIES:
            energies[_DETAILED_ENERGIES[match.group(1)]] = float(match.group(2))
    return energies


def to_results(tag: dict[str, Any], workdir: Path, image) -> dict[str, Any]:
    """Arrange the ``results.tag`` entries as the handlers expect them.

    Energies are in Hartree, forces in Hartree/Bohr.
    """
    energy_keys = ("total_energy", "mermin_energy", "extrapolated0_energy",
                   "forcerelated_energy", "fermi_level")
    final = workdir / "geo_end.gen"
    return {
        "errors": [],
        "energy": {
            "energy": tag["mermin_energy"],
            **{key: tag[key] for key in energy_keys if key in tag},
            **read_detailed_out(workdir / "detailed.out"),
        },
        "forces": tag.get("forces"),
        "properties": {
            key: value for key, value in tag.items()
            if key not in energy_keys and key != "forces"
        },
        "input_geometry": image.copy(),
        "output_geometry": (
            ase.io.read(final, format="gen") if final.is_file() else image.copy()
        ),
    }
