"""Tests of amac.engine.profile: executable checks and program execution."""

from pathlib import Path

import pytest

from amac.engine.profile import ExecProcess, Program, checked_executable
from amac.utils.exception import ExecuteFailed


def script(directory: Path, name: str, body: str) -> Path:
    """Write an executable shell script and return its absolute path."""
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


# ----------------------------------------------------------------------
# checked_executable
# ----------------------------------------------------------------------


def test_checked_executable_absolute(fake_executable):
    """An absolute path is returned as a Path."""
    assert checked_executable("soft", str(fake_executable), True) == fake_executable


def test_checked_executable_none_not_required():
    """No executable is accepted when none is required."""
    assert checked_executable("soft", None, False) is None


def test_checked_executable_none_required():
    """No executable is refused when one is required."""
    with pytest.raises(ValueError, match="no executable configured"):
        checked_executable("soft", None, True)


@pytest.mark.parametrize("path", ["dftb+", "bin/dftb+", "", "./orca"])
def test_checked_executable_relative(path):
    """A bare name, a relative path or an empty string is refused."""
    with pytest.raises(ValueError, match="must be absolute"):
        checked_executable("soft", path, False)


# ----------------------------------------------------------------------
# Program
# ----------------------------------------------------------------------


def test_program_defaults():
    """In process: no launcher is kept."""
    program = Program(name="soft", launcher=["/usr/bin/mpirun"])
    assert program.process == "inprocess"
    assert program.launcher == []


def test_program_unknown_process():
    """Only "inprocess" and "mpi" are accepted."""
    with pytest.raises(ValueError, match="process must be one of"):
        Program(name="soft", process="threads")


@pytest.mark.parametrize("timeout", [0, -1, "10"])
def test_program_bad_timeout(timeout):
    """The timeout must be a positive number."""
    with pytest.raises(ValueError, match="timeout must be a positive number"):
        Program(name="soft", timeout=timeout)


def test_program_mpi_launcher():
    """{process_unit} is replaced in the MPI launcher."""
    program = Program(
        name="soft", process="mpi", process_unit=4, launcher=["/usr/bin/mpirun", "-np", "{process_unit}"]
    )
    assert program.launcher == ["/usr/bin/mpirun", "-np", "4"]


@pytest.mark.parametrize("launcher", [[], ["mpirun", "-np", "2"]])
def test_program_mpi_launcher_not_absolute(launcher):
    """An MPI run needs a launcher starting with an absolute path."""
    with pytest.raises(ValueError, match="launcher must start with an absolute path"):
        Program(name="soft", process="mpi", launcher=launcher)


def test_program_execute_sets_threads(tmp_path):
    """OMP_NUM_THREADS is the process unit; env is added."""
    exe = script(tmp_path, "env.sh", 'echo "$OMP_NUM_THREADS $AMAC_TEST_VALUE"')
    program = Program(name="soft", executable=exe, process_unit=3, env={"AMAC_TEST_VALUE": "ok"})
    program.execute(tmp_path, output="out.log")
    assert (tmp_path / "out.log").read_text().strip() == "3 ok"


def test_program_execute_mpi_one_thread(tmp_path):
    """With MPI, each process runs one thread, behind the launcher."""
    launcher = script(tmp_path, "launcher.sh", 'echo "launched $*"; exec "$3"')
    exe = script(tmp_path, "env.sh", 'echo "threads $OMP_NUM_THREADS"')
    program = Program(
        name="soft",
        executable=exe,
        process="mpi",
        process_unit=2,
        launcher=[str(launcher), "-np", "{process_unit}"],
    )
    program.execute(tmp_path, output="out.log")
    lines = (tmp_path / "out.log").read_text().splitlines()
    assert lines == [f"launched -np 2 {exe}", "threads 1"]


# ----------------------------------------------------------------------
# ExecProcess
# ----------------------------------------------------------------------


def test_exec_process_writes_outputs(tmp_path):
    """Stdout goes to the output file, stderr to the .err file, args are passed."""
    exe = script(tmp_path, "echo.sh", 'echo "out $1"; echo "err" >&2')
    process = ExecProcess(exe, workdir=tmp_path, args=("input.inp",), output="run.log", prefix="soft")
    assert process.command == [str(exe), "input.inp"]
    process.execute()
    assert (tmp_path / "run.log").read_text() == "out input.inp\n"
    assert (tmp_path / "run.err").read_text() == "err\n"


def test_exec_process_runs_in_workdir(tmp_path):
    """The program runs in the working directory."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    exe = script(tmp_path, "pwd.sh", "pwd")
    ExecProcess(exe, workdir=workdir).execute()
    assert Path((workdir / "output.log").read_text().strip()).resolve() == workdir.resolve()


def test_exec_process_missing_workdir(tmp_path, fake_executable):
    """A missing working directory is an error."""
    with pytest.raises(ExecuteFailed, match="working directory missing"):
        ExecProcess(fake_executable, workdir=tmp_path / "none", prefix="soft").execute()


def test_exec_process_return_code(tmp_path):
    """A non-zero return code is an error showing the end of stderr."""
    exe = script(tmp_path, "fail.sh", 'echo "bad input" >&2; exit 3')
    with pytest.raises(ExecuteFailed, match="return code 3") as error:
        ExecProcess(exe, workdir=tmp_path, prefix="soft").execute()
    assert "bad input" in str(error.value)


def test_exec_process_timeout(tmp_path):
    """A program running longer than the timeout is an error."""
    exe = script(tmp_path, "slow.sh", "sleep 5")
    with pytest.raises(ExecuteFailed, match="exceeded 0.2 s"):
        ExecProcess(exe, workdir=tmp_path, timeout=0.2, prefix="soft").execute()


def test_exec_process_cannot_start(tmp_path):
    """A file that cannot be executed is an error."""
    path = tmp_path / "not-a-program"
    path.write_text("")
    with pytest.raises(ExecuteFailed, match="cannot execute"):
        ExecProcess(path, workdir=tmp_path, prefix="soft").execute()
