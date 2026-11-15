"""B3LYP/def2-SVP transition state of the NH3 umbrella inversion with ORCA.

The search starts from a flattened ammonia, with an exact initial Hessian;
the transition state is planar.

Usage:
    python examples/orca/10_transition_state.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

ammonia = molecule("NH3")
ammonia.positions[:, 2] *= 0.3  # close to planar

calc = AMAC(software="orca", workdir=".run/orca/transition_state", label="nh3")
calc.handler_register("lowest-energy", "final-geometry")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="transition-state",
    module_args={"hessian": "calculate", "max-step": 100},
)
calc.run(ammonia)

ts = calc.instance.res.product["final-geometry"]
angles = sum(ts.get_angle(i, 0, j) for i, j in ((1, 2), (2, 3), (3, 1)))
print(f"TS energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
print(f"Sum of H-N-H angles: {angles:.1f}° (360° when planar)")
