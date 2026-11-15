"""Write the OpenMolcas input file and read the OpenMolcas text output.

The output patterns are the usual OpenMolcas strings; the manual does not
document them (see ``documentation/openmolcas-doc.md``, "Parsing output").
"""

import re
from pathlib import Path
from typing import Any

import numpy as np
from ase import Atoms, units

from amac.utils.exception import OutputParseError

_NUMBER = r"-?\d+\.\d*(?:[EeDd][-+]?\d+)?"

# Entries before which the extra blocks are written.
_POST = ("alaska", "slapaf", "mckinley", ">> ENDDO")

# Dipole moment: Debye -> e.Bohr.
DEBYE_TO_EBOHR = units.Debye / units.Bohr


def xyz_block(image: Atoms) -> str:
    """Inline XYZ geometry for the GATEWAY ``Coord`` keyword (Angstrom)."""
    lines = [str(len(image)), "AMAC geometry"]
    for symbol, (x, y, z) in zip(image.get_chemical_symbols(), image.positions):
        lines.append(f"{symbol:2s} {x:16.10f} {y:16.10f} {z:16.10f}")
    return "\n".join(lines)


def _keyword_lines(block: dict, indent: str = " ") -> list[str]:
    """Lines of a program block.

    ``True`` writes the keyword alone, ``False`` and ``None`` nothing, a
    multi-line string the keyword then its data lines, a dict a sub-block
    closed by ``End of <keyword>``; any other value ``keyword = value``.
    """
    lines = []
    for key, value in block.items():
        if value is None or value is False:
            continue
        if value is True:
            lines.append(f"{indent}{key}")
        elif isinstance(value, dict):
            lines += [f"{indent}{key}", *_keyword_lines(value, indent + " "), f"{indent}End of {key}"]
        elif isinstance(value, str) and "\n" in value:
            lines += [f"{indent}{key}", *(f"{indent}{line}" for line in value.splitlines())]
        elif isinstance(value, (list, tuple)):
            lines.append(f"{indent}{key} = {' '.join(str(item) for item in value)}")
        else:
            lines.append(f"{indent}{key} = {value}")
    return lines


def to_input(params: dict) -> str:
    """Build the OpenMolcas input from the program blocks of ``params``.

    ``params["sequence"]`` gives the order: program names (lower case) and
    EMIL lines (starting with ``>>``). Blocks missing from the sequence
    (raw software arguments) are written before the first gradient,
    optimizer or Hessian program, or before the end of the loop.

    Args:
        params: ``{program: {keyword: value}}`` and ``"sequence"``.
    """
    sequence = list(params.get("sequence") or ("gateway", "seward"))
    extras = [name for name in params if name != "sequence" and name not in sequence]
    at = next((i for i, entry in enumerate(sequence) if entry in _POST), len(sequence))
    sequence[at:at] = extras
    lines = []
    for entry in sequence:
        if entry.startswith(">>"):
            lines.append(entry)
        else:
            lines += [f"&{entry.upper()}", *_keyword_lines(params.get(entry, {}))]
    return "\n".join(lines) + "\n"


def _rows_after(lines: list[str], title: str, pattern: str, count: int) -> list[re.Match]:
    """The first ``count`` rows matching ``pattern`` after the last ``title``.

    Lines that do not match are skipped; scanning stops at ``count`` rows
    or at the next ``title``.
    """
    starts = [i for i, line in enumerate(lines) if title in line]
    if not starts:
        return []
    rows = []
    for line in lines[starts[-1] + 1 :]:
        if title in line or len(rows) == count:
            break
        match = re.match(pattern, line)
        if match is not None:
            rows.append(match)
    return rows


def _number(text: str) -> float:
    """Float from a Fortran number (``D`` exponent accepted)."""
    return float(text.replace("D", "E").replace("d", "e"))


def _mulliken(lines: list[str], natoms: int) -> list[float] | None:
    """Mulliken charges: ``N-E`` rows of the last population table."""
    starts = [i for i, line in enumerate(lines) if "Mulliken charges per centre" in line]
    if not starts:
        return None
    charges: list[float] = []
    for line in lines[starts[-1] + 1 :]:
        if len(charges) >= natoms:
            break
        match = re.match(r"\s*N-E\s+(.*)$", line)
        if match:
            charges += [_number(value) for value in match.group(1).split()]
    return charges[:natoms] if len(charges) >= natoms else None


def _dipole(lines: list[str]) -> list[float] | None:
    """Last dipole moment (e.Bohr), printed in Debye."""
    starts = [i for i, line in enumerate(lines) if "dipole moment (debye)" in line.lower()]
    if not starts:
        return None
    pattern = rf"\s*X=\s*({_NUMBER})\s+Y=\s*({_NUMBER})\s+Z=\s*({_NUMBER})"
    for line in lines[starts[-1] + 1 : starts[-1] + 4]:
        match = re.match(pattern, line)
        if match:
            return [_number(value) * DEBYE_TO_EBOHR for value in match.groups()]
    return None


def read_geometry(path: str | Path, image: Atoms) -> Atoms | None:
    """Last geometry of the SLAPAF ``[GEOMETRIES] (XYZ)`` Molden file.

    Returns:
        A copy of ``image`` at the last geometry (Angstrom), or None if the
        file or the section is missing.
    """
    path = Path(path)
    if not path.is_file():
        return None
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if "[GEOMETRIES]" in line.upper()]
    if not starts:
        return None
    natoms = len(image)
    frames = []
    index = starts[0] + 1
    while index < len(lines) and lines[index].strip().isdigit():
        frames.append(lines[index + 2 : index + 2 + natoms])
        index += natoms + 2
    if not frames or len(frames[-1]) != natoms:
        return None
    final = image.copy()
    final.positions = [[_number(value) for value in line.split()[1:4]] for line in frames[-1]]
    return final


def _molden_section(lines: list[str], name: str) -> list[float] | None:
    """First number of each line of a Molden ``[name]`` section."""
    starts = [i for i, line in enumerate(lines) if line.strip().upper() == f"[{name}]"]
    if not starts:
        return None
    values = []
    for line in lines[starts[0] + 1 :]:
        if line.strip().startswith("["):
            break
        if line.split():
            values.append(_number(line.split()[0]))
    return values


def read_frequencies(path: str | Path) -> np.ndarray | None:
    """Harmonic frequencies of the MCLR / SLAPAF ``freq.molden`` file.

    Returns:
        Array (n, 2): frequencies (cm^-1, imaginary ones negative) and IR
        intensities (km/mol, NaN when the file has none); None if the
        file or its ``[FREQ]`` section is missing.
    """
    path = Path(path)
    if not path.is_file():
        return None
    lines = path.read_text().splitlines()
    frequencies = _molden_section(lines, "FREQ")
    if not frequencies:
        return None
    intensities = _molden_section(lines, "INT")
    if intensities is None or len(intensities) != len(frequencies):
        intensities = [np.nan] * len(frequencies)
    return np.column_stack([frequencies, intensities])


def _last(text: str, pattern: str) -> float | None:
    """Last number captured by ``pattern`` (case ignored), None if absent."""
    found = re.findall(pattern, text, re.IGNORECASE)
    return _number(found[-1]) if found else None


def _pt2_roots(text: str) -> dict[str, list[float]]:
    """Root energies of the ``:: <label> Root N Total energy:`` lines of
    &CASPT2, by upper-case label (``CASPT2``, ``MS-CASPT2``, ``SC-NEVPT2``...).
    """
    found: dict[str, dict[int, float]] = {}
    for label, root, value in re.findall(
        rf"::\s+([\w-]*(?:CASPT2|NEVPT2))\s+Root\s+(\d+)\s+Total energy:\s*({_NUMBER})",
        text,
        re.IGNORECASE,
    ):
        found.setdefault(label.upper(), {})[int(root)] = _number(value)
    return {label: [roots[key] for key in sorted(roots)] for label, roots in found.items()}


def _coupled_cluster(text: str, scf: float | None) -> dict[str, float]:
    """CCSD and CCSD(T) total energies of &CHCC / &CHT3.

    CHCC and CHT3 print only correlation energies (``E1``/``E2 CCSD energy``
    of the CHCC decomposition, ``CCSD(T) corr.`` of CHT3); they are added
    to the SCF energy.
    """
    energy = {}
    ccsd = None
    singles = _last(text, rf"E1 CCSD energy\s*:\s*({_NUMBER})")
    doubles = _last(text, rf"E2 CCSD energy\s*:\s*({_NUMBER})")
    if scf is not None and singles is not None and doubles is not None:
        ccsd = scf + singles + doubles
    if ccsd is not None:
        energy["ccsd"] = ccsd
    # CHT3 "Final Results": "CCSD(T) corr. = ..." (CCSD + (T) correlation).
    triples = _last(text, rf"CCSD\(T\)\s+corr\.\s*=\s*({_NUMBER})")
    if scf is not None and triples is not None:
        energy["ccsd(t)"] = scf + triples
    return energy


MULTI_ROOT = ("casscf", "caspt2", "nevpt2")
SINGLE_REFERENCE = ("mp2", "ccsd", "ccsd(t)")


def _root_energies(energy: dict, method: str, variant: str | None) -> list[float] | None:
    """Root energies of a CAS-based method, at its highest level (Hartree)."""
    if method == "casscf":
        return energy.get("roots")
    pt2 = energy.get("pt2", {})
    if method == "caspt2":
        # Multi-state energies (MS-, XMS-, RMS-) replace the single-state ones.
        labels = [label for label in pt2 if label.endswith("-CASPT2")] or ["CASPT2"]
    elif method == "nevpt2":
        labels = [label for label in pt2 if label.startswith(f"{variant}-")]
        labels = labels or [label for label in pt2 if "NEVPT2" in label]
    else:
        return None
    return pt2.get(labels[0]) if labels else None


def _final_energy(energy: dict, method: str, variant: str | None) -> float | None:
    """Final energy of ``method``: lowest root for the multi-root methods."""
    if method in MULTI_ROOT:
        roots = _root_energies(energy, method, variant)
        return min(roots) if roots else None
    return energy.get(method)


def _states(roots: list[float]) -> list[dict]:
    """One dict per root: ``root`` (from 1), ``energy`` (Hartree) and
    ``excitation`` (eV) above the lowest root."""
    lowest = min(roots)
    return [
        {"root": index, "energy": value, "excitation": (value - lowest) * units.Hartree}
        for index, value in enumerate(roots, start=1)
    ]


def read_output(
    path: str | Path, image: Atoms, method: str, variant: str | None = None
) -> dict[str, Any]:
    """Read the OpenMolcas log (energy in Hartree, gradient in Hartree/Bohr).

    The last value of each quantity is kept: in an optimization loop, it is
    the one of the final geometry.

    Args:
        path: Standard output of ``pymolcas``.
        image: Input geometry.
        method: ``"scf"``, ``"mp2"``, ``"ccsd"``, ``"ccsd(t)"``, ``"casscf"``,
            ``"caspt2"`` or ``"nevpt2"``: selects the final energy.
        variant: ``"SC"`` or ``"PC"`` for NEVPT2.

    Raises:
        OutputParseError: If the file is missing or has no final energy.
    """
    path = Path(path)
    if not path.is_file():
        raise OutputParseError(f"Missing OpenMolcas output file: {path}")
    text = path.read_text(errors="replace")
    lines = text.splitlines()

    energy: dict[str, Any] = {}
    scf = re.findall(rf"::\s+Total (?:SCF|KS-DFT) energy\s+({_NUMBER})", text)
    if scf:
        energy["scf"] = _number(scf[-1])
    mp2 = re.findall(rf"Total MBPT2 energy\s*[=:]?\s*({_NUMBER})", text)
    if mp2:
        energy["mp2"] = _number(mp2[-1])
    energy.update(_coupled_cluster(text, energy.get("scf")))
    roots: dict[int, float] = {}
    for root, value in re.findall(
        rf"::\s+RASSCF root number\s+(\d+)\s+Total energy:\s+({_NUMBER})", text
    ):
        roots[int(root)] = _number(value)
    if roots:
        energy["roots"] = [roots[key] for key in sorted(roots)]
    pt2 = _pt2_roots(text)
    if pt2:
        energy["pt2"] = pt2

    final = _final_energy(energy, method, variant)
    if final is None:
        # The summary lines found help to fix an unknown output format.
        labels = sorted(set(re.findall(r"^::\s+(.+?)\s+-?\d", text, re.MULTILINE)))
        raise OutputParseError(f"No final {method} energy in {path}; summary lines: {labels}")
    energy["energy"] = final
    roots = _root_energies(energy, method, variant)
    states = _states(roots) if roots else None
    correlation = None
    if method in SINGLE_REFERENCE and "scf" in energy:
        correlation = final - energy["scf"]

    natoms = len(image)
    gradient = _rows_after(
        lines,
        "Molecular gradients",
        rf"\s*\S+\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s*$",
        natoms,
    )
    forces = None
    if len(gradient) == natoms:
        forces = -np.array([[_number(value) for value in row.groups()] for row in gradient])

    return {
        "errors": [],
        "energy": energy,
        "states": states,
        "correlation": correlation,
        "forces": forces,
        "charges": _mulliken(lines, natoms),
        "dipole": _dipole(lines),
        "input_geometry": image.copy(),
        "output_geometry": image.copy(),
    }
