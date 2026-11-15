"""Solvation energy of water in water (C-PCM / ddCOSMO), DFTB-2 with DFTB+.

DFTB+ supports the cpcm model only.

Usage:
    python examples/dftbplus/09_solvation.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

HARTREE_KCAL = 627.509

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

energies = {}
for label, options in (
    ("vacuum", {}),
    ("cpcm", {"solvation": {"model": "cpcm", "solvent": "water"}}),
):
    calc = AMAC(software="dftb+", workdir=f".run/dftbplus/solvation/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dftb-2",
        method_args={"basis": BASIS},
        module="single-point",
        options=options,
    )
    calc.run(molecule("H2O"))
    energies[label] = calc.instance.res.product["lowest-energy"]

delta = (energies["cpcm"] - energies["vacuum"]) * HARTREE_KCAL
print(f"Solvation energy: {delta:.2f} kcal/mol")
