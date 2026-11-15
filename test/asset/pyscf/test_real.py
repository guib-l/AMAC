"""Real PySCF calculations on water (skipped if PySCF is unavailable).

Reference values: PySCF of the test machine, ase.build.molecule("H2O"),
STO-3G basis, restricted references.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.real

# Reference energies (Hartree).
HF_ENERGY = -74.96440482399434
MP2_ENERGY = -75.00091684132526
CCSD_T_ENERGY = -75.01537643242935
CASSCF_ENERGY = -74.9868405466311
CPCM_ENERGY = -74.97044317953349

STO3G = {"basis": "sto-3g"}


def test_hf_single_point(pyscf_real, run_calc, water):
    """HF energy, forces, charges and dipole."""
    instance = run_calc(
        "pyscf",
        water,
        "hf",
        STO3G,
        "single-point",
        handlers=("lowest-energy", "energy-resume", "forces", "charges", "dipole"),
    )
    product = instance.res.product
    assert instance.res.complet
    assert product["lowest-energy"] == pytest.approx(HF_ENERGY, abs=1e-6)
    assert product["energy-resume"]["scf_energy"] == pytest.approx(HF_ENERGY, abs=1e-6)
    assert product["forces"].shape == (3, 3)
    assert np.allclose(product["forces"].sum(axis=0), 0.0, atol=1e-6)
    assert sum(product["charges"]) == pytest.approx(0.0, abs=1e-6)
    assert product["dipole"][2] < 0.0


def test_dft_single_point(pyscf_real, run_calc, water):
    """PBE energy is below the HF energy."""
    instance = run_calc(
        "pyscf", water, "dft", {**STO3G, "functional": "pbe"}, "sp", handlers=("lowest-energy",)
    )
    assert instance.res.product["lowest-energy"] < HF_ENERGY


@pytest.mark.parametrize(
    ("method", "args", "energy"),
    [
        ("mp2", {}, MP2_ENERGY),
        ("ccsd(t)", {}, CCSD_T_ENERGY),
        ("casscf", {"active-orbitals": 4, "active-electrons": 4}, CASSCF_ENERGY),
    ],
    ids=["mp2", "ccsd(t)", "casscf"],
)
def test_post_hf(pyscf_real, run_calc, water, method, args, energy):
    """Post-HF energies; the SCF energy is kept apart."""
    instance = run_calc(
        "pyscf", water, method, {**STO3G, **args}, "sp", handlers=("lowest-energy", "energy-resume")
    )
    product = instance.res.product
    assert product["lowest-energy"] == pytest.approx(energy, abs=1e-6)
    assert product["energy-resume"]["scf_energy"] == pytest.approx(HF_ENERGY, abs=1e-6)


def test_excited_states(pyscf_real, run_calc, water):
    """TDHF: 3 singlet states in increasing energy."""
    instance = run_calc(
        "pyscf", water, "hf", STO3G, "td", {"excitations": 3}, handlers=("excited-states",)
    )
    singlets = instance.res.product["excited-states"]["singlet"]
    energies = [state["w"] for state in singlets.values()]
    assert len(energies) == 3
    assert energies == sorted(energies)
    assert energies[0] > 0.0


def test_frequencies(pyscf_real, run_calc, water):
    """Harmonic frequencies: the 3 vibrations of water are positive."""
    instance = run_calc("pyscf", water, "hf", STO3G, "freq", handlers=("frequencies",))
    frequencies = instance.res.product["frequencies"]
    assert frequencies.shape == (3, 2)
    assert np.all(frequencies[:, 0] > 1000.0)
    assert np.all(np.isnan(frequencies[:, 1]))


def test_molecular_dynamics(pyscf_real, run_calc, water):
    """NVE run: one frame per step, increasing time, energies stored."""
    instance = run_calc(
        "pyscf", water, "hf", STO3G, "md", {"steps": 3, "time-step": 0.5}, handlers=("trajectory",)
    )
    frames = instance.res.product["trajectory"]
    times = [frame.info["time"] for frame in frames]
    assert len(frames) >= 3
    assert times == sorted(times)
    assert all(np.isfinite(frame.info["epot"]) for frame in frames)


def test_solvation(pyscf_real, run_calc, water):
    """C-PCM in water lowers the HF energy."""
    instance = run_calc(
        "pyscf",
        water,
        "hf",
        STO3G,
        "sp",
        handlers=("lowest-energy",),
        options={"solvation": {"model": "cpcm", "solvent": "water"}},
    )
    assert instance.res.product["lowest-energy"] == pytest.approx(CPCM_ENERGY, abs=1e-5)


def test_frequencies_post_hf_refused(pyscf_real, run_calc, water):
    """Frequencies are available for HF and DFT only."""
    with pytest.raises(ValueError, match="frequencies is available for HF and DFT only"):
        run_calc("pyscf", water, "mp2", STO3G, "freq", handlers=("frequencies",))


def test_optimization(pyscf_real, needs_geometric, run_calc, water):
    """The optimized geometry has a lower energy."""
    instance = run_calc(
        "pyscf",
        water,
        "hf",
        STO3G,
        "optimization-geometry",
        handlers=("lowest-energy", "forces", "final-geometry"),
    )
    product = instance.res.product
    assert product["lowest-energy"] < HF_ENERGY
    assert np.abs(product["forces"]).max() < 1e-3


def test_transition_state(pyscf_real, needs_geometric, run_calc, water):
    """A transition-state search runs and returns a geometry."""
    instance = run_calc(
        "pyscf",
        water,
        "hf",
        STO3G,
        "transition-state",
        handlers=("lowest-energy", "final-geometry"),
    )
    assert np.isfinite(instance.res.product["lowest-energy"])
    assert len(instance.res.product["final-geometry"]) == 3
