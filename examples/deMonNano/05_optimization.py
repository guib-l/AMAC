"""DFTB-2 geometry optimization of water with deMonNano.

Usage:
    python examples/deMonNano/05_optimization.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/optimization", label="water")
calc.handler_register("lowest-energy", "final-geometry")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS},
    module="optimization-geometry",
)
calc.run(molecule("H2O"))

final = calc.instance.res.product["final-geometry"]
print(f"Optimized energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"O-H distance: {final.get_distance(0, 1):.4f} Å")
print(f"H-O-H angle:  {final.get_angle(1, 0, 2):.2f}°")
