"""Periodic DFTB-2 single-point energy of graphene with DFTB+.

Graphene is metallic: a Fermi filling temperature is set.

Usage:
    python examples/dftbplus/10_periodic.py
"""

import json
from pathlib import Path

from ase.build import graphene

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

sheet = graphene(a=2.46, vacuum=10.0)
sheet.pbc = True

calc = AMAC(software="dftb+", workdir=".run/dftbplus/periodic", label="graphene")
calc.handler_register("lowest-energy", "k-points")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS, "kpoints": [12, 12, 1], "filling": 300.0},
    module="single-point",
)
calc.run(sheet)

product = calc.instance.res.product
print(f"Energy: {product['lowest-energy']:.8f} Ha ({len(product['k-points'])} k-points)")
