
import copy
from pathlib import Path

from amac import config
from amac.engine.software import Software
from amac.engine.timeout import time_limited
# Importing the module registers the deMonNano handlers.
from amac.asset.deMonNano import handler  # noqa: F401
from dataclasses import dataclass

import deMonPy
from deMonPy.deMonNano import deMonNano
from deMonPy.molden import read_XYZ


class software_deMonNano(Software):

    name = "deMonNano"
    alias = ("demonano", "demon_nano", "demon-nano")
    requires_executable = True

    @time_limited
    def collect(self, instance):
        params = super().collect(instance)
        params["DEMON_EXECUTABLE"] = str(self.executable)
        params["BASIS"]["SKFILE"] = self.options.get("basis")
        # Hubbard derivatives (DFTB-3) go to the "3ord_param" file, not to
        # the deMonNanoPy arguments.
        self.orb_params = params.pop("ORB_PARAMS", None)
        return params

    @time_limited
    def prepare(self, instance):
        if not self.orb_params:
            return
        path = Path(instance.ctx.workdir) / "3ord_param"
        # deMonNano leaves an empty file behind when it finds none.
        if not path.exists() or not path.stat().st_size:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(
                f"{symbol} {value}\n"
                for symbol, value in self.orb_params.items()
            ))

    @time_limited
    def calculate(self, instance):
        objt = deMonNano(
            title="CALCULATION DEMONANO",
            workdir=instance.ctx.workdir,
            clean_repository=False,
            **self.parameters,
        )
        objt.calculate(
            positions=instance.props.image.positions,
            symbols=instance.props.image.symbols,
        )
        return objt.results





