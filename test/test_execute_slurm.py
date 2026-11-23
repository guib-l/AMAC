"""Tests of the execution backends (roadmap Phase 4)."""

from __future__ import annotations

import subprocess

import pytest

import amac.config
from amac.asset import Software
from amac.engine.execute import Execute, ExecuteIO, ExecuteLIB, ExecuteSlurm, format_wall_time
from amac.engine.profile import ExecProcess, Program
from amac.utils.exception import ExecuteFailed

HPC = {"scheduler": "slurm", "sbatch": None, "defaults": {"partition": "std", "time": "02:00:00"}}


def fake_script(tmp_path, name, body):
    """Write an absolute executable shell script and return its path."""
    path = tmp_path / "bin" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


def test_select_profile_without_hpc_is_local():
    assert isinstance(Execute.select_profile(None), ExecuteIO)


def test_select_profile_for_library_software():
    assert isinstance(Execute.select_profile(None, library=True), ExecuteLIB)


def test_select_profile_with_slurm(tmp_path):
    sbatch = fake_script(tmp_path, "sbatch", "exit 0")
    backend = Execute.select_profile({**HPC, "sbatch": str(sbatch)})
    assert isinstance(backend, ExecuteSlurm)
    assert backend.schedules


def test_unknown_scheduler_is_rejected():
    with pytest.raises(ValueError, match="unknown scheduler"):
        Execute.select_profile({"scheduler": "pbs"})


def test_relative_sbatch_is_rejected():
    with pytest.raises(ValueError, match="must be absolute"):
        Execute.select_profile({**HPC, "sbatch": "sbatch"})


def test_missing_sbatch_is_rejected():
    with pytest.raises(ValueError, match="no sbatch configured"):
        Execute.select_profile({"scheduler": "slurm"})


def test_format_wall_time():
    assert format_wall_time(7200) == "02:00:00"
    assert format_wall_time(5400.7) == "01:30:00"


def test_job_script_content(tmp_path):
    program = fake_script(tmp_path, "program", "exit 0")
    backend = ExecuteSlurm(
        {
            **HPC,
            "sbatch": str(fake_script(tmp_path, "sbatch", "exit 0")),
            "prologue": ["module load x"],
        },
        process="mpi",
        process_unit=4,
    )
    process = ExecProcess(
        program,
        workdir=tmp_path / "run",
        args=("--flag",),
        launcher=("/usr/bin/mpirun", "-np", "4"),
        env={"OMP_NUM_THREADS": "1"},
        output="out.log",
    )
    lines = backend.job_script(process).splitlines()
    assert lines[0] == "#!/bin/bash"
    assert "#SBATCH --job-name=amac-" in lines[1]
    assert "#SBATCH --partition=std" in lines
    assert "#SBATCH --time=02:00:00" in lines
    assert "#SBATCH --ntasks=4" in lines
    assert not any("--cpus-per-task" in line for line in lines)
    assert lines.index("module load x") > max(
        i for i, line in enumerate(lines) if line.startswith("#SBATCH")
    )
    assert f"cd {(tmp_path / 'run').resolve()}" in lines
    assert "export OMP_NUM_THREADS=1" in lines
    assert lines[-1] == "/usr/bin/mpirun -np 4 " + str(program) + " --flag"
    assert str((tmp_path / "run" / "out.log").resolve()) in backend.job_script(process)


def test_job_script_omits_unknown_directives_and_uses_cpus(tmp_path):
    backend = ExecuteSlurm(
        {"scheduler": "slurm", "sbatch": str(fake_script(tmp_path, "sbatch", "exit 0"))},
        process="inprocess",
        process_unit=4,
    )
    process = ExecProcess(fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path)
    lines = backend.job_script(process).splitlines()
    assert "#SBATCH --partition=std" not in lines
    assert "#SBATCH --time=02:00:00" not in lines
    assert "#SBATCH --ntasks=1" in lines
    assert "#SBATCH --cpus-per-task=4" in lines


def test_time_derived_from_timeout(tmp_path):
    backend = ExecuteSlurm(
        {"scheduler": "slurm", "sbatch": str(fake_script(tmp_path, "sbatch", "exit 0"))},
        timeout=3600,
    )
    assert backend.time == "01:00:00"


def test_slurm_success_runs_the_job(tmp_path):
    sbatch = fake_script(tmp_path, "sbatch", "echo ok > out.log\nexit 0")
    backend = ExecuteSlurm({**HPC, "sbatch": str(sbatch)})
    process = ExecProcess(
        fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path, output="out.log"
    )
    assert backend.run(process).returncode == 0
    assert (tmp_path / "job.sh").is_file()


def test_slurm_job_failure_is_reported(tmp_path):
    sbatch = fake_script(tmp_path, "sbatch", "echo boom > out.log\nexit 3")
    backend = ExecuteSlurm({**HPC, "sbatch": str(sbatch)})
    process = ExecProcess(
        fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path, output="out.log"
    )
    with pytest.raises(ExecuteFailed, match="return code 3"):
        backend.run(process)


def test_slurm_submission_failure_is_reported(tmp_path):
    sbatch = fake_script(tmp_path, "sbatch", 'echo "sbatch: error: invalid partition" >&2\nexit 1')
    backend = ExecuteSlurm({**HPC, "sbatch": str(sbatch)})
    process = ExecProcess(
        fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path, output="out.log"
    )
    with pytest.raises(ExecuteFailed, match="sbatch failed"):
        backend.run(process)


def test_library_backend_refuses_to_launch(tmp_path):
    process = ExecProcess(fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path)
    with pytest.raises(ExecuteFailed, match="Python library"):
        ExecuteLIB().run(process)


def test_local_backend_still_runs(tmp_path):
    program = fake_script(tmp_path, "program", 'echo "hi" > out.log\nexit 0')
    process = ExecProcess(program, workdir=tmp_path, output="out.log")
    assert process.execute().returncode == 0
    assert (tmp_path / "out.log").read_text() == "hi\n"


def test_process_unit_comes_from_slurm_defaults(tmp_path, monkeypatch):
    sbatch = fake_script(tmp_path, "sbatch", "exit 0")
    monkeypatch.setattr(
        amac.config,
        "CONFIGURE",
        {"hpc": {"scheduler": "slurm", "sbatch": str(sbatch), "defaults": {"ntasks": 4}}},
    )
    soft = Software.create("dftb+", executable="/bin/true")
    assert soft.program.process_unit == 4
    explicit = Software.create("dftb+", executable="/bin/true", process_unit=2)
    assert explicit.program.process_unit == 2


def test_process_unit_stays_one_without_scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(
        amac.config,
        "CONFIGURE",
        {"hpc": {"defaults": {"ntasks": 4}}},
    )
    soft = Software.create("dftb+", executable="/bin/true")
    assert soft.program.process_unit == 1


def test_library_software_is_refused_under_slurm(tmp_path, monkeypatch):
    sbatch = fake_script(tmp_path, "sbatch", "exit 0")
    monkeypatch.setattr(
        amac.config,
        "CONFIGURE",
        {"hpc": {"scheduler": "slurm", "sbatch": str(sbatch)}},
    )
    with pytest.raises(ValueError, match="Python library"):
        Software.create("pyscf")


def test_slurm_submits_with_wait(tmp_path):
    sbatch = fake_script(
        tmp_path, "sbatch", 'printf "%s\\n" "$@" > args.txt\necho ok > out.log\nexit 0'
    )
    backend = ExecuteSlurm({**HPC, "sbatch": str(sbatch)})
    process = ExecProcess(
        fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path, output="out.log"
    )
    backend.run(process)
    assert (tmp_path / "args.txt").read_text().splitlines() == ["--wait", str(tmp_path / "job.sh")]


def test_job_script_resolves_a_relative_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = ExecuteSlurm({**HPC, "sbatch": str(fake_script(tmp_path, "sbatch", 'sh "$2"'))})
    (tmp_path / "run").mkdir()
    process = ExecProcess(
        fake_script(tmp_path, "program", "echo ok > out.log"), workdir="run", output="out.log"
    )
    lines = backend.job_script(process).splitlines()
    assert f"#SBATCH --output={(tmp_path / 'run' / 'out.log').resolve()}" in lines
    assert f"#SBATCH --error={(tmp_path / 'run' / 'out.err').resolve()}" in lines
    assert f"cd {(tmp_path / 'run').resolve()}" in lines
    assert backend.run(process).returncode == 0
    assert (tmp_path / "run" / "out.log").read_text() == "ok\n"


def test_stale_output_does_not_hide_a_submission_failure(tmp_path):
    backend = ExecuteSlurm({**HPC, "sbatch": str(fake_script(tmp_path, "sbatch", "exit 1"))})
    process = ExecProcess(
        fake_script(tmp_path, "program", "exit 0"), workdir=tmp_path, output="out.log"
    )
    (tmp_path / "out.log").write_text("stale\n")
    with pytest.raises(ExecuteFailed, match="sbatch failed"):
        backend.run(process)


def test_local_timeout_is_dropped_when_scheduled(tmp_path, monkeypatch):
    sbatch = fake_script(tmp_path, "sbatch", "exit 0")
    program = Program(
        name="demo",
        executable="/bin/true",
        timeout=5,
        hpc={"scheduler": "slurm", "sbatch": str(sbatch)},
    )
    seen = {}

    def fake_run(self, process):
        seen["timeout"] = process.timeout
        return subprocess.CompletedProcess(process.command, 0)

    monkeypatch.setattr(ExecuteSlurm, "run", fake_run)
    program.execute(tmp_path)
    assert seen["timeout"] is None


def test_non_list_prologue_is_rejected(tmp_path):
    sbatch = fake_script(tmp_path, "sbatch", "exit 0")
    with pytest.raises(ValueError, match="prologue"):
        Execute.select_profile(
            {"scheduler": "slurm", "sbatch": str(sbatch), "prologue": "module load x"}
        )
