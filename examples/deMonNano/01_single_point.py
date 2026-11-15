"""DFTB-2 single-point energy of water with deMonNano.

Needs the "deMonNano" section of config-amac.json: absolute "executable" and
"basis" (directory of the Slater-Koster files).

Usage:
    python examples/deMonNano/01_single_point.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/single_point", label="water")
calc.handler_register("lowest-energy", "energy-resume")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS, "scc-tol": 1e-6},
    module="single-point",
)
calc.run(molecule("H2O"))

for name, value in calc.instance.res.product["energy-resume"].items():
    print(f"{name:20s} {value}")
