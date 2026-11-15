"""CASSCF(4,4)/def2-SVP energy of water with ORCA.

Usage:
    python examples/orca/04_casscf.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/casscf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="casscf",
    method_args={"basis": "def2-svp", "active-orbitals": 4, "active-electrons": 4},
    module="single-point",
)
calc.run(molecule("H2O"))

print(f"CASSCF(4,4)/def2-SVP energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
