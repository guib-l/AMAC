"""Solvation energy of water in water (C-PCM), B3LYP/def2-SVP with PySCF.

Usage:
    python examples/pyscf/10_solvation.py
"""

from ase.build import molecule

from amac.amac import AMAC

HARTREE_KCAL = 627.509

energies = {}
for label, options in (
    ("vacuum", {}),
    ("cpcm", {"solvation": {"model": "cpcm", "solvent": "water"}}),
):
    calc = AMAC(software="pyscf", workdir=f".run/pyscf/solvation/{label}", label=label)
    calc.handler_register("lowest-energy")
    calc.parameters_register(
        method="dft",
        method_args={"basis": "def2-svp", "functional": "b3lyp"},
        module="single-point",
        options=options,
    )
    calc.run(molecule("H2O"))
    energies[label] = calc.instance.res.product["lowest-energy"]

delta = (energies["cpcm"] - energies["vacuum"]) * HARTREE_KCAL
print(f"Solvation energy: {delta:.2f} kcal/mol")
