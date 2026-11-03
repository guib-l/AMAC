from pathlib import Path

import ase.io

from amac.asset.dftbplus import handler  # noqa: F401
from amac.asset.dftbplus.hsd import to_hsd
from amac.asset.dftbplus.parser import read_results_tag, to_results
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
        return to_results(tag, workdir, instance.props.image)
