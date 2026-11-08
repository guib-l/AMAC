from amac.engine.handler import handler

__all__ = [
    "properties",
    "lowest_energy",
    "energy_resume",
    "final_geometry",
    "forces",
    "n_electrons",
    "homo_lumo_gap",
    "repulsive_energy",
    "electronic_energy",
]


@handler(software="deMonNano", name="properties")
def properties(results):

    return results["properties"]

@handler(software="deMonNano", name="lowest_energy")
def lowest_energy(results):

    return results["energy"]["energy"]

@handler(software="deMonNano", name="energy_resume")
def energy_resume(results):

    return results["energy"]

# deMonNano writes no forces for a single point.
@handler(
    software="deMonNano",
    name="forces",
    modules=("optimization-geometry",),
)
def forces(results):
    """Forces on the atoms (Hartree/Bohr)."""
    return results["forces"]

@handler(software="deMonNano", name="final_geometry")
def final_geometry(results):

    return results["output_geometry"]

@handler(software="deMonNano", name="n_electrons")
def n_electrons(results):
    """Total number of electrons."""
    return float(results["properties"]["n_electrons"])

@handler(software="deMonNano", name="homo_lumo_gap")
def homo_lumo_gap(results):
    """HOMO-LUMO gap (eV)."""
    return results["energy"]["HOMO-LUMO_gap"]

@handler(software="deMonNano", name="repulsive_energy")
def repulsive_energy(results):
    """Repulsive energy (Hartree)."""
    return results["energy"]["repulsive_energy"]

@handler(software="deMonNano", name="electronic_energy")
def electronic_energy(results):
    """Electronic energy (Hartree)."""
    return results["energy"]["electronic_energy"]
