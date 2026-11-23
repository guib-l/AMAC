#!/usr/bin/env python3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from amac.engine.execute import Execute, ExecuteIO


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
        backend: Where the command runs; local subprocess by default.
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
        backend: Execute | None = None,
    ):
        self.executable = Path(executable)
        self.workdir = Path(workdir)
        self.args = tuple(args)
        self.launcher = tuple(launcher)
        self.env = dict(env or {})
        self.output = output
        self.timeout = timeout
        self.prefix = prefix
        self.backend = backend if backend is not None else ExecuteIO()

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
        return self.backend.run(self)


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
        hpc: The ``hpc`` section of the configuration, ``None`` when absent.
        execute_library: True when the software runs through a Python library.
        backend: Where the command runs; selected in :meth:`__post_init__`.
    """

    name: str
    executable: Path | None = None
    process: str = "inprocess"
    process_unit: int = 1
    env: dict[str, str] = field(default_factory=dict)
    launcher: list[str] = field(default_factory=list)
    timeout: float | None = None
    hpc: dict | None = None
    execute_library: bool = False
    backend: Execute | None = None

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
        if (
            not isinstance(self.process_unit, int)
            or isinstance(self.process_unit, bool)
            or (self.process_unit < 1)
        ):
            raise ValueError(
                f"{self.name}: process_unit must be a positive integer, got {self.process_unit!r}"
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
        self.backend = Execute.select_profile(
            self.hpc,
            library=self.execute_library,
            process=self.process,
            process_unit=self.process_unit,
            timeout=self.timeout,
        )

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
            timeout=None if self.backend.schedules else self.timeout,
            prefix=self.name,
            backend=self.backend,
        ).execute()
