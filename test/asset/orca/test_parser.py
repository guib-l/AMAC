"""Tests of the ORCA output readers.

The error cases use small synthetic files and are complete. The tests on
real ORCA outputs are skeletons: they need the reference outputs of
``data/`` (see ``data/README.md``), written once ORCA is installed.
"""

import pytest

from amac.asset.orca.parser import _excited_states, read_md_trajectory, read_output
from amac.utils.exception import OutputParseError

# ----------------------------------------------------------------------
# Error cases (synthetic files, complete)
# ----------------------------------------------------------------------


def test_read_output_missing(tmp_path, water):
    """A missing output is an OutputParseError."""
    with pytest.raises(OutputParseError, match="Missing ORCA output file"):
        read_output(tmp_path / "output-orca.out", water)


def test_read_output_not_terminated(tmp_path, water):
    """An output without ORCA TERMINATED NORMALLY is refused."""
    path = tmp_path / "output-orca.out"
    path.write_text("FINAL SINGLE POINT ENERGY      -74.962928\n")
    with pytest.raises(OutputParseError, match="did not terminate normally"):
        read_output(path, water)


def test_read_output_no_energy(tmp_path, water):
    """An output without final energy is refused."""
    path = tmp_path / "output-orca.out"
    path.write_text("****ORCA TERMINATED NORMALLY****\n")
    with pytest.raises(OutputParseError, match="No final energy"):
        read_output(path, water)


def test_read_output_minimal(tmp_path, water):
    """The last final energy is kept; missing blocks give None."""
    path = tmp_path / "output-orca.out"
    path.write_text(
        "FINAL SINGLE POINT ENERGY      -74.900000\n"
        "FINAL SINGLE POINT ENERGY      -74.962928\n"
        "****ORCA TERMINATED NORMALLY****\n"
    )
    results = read_output(path, water)
    assert results["energy"] == {"energy": -74.962928}
    for key in ("forces", "charges", "dipole", "frequencies", "excited-states"):
        assert results[key] is None


def test_excited_states_synthetic():
    """States from STATE lines; oscillator strengths from the spectrum rows."""
    text = (
        "TD-DFT/TDA EXCITED STATES (SINGLETS)\n"
        "STATE  1:  E=   0.300000 au      8.163 eV    65842.6 cm**-1\n"
        "STATE  2:  E=   0.400000 au     10.884 eV    87790.1 cm**-1\n"
        "  0-1A  ->  2-1A    10.884   87790.1   113.9   0.123456789   0.1\n"
    )
    assert _excited_states(text) == {
        "singlet": {
            "state_0": {"w": 8.163, "oscillator": 0.0},
            "state_1": {"w": 10.884, "oscillator": 0.123456789},
        }
    }


def test_excited_states_none():
    """No excited state section gives None."""
    assert _excited_states("nothing here") is None


def test_read_md_trajectory_missing(tmp_path, water):
    """A missing trajectory is an OutputParseError."""
    with pytest.raises(OutputParseError, match="Missing ORCA MD trajectory"):
        read_md_trajectory(tmp_path / "md-trajectory.xyz", water, 0.5)


def test_read_md_trajectory_synthetic(tmp_path, water):
    """Frames with time, and epot/ekin from the comment line when present."""
    frame = "\n".join(f"{s} {x:.6f} {y:.6f} {z:.6f}" for s, (x, y, z) in zip("OHH", water.positions))
    path = tmp_path / "md-trajectory.xyz"
    path.write_text(f"3\nE_Pot= -74.96 E_Kin= 0.002\n{frame}\n3\nstep 1\n{frame}\n")
    frames = read_md_trajectory(path, water, 0.5)
    assert [atoms.info["time"] for atoms in frames] == [0.0, 0.5]
    assert frames[0].info["epot"] == -74.96
    assert frames[0].info["ekin"] == 0.002
    assert frames[1].info["epot"] is None


# ----------------------------------------------------------------------
# Real ORCA outputs (skeletons)
# ----------------------------------------------------------------------


def test_read_output_single_point():
    """data/sp.out (HF/STO-3G water, EnGrad): energy, forces (3, 3), Mulliken
    charges summing to 0, dipole (3 values), final geometry = input geometry."""
    pytest.skip("TODO: needs ORCA reference output data/sp.out")


def test_read_output_optimization():
    """data/opt.out: final energy below the single point; final geometry read
    from the last CARTESIAN COORDINATES (ANGSTROEM) block."""
    pytest.skip("TODO: needs ORCA reference output data/opt.out")


def test_read_output_frequencies():
    """data/freq.out: IR SPECTRUM rows, shape (3, 2) for water, frequencies
    (cm^-1) and intensities (km/mol) positive."""
    pytest.skip("TODO: needs ORCA reference output data/freq.out")


def test_read_output_excited_states():
    """data/td.out (3 roots, singlets): 3 states with w (eV) increasing and
    oscillator strengths from the absorption spectrum."""
    pytest.skip("TODO: needs ORCA reference output data/td.out")


def test_read_md_trajectory_real():
    """data/md-trajectory.xyz (5 steps of 0.5 fs): number of frames, time,
    epot/ekin read from the ORCA comment line."""
    pytest.skip("TODO: needs ORCA reference output data/md-trajectory.xyz")
