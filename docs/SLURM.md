# Running on a Slurm cluster

AMAC can hand the calculation to Slurm instead of starting it locally: it
writes a `job.sh` script and submits it with `sbatch --wait`, so the Python
call blocks until the job ends, as it does locally, and only the configuration
changes. This is synchronous only: no job is tracked after submission.

## Requirements

- An absolute path to `sbatch`, and to `squeue` for the installation check
  (optional), both reachable from the login node.
- A work directory on a filesystem shared with the compute nodes, where the
  job reads and writes and where AMAC parses the results.
- The QC executable reachable on the compute nodes, as an absolute path in
  its `software` section, with `module load ...` lines in `hpc.prologue`.
- AMAC and its dependencies importable on the login node: AMAC computes
  nothing, but the asset writes the input, submits and parses the output.

## Configuration

The scheduler is described by a global `hpc` block in `config-amac.json`,
next to the `software` sections:

```json
{
  "hpc": {
    "scheduler": "slurm",
    "sbatch": "/usr/bin/sbatch",
    "squeue": "/usr/bin/squeue",
    "defaults": {"partition": "standard", "time": "02:00:00", "ntasks": 4},
    "prologue": ["module load dftbplus/25.1"]
  },
  "software": {
    "dftb+": {"executable": "/opt/dftbplus/25.1/bin/dftb+", "basis": "/scratch/me/skfiles"}
  }
}
```

| Key | Meaning | Required |
|---|---|---|
| `scheduler` | Backend: `"slurm"` submits to Slurm, `"local"` or no block keeps local execution | Yes, to enable Slurm |
| `sbatch` | Absolute path of `sbatch` | Yes, with a scheduler |
| `squeue` | Absolute path of `squeue`; installation check, reserved for asynchronous mode | No |
| `defaults.partition` | Value of `#SBATCH --partition` | No |
| `defaults.time` | Value of `#SBATCH --time`, used as written (`HH:MM:SS`) | No |
| `defaults.ntasks` | Default number of process units (threads or MPI ranks) | No, 1 |
| `prologue` | Shell lines run before the command, e.g. `module load` | No |

The block is **global**: no per-software or per-calculation override.
`"scheduler": "local"`, or no `hpc` block, keeps local execution.

## How resources are chosen

- `--job-name=amac-<software name>` (`amac-dftb+`), `--partition` from
  `defaults.partition`, and `--time` from `defaults.time`, else from the
  software `timeout` in seconds formatted as `HH:MM:SS`.
- `--ntasks=<process_unit>` and no `--cpus-per-task` for `process="mpi"`;
  otherwise `--ntasks=1` and `--cpus-per-task` only above 1 unit.
- `--output` and `--error`: absolute paths of the program output and of its
  error companion inside the work directory; the companion has the same name
  with its suffix replaced by `.err` (`dftb.out` gives `dftb.err`).

The number of process units is the one given to the software object, else
`hpc.defaults.ntasks` with a Slurm scheduler, else 1: OpenMP threads
(`OMP_NUM_THREADS`) for a file-based software, MPI ranks with the configured
`launcher` otherwise. An unknown directive is omitted, so the default applies.

## What AMAC writes

AMAC writes in the work directory (here a DFTB+ single point on 4 threads):

- `job.sh`: the generated script, never deleted by AMAC.
- `sbatch.log`: the output and error of `sbatch` itself.
- `<output>` and its `.err` companion, that is the output name with its suffix
  replaced by `.err` (`dftb.out` → `dftb.err`): the job output and error,
  written by Slurm through `--output` and `--error`.
- The usual input and parsed files of the software.

```bash
#!/bin/bash
#SBATCH --job-name=amac-dftb+
#SBATCH --partition=standard
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --output=/scratch/me/.run/water/dftb.out
#SBATCH --error=/scratch/me/.run/water/dftb.err
module load dftbplus/25.1
cd /scratch/me/.run/water
export OMP_NUM_THREADS=4
/opt/dftbplus/25.1/bin/dftb+
```

## Checking the configuration

`amac-check` adds these lines when the block enables Slurm:

```
core        ✔  hpc         scheduler: slurm
core        ✔  sbatch      /usr/bin/sbatch
core        ✔  squeue      /usr/bin/squeue
```

These lines are excerpts: in a full report the two columns are padded to the
widest scope and the widest check name, which depend on the configured
software, so the spacing differs from a real run.

A missing, relative or non-executable `sbatch` is a ✘, and so is a scheduler
other than `slurm`. A missing `squeue` is only a ⚠, since the submission path
does not use it; without an `hpc` block no extra line appears, and
`"scheduler": "local"` gives a ⚠ `no scheduler (local execution)`.

## Running a calculation

Nothing changes in the Python code: the same call runs locally or on the
cluster, depending on the configuration file, and blocks until `sbatch --wait`
returns, so the queue wait is part of the run.

```python
from ase.build import molecule

import amac
from amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="dftb+", workdir="/scratch/me/.run/water", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="dftb-2",
    method_args={"basis": {"directory": "/scratch/me/skfiles"}, "scc-tol": 1e-5},
    module="single-point",
)
calc.run(molecule("H2O"))
print(calc.instance.res.product["lowest-energy"])
```

## Troubleshooting

The submission was refused (wrong partition, rejected directive, or `sbatch`
that cannot be executed):

```
dftb+: sbatch failed (return code 1) in /scratch/me/.run/water (see /scratch/me/.run/water/sbatch.log)
sbatch: error: invalid partition specified: standard
```

The job was submitted and ran, then exited non-zero:

```
dftb+: return code 3 in /scratch/me/.run/water (see /scratch/me/.run/water/dftb.out)
<last lines of dftb.err, or of dftb.out when it is empty>
```

AMAC tells them apart by the output file, which Slurm creates when the job
starts: without it, the submission was refused. Both the output file and its
`.err` companion (`dftb.out` and `dftb.err`) are removed before submitting, so
a stale file cannot fake a job failure. The work directory must exist, or AMAC
stops with `working directory missing`.

## Limitations

- Synchronous only: nothing is tracked after submission, and `squeue` is
  never polled.
- Slurm only; PBS and SGE are not supported.
- The `hpc` block is global, never per software or per calculation.
- Software driven by a Python library (`deMonNano`, `pyscf`) is refused when
  the object is created: it would otherwise run on the login node.
- With a scheduler, the local wall-clock timeout is disabled (the queue wait
  would count against it) and `#SBATCH --time` enforces the wall time.
