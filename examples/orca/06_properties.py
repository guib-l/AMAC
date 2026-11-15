"""B3LYP/def2-SVP charges, dipole and forces of water with ORCA.

Asking for "forces" turns the single point into an ORCA EnGrad run.

Usage:
    python examples/orca/06_properties.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

HANDLERS = (
    "charges",  # Mulliken charges (e)
    "dipole",   # e.Bohr
    "forces",   # Hartree/Bohr
)

calc = AMAC(software="orca", workdir=".run/orca/properties", label="water")
calc.handler_register("lowest-energy", *HANDLERS)
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="single-point",
)
calc.run(molecule("H2O"))

for name in HANDLERS:
    print(f"{name}:\n{calc.instance.res.product[name]}\n")
