from amac.engine.handler import handler

__all__ = [
    "lowest_energy",
    "energy_resume",
    "state_energies",
    "correlation_energy",
    "forces",
    "final_geometry",
    "frequencies",
    "charges",
    "dipole",
]


@handler(software="openmolcas", name="lowest_energy")
def lowest_energy(results):
    """Final energy (Hartree); lowest root for CASSCF."""
    return results["energy"]["energy"]


@handler(software="openmolcas", name="energy_resume")
def energy_resume(results):
    """Final energy with the intermediate energies found (Hartree).

    Keys when present: ``scf``, ``mp2``, ``ccsd``, ``ccsd(t)``, ``roots``
    (CASSCF) and ``pt2`` (root energies by label, e.g. ``XMS-CASPT2``).
    """
    return results["energy"]


@handler(software="openmolcas", name="state_energies")
def state_energies(results):
    """Roots of CASSCF, CASPT2 or NEVPT2, at the highest level computed.

    A list of ``{"root", "energy" (Hartree), "excitation" (eV above the
    lowest root)}``; for CASPT2, multi-state (MS, XMS, RMS) energies when
    requested.
    """
    if results["states"] is None:
        raise KeyError("state energies need a CAS-based method (CASSCF, CASPT2, NEVPT2)")
    return results["states"]


@handler(software="openmolcas", name="correlation_energy")
def correlation_energy(results):
    """Correlation energy E - E(SCF) of MP2, CCSD or CCSD(T) (Hartree)."""
    if results["correlation"] is None:
        raise KeyError("correlation energy needs MP2, CCSD or CCSD(T)")
    return results["correlation"]


@handler(software="openmolcas", name="forces")
def forces(results):
    """Forces on the atoms (Hartree/Bohr)."""
    if results["forces"] is None:
        raise KeyError("no ALASKA gradient in the OpenMolcas output")
    return results["forces"]


@handler(software="openmolcas", name="final_geometry")
def final_geometry(results):
    if results["output_geometry"] is None:
        raise KeyError("no final geometry in the OpenMolcas outputs")
    return results["output_geometry"]


@handler(software="openmolcas", name="frequencies")
def frequencies(results):
    """Vibrational frequencies (cm^-1) and IR intensities (km/mol), shape (n, 2)."""
    if results["frequencies"] is None:
        raise KeyError("no freq.molden frequencies in the OpenMolcas outputs")
    return results["frequencies"]


@handler(software="openmolcas", name="charges")
def charges(results):
    """Mulliken charge of each atom (e)."""
    if results["charges"] is None:
        raise KeyError("no Mulliken charges in the OpenMolcas output")
    return results["charges"]


@handler(software="openmolcas", name="dipole")
def dipole(results):
    """Dipole moment (e.Bohr)."""
    if results["dipole"] is None:
        raise KeyError("no dipole moment in the OpenMolcas output")
    return results["dipole"]
