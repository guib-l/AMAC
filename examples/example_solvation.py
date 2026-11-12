"""Solvation energy of water in water (C-PCM), B3LYP/def2-SVP with PySCF.

Usage:
    python examples/example_solvation.py
"""

from ase.build import molecule

from amac.amac import AMAC

HARTREE_KCAL = 627.509

water = molecule("H2O")
energies = {}
for label, options in (
    ("vacuum", {}),
    ("cpcm", {"solvation": {"model": "cpcm", "solvent": "water"}}),
):
    calc = AMAC(software="pyscf", workdir=f".run/solvation/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dft",
        method_args={"functional": "b3lyp", "basis": "def2-svp"},
        module="single-point",
        module_args={},
        options=options,
    )
    calc.run(water)
    energies[label] = calc.instance.res.product["lowest-energy"]

delta = (energies["cpcm"] - energies["vacuum"]) * HARTREE_KCAL
print(f"E(vacuum) = {energies['vacuum']:.8f} Ha")
print(f"E(C-PCM)  = {energies['cpcm']:.8f} Ha")
print(f"Solvation energy: {delta:.2f} kcal/mol")
