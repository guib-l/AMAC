from pathlib import Path

import numpy as np
from deMonPy.deMonNano import deMonNano

import amac.asset.deMonNano.handler  # noqa: F401
from amac.engine.software import Software
from amac.engine.timeout import time_limited


class software_deMonNano(Software):
    name = "deMonNano"
    alias = ("demonano", "demon_nano", "demon-nano")
    requires_executable = True

    @time_limited
    def collect(self, instance):
        params = super().collect(instance)
        if instance.props.module == "single-point" and "forces" in instance.props.handler:
            params.setdefault("DEMON_MODULE", {}).setdefault("ACTIVE", {})["OPT"] = {"SP": True}
        params["DEMON_EXECUTABLE"] = str(self.executable)
        params["BASIS"]["SKFILE"] = self.options.get("basis")
        # Hubbard derivatives (DFTB-3) go to the "3ord_param" file, not to
        # the deMonNanoPy arguments.
        self.orb_params = params.pop("ORB_PARAMS", None)
        image = instance.props.image
        pbc = params.get("DEMON_PARAMETERS", {}).get("ACTIVE", {}).get("PBC")
        is_periodic = bool(image.cell.any() and image.pbc.any())
        if pbc is not None:
            if not is_periodic:
                raise ValueError("kpoints requires a periodic image (cell and periodic directions)")
            pbc.setdefault("TYPE", "GENERAL")
        elif is_periodic:
            raise ValueError(
                "a periodic image requires a kpoints grid, e.g. [1, 1, 1] for the gamma point"
            )
        active = params.get("DEMON_PARAMETERS", {}).get("ACTIVE", {})
        if "TD-DFTB" in active and pbc is not None and list(pbc.get("KPTS", ())) != [1, 1, 1]:
            raise ValueError(
                "TD-DFTB is molecular: for a periodic image use kpoints "
                "[1, 1, 1] (gamma point) at most"
            )
        if "FREQ" in active and pbc is not None:
            raise ValueError("frequencies are not supported for periodic systems with deMonNano")
        return params

    @time_limited
    def prepare(self, instance):
        if not self.orb_params:
            return
        path = Path(instance.ctx.workdir) / "3ord_param"
        # deMonNano leaves an empty file behind when it finds none.
        if not path.exists() or not path.stat().st_size:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "".join(f"{symbol} {value}\n" for symbol, value in self.orb_params.items())
            )

    @time_limited
    def calculate(self, instance):
        objt = deMonNano(
            title="CALCULATION DEMONANO",
            workdir=instance.ctx.workdir,
            clean_repository=False,
            omp_threads=self.program.process_unit,
            **self.parameters,
        )
        pbc = self.parameters.get("DEMON_PARAMETERS", {}).get("ACTIVE", {}).get("PBC")
        extra = {}
        if pbc is not None:
            extra["cell"] = instance.props.image.cell
            extra["kpts"] = np.asarray(pbc["KPTS"])
        objt.calculate(
            positions=instance.props.image.positions,
            symbols=instance.props.image.symbols,
            **extra,
        )
        return objt.results
