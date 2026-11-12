from amac.engine.handler import handler

__all__ = [
    "lowest_energy",
    "energy_resume",
    "forces",
    "final_geometry",
    "charges",
    "dipole",
    "frequencies",
    "excited_states",
    "trajectory",
]


@handler(software="pyscf", name="trajectory")
def trajectory(results):
    """MD frames (ase.Atoms) with ``info`` time (fs), epot and ekin (Hartree)."""
    return results["trajectory"]


@handler(software="pyscf", name="lowest_energy")
def lowest_energy(results):
    """Total energy of the requested method (Hartree)."""
    return results["energy"]["energy"]


@handler(software="pyscf", name="energy_resume")
def energy_resume(results):
    return results["energy"]


@handler(software="pyscf", name="forces")
def forces(results):
    """Forces on the atoms (Hartree/Bohr)."""
    return results["forces"]


@handler(software="pyscf", name="final_geometry")
def final_geometry(results):
    return results["output_geometry"]


@handler(software="pyscf", name="charges")
def charges(results):
    """Mulliken charge of each atom (e), from the mean-field density."""
    return results["charges"]


@handler(software="pyscf", name="dipole")
def dipole(results):
    """Dipole moment (e.Bohr), from the mean-field density."""
    return results["dipole"]


@handler(software="pyscf", name="frequencies")
def frequencies(results):
    """Harmonic frequencies (cm^-1) and IR intensities (NaN), shape (n, 2)."""
    return results["frequencies"]


@handler(software="pyscf", name="excited_states")
def excited_states(results):
    """Excited states by spin symmetry: ``w`` (eV) and ``oscillator``."""
    return results["excited-states"]
