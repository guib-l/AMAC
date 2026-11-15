"""Fixtures of the deMonNano tests."""

import pytest

from amac.asset import Software


@pytest.fixture
def demonnano(offline_config):
    """deMonNano asset with a fake executable (translation only, nothing is run)."""
    return Software.create("deMonNano")


@pytest.fixture
def bio_basis(tmp_path) -> dict:
    """Canonical basis argument of the BIO parameter set."""
    return {"directory": str(tmp_path / "sk"), "ptype": "BIO"}


@pytest.fixture
def demonnano_real(real_config) -> dict:
    """Real deMonNano configuration; skips the test if deMonNano is unavailable.

    Returns:
        The canonical basis argument (BIO parameters of the "basis"
        directory of the configuration).
    """
    section = real_config("deMonNano")
    return {"directory": section["basis"], "ptype": "BIO"}
