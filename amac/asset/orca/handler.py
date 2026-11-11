from amac.engine.handler import handler

__all__ = [
    "lowest_energy",
    "energy_resume",
    "forces",
    "final_geometry",
    "charges",
    "dipole",
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
