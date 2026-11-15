"""MP2, CCSD and CCSD(T) energies of water (cc-pVDZ, frozen core) with PySCF.

``energy-resume`` also gives the underlying HF energy (``scf_energy``), so the
correlation energy is the difference of the two.

Usage:
    python examples/pyscf/03_correlated.py
"""

from ase.build import molecule

from amac.amac import AMAC

water = molecule("H2O")

for method in ("mp2", "ccsd", "ccsd(t)"):
    calc = AMAC(software="pyscf", workdir=f".run/pyscf/correlated/{method}", label="water")
    calc.handler_register("lowest-energy", "energy-resume")
    calc.parameters_register(
        method=method,
        method_args={"basis": "cc-pvdz", "frozen-core": True},
        module="single-point",
    )
    calc.run(water)
    energy = calc.instance.res.product["energy-resume"]
    print(
        f"{method:8s} E = {energy['energy']:.8f} Ha  "
        f"E_corr = {energy['energy'] - energy['scf_energy']:.8f} Ha"
    )
