"""Fixtures of the ORCA tests.

ORCA is not installed on the development machine yet: the real tests and
the tests needing an ORCA output are skeletons (see
documentation/plan-tests.md, section 5).
"""

import pytest

from amac.asset import Software


@pytest.fixture
def orca(offline_config):
    """ORCA asset with a fake executable (translation only, nothing is run)."""
    return Software.create("orca")


@pytest.fixture
def orca_real(real_config) -> dict:
    """Real ORCA configuration; skips the test if ORCA is unavailable."""
    return real_config("orca")
