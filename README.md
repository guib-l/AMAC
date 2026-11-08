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

## Project layout

| Path | Content |
|---|---|
| [`catalog/`](catalog/README.md) | Canonical methods and modules, and the parameters they accept |
| [`amac/asset/`](amac/asset/README.md) | One adapter per software, including its `equiv.json` translation table |
| `amac/engine/` | Shared machinery: catalog loading, validation, translation, handlers, execution |
| `amac/amac.py` | The `AMAC` user class |
| `examples/` | Runnable scripts |

## Development

```bash
pytest            # test suite
ruff check amac   # linter
```
