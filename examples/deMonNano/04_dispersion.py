"""Binding energy of the water dimer in DFTB-2 with each deMonNano dispersion.

E_bind = E(dimer) - 2 E(monomer) with dispersion model-1 and model-2.
deMonNano cannot switch its dispersion off through AMAC (model-1 is the
default).

Usage:
    python examples/deMonNano/04_dispersion.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

HARTREE_KCAL = 627.509

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

water = molecule("H2O")
dimer = water + water.copy()
dimer.positions[3:] += [-0.2, 0.0, 2.7]


def energy(image, label, dispersion):
    """DFTB-2 energy (Hartree) of ``image`` with the ``dispersion`` model."""
    calc = AMAC(software="deMonNano", workdir=f".run/deMonNano/dispersion/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dftb-2",
        method_args={"basis": BASIS, "dispersion": dispersion},
        module="single-point",
    )
    calc.run(image)
    return calc.instance.res.product["lowest-energy"]


for dispersion in ("model-1", "model-2"):
    bind = energy(dimer, f"{dispersion}-dimer", dispersion) - 2 * energy(
        water, dispersion, dispersion
    )
    print(f"{dispersion}: E_bind = {bind * HARTREE_KCAL:7.2f} kcal/mol")
