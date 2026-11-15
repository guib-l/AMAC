"""B3LYP/cc-pVDZ charges, dipole and forces of water with OpenMolcas.

Asking for "forces" adds &ALASKA (analytic gradient) after &SCF.

Usage:
    python examples/openmolcas/06_properties.py
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

calc = AMAC(software="openmolcas", workdir=".run/openmolcas/properties", label="water")
calc.handler_register("lowest-energy", *HANDLERS)
calc.parameters_register(
    method="dft",
    method_args={"basis": "cc-pvdz", "functional": "b3lyp"},
    module="single-point",
)
calc.run(molecule("H2O"))

for name in HANDLERS:
    print(f"{name}:\n{calc.instance.res.product[name]}\n")
