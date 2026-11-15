"""HF/cc-pVDZ single-point energy of water with OpenMolcas.

Needs an "openmolcas" section with the absolute path of pymolcas in
config-amac.json.

Usage:
    python examples/openmolcas/01_single_point_hf.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="openmolcas", workdir=".run/openmolcas/single_point_hf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(method="hf", method_args={"basis": "cc-pvdz"}, module="single-point")
calc.run(molecule("H2O"))

print(f"HF/cc-pVDZ energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
