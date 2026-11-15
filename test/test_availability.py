"""Tests of the software detection used by the real tests."""

import pytest
from availability import (
    REQUIREMENTS,
    Requirement,
    check_all,
    check_software,
    config_section,
    executable_problem,
    smoke_problem,
)


def test_config_section_by_alias():
    """A section written under an alias is found."""
    config = {"software": {"dftbplus": {"executable": "/x"}}}
    assert config_section(config, "dftb+", ("dftbplus",)) == {"executable": "/x"}


def test_config_section_missing():
    """No section gives None, even without a "software" key."""
    assert config_section({}, "orca", ("ORCA",)) is None


@pytest.mark.parametrize("value", [None, ""])
def test_executable_problem_not_configured(value):
    """An empty or missing executable is reported."""
    assert executable_problem(value) == "executable not configured"


def test_executable_problem_relative():
    """A relative path or a bare name is refused (never searched in PATH)."""
    assert "absolute" in executable_problem("dftb+")
    assert "absolute" in executable_problem("bin/dftb+")


def test_executable_problem_missing(tmp_path):
    """A missing file is reported."""
    assert "not found" in executable_problem(tmp_path / "nothing")


def test_executable_problem_not_executable(tmp_path):
    """A file without execution permission is reported."""
    path = tmp_path / "program"
    path.write_text("")
    path.chmod(0o644)
    assert "not executable" in executable_problem(path)


def test_executable_problem_ok(fake_executable):
    """An absolute executable file has no problem."""
    assert executable_problem(fake_executable) == ""


def test_smoke_problem_ok(fake_executable):
    """A program that starts passes the smoke check."""
    assert smoke_problem(fake_executable) == ""


def test_smoke_problem_cannot_start(tmp_path):
    """An executable file that the system cannot start is reported."""
    path = tmp_path / "broken"
    path.write_text("not a program\n")
    path.chmod(0o755)
    assert "cannot start" in smoke_problem(path)


def test_smoke_problem_hangs(tmp_path):
    """A program that does not end within the timeout is reported."""
    path = tmp_path / "slow"
    path.write_text("#!/bin/sh\nsleep 5\n")
    path.chmod(0o755)
    assert "did not answer" in smoke_problem(path, timeout=0.2)


def test_check_software_available(tmp_path, fake_executable):
    """Executable and basis present: the software is available."""
    config = {"software": {"dftb+": {"executable": str(fake_executable), "basis": str(tmp_path)}}}
    status = check_software("dftb+", config)
    assert status.available
    assert status.reason == ""


def test_check_software_no_section():
    """A software without configuration section is unavailable."""
    status = check_software("orca", {})
    assert not status.available
    assert status.reason == "no section in the configuration"


def test_check_software_empty_executable():
    """An empty executable (as ORCA in config-amac.json) is unavailable."""
    status = check_software("orca", {"software": {"orca": {"executable": ""}}})
    assert not status.available
    assert status.reason == "executable not configured"


def test_check_software_missing_basis(fake_executable, tmp_path):
    """A missing basis directory makes the software unavailable."""
    config = {
        "software": {
            "dftb+": {"executable": str(fake_executable), "basis": str(tmp_path / "none")}
        }
    }
    status = check_software("dftb+", config)
    assert not status.available
    assert "basis directory" in status.reason


def test_check_software_missing_module():
    """A Python module that cannot be imported makes the software unavailable."""
    requirement = Requirement(modules=("amac_module_that_does_not_exist",))
    status = check_software("pyscf", {}, requirement)
    assert not status.available
    assert "amac_module_that_does_not_exist" in status.reason


def test_check_software_module_only():
    """A Python-only software needs no configuration section."""
    status = check_software("fake", {}, Requirement(modules=("json",)))
    assert status.available


def test_check_software_smoke(tmp_path):
    """The smoke check is run only when asked."""
    path = tmp_path / "broken"
    path.write_text("not a program\n")
    path.chmod(0o755)
    config = {"software": {"orca": {"executable": str(path)}}}
    assert check_software("orca", config).available
    assert not check_software("orca", config, smoke=True).available


def test_check_all_names():
    """Every asset of AMAC is checked."""
    assert set(check_all({})) == set(REQUIREMENTS) == {"deMonNano", "dftb+", "orca", "pyscf"}


@pytest.mark.parametrize("name", sorted(REQUIREMENTS))
def test_requirements_match_assets(name):
    """Names, aliases and executable need match the AMAC asset classes."""
    from amac.asset import Software

    soft_cls = Software._registry[name.upper()]
    assert soft_cls.name == name
    assert REQUIREMENTS[name].aliases == soft_cls.alias
    assert REQUIREMENTS[name].executable == soft_cls.requires_executable
