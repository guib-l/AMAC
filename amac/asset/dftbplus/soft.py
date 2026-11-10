from pathlib import Path

import ase.io
import numpy as np

from amac.asset.dftbplus import handler  # noqa: F401
from amac.asset.dftbplus.hsd import to_hsd
from amac.asset.dftbplus.parser import read_exc_dat, read_results_tag, to_results
from amac.engine.software import Software
from amac.engine.timeout import time_limited

# Highest angular momentum per element (3ob-like default). Overridden by
# the "max-angular-momenta" option of the configuration.
DEFAULT_ANGULAR_MOM = {
    "H": "s", "He": "s",
    "Li": "p", "Be": "p", "B": "p", "C": "p", "N": "p", "O": "p", "F": "p",
    "Na": "p", "Mg": "p", "Al": "p", "Si": "p", "P": "d", "S": "d", "Cl": "d",
    "K": "p", "Ca": "p", "Zn": "d", "Br": "d", "I": "d",
}


def skf_type2filenames(basis: dict) -> dict:
    """Translate the canonical basis into a DFTB+ Type2FileNames block."""
    prefix = Path(basis["directory"]).expanduser().resolve()
    return {
        "Type2FileNames": {
            "Prefix": f"{prefix}/",
            "Separator": basis.get("separator", "-"),
            "Suffix": basis.get("suffix", ".skf"),
            "LowerCaseTypeName": basis.get("lower-case", False),
        }
    }


def kpoints_supercell_folding(grid: list[int]) -> dict:
    """Translate a Monkhorst-Pack grid into a DFTB+ SupercellFolding block.

    The shift is 0.5 along an even direction and 0.0 along an odd one,
    as in the original Monkhorst-Pack scheme.
    """
    l1, l2, l3 = grid
    matrix = [l1, 0, 0, 0, l2, 0, 0, 0, l3]
    shifts = [0.5 if n % 2 == 0 else 0.0 for n in grid]
    return {"SupercellFolding": {"": matrix + shifts}}


def is_periodic(image) -> bool:
    """Return True if the image has a nonzero cell and a periodic direction."""
    return bool(image.cell.any()) and bool(image.pbc.any())


def supercell_folding_kpoints(matrix: list[float]) -> np.ndarray:
    """Expand a DFTB+ SupercellFolding matrix into fractional k-points.

    Args:
        matrix: The 12 numbers ``[l1,0,0,0,l2,0,0,0,l3,s1,s2,s3]``, i.e.
            the diagonal folding grid followed by one shift per direction.

    Returns:
        The fractional k-point coordinates, shape (l1*l2*l3, 3).

    Raises:
        ValueError: If the matrix is not a 12-number diagonal grid.
    """
    values = list(matrix)
    if len(values) != 12:
        raise ValueError(
            f"SupercellFolding matrix needs 12 numbers, got {len(values)}"
        )
    if any(values[i] != 0 for i in (1, 2, 3, 5, 6, 7)):
        raise ValueError(f"SupercellFolding matrix is not diagonal: {matrix!r}")
    sizes = [values[0], values[4], values[8]]
    shifts = values[9:12]
    for size, shift in zip(sizes, shifts):
        if int(size) != size or size < 1:
            raise ValueError(
                f"SupercellFolding grid sizes must be positive integers: {matrix!r}"
            )
        # The original Monkhorst-Pack scheme shifts 0.5 along an even
        # direction, but DFTB+ also documents a hexagonal variant with
        # 0.0 shifts there; both are accepted.
        if shift not in (0.0, 0.5):
            raise ValueError(f"SupercellFolding shifts must be 0.0 or 0.5: {matrix!r}")
    sizes = [int(size) for size in sizes]
    axes = [
        [(index + shift) / size for index in range(size)]
        for size, shift in zip(sizes, shifts)
    ]
    return np.array([[x, y, z] for x in axes[0] for y in axes[1] for z in axes[2]])


def merge_filling(params: dict) -> None:
    """Move the Fermi temperature into the scheme chosen by "smearing".

    "filling" always writes its temperature under ``Filling.Fermi``; when
    "smearing" selects another scheme, both end up in ``Filling``.
    """
    filling = params.get("Hamiltonian", {}).get("DFTB", {}).get("Filling", {})
    if "Fermi" in filling and len(filling) > 1:
        temperature = filling.pop("Fermi")
        next(iter(filling.values())).update(temperature)


class software_dftbplus(Software):

    name = "dftb+"
    alias = ("dftbplus", "DFTB+", "DFTBplus")
    requires_executable = True
    transforms = {
        "skf_type2filenames": skf_type2filenames,
        "kpoints_supercell_folding": kpoints_supercell_folding,
    }

    input_file = "dftb_in.hsd"
    geometry_file = "geo.gen"
    output_file = "dftb.out"

    @time_limited
    def collect(self, instance):
        params = super().collect(instance)
        momenta = {
            **DEFAULT_ANGULAR_MOM,
            **self.options.get("max-angular-momenta", {}),
        }
        symbols = dict.fromkeys(instance.props.image.get_chemical_symbols())
        params["Geometry"] = {"GenFormat": {"<<<": self.geometry_file}}
        self.set_path(
            params, "Hamiltonian.DFTB.MaxAngularMomentum",
            {symbol: momenta[symbol] for symbol in symbols},
        )
        merge_filling(params)
        # "lj-uff" only names the model: DFTB+ needs the UFF parameters block.
        dispersion = params["Hamiltonian"]["DFTB"].get("Dispersion", {})
        if dispersion.get("LennardJones") == {}:
            dispersion["LennardJones"] = {"Parameters": {"UFFParameters": {}}}
        image = instance.props.image
        periodic = is_periodic(image)
        dftb = params["Hamiltonian"]["DFTB"]
        if "KPointsAndWeights" in dftb and not periodic:
            raise ValueError("kpoints requires a periodic image (cell and periodic directions)")
        if periodic and "KPointsAndWeights" not in dftb:
            raise ValueError(
                "a periodic image requires a kpoints grid, e.g. [1, 1, 1] "
                "for the gamma point"
            )
        casida = params.get("ExcitedState", {}).get("Casida")
        if casida is not None and not dftb.get("Scc"):
            raise ValueError("TD-DFTB (Casida) requires SCC: use method dftb-2 or dftb-3")
        if casida is not None and dftb.get("SpinPolarisation"):
            raise ValueError("TD-DFTB (Casida) is not supported for spin-polarized runs")
        if casida is not None and dftb.get("KPointsAndWeights", {}).get("SupercellFolding"):
            grid = dftb["KPointsAndWeights"]["SupercellFolding"][""]
            if [grid[0], grid[4], grid[8]] != [1, 1, 1]:
                raise ValueError(
                    "TD-DFTB (Casida) requires the gamma point for periodic images: "
                    "use kpoints [1, 1, 1]"
                )
        return params

    @time_limited
    def prepare(self, instance):
        workdir = Path(instance.ctx.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        ase.io.write(
            workdir / self.geometry_file, instance.props.image, format="gen",
        )
        (workdir / self.input_file).write_text(to_hsd(self.parameters) + "\n")

    @time_limited
    def calculate(self, instance):
        workdir = Path(instance.ctx.workdir)
        self.execute_program(workdir, output=self.output_file)
        tag = read_results_tag(workdir / "results.tag")
        results = to_results(tag, workdir, instance.props.image)
        dftb = self.parameters["Hamiltonian"]["DFTB"]
        if "KPointsAndWeights" in dftb:
            kpw = dftb["KPointsAndWeights"]
            folding = kpw.get("SupercellFolding") if isinstance(kpw, dict) else None
            if not isinstance(folding, dict):
                raise ValueError(
                    "the k-points product supports SupercellFolding grids only "
                    "(an explicit k-point list set via software_args is not supported)"
                )
            results["k-points"] = supercell_folding_kpoints(folding[""])
        exc_dat = workdir / "EXC.DAT"
        if exc_dat.is_file():
            results["td-dftb"] = read_exc_dat(exc_dat)
        return results
