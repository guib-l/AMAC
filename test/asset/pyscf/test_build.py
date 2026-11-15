"""Tests of the PySCF builders (molecule, mean field, solvent) without SCF.

Skipped if PySCF is not installed.
"""

import pytest
from ase import Atoms

pytest.importorskip("pyscf")

from amac.asset.pyscf.soft import build_mol, mean_field, with_solvent  # noqa: E402
from amac.asset.solvation import solvation_settings  # noqa: E402


def mol_params(basis="sto-3g", charge=0, multiplicity=1):
    return {"mol": {"basis": basis, "charge": charge, "multiplicity": multiplicity}}


def test_build_mol(tmp_path, water):
    """Atoms, charge, spin and basis of the PySCF molecule."""
    mol = build_mol(water, mol_params(charge=1.0, multiplicity=2), tmp_path / "out.log")
    assert mol.natm == 3
    assert mol.charge == 1
    assert mol.spin == 1
    assert mol.basis == "sto-3g"
    assert mol.atom_coords(unit="Angstrom") == pytest.approx(water.positions, abs=1e-8)


def test_build_mol_ecp_for_heavy_elements(tmp_path):
    """def2 bases get their ECP beyond Kr."""
    image = Atoms("I2", positions=[[0, 0, 0], [0, 0, 2.7]])
    mol = build_mol(image, mol_params(basis="def2-svp"), tmp_path / "out.log")
    assert mol.ecp == "def2-svp"


def test_build_mol_no_ecp_for_light_elements(tmp_path, water):
    """No ECP for light elements."""
    mol = build_mol(water, mol_params(basis="def2-svp"), tmp_path / "out.log")
    assert not mol.ecp


@pytest.fixture
def mol(tmp_path, water):
    return build_mol(water, mol_params(), tmp_path / "out.log")


def test_mean_field_hf(mol):
    """HF: restricted for a singlet, SCF settings applied."""
    mf = mean_field(mol, {"scf": {"conv_tol": 1e-10, "max_cycle": 7, "level_shift": 0.2}})
    assert type(mf).__name__ == "RHF"
    assert (mf.conv_tol, mf.max_cycle, mf.level_shift) == (1e-10, 7, 0.2)


def test_mean_field_unrestricted(mol):
    """An explicit unrestricted reference."""
    assert type(mean_field(mol, {"scf": {"reference": "U"}})).__name__ == "UHF"


def test_mean_field_dft(mol):
    """DFT: functional and grid level."""
    mf = mean_field(mol, {"dft": {"xc": "pbe", "grids_level": 5}})
    assert type(mf).__name__ == "RKS"
    assert mf.xc == "pbe"
    assert mf.grids.level == 5


def test_mean_field_density_fitting(mol):
    """Density fitting wraps the mean field."""
    mf = mean_field(mol, {"scf": {"density_fit": True}})
    assert hasattr(mf, "with_df")


def test_mean_field_solvent(mol):
    """The solvation node attaches a solvent model."""
    mf = mean_field(mol, {"solvation": {"model": "cpcm", "solvent": "water"}})
    assert mf.with_solvent.method == "C-PCM"


def test_with_solvent_epsilon(mol):
    """C-PCM with a dielectric constant."""
    from pyscf import scf

    mf = with_solvent(scf.RHF(mol), solvation_settings({"model": "cpcm", "epsilon": 78.4}))
    assert mf.with_solvent.eps == 78.4


def test_with_solvent_gbsa(mol):
    """GBSA is not available with PySCF."""
    from pyscf import scf

    with pytest.raises(ValueError, match="gbsa is not available"):
        with_solvent(scf.RHF(mol), solvation_settings({"model": "gbsa", "solvent": "water"}))
