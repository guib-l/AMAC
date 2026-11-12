"""B3LYP/def2-SVP single-point energy of water with ORCA.

Needs an "orca" section with the absolute executable in config-amac.json.

Usage:
    python examples/example_orca.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

water = molecule("H2O")

calc = AMAC(software="orca", workdir=".run/orca", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="single-point",
    module_args={},
)
calc.run(water)

print(f"ORCA B3LYP/def2-SVP energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
