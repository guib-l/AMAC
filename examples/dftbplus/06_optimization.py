"""DFTB-2 geometry optimization of water with DFTB+.

Usage:
    python examples/dftbplus/06_optimization.py
"""

import json
from pathlib import Path

import numpy as np
from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

calc = AMAC(software="dftb+", workdir=".run/dftbplus/optimization", label="water")
calc.handler_register("lowest-energy", "final-geometry", "forces")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS},
    module="optimization-geometry",
    module_args={"max-step": 100},
)
calc.run(molecule("H2O"))

product = calc.instance.res.product
final = product["final-geometry"]
print(f"Optimized energy: {product['lowest-energy']:.8f} Ha")
print(f"Max residual force: {np.abs(product['forces']).max():.2e} Ha/Bohr")
print(f"O-H distance: {final.get_distance(0, 1):.4f} Å")
print(f"H-O-H angle:  {final.get_angle(1, 0, 2):.2f}°")
