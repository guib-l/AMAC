"""HF/def2-SVP single-point energy of water with ORCA.

Needs an "orca" section with the absolute executable in config-amac.json.

Usage:
    python examples/orca/01_single_point_hf.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/single_point_hf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(method="hf", method_args={"basis": "def2-svp"}, module="single-point")
calc.run(molecule("H2O"))

print(f"HF/def2-SVP energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
