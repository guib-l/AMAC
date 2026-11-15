"""Harmonic frequencies and IR intensities of water with OpenMolcas, cc-pVDZ.

HF gets an analytic Hessian (&MCKINLEY, then &MCLR); B3LYP and MP2 a
numerical one (finite differences of gradients in a &SLAPAF loop). The
frequencies are computed at the given geometry: optimize it first for a
meaningful spectrum.

Usage:
    python examples/openmolcas/12_frequencies.py
"""

from ase.build import molecule

import amac
from amac.amac import AMAC

amac.configure_from_file("config-amac.json")

RUNS = (
    ("hf-analytic", "hf", {}),
    ("b3lyp-numerical", "dft", {"functional": "b3lyp"}),
    ("mp2-numerical", "mp2", {}),
)

for label, method, extra in RUNS:
    calc = AMAC(software="openmolcas", workdir=f".run/openmolcas/frequencies/{label}", label=label)
    calc.handler_register("frequencies")
    calc.parameters_register(
        method=method,
        method_args={"basis": "cc-pvdz", **extra},
        module="frequencies",
    )
    calc.run(molecule("H2O"))
    print(f"{label}:")
    for wavenumber, intensity in calc.instance.res.product["frequencies"]:
        print(f"  {wavenumber:9.2f} cm-1  {intensity:8.2f} km/mol")
