"""DFTB-2 Born-Oppenheimer MD of water with DFTB+ (Berendsen, 300 K).

Usage:
    python examples/dftbplus/08_molecular_dynamics.py
"""

import json
from pathlib import Path

from ase.build import molecule

import amac
from amac.amac import AMAC

CONFIG = json.loads(Path("config-amac.json").read_text())
amac.configure(config=CONFIG)
BASIS = {"directory": CONFIG["software"]["dftb+"]["basis"]}

calc = AMAC(software="dftb+", workdir=".run/dftbplus/molecular_dynamics", label="water")
calc.handler_register("trajectory")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": BASIS},
    module="molecular-dynamics",
    module_args={
        "steps": 100,
        "time-step": 0.5,
        "temperature": 300.0,
        "thermostat": {"value": "berendsen", "time-constant": 50.0},
    },
)
calc.run(molecule("H2O"))

print(f"{'time (fs)':>10} {'Epot (Ha)':>14} {'Ekin (Ha)':>12}")
for frame in calc.instance.res.product["trajectory"][::10]:
    print(f"{frame.info['time']:10.2f} {frame.info['epot']:14.8f} {frame.info['ekin']:12.8f}")
