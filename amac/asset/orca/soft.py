from pathlib import Path

import amac.asset.orca.handler  # noqa: F401
from amac.asset.orca.parser import read_output, to_inp
from amac.engine.software import Software
from amac.engine.timeout import time_limited


def ri(enabled: bool) -> str:
    """Density fitting of the two-electron integrals (RI-J + COSX)."""
    return "RIJCOSX" if enabled else "NoRIJCOSX"


def frozen_core(enabled: bool) -> str:
    """Frozen-core keyword of the correlated methods."""
    return "FrozenCore" if enabled else "NoFrozenCore"


class software_orca(Software):
    name = "orca"
    alias = ("ORCA",)
    requires_executable = True
    transforms = {"ri": ri, "frozen_core": frozen_core}

    input_file = "input-orca.inp"
    output_file = "output-orca.out"

    @time_limited
    def collect(self, instance):
        params = super().collect(instance)
        # ORCA expects an integer charge.
        params["*"]["charge"] = int(round(params["*"]["charge"]))
        if "forces" in instance.props.handler and params["!"].get("run") == "SP":
            params["!"]["run"] = "EnGrad"
        # ORCA starts its MPI processes itself: never through a launcher.
        if self.program.process_unit > 1:
            params["%pal"] = {"nprocs": self.program.process_unit}
        return params

    @time_limited
    def prepare(self, instance):
        workdir = Path(instance.ctx.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / self.input_file).write_text(to_inp(self.parameters, instance.props.image))

    @time_limited
    def calculate(self, instance):
        workdir = Path(instance.ctx.workdir)
        self.execute_program(workdir, self.input_file, output=self.output_file)
        return read_output(workdir / self.output_file, instance.props.image)
