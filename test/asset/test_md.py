"""Tests of amac.asset.md: canonical MD settings."""

import pytest

from amac.asset.md import DEFAULT_TIME_CONSTANT, md_settings


def test_nve():
    """Without thermostat: NVE, no temperature."""
    settings = md_settings({"steps": 10, "dt": 0.5})
    assert settings.steps == 10
    assert settings.time_step == 0.5
    assert settings.temperature is None
    assert settings.thermostat == "none"
    assert settings.time_constant == DEFAULT_TIME_CONSTANT


def test_berendsen():
    """The Berendsen thermostat keeps its time constant."""
    md = {"steps": 5, "dt": 1.0, "temperature": 300.0, "thermostat": {"berendsen": {"time_constant": 50.0}}}
    settings = md_settings(md)
    assert settings.thermostat == "berendsen"
    assert settings.temperature == 300.0
    assert settings.time_constant == 50.0


def test_berendsen_default_time_constant():
    """Without time constant, the default one is used."""
    md = {"steps": 5, "dt": 1.0, "temperature": 300.0, "thermostat": {"berendsen": {}}}
    assert md_settings(md).time_constant == DEFAULT_TIME_CONSTANT


def test_berendsen_needs_temperature():
    """Berendsen without temperature is refused."""
    with pytest.raises(ValueError, match="needs a temperature"):
        md_settings({"steps": 5, "dt": 1.0, "thermostat": {"berendsen": {}}})
