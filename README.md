# AMAC

**A**toms – **M**olecules – **A**ggregates **C**alculator: one Python syntax to
describe and run quantum chemistry calculations, whatever the software behind
them.

A calculation is described once, in a software-independent form (method,
module, parameters). AMAC checks it against the canonical catalog, translates
it for the chosen software, runs the program and extracts the requested
results with *handlers*.

Supported software: **DFTB+** (`dftb+`) and **deMonNano** (`deMonNano`).

## Installation

Python ≥ 3.12 is required. Install AMAC from a checkout of the repository:

```bash
pip install -e .          # numpy, ase
pip install -e ".[dev]"   # adds pytest and ruff
```

deMonNano runs in process through the
[`deMonPy`](https://github.com/guib-l/DeMonNanoPy) library, which you install
from its own repository.

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
    }
  }
}
```

Executables must be absolute paths. Load the file once per process:

```python
import amac
amac.configure_from_file("config-amac.json")   # or amac.configure(config=dict)
```

If you don't load a file, the configuration is empty.

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

More examples are in [`examples/`](examples/). For instance,
`examples/compare_dftb.py` runs the same DFTB-2 calculation with both programs
and compares the energies.

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

calc.store(Store("results.json"))   # or "results.db"
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

See `examples/store.py`.

## Project layout

| Path | Content |
|---|---|
| [`catalog/`](catalog/README.md) | Canonical methods and modules, and the parameters they accept |
| [`amac/asset/`](amac/asset/README.md) | One adapter per software, including its `equiv.json` translation table |
| `amac/engine/` | Shared machinery: catalog loading, validation, translation, handlers, execution |
| `amac/amac.py` | The `AMAC` user class |
| `amac/store/` | The `Store` class: save and read results (txt, JSON, SQLite) |
| `examples/` | Runnable scripts |

## Development

```bash
pytest            # test suite
ruff check amac   # linter
```
