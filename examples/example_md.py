"""HF/STO-3G Born-Oppenheimer MD of water with PySCF (Berendsen, 300 K).

Usage:
    python examples/example_md.py
"""

from ase.build import molecule

from amac.amac import AMAC

water = molecule("H2O")

calc = AMAC(software="pyscf", workdir=".run/md", label="water")
calc.handler_register("trajectory")
calc.parameters_register(
    method="hf",
    method_args={"basis": "sto-3g"},
    module="molecular-dynamics",
    module_args={
        "steps": 20,
        "time-step": 0.5,
        "temperature": 300.0,
        "thermostat": {"value": "berendsen", "time-constant": 50.0},
    },
)
calc.run(water)

print(f"{'time (fs)':>10} {'Epot (Ha)':>14} {'Ekin (Ha)':>12}")
for frame in calc.instance.res.product["trajectory"]:
    print(f"{frame.info['time']:10.2f} {frame.info['epot']:14.8f} {frame.info['ekin']:12.8f}")
