"""HF/STO-3G single-point energy of water with PySCF.

PySCF runs in-process: no executable to configure.

Usage:
    python examples/pyscf/01_single_point_hf.py
"""

from ase.build import molecule

from amac.amac import AMAC

calc = AMAC(software="pyscf", workdir=".run/pyscf/single_point_hf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(method="hf", method_args={"basis": "sto-3g"}, module="single-point")
calc.run(molecule("H2O"))

print(f"HF/STO-3G energy: {calc.instance.res.product['lowest-energy']:.8f} Ha")
