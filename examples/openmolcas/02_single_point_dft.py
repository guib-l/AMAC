"""B3LYP/cc-pVDZ energy of water with OpenMolcas: grid and RICD.

"b3lyp" is B3LYP with VWN5 (OpenMolcas B3LYP5); "b3lyp-g" is the Gaussian
B3LYP (VWN RPA). "density-fitting" turns on the on-the-fly RICD auxiliary
basis.

Usage:
    python examples/openmolcas/02_single_point_dft.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

for label, extra in (
    ("default", {}),
    ("fine-grid", {"grid": "fine"}),
    ("ricd", {"density-fitting": True}),
):
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/dft/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dft",
        method_args={"basis": "cc-pvdz", "functional": "b3lyp", **extra},
        module="single-point",
    )
    calc.run(molecule("H2O"))
    print(f"B3LYP/cc-pVDZ ({label}): {calc.instance.res.product['lowest-energy']:.8f} Ha")
