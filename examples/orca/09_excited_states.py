"""TD-DFT (B3LYP/def2-SVP) singlet and triplet excitations of water with ORCA.

Usage:
    python examples/orca/09_excited_states.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/excited_states", label="water")
calc.handler_register("excited-states")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="excited-states",
    module_args={"excitations": 4, "symmetry": "both"},
)
calc.run(molecule("H2O"))

for symmetry, states in calc.instance.res.product["excited-states"].items():
    for name, state in states.items():
        print(f"{symmetry:8s} {name}: {state['w']:7.3f} eV  f = {state['oscillator']:.4f}")
