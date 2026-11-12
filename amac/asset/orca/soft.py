from pathlib import Path

import amac.asset.orca.handler  # noqa: F401
from amac.asset.md import MDSettings, md_settings
from amac.asset.orca.parser import read_md_trajectory, read_output, to_inp
from amac.asset.solvation import SolvationSettings, solvation_settings
from amac.engine.software import Software
from amac.engine.timeout import time_limited

MD_TRAJECTORY = "md-trajectory.xyz"


def ri(enabled: bool) -> str:
    """Density fitting of the two-electron integrals (RI-J + COSX)."""
    return "RIJCOSX" if enabled else "NoRIJCOSX"


def frozen_core(enabled: bool) -> str:
    """Frozen-core keyword of the correlated methods."""
    return "FrozenCore" if enabled else "NoFrozenCore"


def md_block(md: MDSettings) -> dict:
    """ORCA ``%md`` commands, in execution order (Run last)."""
    block = {"Timestep": f"{md.time_step}_fs"}
    if md.temperature is not None:
        block["Initvel"] = f"{md.temperature}_K"
    if md.thermostat == "berendsen":
        block["Thermostat"] = f"Berendsen {md.temperature}_K Timecon {md.time_constant}_fs"
    block["Dump"] = f'Position Stride 1 Filename "{MD_TRAJECTORY}"'
    block["Run"] = md.steps
    return block


def solvent_keyword(params: dict, solv: SolvationSettings) -> None:
    """Add the solvation keyword (``CPCM``, ``SMD`` or ``ALPB`` for xTB)."""
    if solv.model == "gbsa":
        if params["!"].get("method") not in ("XTB1", "XTB2"):
            raise ValueError("ORCA asset: gbsa (ALPB) is available with xTB only")
        params["!"]["solvation"] = f"ALPB({solv.solvent})"
    elif solv.model == "smd":
        params["!"]["solvation"] = f"SMD({solv.solvent})"
    elif solv.solvent is not None:
        params["!"]["solvation"] = f"CPCM({solv.solvent})"
    else:
        params["!"]["solvation"] = "CPCM"
        params["%cpcm"] = {"epsilon": solv.epsilon}


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
        md = params.pop("md", None)
        if md is not None:
            params["%md"] = md_block(md_settings(md))
        solvation = params.pop("solvation", None)
        if solvation is not None:
            solvent_keyword(params, solvation_settings(solvation))
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
        results = read_output(workdir / self.output_file, instance.props.image)
        block = self.parameters.get("%md")
        if block is not None:
            time_step = float(block["Timestep"].removesuffix("_fs"))
            results["trajectory"] = read_md_trajectory(
                workdir / MD_TRAJECTORY, instance.props.image, time_step
            )
        return results
