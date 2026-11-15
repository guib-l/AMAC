"""B3LYP/def2-SVP geometry optimization of water with ORCA.

Usage:
    python examples/orca/07_optimization.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/optimization", label="water")
calc.handler_register("lowest-energy", "final-geometry")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="optimization-geometry",
    module_args={"max-step": 50},
)
calc.run(molecule("H2O"))

final = calc.instance.res.product["final-geometry"]
print(f"Optimized energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"O-H distance: {final.get_distance(0, 1):.4f} Å")
print(f"H-O-H angle:  {final.get_angle(1, 0, 2):.2f}°")
