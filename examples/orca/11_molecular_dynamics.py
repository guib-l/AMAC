"""GFN2-xTB Born-Oppenheimer MD of water with ORCA (Berendsen, 300 K).

The potential energy of a frame is None when ORCA does not print it.

Usage:
    python examples/orca/11_molecular_dynamics.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="orca", workdir=".run/orca/molecular_dynamics", label="water")
calc.handler_register("trajectory")
calc.parameters_register(
    method="xtb",
    method_args={"level": "gfn2"},
    module="molecular-dynamics",
    module_args={
        "steps": 100,
        "time-step": 0.5,
        "temperature": 300.0,
        "thermostat": {"value": "berendsen", "time-constant": 50.0},
    },
)
calc.run(molecule("H2O"))

trajectory = calc.instance.res.product["trajectory"]
print(f"{len(trajectory)} frames")
for frame in trajectory[::10]:
    print(f"{frame.info['time']:8.2f} fs  Epot = {frame.info['epot']}")
