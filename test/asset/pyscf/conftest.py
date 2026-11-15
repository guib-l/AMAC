"""Fixtures of the PySCF tests."""

import pytest

from amac.asset import Software


@pytest.fixture
def pyscf_soft():
    """PySCF asset (in process, no executable)."""
    return Software.create("pyscf")


@pytest.fixture
def pyscf_real(real_config):
    """Real PySCF configuration; skips the test if PySCF is unavailable."""
    return real_config("pyscf")


@pytest.fixture
def needs_geometric():
    """Skip the test if geomeTRIC (optimizations of PySCF) is not installed."""
    pytest.importorskip("geometric", reason="geomeTRIC is needed by PySCF optimizations")
