"""GFN1-xTB and GFN2-xTB single-point energies of water with ORCA.

Usage:
    python examples/orca/05_xtb.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

for level in ("gfn1", "gfn2"):
    calc = AMAC(software="orca", workdir=f".run/orca/xtb/{level}", label="water")
    calc.handler_register("lowest-energy")
    calc.parameters_register(method="xtb", method_args={"level": level}, module="single-point")
    calc.run(molecule("H2O"))
    print(f"{level}: {calc.instance.res.product['lowest-energy']:.8f} Ha")
