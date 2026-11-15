"""TD-DFTB singlet and triplet excitations of water with deMonNano.

deMonNano accepts the symmetries "singlet" and "both".

Usage:
    python examples/deMonNano/07_td_dftb.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["deMonNano"]["basis"], "ptype": "BIO"}

calc = AMAC(software="deMonNano", workdir=".run/deMonNano/td_dftb", label="water")
calc.handler_register("excited_states")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS},
    module="td-dftb",
    module_args={"excitations": 4, "symmetry": "both"},
)
calc.run(molecule("H2O"))


for symmetry, states in calc.instance.res.product["excited-states"].items():
    for name, state in states.items():
        print(
            f"{symmetry:8s} {name}: {state['w']:7.3f} eV  f = {state['oscillator']:.4f}  "
            f"{state['from']} -> {state['to']} ({state['weight']:.2f})"
        )
