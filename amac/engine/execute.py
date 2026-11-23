"""Execution backends: run a prepared command locally or through a scheduler."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from amac.utils.exception import ExecuteFailed

if TYPE_CHECKING:
    from amac.engine.profile import ExecProcess

# Scheduler name -> backend class (roadmap 4.5 adds PBS and SGE here).
SCHEDULERS: dict[str, type[Execute]] = {}


def _tail(path: Path, lines: int = 20) -> str:
    """Return the last ``lines`` lines of ``path`` (empty if missing)."""
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])


def format_wall_time(seconds: float) -> str:
    """Format a duration in seconds as a Slurm ``HH:MM:SS`` wall time."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class Execute:
    """Run one prepared command (see :class:`~amac.engine.profile.ExecProcess`)."""

    # True when the backend hands the command to a job scheduler.
    schedules: bool = False

    @classmethod
    def select_profile(
        cls,
        hpc: dict | None = None,
        *,
        library: bool = False,
        process: str = "inprocess",
        process_unit: int = 1,
        timeout: float | None = None,
    ) -> Execute:
        """Build the backend described by the ``hpc`` configuration block.

        Args:
            hpc: The ``hpc`` section of the configuration; ``None`` when absent.
            library: True for a software driven by a Python library, which has
                no command line to hand to a scheduler.
            process: ``"inprocess"`` (OpenMP threads) or ``"mpi"`` (launcher).
            process_unit: Number of threads, or of MPI processes.
            timeout: Wall time of the job in seconds, when the software sets one.

        Returns:
            The backend to use: local, library, or the configured scheduler.

        Raises:
            ValueError: Unknown scheduler, unusable scheduler settings, or a
                library software combined with a scheduler.
        """
        scheduler = (hpc or {}).get("scheduler")
        if scheduler in (None, "local"):
            return ExecuteLIB() if library else ExecuteIO()
        if not isinstance(scheduler, str):
            raise ValueError(
                f"hpc.scheduler: must be a string, got {scheduler!r}; "
                f"supported: {sorted(SCHEDULERS)}"
            )
        backend = SCHEDULERS.get(scheduler)
        if backend is None:
            raise ValueError(
                f"hpc.scheduler: unknown scheduler {scheduler!r}; supported: {sorted(SCHEDULERS)}"
            )
        if library:
            raise ValueError(
                f"hpc.scheduler: {scheduler!r} cannot submit a software that runs "
                "through a Python library; leave hpc.scheduler unset for it"
            )
        return backend(hpc, process=process, process_unit=process_unit, timeout=timeout)

    def run(self, process: ExecProcess) -> subprocess.CompletedProcess:
        """Run ``process`` and return the finished process."""
        raise NotImplementedError


class ExecuteIO(Execute):
    """Run the command as a local subprocess (historical behaviour)."""

    def run(self, process: ExecProcess) -> subprocess.CompletedProcess:
        """Run the command and return the finished process.

        Raises:
            ExecuteFailed: The program cannot start, times out or exits with
                a non-zero code.
        """
        if not process.workdir.is_dir():
            raise ExecuteFailed(f"{process.prefix}: working directory missing: {process.workdir}")

        try:
            with (
                open(process.output_path, "w") as out,
                open(process.error_path, "w") as err,
            ):
                result = subprocess.run(
                    process.command,
                    cwd=process.workdir,
                    env={**os.environ, **process.env},
                    stdout=out,
                    stderr=err,
                    timeout=process.timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            raise ExecuteFailed(
                f"{process.prefix}: exceeded {process.timeout} s in {process.workdir}"
            ) from error
        except OSError as error:
            raise ExecuteFailed(f"{process.prefix}: cannot execute {process.command[0]}") from error

        if result.returncode != 0:
            raise ExecuteFailed(
                f"{process.prefix}: return code {result.returncode} in "
                f"{process.workdir} (see {process.output_path})\n"
                f"{_tail(process.error_path) or _tail(process.output_path)}"
            )
        return result


class ExecuteLIB(Execute):
    """Software run through its Python library: there is no command to launch."""

    def run(self, process: ExecProcess) -> subprocess.CompletedProcess:
        """Refuse: a library software is never handed to a scheduler.

        Raises:
            ExecuteFailed: Always.
        """
        raise ExecuteFailed(
            f"{process.prefix}: runs through a Python library, there is no command to launch"
        )


class ExecuteSlurm(ExecuteIO):
    """Submit the command as a Slurm job and wait for its end."""

    schedules = True

    def __init__(
        self,
        hpc: dict,
        *,
        process: str = "inprocess",
        process_unit: int = 1,
        timeout: float | None = None,
    ) -> None:
        """Read and validate the ``hpc`` block.

        Raises:
            ValueError: Missing or relative ``sbatch`` path, a malformed
                ``defaults`` object, or a ``prologue`` that is not a list.
        """
        sbatch = hpc.get("sbatch")
        if sbatch is None:
            raise ValueError("hpc.sbatch: no sbatch configured")
        self.sbatch = Path(sbatch)
        if not self.sbatch.is_absolute():
            raise ValueError(f"hpc.sbatch: must be absolute, got {self.sbatch}")
        defaults = hpc.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise ValueError(f"hpc.defaults: must be a JSON object, got {defaults!r}")
        self.defaults = dict(defaults)
        prologue = hpc.get("prologue") or ()
        if not isinstance(prologue, (list, tuple)):
            raise ValueError(f"hpc.prologue: must be a list of shell lines, got {prologue!r}")
        self.prologue = [str(line) for line in prologue]
        self.process = process
        self.process_unit = int(process_unit)
        # --time comes from the defaults, or from the software timeout.
        self.time = self.defaults.get("time") or (format_wall_time(timeout) if timeout else None)

    def job_script(self, process: ExecProcess) -> str:
        """Return the ``job.sh`` content for one command.

        One directive per line, each emitted only when the value is known.
        A file-based software gets one task and one CPU per OpenMP thread;
        an MPI software gets one task per process unit.
        """
        ntasks = self.process_unit if self.process == "mpi" else 1
        cpus = self.process_unit if self.process != "mpi" and self.process_unit > 1 else None
        workdir = process.workdir.resolve()
        output = process.output_path.resolve()
        error = process.error_path.resolve()
        directives = (
            ("--job-name", f"amac-{process.prefix}"),
            ("--partition", self.defaults.get("partition")),
            ("--time", self.time),
            ("--ntasks", ntasks),
            ("--cpus-per-task", cpus),
            ("--output", output),
            ("--error", error),
        )
        lines = ["#!/bin/bash"]
        lines.extend(f"#SBATCH {option}={value}" for option, value in directives if value)
        lines.extend(self.prologue)
        lines.append(f"cd {shlex.quote(str(workdir))}")
        lines.extend(
            f"export {key}={shlex.quote(str(value))}" for key, value in process.env.items()
        )
        lines.append(" ".join(shlex.quote(part) for part in process.command))
        return "\n".join(lines) + "\n"

    def run(self, process: ExecProcess) -> subprocess.CompletedProcess:
        """Write ``job.sh``, submit it with ``--wait`` and return the result.

        The local timeout is not applied: the queue wait would count against
        it. The wall time is enforced by ``#SBATCH --time`` instead.

        Raises:
            ExecuteFailed: The job cannot be submitted, or exits non-zero.
        """
        if not process.workdir.is_dir():
            raise ExecuteFailed(f"{process.prefix}: working directory missing: {process.workdir}")

        # A leftover output from a previous run would defeat the check below.
        process.output_path.unlink(missing_ok=True)
        process.error_path.unlink(missing_ok=True)

        script = process.workdir / "job.sh"
        script.write_text(self.job_script(process))
        log = process.workdir / "sbatch.log"

        try:
            with open(log, "w") as out:
                result = subprocess.run(
                    [str(self.sbatch), "--wait", str(script.resolve())],
                    cwd=process.workdir,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
        except OSError as error:
            raise ExecuteFailed(f"{process.prefix}: cannot execute {self.sbatch}") from error

        if result.returncode != 0:
            # Slurm creates the output file when the job starts: its absence
            # means the submission itself was refused.
            if not process.output_path.is_file():
                raise ExecuteFailed(
                    f"{process.prefix}: sbatch failed (return code {result.returncode}) in "
                    f"{process.workdir} (see {log})\n{_tail(log)}"
                )
            raise ExecuteFailed(
                f"{process.prefix}: return code {result.returncode} in "
                f"{process.workdir} (see {process.output_path})\n"
                f"{_tail(process.error_path) or _tail(process.output_path)}"
            )
        return result


SCHEDULERS["slurm"] = ExecuteSlurm
