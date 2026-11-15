"""Tests of the deMonNano handlers.

deMonNano outputs are parsed by deMonPy, not by AMAC: the raw results
below reproduce the shape of the deMonPy results dict.
"""

import numpy as np
import pytest

from amac.asset.deMonNano import handler
from amac.engine.handler import registered_handlers


@pytest.fixture
def results(water):
    """Raw results with the deMonPy layout."""
    return {
        "errors": [],
        "properties": {"n_electrons": 8},
        "energy": {
            "energy": -4.07494896,
            "electronic_energy": -4.14675238,
            "repulsive_energy": 0.07180342,
            "HOMO-LUMO_gap": 12.5,
        },
        "forces": np.zeros((3, 3)),
        "charges": {"charges mulliken": [-0.6, 0.3, 0.3]},
        "tensors": {"charge_dipole": [0.0, 0.0, -0.7]},
        "kpts_coords": np.zeros((1, 3)),
        "singlet": {"state_0": {"w": 7.1, "oscillator": 0.01}},
        "triplet": {},
        "frequency": [{"frequency": 1596.8, "intensity": 65.0}, {"frequency": 3690.7, "intensity": 21.2}],
        "input_geometry": water,
        "output_geometry": water,
    }


def test_every_handler_registered():
    """Every handler of the module is registered for deMonNano."""
    names = {name.replace("_", "-") for name in handler.__all__}
    assert names <= set(registered_handlers("deMonNano"))


def test_energies(results):
    """Energy handlers."""
    assert handler.lowest_energy(results) == -4.07494896
    assert handler.electronic_energy(results) == -4.14675238
    assert handler.repulsive_energy(results) == 0.07180342
    assert handler.homo_lumo_gap(results) == 12.5
    assert handler.energy_resume(results) is results["energy"]


def test_properties(results, water):
    """Electrons, charges, dipole, forces, geometry and k-points."""
    assert handler.n_electrons(results) == 8.0
    assert handler.charges(results) == [-0.6, 0.3, 0.3]
    assert handler.dipole(results) == [0.0, 0.0, -0.7]
    assert handler.forces(results).shape == (3, 3)
    assert handler.final_geometry(results) is water
    assert handler.k_points(results).shape == (1, 3)
    assert handler.properties(results) == {"n_electrons": 8}


def test_charges_missing(results):
    """Mulliken charges are only parsed by deMonPy for CI-DFTB."""
    results["charges"] = {}
    with pytest.raises(KeyError, match="only parsed for CI-DFTB"):
        handler.charges(results)


def test_dipole_missing(results):
    """A missing dipole is a KeyError."""
    del results["tensors"]
    with pytest.raises(KeyError, match="no dipole"):
        handler.dipole(results)


def test_excited_states(results):
    """Only the symmetries holding states are returned."""
    assert handler.excited_states(results) == {"singlet": {"state_0": {"w": 7.1, "oscillator": 0.01}}}


def test_excited_states_missing(results):
    """No state at all is a KeyError."""
    results["singlet"] = {}
    with pytest.raises(KeyError, match="no TD-DFTB states"):
        handler.excited_states(results)


def test_frequencies(results):
    """Frequencies and intensities, shape (n, 2)."""
    assert handler.frequencies(results).tolist() == [[1596.8, 65.0], [3690.7, 21.2]]
