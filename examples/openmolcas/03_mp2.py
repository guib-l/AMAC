"""MP2/cc-pVDZ energy of water with OpenMolcas, with and without frozen core.

MBPT2 is closed-shell only and freezes the core by default.

Usage:
    python examples/openmolcas/03_mp2.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

for frozen in (True, False):
    label = "frozen-core" if frozen else "all-electron"
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/mp2/{label}", label=label)
    calc.handler_register("lowest-energy", "energy-resume")
    calc.parameters_register(
        method="mp2",
        method_args={"basis": "cc-pvdz", "frozen-core": frozen},
        module="single-point",
    )
    calc.run(molecule("H2O"))
    resume = calc.instance.res.product["energy-resume"]
    print(f"MP2 ({label}): {resume['energy']:.8f} Ha (HF reference {resume['scf']:.8f} Ha)")
