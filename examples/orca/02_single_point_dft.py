"""B3LYP-D3(BJ)/def2-SVP single-point energy of water with ORCA (RI).

Usage:
    python examples/orca/02_single_point_dft.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/single_point_dft", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="dft",
    method_args={
        "basis": "def2-svp",
        "functional": "b3lyp",
        "dispersion": "d3-bj",
        "density-fitting": True,
    },
    module="single-point",
)
calc.run(molecule("H2O"))

print(f"B3LYP-D3(BJ)/def2-SVP energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
