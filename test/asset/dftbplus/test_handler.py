"""Tests of the DFTB+ handlers on reference outputs."""

import shutil

import numpy as np
import pytest

from amac.asset.dftbplus import handler
from amac.asset.dftbplus.parser import read_exc_dat, read_results_tag, to_results
from amac.engine.handler import registered_handlers
from asset.dftbplus.conftest import DATA, SP_ENERGY


@pytest.fixture
def results(tmp_path, water):
    """Raw results of the reference single point."""
    shutil.copy(DATA / "sp" / "detailed.out", tmp_path)
    return to_results(read_results_tag(DATA / "sp" / "results.tag"), tmp_path, water)


def test_every_handler_registered():
    """Every handler of the module is registered for dftb+."""
    names = {name.replace("_", "-") for name in handler.__all__}
    assert names <= set(registered_handlers("dftb+"))


def test_energies(results):
    """Energy handlers (Hartree)."""
    assert handler.lowest_energy(results) == pytest.approx(SP_ENERGY)
    assert handler.energy_resume(results)["mermin_energy"] == pytest.approx(SP_ENERGY)
    assert handler.repulsive_energy(results) == pytest.approx(0.0718034081)
    assert handler.electronic_energy(results) == pytest.approx(-4.1495227449)
    assert handler.fermi_level(results) == pytest.approx([0.0625166836066399])


def test_forces_and_geometry(results, water):
    """Forces (Hartree/Bohr) and final geometry."""
    forces = handler.forces(results)
    assert forces.shape == (3, 3)
    assert np.allclose(forces.sum(axis=0), 0.0, atol=1e-8)
    assert handler.final_geometry(results).get_chemical_symbols() == ["O", "H", "H"]


def test_electronic_properties(results):
    """Electrons, charges, dipole, eigenvalues and occupations."""
    assert handler.n_electrons(results) == 8.0
    assert handler.charges(results) == pytest.approx([-0.5875805, 0.29379025, 0.29379025])
    assert handler.dipole(results).shape == (1, 3)
    assert handler.eigenvalues(results).shape == (1, 1, 6)
    assert handler.occupations(results).sum() == pytest.approx(8.0)
    assert "gross_atomic_charges" in handler.properties(results)


def test_excited_states():
    """TD-DFTB states read from EXC.DAT."""
    states = handler.excited_states({"td-dftb": read_exc_dat(DATA / "td" / "EXC.DAT")})
    assert states["singlet"]["state_0"]["w"] == pytest.approx(17.536)


def test_k_points_and_trajectory():
    """These handlers return the prepared values unchanged."""
    kpoints = np.zeros((1, 3))
    assert handler.k_points({"k-points": kpoints}) is kpoints
    assert handler.trajectory({"trajectory": []}) == []
