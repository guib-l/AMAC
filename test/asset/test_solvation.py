"""Tests of amac.asset.solvation: canonical solvation settings."""

import pytest

from amac.asset.solvation import solvation_settings


def test_solvent():
    """A named solvent."""
    settings = solvation_settings({"model": "smd", "solvent": "water"})
    assert (settings.model, settings.solvent, settings.epsilon) == ("smd", "water", None)


def test_epsilon_with_cpcm():
    """A dielectric constant with C-PCM."""
    settings = solvation_settings({"model": "cpcm", "epsilon": 78.4})
    assert (settings.solvent, settings.epsilon) == (None, 78.4)


@pytest.mark.parametrize("node", [{"model": "cpcm"}, {"model": "cpcm", "solvent": "water", "epsilon": 1.0}])
def test_solvent_xor_epsilon(node):
    """Exactly one of solvent and epsilon is required."""
    with pytest.raises(ValueError, match="either a solvent or an epsilon"):
        solvation_settings(node)


def test_epsilon_only_with_cpcm():
    """A dielectric constant is refused with another model."""
    with pytest.raises(ValueError, match="only allowed with cpcm"):
        solvation_settings({"model": "smd", "epsilon": 78.4})
