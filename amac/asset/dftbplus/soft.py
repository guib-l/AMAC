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


class software_dftbplus(Software):

    name = "dftb+"
    alias = ("dftbplus", "DFTB+", "DFTBplus")
    requires_executable = True
    transforms = {"skf_type2filenames": skf_type2filenames}

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
