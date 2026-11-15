"""TD-DFTB (Casida) singlet excitations of water with DFTB+.

Usage:
    python examples/dftbplus/07_td_dftb.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

calc = AMAC(software="dftb+", workdir=".run/dftbplus/td_dftb", label="water")
calc.handler_register("excited-states")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS},
    module="td-dftb",
    module_args={"excitations": 4, "symmetry": "singlet", "diagonalizer": "arpack"},
)
calc.run(molecule("H2O"))

for symmetry, states in calc.instance.res.product["excited-states"].items():
    for name, state in states.items():
        print(
            f"{symmetry:8s} {name}: {state['w']:7.3f} eV  f = {state['oscillator']:.4f}  "
            f"{state['from']} -> {state['to']} ({state['weight']:.2f})"
        )
