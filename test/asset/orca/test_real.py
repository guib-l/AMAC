"""Real ORCA calculations on water (skeletons, ORCA is not installed yet).

Each test is skipped by ``orca_real`` while ORCA is unavailable. Once ORCA
is configured, replace each ``pytest.skip`` by the calculation described
in the docstring (with ``run_calc``) and its reference values.
"""

import pytest

pytestmark = pytest.mark.real


def test_hf_single_point(orca_real):
    """HF/STO-3G single point with forces: energy (reference value to note),
    forces (3, 3) summing to 0, Mulliken charges summing to 0, dipole."""
    pytest.skip("TODO: write once ORCA is installed")


def test_dft_single_point(orca_real):
    """B3LYP/def2-SVP single point (examples/example_orca.py): energy below
    the HF energy."""
    pytest.skip("TODO: write once ORCA is installed")


def test_post_hf(orca_real):
    """MP2, CCSD(T) and CASSCF(4,4)/STO-3G energies, below the HF energy."""
    pytest.skip("TODO: write once ORCA is installed")


def test_xtb(orca_real):
    """GFN2-xTB single point (needs the xtb program of ORCA)."""
    pytest.skip("TODO: write once ORCA is installed")


def test_optimization(orca_real):
    """HF/STO-3G optimization: lower energy, new geometry, small forces."""
    pytest.skip("TODO: write once ORCA is installed")


def test_frequencies(orca_real):
    """HF/STO-3G frequencies on the optimized geometry: 3 positive modes."""
    pytest.skip("TODO: write once ORCA is installed")


def test_excited_states(orca_real):
    """TD-DFT, 3 roots: 3 singlet states with increasing energies."""
    pytest.skip("TODO: write once ORCA is installed")


def test_transition_state(orca_real):
    """OptTS run returning a final geometry and an energy."""
    pytest.skip("TODO: write once ORCA is installed")


def test_molecular_dynamics(orca_real):
    """5 MD steps of 0.5 fs: frames, time and epot/ekin of each frame."""
    pytest.skip("TODO: write once ORCA is installed")


def test_solvation(orca_real):
    """C-PCM(water) and SMD(water): energies below the gas-phase energy."""
    pytest.skip("TODO: write once ORCA is installed")
