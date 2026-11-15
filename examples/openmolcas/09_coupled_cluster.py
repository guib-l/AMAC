"""CCSD and CCSD(T)/cc-pVDZ energies of water with OpenMolcas (&CHCC, &CHT3).

CHCC is closed-shell, without symmetry, on Cholesky integrals (added to
&SEWARD by the asset). The core is frozen unless "frozen-core" is false.

Usage:
    python examples/openmolcas/09_coupled_cluster.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

RUNS = (
    ("ccsd", "ccsd", {}),
    ("ccsd-t", "ccsd(t)", {}),
    ("ccsd-t-all-electron", "ccsd(t)", {"frozen-core": False}),
)

for label, method, extra in RUNS:
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/coupled_cluster/{label}", label=label)
    calc.handler_register("lowest-energy", "correlation-energy")
    calc.parameters_register(
        method=method,
        method_args={"basis": "cc-pvdz", **extra},
        module="single-point",
    )
    calc.run(molecule("H2O"))
    product = calc.instance.res.product
    print(
        f"{label}: {product['lowest-energy']:.8f} Ha "
        f"(correlation {product['correlation-energy']:.8f} Ha)"
    )
