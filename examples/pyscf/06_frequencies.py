"""HF/6-31G harmonic frequencies of water with PySCF.

The geometry is not optimized first, so small or imaginary (negative)
modes are expected among the six translations/rotations.

Usage:
    python examples/pyscf/06_frequencies.py
"""

from ase.build import molecule

from amac.amac import AMAC

calc = AMAC(software="pyscf", workdir=".run/pyscf/frequencies", label="water")
calc.handler_register("frequencies")
calc.parameters_register(method="hf", method_args={"basis": "6-31g"}, module="frequencies")
calc.run(molecule("H2O"))

for wavenumber, _ in calc.instance.res.product["frequencies"]:
    print(f"{wavenumber:10.2f} cm^-1")
