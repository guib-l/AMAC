"""DFTB-2 electronic properties of water with DFTB+.

Usage:
    python examples/dftbplus/03_properties.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

HANDLERS = (
    "n-electrons",          # e
    "charges",              # Mulliken charges (e)
    "dipole",               # e.Bohr
    "eigenvalues",          # Hartree, per spin and k-point
    "occupations",          # per spin and k-point
    "fermi-level",          # Hartree, per spin
    "repulsive-energy",     # Hartree
    "electronic-energy",    # Hartree
    "forces",               # Hartree/Bohr
)

calc = AMAC(software="dftb+", workdir=".run/dftbplus/properties", label="water")
calc.handler_register("lowest-energy", *HANDLERS)
calc.parameters_register(method="dftb-2", method_args={"basis": BASIS}, module="single-point")
calc.run(molecule("H2O"))

for name in HANDLERS:
    print(f"{name}:\n{calc.instance.res.product[name]}\n")
