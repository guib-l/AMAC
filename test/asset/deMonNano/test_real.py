"""Real deMonNano calculations on water (skipped if deMonNano is unavailable).

Reference values: deMonNano of the test machine with the BIO parameters
(the "basis" directory of the configuration).
"""

import numpy as np
import pytest

pytestmark = pytest.mark.real

# Reference DFTB-2/BIO energy of ase.build.molecule("H2O") (Hartree).
SP_ENERGY = -4.07494896


def test_single_point(demonnano_real, run_calc, water):
    """DFTB-2 energy and forces."""
    instance = run_calc(
        "deMonNano",
        water,
        "dftb-2",
        {"basis": demonnano_real},
        "single-point",
        handlers=("lowest-energy", "forces", "n-electrons"),
    )
    product = instance.res.product
    assert instance.res.complet
    assert product["lowest-energy"] == pytest.approx(SP_ENERGY, abs=1e-6)
    assert np.asarray(product["forces"]).shape == (3, 3)
    assert product["n-electrons"] == 8.0


def test_optimization(demonnano_real, run_calc, water):
    """Optimization (forces are optional): lower energy, new geometry."""
    instance = run_calc(
        "deMonNano",
        water,
        "dftb-2",
        {"basis": demonnano_real},
        "optimization-geometry",
        handlers=("lowest-energy", "final-geometry"),
    )
    product = instance.res.product
    assert product["lowest-energy"] < SP_ENERGY
    assert not np.allclose(product["final-geometry"].positions, water.positions)


@pytest.mark.xfail(
    strict=True,
    raises=KeyError,
    reason="known bug: deMonPy returns no TD-DFTB states for this output",
)
def test_td_dftb(demonnano_real, run_calc, water):
    """TD-DFTB: 4 singlet excitations."""
    instance = run_calc(
        "deMonNano",
        water,
        "dftb-2",
        {"basis": demonnano_real},
        "td-dftb",
        {"excitations": 4, "symmetry": "singlet"},
        handlers=("excited-states",),
    )
    assert len(instance.res.product["excited-states"]["singlet"]) == 4


def test_frequencies(demonnano_real, run_calc, water):
    """Frequencies: the 3 vibrations of water are positive."""
    instance = run_calc(
        "deMonNano",
        water,
        "dftb-2",
        {"basis": demonnano_real},
        "frequencies",
        handlers=("frequencies",),
    )
    frequencies = instance.res.product["frequencies"]
    assert frequencies.shape[1] == 2
    vibrations = np.sort(frequencies[:, 0])[-3:]
    assert np.all(vibrations > 1000.0)
