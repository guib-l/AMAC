"""MP2, CCSD and CCSD(T) energies of water (cc-pVDZ, frozen core) with ORCA.

Usage:
    python examples/orca/03_correlated.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

water = molecule("H2O")

for method in ("mp2", "ccsd", "ccsd(t)"):
    calc = AMAC(software="orca", workdir=f".run/orca/correlated/{method}", label="water")
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method=method,
        method_args={"basis": "cc-pvdz", "frozen-core": True},
        module="single-point",
    )
    calc.run(water)
    print(f"{method:8s} {calc.instance.res.product['lowest-energy']:.8f} Ha")
