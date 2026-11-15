"""CI-DFTB on the water dimer cation with deMonNano.

The positive charge is shared between the two water fragments (3 atoms
each); the Mulliken charges show how it is distributed.

Usage:
    python examples/deMonNano/09_ci_dftb.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

water = molecule("H2O")
dimer = water + water.copy()
dimer.positions[3:] += [-0.2, 0.0, 2.7]

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/ci_dftb", label="dimer")
calc.handler_register("lowest-energy", "charges")
calc.parameters_register(
    method="ci-dftb",
    method_args={"basis": BASIS, "charge": 1.0, "size-ci": 2, "fragments": [3, 3]},
    module="single-point",
)
calc.run(dimer)

charges = calc.instance.res.product["charges"]
print(f"CI-DFTB energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"Fragment charges: {sum(charges[:3]):+.3f} e, {sum(charges[3:]):+.3f} e")
