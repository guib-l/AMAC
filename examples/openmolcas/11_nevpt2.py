"""Strongly (SC) and partially (PC) contracted NEVPT2 on a CASSCF(4,4)/cc-pVDZ
reference of water with OpenMolcas (CAS-based NEVPT2 of &CASPT2).

QD-NEVPT2 ("multistate": "qd") needs the DMRG &NEVPT2 program and is refused.

Usage:
    python examples/openmolcas/11_nevpt2.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

ACTIVE = {"basis": "cc-pvdz", "active-orbitals": 4, "active-electrons": 4}

for variant in ("sc", "pc"):
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/nevpt2/{variant}", label=variant)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="nevpt2",
        method_args={**ACTIVE, "variant": variant},
        module="single-point",
    )
    calc.run(molecule("H2O"))
    print(f"{variant.upper()}-NEVPT2: {calc.instance.res.product['lowest-energy']:.8f} Ha")
