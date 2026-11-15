"""CASPT2 on a CASSCF(4,4)/cc-pVDZ reference of water with OpenMolcas.

Single-state CASPT2 on the ground state, then three state-averaged roots
treated state by state (single), and coupled (MS and XMS) with an
imaginary shift. OpenMolcas applies an IPEA shift of 0.25 Eh by default;
the last run sets it to 0.

Usage:
    python examples/openmolcas/10_caspt2.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

ACTIVE = {"basis": "cc-pvdz", "active-orbitals": 4, "active-electrons": 4}
THREE_ROOTS = {"roots": 3, "imaginary-shift": 0.1}

RUNS = (
    ("ground-state", {}),
    ("single", {**THREE_ROOTS, "multistate": "single"}),
    ("ms", {**THREE_ROOTS, "multistate": "ms"}),
    ("xms", {**THREE_ROOTS, "multistate": "xms"}),
    ("xms-ipea-0", {**THREE_ROOTS, "multistate": "xms", "ipea-shift": 0.0}),
)

for label, extra in RUNS:
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/caspt2/{label}", label=label)
    calc.handler_register("lowest-energy", "state-energies")
    calc.parameters_register(method="caspt2", method_args={**ACTIVE, **extra}, module="single-point")
    calc.run(molecule("H2O"))
    print(f"{label}:")
    for state in calc.instance.res.product["state-energies"]:
        print(f"  root {state['root']}: {state['energy']:.8f} Ha  {state['excitation']:6.3f} eV")
