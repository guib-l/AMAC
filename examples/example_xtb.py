"""GFN2-xTB single-point energy of water with DFTB+ (tblite build).

Needs the "dftb+" section with the absolute executable in config-amac.json.

Usage:
    python examples/example_xtb.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

water = molecule("H2O")

calc = AMAC(software="dftb+", workdir=".run/xtb", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="xtb",
    method_args={"level": "gfn2"},
    module="single-point",
    module_args={},
)
calc.run(water)

print(f"DFTB+ GFN2-xTB energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
