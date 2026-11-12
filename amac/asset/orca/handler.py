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


@handler(software="orca", name="lowest_energy")
def lowest_energy(results):
    """Final single-point energy (Hartree)."""
    return results["energy"]["energy"]


@handler(software="orca", name="energy_resume")
def energy_resume(results):
    return results["energy"]


@handler(software="orca", name="forces")
def forces(results):
    """Forces on the atoms (Hartree/Bohr)."""
    return results["forces"]


@handler(software="orca", name="final_geometry")
def final_geometry(results):
    return results["output_geometry"]


@handler(software="orca", name="charges")
def charges(results):
    """Mulliken charge of each atom (e)."""
    return results["charges"]


@handler(software="orca", name="dipole")
def dipole(results):
    """Dipole moment (e.Bohr)."""
    return results["dipole"]


@handler(software="orca", name="frequencies")
def frequencies(results):
    """Vibrational frequencies (cm^-1) and IR intensities (km/mol), shape (n, 2)."""
    if results["frequencies"] is None:
        raise KeyError("no IR SPECTRUM block in the ORCA output")
    return results["frequencies"]


@handler(software="orca", name="excited_states")
def excited_states(results):
    """Excited states by spin symmetry: ``w`` (eV) and ``oscillator``."""
    if results["excited-states"] is None:
        raise KeyError("no excited states in the ORCA output")
    return results["excited-states"]


@handler(software="orca", name="trajectory")
def trajectory(results):
    """MD frames (ase.Atoms) with ``info`` time (fs), epot and ekin (Hartree or None)."""
    return results["trajectory"]
