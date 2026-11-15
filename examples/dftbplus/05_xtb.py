"""GFN1-xTB and GFN2-xTB single-point energies of water with DFTB+.

Needs a DFTB+ build with tblite; no Slater-Koster files are used.

Usage:
    python examples/dftbplus/05_xtb.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

for level in ("gfn1", "gfn2"):
    calc = AMAC(software="dftb+", workdir=f".run/dftbplus/xtb/{level}", label="water")
    calc.handler_register("lowest-energy")
    calc.parameters_register(method="xtb", method_args={"level": level}, module="single-point")
    calc.run(molecule("H2O"))
    print(f"{level}: {calc.instance.res.product['lowest-energy']:.8f} Ha")
