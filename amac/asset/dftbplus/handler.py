from amac.engine.handler import handler

__all__ = [
    "properties",
    "lowest_energy",
    "energy_resume",
    "final_geometry",
    "forces",
    "n_electrons",
    "charges",
    "dipole",
    "eigenvalues",
    "occupations",
    "fermi_level",
    "repulsive_energy",
    "electronic_energy",
    "k_points",
    "excited_states",
]


@handler(software="dftb+", name="properties")
def properties(results):

    return results["properties"]


@handler(software="dftb+", name="lowest_energy")
def lowest_energy(results):

    return results["energy"]["energy"]


@handler(software="dftb+", name="energy_resume")
def energy_resume(results):

    return results["energy"]


@handler(software="dftb+", name="forces")
def forces(results):
    """Forces on the atoms (Hartree/Bohr)."""
    return results["forces"]


@handler(software="dftb+", name="final_geometry")
def final_geometry(results):

    return results["output_geometry"]


@handler(software="dftb+", name="n_electrons")
def n_electrons(results):
    """Total number of electrons."""
    return float(results["properties"]["number_of_electrons"][0])


@handler(software="dftb+", name="charges")
def charges(results):
    """Mulliken charge of each atom (e)."""
    return results["properties"]["gross_atomic_charges"]


@handler(software="dftb+", name="dipole")
def dipole(results):
    """Dipole moment (e.Bohr)."""
    return results["properties"]["dipole_moments"]


@handler(software="dftb+", name="eigenvalues")
def eigenvalues(results):
    """Orbital energies (Hartree), per spin and k-point."""
    return results["properties"]["eigenvalues"]


@handler(software="dftb+", name="occupations")
def occupations(results):
    """Orbital occupations, per spin and k-point."""
    return results["properties"]["filling"]


@handler(software="dftb+", name="fermi_level")
def fermi_level(results):
    """Fermi level (Hartree), per spin."""
    return results["energy"]["fermi_level"]


@handler(software="dftb+", name="repulsive_energy")
def repulsive_energy(results):
    """Repulsive energy (Hartree)."""
    return results["energy"]["repulsive_energy"]


@handler(software="dftb+", name="electronic_energy")
def electronic_energy(results):
    """Electronic energy (Hartree)."""
    return results["energy"]["electronic_energy"]


@handler(software="dftb+", name="k_points")
def k_points(results):
    """Fractional k-point coordinates used, shape (N, 3)."""
    return results["k-points"]


@handler(software="dftb+", name="excited_states")
def excited_states(results):
    """Linear-response excited states (eV), same shape as deMonNanoPy."""
    return results["td-dftb"]
