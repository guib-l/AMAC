"""Tests of the AMAC installation check (roadmap Phase 1)."""

import pytest

from amac.verify import check
from amac.verify.__main__ import main


def test_empty_config_is_ready():
    report = check({"software": {}})
    assert not report.failed
    assert [item.name for item in report.checks] == [
        "python",
        "numpy",
        "ase",
        "pip",
        "amac",
        "h5py",
    ]


def test_missing_software_section():
    report = check({})
    assert report.failed
    assert report.checks[-1].name == "config"


def test_unknown_software():
    report = check({"software": {"nope": {}}})
    assert report.failed
    assert report.checks[-1].scope == "nope"


@pytest.mark.parametrize("name", ["dftb+", "DFTB+", "molcas", "OpenMolcas"])
def test_alias_is_accepted(name):
    assert not check({"software": {name: {}}}).failed


def test_alias_is_resolved_for_module_software():
    report = check({"software": {"PySCF": {}}})
    assert not any(item.name == "software" for item in report.checks)


def test_section_must_be_object():
    report = check({"software": {"pyscf": []}})
    assert report.failed
    assert "JSON object" in report.checks[-1].message


def test_duplicate_section_is_only_a_warning():
    report = check({"software": {"dftb+": {}, "DFTB+": {}}})
    assert not report.failed
    assert report.checks[-1].status == "warn"


def test_cli_exit_code(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"software": {}}')
    assert main([str(path)]) == 0
    path.write_text('{"software": {"nope": {}}}')
    assert main([str(path)]) == 1


def test_unconfigured_software_is_only_a_warning():
    report = check({"software": {"orca": {}}})
    assert not report.failed
    assert report.checks[-1].name == "executable"
    assert report.checks[-1].status == "warn"


def test_executable_is_ready(fake_executable):
    report = check({"software": {"dftb+": {"executable": str(fake_executable)}}})
    assert not report.failed
    assert report.checks[-1].status == "ok"


def test_executable_must_exist(tmp_path):
    report = check({"software": {"dftb+": {"executable": str(tmp_path / "nope")}}})
    assert report.failed
    assert "not found" in report.checks[-1].message


def test_executable_must_be_absolute():
    report = check({"software": {"dftb+": {"executable": "dftb+"}}})
    assert report.failed
    assert "must be absolute" in report.checks[-1].message


def test_executable_must_be_executable(tmp_path):
    path = tmp_path / "not-executable"
    path.write_text("#!/bin/sh\nexit 0\n")
    report = check({"software": {"dftb+": {"executable": str(path)}}})
    assert report.failed
    assert "not executable" in report.checks[-1].message


def test_env_values_must_be_strings():
    report = check({"software": {"dftb+": {"env": {"OMP_NUM_THREADS": 4}}}})
    assert not report.failed
    assert report.checks[-1].status == "warn"
    assert "not a string" in report.checks[-1].message


def test_env_is_ok_with_strings():
    report = check({"software": {"dftb+": {"env": {"A": "b"}}}})
    assert report.checks[-1].name == "env"
    assert report.checks[-1].status == "ok"
