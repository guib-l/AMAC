"""B3LYP/def2-SVP vibrational frequencies and IR intensities of water with ORCA.

The geometry is not optimized first (see 07_optimization.py).

Usage:
    python examples/orca/08_frequencies.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/frequencies", label="water")
calc.handler_register("frequencies")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="frequencies",
)
calc.run(molecule("H2O"))

for wavenumber, intensity in calc.instance.res.product["frequencies"]:
    print(f"{wavenumber:10.2f} cm^-1   IR {intensity:8.2f} km/mol")
