"""Real DFTB+ calculations on water (skipped if DFTB+ is unavailable).

Reference values: DFTB+ of the test machine with the mio-1-1 parameters
(the "basis" directory of the configuration).
"""

import numpy as np
import pytest

from asset.dftbplus.conftest import SP_ENERGY

pytestmark = pytest.mark.real

# Reference GFN2-xTB energy of water with DFTB+ (Hartree).
XTB_ENERGY = -5.0702223553373


def test_single_point(dftbplus_real, run_calc, water):
    """DFTB-2 energy, forces, charges and number of electrons."""
    instance = run_calc(
        "dftb+",
        water,
        "dftb-2",
        {"basis": dftbplus_real},
        "single-point",
        handlers=("lowest-energy", "forces", "charges", "n-electrons"),
    )
    product = instance.res.product
    assert instance.res.complet
    assert product["lowest-energy"] == pytest.approx(SP_ENERGY, abs=1e-6)
    assert product["forces"].shape == (3, 3)
    assert sum(product["charges"]) == pytest.approx(0.0, abs=1e-6)
    assert product["n-electrons"] == 8.0
    assert "calculate" in instance.duree.steps


def test_optimization(dftbplus_real, run_calc, water):
    """The optimized geometry has a lower energy and small forces."""
    instance = run_calc(
        "dftb+",
        water,
        "dftb-2",
        {"basis": dftbplus_real},
        "optimization-geometry",
        handlers=("lowest-energy", "forces", "final-geometry"),
    )
    product = instance.res.product
    assert product["lowest-energy"] < SP_ENERGY
    assert np.abs(product["forces"]).max() < 1e-3
    assert not np.allclose(product["final-geometry"].positions, water.positions)


def test_td_dftb(dftbplus_real, run_calc, water):
    """TD-DFTB: 4 singlet excitations in increasing energy."""
    instance = run_calc(
        "dftb+",
        water,
        "dftb-2",
        {"basis": dftbplus_real},
        "td-dftb",
        {"excitations": 4, "symmetry": "singlet", "diagonalizer": "arpack"},
        handlers=("excited-states", "lowest-energy"),
    )
    singlets = instance.res.product["excited-states"]["singlet"]
    assert len(singlets) == 4
    energies = [state["w"] for state in singlets.values()]
    assert energies == sorted(energies)
    assert energies[0] > 0.0


def test_molecular_dynamics(dftbplus_real, run_calc, water):
    """NVE run of 4 steps: 5 frames, constant total energy."""
    instance = run_calc(
        "dftb+",
        water,
        "dftb-2",
        {"basis": dftbplus_real},
        "md",
        {"steps": 4, "time-step": 0.5, "temperature": 300.0},
        handlers=("trajectory",),
    )
    frames = instance.res.product["trajectory"]
    assert len(frames) == 5
    assert [frame.info["time"] for frame in frames] == [0.0, 0.5, 1.0, 1.5, 2.0]
    totals = [frame.info["epot"] + frame.info["ekin"] for frame in frames]
    assert max(totals) - min(totals) < 1e-4


def test_xtb(dftbplus_real, run_calc, water):
    """GFN2-xTB energy through DFTB+."""
    instance = run_calc("dftb+", water, "xtb", {}, "sp", handlers=("lowest-energy",))
    assert instance.res.product["lowest-energy"] == pytest.approx(XTB_ENERGY, abs=1e-5)


def test_solvation(dftbplus_real, run_calc, water):
    """C-PCM (ddCOSMO) in water lowers the energy of water."""
    instance = run_calc(
        "dftb+",
        water,
        "dftb-2",
        {"basis": dftbplus_real},
        "sp",
        handlers=("lowest-energy",),
        options={"solvation": {"model": "cpcm", "solvent": "water"}},
    )
    assert instance.res.product["lowest-energy"] < SP_ENERGY
