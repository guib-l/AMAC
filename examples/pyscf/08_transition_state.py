"""HF/6-31G transition state of the NH3 umbrella inversion with PySCF.

The search starts from a flattened ammonia; the transition state is planar.
Needs the "geometric" Python package.

Usage:
    python examples/pyscf/08_transition_state.py
"""

from ase.build import molecule

from amac.amac import AMAC

ammonia = molecule("NH3")
ammonia.positions[:, 2] *= 0.3  # close to planar

calc = AMAC(software="pyscf", workdir=".run/pyscf/transition_state", label="nh3")
calc.handler_register("lowest-energy", "final-geometry")
calc.parameters_register(
    method="hf",
    method_args={"basis": "6-31g"},
    module="transition-state",
    module_args={"hessian": "calculate", "max-step": 100},
)
calc.run(ammonia)

ts = calc.instance.res.product["final-geometry"]
angles = sum(ts.get_angle(i, 0, j) for i, j in ((1, 2), (2, 3), (3, 1)))
print(f"TS energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"Sum of H-N-H angles: {angles:.1f}° (360° when planar)")
