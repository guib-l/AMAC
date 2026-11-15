"""Fixtures of the DFTB+ tests."""

from pathlib import Path

import pytest

from amac.asset import Software

DATA = Path(__file__).with_name("data")
# Reference DFTB-2/mio-1-1 energy of ase.build.molecule("H2O") (Hartree).
SP_ENERGY = -4.0777193367704


@pytest.fixture
def dftbplus(offline_config):
    """DFTB+ asset with a fake executable (translation only, nothing is run)."""
    return Software.create("dftb+")


@pytest.fixture
def sk_basis(tmp_path) -> dict:
    """Canonical basis argument pointing to a Slater-Koster directory."""
    return {"directory": str(tmp_path / "sk")}


@pytest.fixture
def dftbplus_real(real_config) -> dict:
    """Real DFTB+ configuration; skips the test if DFTB+ is unavailable.

    Returns:
        The canonical basis argument (the "basis" directory of the
        configuration, e.g. mio-1-1).
    """
    section = real_config("dftb+")
    return {"directory": section["basis"]}
