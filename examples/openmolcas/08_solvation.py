"""Solvation energy of water with OpenMolcas C-PCM, B3LYP/cc-pVDZ.

Two solvents by name, and one by its dielectric constant. Only "cpcm" is
available (PCM, conductor version); "smd" and "gbsa" are refused.

Usage:
    python examples/openmolcas/08_solvation.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

HARTREE_KCAL = 627.509

amac.configure_from_file("config-amac.json")

SOLVENTS = {
    "vacuum": None,
    "water": {"model": "cpcm", "solvent": "water"},
    "dmso": {"model": "cpcm", "solvent": "dmso"},
    "epsilon-10": {"model": "cpcm", "epsilon": 10.0},
}

energies = {}
for label, solvation in SOLVENTS.items():
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/solvation/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dft",
        method_args={"basis": "cc-pvdz", "functional": "b3lyp"},
        module="single-point",
        options={"solvation": solvation} if solvation else {},
    )
    calc.run(molecule("H2O"))
    energies[label] = calc.instance.res.product["lowest-energy"]

for label in list(SOLVENTS)[1:]:
    delta = (energies[label] - energies["vacuum"]) * HARTREE_KCAL
    print(f"{label}: solvation energy {delta:.2f} kcal/mol")
