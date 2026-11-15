"""Periodic DFTB-2 single-point energy of graphene with deMonNano.

Graphene is metallic: a Fermi filling temperature is set. A periodic image
always needs a kpoints grid ([1, 1, 1] for the gamma point).

Usage:
    python examples/deMonNano/08_periodic.py
"""

import json
from pathlib import Path

from ase.build import graphene

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

sheet = graphene(a=2.46, vacuum=10.0)
sheet.pbc = True

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/periodic", label="graphene")
calc.handler_register("lowest-energy", "k-points")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS, "kpoints": [12, 12, 1], "filling": 300.0},
    module="single-point",
    # Raw deMonNano keyword, as in examples/general/periodic.py.
    software_args={"deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.FHUB": True}},
)
calc.run(sheet)

product = calc.instance.res.product
print(f"Energy: {product['lowest-energy']:.8f} Ha ({len(product['k-points'])} k-points)")
