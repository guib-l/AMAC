"""CASSCF(4,4)/cc-pVDZ of water with OpenMolcas: one state, then three
states averaged with weights 0.5, 0.25, 0.25.

The inactive orbitals are deduced from the number of electrons. RASSCF
weights are integers: [0.5, 0.25, 0.25] is written 2 1 1.

Usage:
    python examples/openmolcas/04_casscf.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

ACTIVE = {"basis": "cc-pvdz", "active-orbitals": 4, "active-electrons": 4}

for label, extra in (
    ("ground-state", {}),
    ("state-average", {"roots": 3, "weights": [0.5, 0.25, 0.25]}),
):
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/casscf/{label}", label=label)
    calc.handler_register("lowest-energy", "energy-resume")
    calc.parameters_register(method="casscf", method_args={**ACTIVE, **extra}, module="single-point")
    calc.run(molecule("H2O"))
    roots = calc.instance.res.product["energy-resume"]["roots"]
    print(f"CASSCF(4,4) {label}: " + ", ".join(f"{energy:.8f}" for energy in roots) + " Ha")
