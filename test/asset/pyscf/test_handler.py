"""Tests of the PySCF handlers on a raw results dict."""

import numpy as np
import pytest

from amac.asset.pyscf import handler
from amac.engine.handler import registered_handlers


@pytest.fixture
def results(water):
    """Raw results with the layout of software_pyscf.calculate()."""
    return {
        "errors": [],
        "energy": {"energy": -75.0, "scf_energy": -74.9},
        "forces": np.zeros((3, 3)),
        "charges": [-0.35, 0.175, 0.175],
        "dipole": [0.0, 0.0, -0.67],
        "frequencies": np.array([[1700.0, np.nan]]),
        "excited-states": {"singlet": {"state_0": {"w": 12.9, "oscillator": 0.003}}},
        "trajectory": [water],
        "input_geometry": water,
        "output_geometry": water,
    }


def test_every_handler_registered():
    """Every handler of the module is registered for pyscf."""
    names = {name.replace("_", "-") for name in handler.__all__}
    assert names <= set(registered_handlers("pyscf"))


def test_handlers(results, water):
    """Each handler returns its part of the raw results."""
    assert handler.lowest_energy(results) == -75.0
    assert handler.energy_resume(results) == {"energy": -75.0, "scf_energy": -74.9}
    assert handler.forces(results).shape == (3, 3)
    assert handler.charges(results) == [-0.35, 0.175, 0.175]
    assert handler.dipole(results) == [0.0, 0.0, -0.67]
    assert handler.frequencies(results).shape == (1, 2)
    assert handler.excited_states(results)["singlet"]["state_0"]["w"] == 12.9
    assert handler.trajectory(results) == [water]
    assert handler.final_geometry(results) is water
