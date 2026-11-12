"""B3LYP/def2-SVP single-point energy of water with PySCF.

PySCF runs in-process: no executable to configure.

Usage:
    python examples/example_pyscf.py
"""

from ase.build import molecule

from amac.amac import AMAC

water = molecule("H2O")

calc = AMAC(software="pyscf", workdir=".run/pyscf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="dft",
    method_args={"basis": "def2-svp", "functional": "b3lyp"},
    module="single-point",
    module_args={},
)
calc.run(water)

print(f"PySCF B3LYP/def2-SVP energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
