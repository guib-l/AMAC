# AMAC

> **Experimental project.** AMAC is under active development and its API may
> change. It does not replace the official documentation and tools of the
> software it drives: check their manuals for the meaning, defaults and
> limits of each method, and validate important results with them.

**A**toms – **M**olecules – **A**ggregates **C**alculator: one Python syntax to
describe and run quantum chemistry calculations, whatever the software behind
them.

A calculation is described once, in a software-independent form (method,
module, parameters). AMAC checks it against the canonical catalog, translates
it for the chosen software, runs the program and extracts the requested
results with *handlers*.

| Software | Name in AMAC | Runs as | Typical use |
|---|---|---|---|
| [DFTB+](https://dftbplus.org) | `dftb+` | executable | DFTB, xTB, TD-DFTB, MD, periodic |
| deMonNano | `deMonNano` | executable (via `deMonPy`) | DFTB, CI-DFTB, periodic |
| [PySCF](https://pyscf.org) | `pyscf` | in process | HF, DFT, MP2, CC, CASSCF |
| [OpenMolcas](https://gitlab.com/Molcas/OpenMolcas) | `openmolcas` | executable (`pymolcas`) | HF, DFT, MP2, CC, CASSCF, CASPT2, NEVPT2 |
| [ORCA](https://www.faccts.de/orca/) | `orca` | executable | HF, DFT, MP2, CC, CASSCF, xTB, TD-DFT, MD |

The ORCA asset has not yet been validated on a real ORCA installation.

## What can be computed

The canonical catalog ([`catalog/`](catalog/README.md)) defines what a
calculation can ask for; each software supports a subset of it.

- **Methods**: `HF`, `DFT`, `MP2`, `CCSD`, `CCSD(T)`, `CASSCF`, `CASPT2`,
  `NEVPT2`, `DFTB` (`DFTB-2`, `DFTB-3`, `CI-DFTB`), `xTB`.
- **Modules**: `single-point`, `optimization-geometry`, `frequencies`,
  `excited-states`, `transition-state`, `molecular-dynamics`.
- **Options**: `solvation` (`cpcm`, `smd`, `gbsa`).

Results are extracted by *handlers*, registered by name with
`handler_register`. The common ones are `lowest-energy`, `energy-resume`,
`forces`, `final-geometry`, `charges`, `dipole`, `frequencies`,
`excited-states` and `trajectory`. An unsupported request is refused before
any run.

The coverage of each software is in [`examples/README.md`](examples/README.md).

## Installation

Python ≥ 3.12 is required. Install AMAC from a checkout of the repository:

```bash
pip install -e .          # numpy, ase
pip install -e ".[dev]"   # adds pytest and ruff
```

deMonNano runs in process through the
[`deMonPy`](https://github.com/guib-l/DeMonNanoPy) library, which you install
from its own repository.

PySCF runs in process and is not an AMAC dependency: install it with
`pip install pyscf` to use `software="pyscf"`.

## Configuration

AMAC reads no environment variables and never searches `PATH`. All
machine-specific settings come from a JSON file, `config-amac.json`:

```json
{
  "software": {
    "dftb+": {
      "executable": "/absolute/path/to/dftb+",
      "env": {}
    },
    "deMonNano": {
      "executable": "/absolute/path/to/deMon.x",
      "basis": "/absolute/path/to/basis",
      "timeout": 60,
      "launcher": ["/usr/bin/mpirun", "-np", "{process_unit}"]
    },
    "openmolcas": {
      "executable": "/absolute/path/to/pymolcas",
      "env": {"MOLCAS": "/absolute/path/to/OpenMolcas/build"}
    },
    "orca": {
      "executable": "/absolute/path/to/orca"
    },
    "pyscf": {}
  }
}
```

Executables must be absolute paths. `env` adds variables to the environment
of the program only; AMAC itself never reads them. Load the file once per
process:

```python
import amac

amac.configure_from_file("config-amac.json")  # or amac.configure(config=dict)
```

If you don't load a file, the configuration is empty.

## Checking the installation

`amac-check` verifies the Python environment, the configuration file and each
configured software. It prints one line per check:

```bash
amac-check                     # reads config-amac.json
amac-check path/to/config.json
amac-check --json              # machine-readable report
amac-check --run               # also run one H2 single point per software
python -m amac.verify          # same, without installing the script
```

```
AMAC installation check — config-amac.json

✔ core
    ✔ python      3.12.3

✔ dftb+
    ✔ executable  /opt/dftb+/dftb+

⚠ openmolcas
    ⚠ executable  not configured

─────────────────────────────────────────────
2 ✔   1 ⚠   0 ✘   0 –     ready
```

Checks are grouped by software, each block headed by its worst status. Colors
are used when the output is a terminal (`--no-color` disables them).

Exit codes: `0` nothing failed (warnings are allowed), `1` at least one ✘,
`2` the configuration file is missing or is not a JSON object. The check never
searches `PATH`. With `--json`, the report is `{"ready", "summary",
"software", "checks"}`. A missing Python module comes with the `pip` command
that installs it; nothing is installed by the check itself.

With `--run`, each software that passed its static checks runs an H2 single
point (same settings as its `examples/<software>/01_*.py`) and reports the
energy. The runs go in a hidden `.amac-check-*` directory of the current
directory, or of `--workdir`; failed runs are kept there for inspection. With a
scheduler configured, the runs are submitted as jobs with a 10-minute wall time.

## Quickstart

```python
from ase.build import molecule

import amac
from amac import AMAC

amac.configure_from_file("config-amac.json")

calc = AMAC(software="dftb+", workdir=".run/water", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="dftb-2",
    method_args={
        "basis": {"directory": "/path/to/mio-1-1"},
        "scc-tol": 1e-5,
    },
    module="single-point",
)

calc.run(molecule("H2O"))
print(calc.instance.res.product["lowest-energy"])
```

To switch to deMonNano, change only `software` and `basis`. The rest of the
description stays the same.

Wavefunction methods use the same syntax. This CASSCF(4,4) calculation runs
with PySCF, in process, without any executable:

```python
calc = AMAC(software="pyscf", workdir=".run/casscf", label="water")
calc.handler_register("lowest-energy")
calc.parameters_register(
    method="casscf",
    method_args={"basis": "cc-pvdz", "active-orbitals": 4, "active-electrons": 4},
    module="single-point",
)
calc.run(molecule("H2O"))
print(calc.instance.res.product["lowest-energy"])
```

More examples are in [`examples/`](examples/). For instance,
`examples/general/compare_dftb.py` runs the same DFTB-2 calculation with both programs
and compares the energies.

## Options

Cross-cutting options apply to any method and module. They are checked
against the catalog like a method:

```python
calc.parameters_register(
    method="dft",
    method_args={"functional": "b3lyp", "basis": "def2-svp"},
    module="single-point",
    options={"solvation": {"model": "cpcm", "solvent": "water"}},
)
```

`solvation` takes a `model` (`cpcm`, `smd`, `gbsa`) and either a `solvent`
name or an `epsilon` (cpcm only). Each software accepts only the models it
implements.

## Raw software parameters

When a keyword has no canonical equivalent in the catalog, `software_args`
writes it directly into the software parameters. It is indexed by software
(name or alias, any case), and only the section of the current software is
used. The same description therefore still runs with every software:

```python
calc.parameters_register(
    method="dftb-2",
    method_args={...},
    module="single-point",
    software_args={
        "deMonNano": {"DEMON_PARAMETERS.ACTIVE.DFTB.TOL": 1e-7},
        "dftb+": {"Analysis.CalculateForces": True},
        "openmolcas": {"scf.ITERations": 100},  # &SCF block, ITERations keyword
    },
)
```

Paths are dotted, as in the `set` blocks of `equiv.json`
(see [`amac/asset/`](amac/asset/README.md)). The values are written after the
translation of the canonical parameters, so they can override anything,
including what the asset sets itself. They are not checked: a wrong path
produces a wrong keyword in the input, with no error from AMAC.

## Store

A `Store` saves the results of calculations in a file and reads them back.
The format comes from the suffix: `.txt` (columns), `.json`, or `.db` /
`.sqlite` (SQLite). Each save adds one record and never overwrites the file.

```python
from amac.store import Store

calc.store(Store("results.json"))  # or "results.db"
calc.store(Store("energies.txt", columns=["lowest-energy"], calc_file=True))

records = Store("results.db").load(software="dftb+", formula="H2O")
records[0]["lowest-energy"]
```

- **JSON and SQLite** keep everything: id, name, software, method, module,
  formula, status, date, duration, the geometry, and every product of the
  handlers. Nested products use dotted keys (`energy-resume.energy`).
- **txt** writes one line per calculation: index, formula, then the scalar
  products listed in `columns` (`nan` when a product is missing). With
  `calc_file=True`, a `calc.json` file next to the txt file describes the
  calculation (software, method, module and their arguments, handlers,
  `software_args`),
  without the molecules.

`load(**filters)` returns a list of flat dicts and keeps only the records
whose values equal every filter. Geometries come back as `ase.Atoms`, arrays
as lists, and SQLite returns booleans as `1`/`0`.

See `examples/general/store.py`.

## Project layout

| Path | Content |
|---|---|
| [`catalog/`](catalog/README.md) | Canonical methods and modules, and the parameters they accept |
| [`amac/asset/`](amac/asset/README.md) | One adapter per software, including its `equiv.json` translation table |
| `amac/engine/` | Shared machinery: catalog loading, validation, translation, handlers, execution |
| `amac/amac.py` | The `AMAC` user class |
| `amac/verify/` | Installation check: the `amac-check` command and `amac.check()` |
| `amac/store/` | The `Store` class: save and read results (txt, JSON, SQLite) |
| `examples/` | Runnable scripts |

## Development

```bash
pytest            # test suite
ruff check amac   # linter
```
