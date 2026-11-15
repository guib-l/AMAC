"""Tests of the DFTB+ output readers on reference outputs.

Reference outputs: DFTB+ (version of the test machine), water from
``ase.build.molecule("H2O")``, DFTB-2 with the mio-1-1 parameters:

- ``data/sp``: single point (results.tag, detailed.out);
- ``data/opt``: geometry optimization (results.tag, geo_end.gen);
- ``data/md``: 4 VelocityVerlet steps of 0.5 fs at 300 K (md.out, geo_end.xyz);
- ``data/td``: TD-DFTB, 4 singlet excitations (EXC.DAT).
"""

import shutil

import numpy as np
import pytest

from amac.asset.dftbplus.parser import (
    read_detailed_out,
    read_exc_dat,
    read_md,
    read_results_tag,
    to_results,
)
from amac.utils.exception import OutputParseError
from asset.dftbplus.conftest import DATA, SP_ENERGY

# ----------------------------------------------------------------------
# results.tag
# ----------------------------------------------------------------------


def test_results_tag_scalars_and_arrays():
    """Scalars are numbers; arrays have the reversed Fortran shape."""
    tag = read_results_tag(DATA / "sp" / "results.tag")
    assert tag["mermin_energy"] == pytest.approx(SP_ENERGY, abs=1e-10)
    assert tag["forces"].shape == (3, 3)
    assert tag["eigenvalues"].shape == (1, 1, 6)
    assert tag["gross_atomic_charges"] == pytest.approx([-0.5875805, 0.29379025, 0.29379025])
    assert tag["number_of_electrons"] == pytest.approx([8.0])


def test_results_tag_missing(tmp_path):
    """A missing file is an OutputParseError."""
    with pytest.raises(OutputParseError, match=r"Missing DFTB\+ results file"):
        read_results_tag(tmp_path / "results.tag")


def test_results_tag_malformed(tmp_path):
    """A value before any header is an OutputParseError."""
    path = tmp_path / "results.tag"
    path.write_text("  1.0\nmermin_energy       :real:0:\n -4.0\n")
    with pytest.raises(OutputParseError, match="Unexpected line"):
        read_results_tag(path)


def test_results_tag_types(tmp_path):
    """Integer, logical and complex values are converted."""
    path = tmp_path / "results.tag"
    path.write_text("n :integer:0:\n 3\nok :logical:1:2\n T F\nz :complex:0:\n (1+2j)\n")
    tag = read_results_tag(path)
    assert tag["n"] == 3
    assert tag["ok"].tolist() == [True, False]
    assert tag["z"] == 1 + 2j


# ----------------------------------------------------------------------
# detailed.out
# ----------------------------------------------------------------------


def test_detailed_out():
    """Energy components are read in Hartree."""
    energies = read_detailed_out(DATA / "sp" / "detailed.out")
    assert energies == pytest.approx(
        {
            "band_energy": -3.6768166305,
            "h0_energy": -4.1679133533,
            "scc_energy": 0.0183906084,
            "electronic_energy": -4.1495227449,
            "repulsive_energy": 0.0718034081,
        }
    )


def test_detailed_out_missing(tmp_path):
    """A missing detailed.out gives no energy."""
    assert read_detailed_out(tmp_path / "detailed.out") == {}


# ----------------------------------------------------------------------
# EXC.DAT
# ----------------------------------------------------------------------


def test_exc_dat():
    """Excited states are grouped by spin symmetry."""
    states = read_exc_dat(DATA / "td" / "EXC.DAT")
    assert list(states) == ["singlet"]
    assert len(states["singlet"]) == 4
    assert states["singlet"]["state_1"] == {
        "w": 19.43,
        "oscillator": 0.14021058,
        "from": 3,
        "to": 5,
        "weight": 1.0,
        "energy": 19.112,
    }


def test_exc_dat_missing(tmp_path):
    """A missing file is an OutputParseError."""
    with pytest.raises(OutputParseError, match=r"Missing DFTB\+ excitations file"):
        read_exc_dat(tmp_path / "EXC.DAT")


@pytest.mark.parametrize(
    ("line", "message"),
    [("17.5 0.0 4 -> 5 1.0 17.5", "Malformed line"), ("17.5 0.0 4 -> 5 1.0 17.5 Q", "Unrecognized symmetry")],
)
def test_exc_dat_malformed(tmp_path, line, message):
    """A malformed line or an unknown symmetry is an OutputParseError."""
    path = tmp_path / "EXC.DAT"
    path.write_text(line + "\n")
    with pytest.raises(OutputParseError, match=message):
        read_exc_dat(path)


# ----------------------------------------------------------------------
# MD
# ----------------------------------------------------------------------


def test_read_md(water):
    """One frame per logged step, with time, epot and ekin."""
    frames = read_md(DATA / "md", water, time_step=0.5)
    assert len(frames) == 5
    assert [frame.info["time"] for frame in frames] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert frames[0].info["epot"] == pytest.approx(SP_ENERGY, abs=1e-9)
    assert frames[1].info["ekin"] == pytest.approx(0.0025587765)
    assert np.allclose(frames[0].positions, water.positions)


def test_read_md_missing(tmp_path, water):
    """A missing md.out is an OutputParseError."""
    with pytest.raises(OutputParseError, match=r"Missing DFTB\+ MD file"):
        read_md(tmp_path, water, 0.5)


def test_read_md_inconsistent(tmp_path, water):
    """Frames and logged steps must agree."""
    shutil.copy(DATA / "md" / "geo_end.xyz", tmp_path)
    (tmp_path / "md.out").write_text("MD step: 0\n")
    with pytest.raises(OutputParseError, match="frames but"):
        read_md(tmp_path, water, 0.5)


# ----------------------------------------------------------------------
# to_results
# ----------------------------------------------------------------------


def test_to_results_single_point(tmp_path, water):
    """Energies, forces and properties are arranged for the handlers."""
    shutil.copy(DATA / "sp" / "detailed.out", tmp_path)
    tag = read_results_tag(DATA / "sp" / "results.tag")
    results = to_results(tag, tmp_path, water)
    assert results["energy"]["energy"] == pytest.approx(SP_ENERGY)
    assert results["energy"]["repulsive_energy"] == pytest.approx(0.0718034081)
    assert results["forces"].shape == (3, 3)
    assert "forces" not in results["properties"]
    assert "mermin_energy" not in results["properties"]
    assert np.allclose(results["output_geometry"].positions, water.positions)


def test_to_results_final_geometry(tmp_path, water):
    """After an optimization, the final geometry comes from geo_end.gen."""
    shutil.copy(DATA / "opt" / "geo_end.gen", tmp_path)
    tag = read_results_tag(DATA / "opt" / "results.tag")
    results = to_results(tag, tmp_path, water)
    final = results["output_geometry"]
    assert final.get_chemical_symbols() == ["O", "H", "H"]
    assert not np.allclose(final.positions, water.positions)
