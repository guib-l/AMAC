"""Shared pytest configuration: AMAC config file, software detection, fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from ase.build import molecule
from availability import Availability, check_all

import amac.config
from amac.instance import Instance

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config-amac.json"
# Wall time given to every real calculation (s).
REAL_TIMEOUT = 3600

_CONFIG_KEY = pytest.StashKey[dict]()
_PATH_KEY = pytest.StashKey[Path | None]()
_AVAILABILITY_KEY = pytest.StashKey[dict[str, Availability]]()


def pytest_addoption(parser):
    group = parser.getgroup("amac")
    group.addoption(
        "--amac-config",
        default=None,
        help="AMAC configuration file (default: config-amac.json at the repository root).",
    )
    group.addoption(
        "--amac-smoke",
        action="store_true",
        default=False,
        help="Also start each configured executable once to check that it runs.",
    )


def pytest_configure(config):
    """Read the AMAC configuration file once and detect the software."""
    option = config.getoption("--amac-config")
    if option is not None:
        path = Path(option).resolve()
        if not path.is_file():
            raise pytest.UsageError(f"--amac-config: file not found: {path}")
    else:
        path = DEFAULT_CONFIG if DEFAULT_CONFIG.is_file() else None
    data = json.loads(path.read_text()) if path is not None else {}
    config.stash[_PATH_KEY] = path
    config.stash[_CONFIG_KEY] = data
    config.stash[_AVAILABILITY_KEY] = check_all(data, smoke=config.getoption("--amac-smoke"))


def pytest_report_header(config):
    path = config.stash[_PATH_KEY]
    lines = [f"AMAC config: {path if path is not None else '(none, empty configuration)'}"]
    for name, status in config.stash[_AVAILABILITY_KEY].items():
        state = "available" if status.available else f"unavailable ({status.reason})"
        lines.append(f"  {name:10s}: {state}")
    return lines


@pytest.fixture(scope="session")
def amac_config(pytestconfig) -> dict:
    """AMAC configuration read from the configuration file (do not modify)."""
    return pytestconfig.stash[_CONFIG_KEY]


@pytest.fixture(scope="session")
def software_availability(pytestconfig) -> dict[str, Availability]:
    """Availability of each software, by ``Software.name``."""
    return pytestconfig.stash[_AVAILABILITY_KEY]


@pytest.fixture(autouse=True)
def empty_amac_config(monkeypatch):
    """Start every test from an empty, private AMAC configuration."""
    monkeypatch.setattr(amac.config, "CONFIGURE", {})


@pytest.fixture
def real_config(amac_config, software_availability, monkeypatch):
    """Return a function enabling the real configuration of one software.

    The function skips the test if the software is unavailable, installs a
    copy of the configuration file with a timeout of ``REAL_TIMEOUT``
    seconds for this software, and returns its section.
    """

    def enable(name: str) -> dict:
        status = software_availability[name]
        if not status.available:
            pytest.skip(f"{name}: {status.reason}")
        config = copy.deepcopy(amac_config)
        section = config.setdefault("software", {}).setdefault(name, {})
        section["timeout"] = REAL_TIMEOUT
        monkeypatch.setattr(amac.config, "CONFIGURE", config)
        return section

    return enable


@pytest.fixture
def fake_executable(tmp_path) -> Path:
    """Absolute path of a shell script that does nothing and exits with 0."""
    path = tmp_path / "bin" / "fake-program"
    path.parent.mkdir()
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def water():
    """Water molecule (ASE geometry, Angstrom)."""
    return molecule("H2O")


@pytest.fixture
def make_instance(tmp_path, water):
    """Return a function building an Instance of a software (water by default)."""

    def build(soft, **props):
        props.setdefault("image", water)
        return Instance.factory_instance(software=soft, workdir=tmp_path / "run", **props)

    return build
