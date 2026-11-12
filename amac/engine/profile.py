#!/usr/bin/env python3
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from amac.utils.exception import ExecuteFailed


def _tail(path: Path, lines: int = 20) -> str:
    """Return the last ``lines`` lines of ``path`` (empty if missing)."""
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])


class ExecProcess:
    """Run an external program in a working directory.

    Stdout is streamed to ``workdir/output`` and stderr to the same name
    with the ``.err`` suffix, so the output survives a failure.

    Args:
        executable: Absolute path of the program.
        workdir: Existing directory where the program runs.
        args: Command-line arguments given to the executable.
        launcher: Command placed before the executable (e.g. ``mpirun -np 4``).
        env: Variables added to the inherited environment.
        output: File name receiving the standard output.
        timeout: Maximum wall time in seconds, ``None`` for no limit.
        prefix: Software name used in error messages.
    """

    def __init__(
        self,
        executable: str | Path,
        workdir: str | Path = ".",
        args: tuple[str, ...] = (),
        launcher: tuple[str, ...] = (),
        env: dict[str, str] | None = None,
        output: str = "output.log",
        timeout: float | None = None,
        prefix: str = "",
    ):
        self.executable = Path(executable)
        self.workdir = Path(workdir)
        self.args = tuple(args)
        self.launcher = tuple(launcher)
        self.env = dict(env or {})
        self.output = output
        self.timeout = timeout
        self.prefix = prefix

    @property
    def command(self) -> list[str]:
        """Full command line: launcher, executable, then arguments."""
        return [*self.launcher, str(self.executable), *self.args]

    @property
    def output_path(self) -> Path:
        return self.workdir / self.output

    @property
    def error_path(self) -> Path:
        return self.output_path.with_suffix(".err")

    def execute(self) -> subprocess.CompletedProcess:
        """Run the command and return the finished process.

        Raises:
            ExecuteFailed: The program cannot start, times out or exits
                with a non-zero code.
        """
        if not self.workdir.is_dir():
            raise ExecuteFailed(f"{self.prefix}: working directory missing: {self.workdir}")

        try:
            with (
                open(self.output_path, "w") as out,
                open(self.error_path, "w") as err,
            ):
                result = subprocess.run(
                    self.command,
                    cwd=self.workdir,
                    env={**os.environ, **self.env},
                    stdout=out,
                    stderr=err,
                    timeout=self.timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            raise ExecuteFailed(
                f"{self.prefix}: exceeded {self.timeout} s in {self.workdir}"
            ) from error
        except OSError as error:
            raise ExecuteFailed(f"{self.prefix}: cannot execute {self.command[0]}") from error

        if result.returncode != 0:
            raise ExecuteFailed(
                f"{self.prefix}: return code {result.returncode} in "
                f"{self.workdir} (see {self.output_path})\n"
                f"{_tail(self.error_path) or _tail(self.output_path)}"
            )
        return result


def checked_executable(name: str, path, required: bool) -> Path | None:
    """Reject a missing, bare or relative executable (never searched in PATH)."""
    if path is None:
        if required:
            raise ValueError(f"{name}: no executable configured")
        return None
    path = Path(path)
    if not path.is_absolute():
        raise ValueError(f"{name}: executable must be absolute, got {path}")
    return path


PROCESSES = ("inprocess", "mpi")


@dataclass
class Program:
    """How to run the executable of a software.

    Attributes:
        name: Software name, used in error messages.
        executable: Absolute path of the program, ``None`` if not needed.
        process: ``"inprocess"`` (OpenMP threads) or ``"mpi"`` (launcher).
        process_unit: Number of threads, or of MPI processes.
        env: Variables added to the environment of the process.
        launcher: MPI command; ``{process_unit}`` is replaced.
        timeout: Maximum wall time in seconds, ``None`` for no limit.
    """

    name: str
    executable: Path | None = None
    process: str = "inprocess"
    process_unit: int = 1
    env: dict[str, str] = field(default_factory=dict)
    launcher: list[str] = field(default_factory=list)
    timeout: float | None = None

    def __post_init__(self):
        """Check the settings as soon as the software is created."""
        if self.process not in PROCESSES:
            raise ValueError(
                f"{self.name}: process must be one of {PROCESSES}, got {self.process!r}"
            )
        if self.timeout is not None and not (
            isinstance(self.timeout, (int, float)) and self.timeout > 0
        ):
            raise ValueError(
                f"{self.name}: timeout must be a positive number of seconds, got {self.timeout!r}"
            )
        if self.process == "mpi":
            self.launcher = [
                str(part).format(process_unit=self.process_unit) for part in self.launcher
            ]
            if not self.launcher or not Path(self.launcher[0]).is_absolute():
                raise ValueError(
                    f"{self.name}: launcher must start with an absolute path, got {self.launcher}"
                )
        else:
            self.launcher = []

    def execute(self, workdir, *args, output="output.log"):
        """Run the executable in ``workdir`` and return the finished process."""
        threads = 1 if self.process == "mpi" else self.process_unit
        env = {
            "OMP_NUM_THREADS": str(threads),
            **{key: str(value) for key, value in self.env.items()},
        }
        return ExecProcess(
            self.executable,
            workdir=workdir,
            args=args,
            launcher=self.launcher,
            env=env,
            output=output,
            timeout=self.timeout,
            prefix=self.name,
        ).execute()
