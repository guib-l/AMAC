"""DFTB-2 vibrational frequencies and IR intensities of water with deMonNano.

Usage:
    python examples/deMonNano/06_frequencies.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/frequencies", label="water")
calc.handler_register("frequencies")
calc.parameters_register(method="dftb-2", method_args={"basis": BASIS}, module="frequencies")
calc.run(molecule("H2O"))

for wavenumber, intensity in calc.instance.res.product["frequencies"]:
    print(f"{wavenumber:10.2f} cm^-1   IR {intensity:10.4f}")
