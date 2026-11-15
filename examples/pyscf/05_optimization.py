"""HF/6-31G geometry optimization of water with PySCF.

Needs the "geometric" Python package.

Usage:
    python examples/pyscf/05_optimization.py
"""

from ase.build import molecule

from amac.amac import AMAC

calc = AMAC(software="pyscf", workdir=".run/pyscf/optimization", label="water")
calc.handler_register("lowest-energy", "final-geometry")
calc.parameters_register(
    method="hf",
    method_args={"basis": "6-31g"},
    module="optimization-geometry",
    module_args={"max-step": 50},
)
calc.run(molecule("H2O"))

final = calc.instance.res.product["final-geometry"]
print(f"Optimized energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"O-H distance: {final.get_distance(0, 1):.4f} Å")
print(f"H-O-H angle:  {final.get_angle(1, 0, 2):.2f}°")
