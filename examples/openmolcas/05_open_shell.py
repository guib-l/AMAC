"""OH radical (doublet) with OpenMolcas: UHF and CASSCF(3,3).

Without "reference", a multiplicity above 1 gives UHF; "restricted" is
refused and "restricted-open" is not available in &SCF. CASSCF is
spin-adapted and ignores "reference".

Usage:
    python examples/openmolcas/05_open_shell.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

RUNS = (
    ("uhf", "hf", {}),
    ("casscf", "casscf", {"active-orbitals": 3, "active-electrons": 3}),
)

for label, method, extra in RUNS:
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/open_shell/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method=method,
        method_args={"basis": "cc-pvdz", "multiplicity": 2, **extra},
        module="single-point",
    )
    calc.run(molecule("OH"))
    print(f"OH {label}: {calc.instance.res.product['lowest-energy']:.8f} Ha")
