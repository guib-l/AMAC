"""CASSCF(4,4)/6-31G energy of water with PySCF.

Usage:
    python examples/pyscf/04_casscf.py
"""

from ase.build import molecule

from amac.amac import AMAC

calc = AMAC(software="pyscf", workdir=".run/pyscf/casscf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="casscf",
    method_args={"basis": "6-31g", "active-orbitals": 4, "active-electrons": 4},
    module="single-point",
)
calc.run(molecule("H2O"))

print(f"CASSCF(4,4)/6-31G energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
