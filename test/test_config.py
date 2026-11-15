"""Tests of amac.config: process-wide configuration."""

import json

import pytest

import amac
import amac.config


def test_configuration_is_empty_by_default():
    """Without configuration, CONFIGURE is an empty dict."""
    assert amac.config.CONFIGURE == {}


def test_configure_sets_the_dict():
    """configure(config=...) replaces the configuration."""
    config = {"software": {"orca": {"executable": "/opt/orca/orca"}}}
    amac.configure(config=config)
    assert amac.config.CONFIGURE == config


def test_configure_none_keeps_the_configuration():
    """configure() without argument does not change the configuration."""
    amac.configure(config={"software": {}})
    amac.configure()
    assert amac.config.CONFIGURE == {"software": {}}


def test_configure_from_file(tmp_path):
    """The JSON file is loaded as the configuration."""
    config = {"software": {"dftb+": {"executable": "/usr/local/bin/dftb+", "env": {}}}}
    path = tmp_path / "config-amac.json"
    path.write_text(json.dumps(config))
    amac.configure_from_file(path)
    assert amac.config.CONFIGURE == config


def test_configure_from_missing_file(tmp_path):
    """A missing file is an error and leaves the configuration unchanged."""
    with pytest.raises(FileExistsError, match="didn't exists"):
        amac.configure_from_file(tmp_path / "missing.json")
    assert amac.config.CONFIGURE == {}
