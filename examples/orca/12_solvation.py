"""Solvation energy of water in water, C-PCM and SMD, B3LYP/def2-SVP with ORCA.

Usage:
    python examples/orca/12_solvation.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

HARTREE_KCAL = 627.509

amac.configure_from_file("config-amac.json")

energies = {}
for model in (None, "cpcm", "smd"):
    label = model or "vacuum"
    options = {"solvation": {"model": model, "solvent": "water"}} if model else {}
    calc = AMAC(software="orca", workdir=f".run/orca/solvation/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dft",
        method_args={"basis": "def2-svp", "functional": "b3lyp"},
        module="single-point",
        options=options,
    )
    calc.run(molecule("H2O"))
    energies[label] = calc.instance.res.product["lowest-energy"]

for model in ("cpcm", "smd"):
    delta = (energies[model] - energies["vacuum"]) * HARTREE_KCAL
    print(f"{model}: solvation energy {delta:.2f} kcal/mol")
