
import copy

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
        return params

    @time_limited
    def calculate(self, instance):
        objt = deMonNano(
            title="CALCULATION DEMONANO",
            workdir=instance.ctx.workdir,
            **self.parameters,
        )
        objt.calculate(
            positions=instance.props.image.positions,
            symbols=instance.props.image.symbols,
        )
        return objt.results





