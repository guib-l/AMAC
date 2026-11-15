"""Binding energy of the water dimer in DFTB-2 with each DFTB+ dispersion.

E_bind = E(dimer) - 2 E(monomer), without correction then with Lennard-Jones
(UFF), D3-BJ, D3 zero damping and D4.

DFTB+ has no default damping parameters for D3 and D4: they depend on the
Slater-Koster set and must be given. D4 uses the mio values of the DFTB+
manual (Appendix H); D3-BJ (manual example) and D3 zero damping (DFTB3-D3H5)
use 3ob values, only to illustrate the syntax with mio-1-1. "d3-zero" needs a
DFTB+ build with the dftd3 library.

Usage:
    python examples/dftbplus/04_dispersion.py
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

DISPERSIONS = {
    "none": None,
    "lj-uff": "lj-uff",
    "d3-bj": {"value": "d3-bj", "s6": 1.0, "s8": 0.5883, "a1": 0.5719, "a2": 3.6017},
    "d3-zero": {"value": "d3-zero", "s6": 1.0, "s8": 0.49, "sr6": 1.25, "alpha6": 29.61},
    "d4": {
        "value": "d4",
        "s6": 1.0,
        "s8": 1.1948145,
        "s9": 0.0,
        "a1": 0.6074567,
        "a2": 4.9336133,
    },
}

water = molecule("H2O")
dimer = water + water.copy()
dimer.positions[3:] += [-0.2, 0.0, 2.7]


def energy(image, label, dispersion):
    """DFTB-2 energy (Hartree) of ``image`` with the ``dispersion`` correction."""
    args = {"basis": BASIS} | ({"dispersion": dispersion} if dispersion else {})
    calc = AMAC(software="dftb+", workdir=f".run/dftbplus/dispersion/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(method="dftb-2", method_args=args, module="single-point")
    calc.run(image)
    return calc.instance.res.product["lowest-energy"]


for name, dispersion in DISPERSIONS.items():
    bind = energy(dimer, f"{name}-dimer", dispersion) - 2 * energy(water, name, dispersion)
    print(f"{name:8s} E_bind = {bind * HARTREE_KCAL:7.2f} kcal/mol")
