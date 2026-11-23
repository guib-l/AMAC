"""Tests of the `hpc` checks of the installation check."""

from __future__ import annotations

from amac.verify import check


def test_no_hpc_section_adds_no_line():
    report = check({"software": {}})
    assert not any(item.name in ("hpc", "sbatch", "squeue") for item in report.checks)


def test_hpc_must_be_an_object():
    report = check({"software": {}, "hpc": []})
    assert report.failed
    assert report.checks[-1].name == "hpc"


def test_unknown_scheduler_fails():
    report = check({"software": {}, "hpc": {"scheduler": "pbs"}})
    assert report.failed
    assert report.checks[-1].name == "hpc"


def test_missing_sbatch_fails():
    report = check({"software": {}, "hpc": {"scheduler": "slurm"}})
    assert report.failed
    assert report.checks[-1].name == "sbatch"


def test_relative_sbatch_fails():
    report = check({"software": {}, "hpc": {"scheduler": "slurm", "sbatch": "sbatch"}})
    assert report.failed
    assert report.checks[-1].name == "sbatch"


def test_missing_squeue_is_only_a_warning(tmp_path):
    sbatch = tmp_path / "sbatch"
    sbatch.write_text("#!/bin/sh\nexit 0\n")
    sbatch.chmod(0o755)
    report = check({"software": {}, "hpc": {"scheduler": "slurm", "sbatch": str(sbatch)}})
    assert not report.failed
    assert report.checks[-1].name == "squeue"
    assert report.checks[-1].status == "warn"


def test_valid_scheduler_is_ready(tmp_path):
    paths = {}
    for name in ("sbatch", "squeue"):
        path = tmp_path / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
        paths[name] = str(path)
    report = check({"software": {}, "hpc": {"scheduler": "slurm", **paths}})
    assert not report.failed
    assert [item.status for item in report.checks[-2:]] == ["ok", "ok"]


def test_non_string_squeue_fails_cleanly(tmp_path):
    sbatch = tmp_path / "sbatch"
    sbatch.write_text("#!/bin/sh\nexit 0\n")
    sbatch.chmod(0o755)
    report = check(
        {"software": {}, "hpc": {"scheduler": "slurm", "sbatch": str(sbatch), "squeue": 3}}
    )
    assert report.failed
    assert report.checks[-1].name == "squeue"
