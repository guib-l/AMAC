"""Tests of the ORCA handlers.

The tests on a synthetic results dict are complete; the tests on the
reference outputs of ``data/`` are skeletons until ORCA is installed.
"""

import numpy as np
import pytest

from amac.asset.orca import handler
from amac.engine.handler import registered_handlers


@pytest.fixture
def results(water):
    """Raw results with the layout of read_output()."""
    return {
        "errors": [],
        "energy": {"energy": -74.96},
        "forces": np.zeros((3, 3)),
        "charges": [-0.36, 0.18, 0.18],
        "dipole": [0.0, 0.0, -0.68],
        "frequencies": np.array([[1700.0, 60.0]]),
        "excited-states": {"singlet": {"state_0": {"w": 8.1, "oscillator": 0.01}}},
        "trajectory": [water],
        "input_geometry": water,
        "output_geometry": water,
    }


def test_every_handler_registered():
    """Every handler of the module is registered for orca."""
    names = {name.replace("_", "-") for name in handler.__all__}
    assert names <= set(registered_handlers("orca"))


def test_handlers(results, water):
    """Each handler returns its part of the raw results."""
    assert handler.lowest_energy(results) == -74.96
    assert handler.energy_resume(results) == {"energy": -74.96}
    assert handler.forces(results).shape == (3, 3)
    assert handler.charges(results) == [-0.36, 0.18, 0.18]
    assert handler.dipole(results) == [0.0, 0.0, -0.68]
    assert handler.frequencies(results).shape == (1, 2)
    assert handler.excited_states(results)["singlet"]["state_0"]["w"] == 8.1
    assert handler.trajectory(results) == [water]
    assert handler.final_geometry(results) is water


@pytest.mark.parametrize(
    ("key", "function", "message"),
    [
        ("frequencies", handler.frequencies, "no IR SPECTRUM"),
        ("excited-states", handler.excited_states, "no excited states"),
    ],
)
def test_missing_blocks(results, key, function, message):
    """A missing block is a KeyError."""
    results[key] = None
    with pytest.raises(KeyError, match=message):
        function(results)


def test_handlers_on_reference_outputs():
    """Run every handler on the products of read_output() for the data/
    reference outputs (sp, opt, freq, td) and check units and shapes."""
    pytest.skip("TODO: needs the ORCA reference outputs of data/")
