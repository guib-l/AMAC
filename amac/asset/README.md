# amac/asset/

An **asset** is the adapter for one software package (deMonNano, DFTB+…). It
translates a calculation written in canonical form (method, module and
parameters from [`catalog/`](../../catalog/README.md)) into the software's own
syntax. It then runs the calculation and extracts the results.

## Structure

```
asset/
├── __init__.py          # imports each asset to register it
└── <software>/
    ├── __init__.py
    ├── soft.py          # Software class: preparation and execution
    ├── handler.py       # result extraction (@handler)
    └── equiv.json       # translation catalog -> software parameters
```

## How a calculation runs

`Software.run()` chains four steps. An asset only overrides the ones that
differ from the default behavior:

| Step          | Role                                                     | Default                       |
|---------------|----------------------------------------------------------|-------------------------------|
| `collect()`   | Builds `self.parameters` from `equiv.json`               | Translation via `equiv.json`  |
| `prepare()`   | Writes the input files into `workdir`                    | Does nothing                  |
| `calculate()` | Runs the program and returns the raw results (`dict`)    | **Required** (abstract)       |
| `callback()`  | Applies the requested handlers to the raw results        | `HandlerSet.apply`            |

## Adding a software package

1. Create `asset/<software>/soft.py` with a subclass of `Software`:

   ```python
   class software_mysoftware(Software):
       name = "mysoftware"            # key in config-amac.json
       alias = ("my-software",)       # other accepted names (case ignored)
       requires_executable = True     # an absolute executable is required
       transforms = {}                # functions called by "transform"

       def calculate(self, instance):
           self.execute_program(instance.ctx.workdir, output="out.log")
           return {...}               # raw results
   ```

   The class registers itself when it is imported.
2. Import it in `asset/__init__.py`.
3. Write the handlers in `handler.py`. Each one receives the raw results and
   returns a product:

   ```python
   @handler(software="mysoftware", name="lowest_energy")
   def lowest_energy(results):
       return results["energy"]
   ```

   A catalog module can require some handlers (`mandatory-handler`). The
   calculation is rejected if the software does not provide them.
4. Write `equiv.json` (see below).
5. Add the software section to `config-amac.json` (`executable`, `env`, and
   its own options such as `basis`). These options are available in
   `self.options`.

## equiv.json

This file maps each catalog **method** and **module** to the software
parameters. The result is a nested `dict`. The asset then writes it in the
expected format (HSD file, Python arguments…).

### Skeleton

```json
{
    "software": "DFTB+",
    "version": "25.1",
    "library": "https://dftbplus.org",
    "description": "...",
    "default": { "set": { "Options.WriteResultsTag": true } },
    "methods": {
        "dftb-1": { "set": {}, "attributes": {} },
        "CI-DFTB": { "supported": false }
    },
    "module": {
        "optimization-geometry": { "set": {}, "attributes": {} }
    }
}
```

`software`, `version`, `library` and `description` are informational only.

### Dotted paths

A target is written as a dot-separated path in the final `dict`. Missing
nodes are created:

```
"Hamiltonian.DFTB.Scc": true   ->   {"Hamiltonian": {"DFTB": {"Scc": true}}}
```

### An entry (method or module)

| Key          | Role                                                          |
|--------------|---------------------------------------------------------------|
| `set`        | Values written as soon as the entry is used (`{path: value}`) |
| `attributes` | Translation of each user parameter (see below)                |
| `supported`  | `false`: the software rejects this method/module              |

- The entry name is the catalog name **or one of its aliases** (case
  ignored).
- **Inheritance**: entries follow the catalog `inherits`. `dftb-2` inherits
  from `dftb-1`, so it gets its `set` and its `attributes`. Only describe
  what changes.
- `default.set` is written first. The method, the module and the user
  arguments can override it.
- Entries can be grouped under a **family** that has no entry key.
  Example: `"methods": {"dftb": {"dftb-1": ..., "dftb-2": ...}}` (deMonNano).
  The family is simply flattened.

### An attribute

Every parameter accepted by the catalog (`mandatory-attribute`,
`allowed-attribute`) and supported by the software must have a translation.
A user parameter without a translation raises a `KeyError`.

| Key         | Role                                                                  |
|-------------|-----------------------------------------------------------------------|
| `target`    | Path where the value is written (`null`: nothing written, only children count) |
| `values`    | Value mapping table: `{"canonical": "software"}`                      |
| `transform` | Name of a function from `Software.transforms` applied to the value    |
| `children`  | Translation of the sub-parameters, with a `target` **relative** to the parent |
| `unit`      | Unit expected by the software (informational)                         |

They are applied in this order: `values`, then `transform`, then writing at
`target`.

**Simple case**: the value is copied as is.

```json
"charge": { "target": "Hamiltonian.DFTB.Charge" }
```

**Values + children**: the translated value becomes a node, and the children
are written inside it.

```json
"mixer": {
    "target": "Hamiltonian.DFTB.Mixer",
    "values": { "broyden": "Broyden" },
    "children": { "mixing-parameter": { "target": "MixingParameter" } }
}
```

```python
method_args={"mixer": {"value": "broyden", "mixing-parameter": 0.2}}
# -> Hamiltonian.DFTB.Mixer.Broyden.MixingParameter = 0.2
```

**Group**: an attribute with none of the keys in the table above groups
sub-attributes, each with its own absolute `target`.

```json
"basis": {
    "directory": { "target": "BASIS.SKFILE" },
    "ptype":     { "target": "BASIS.PTYPE" }
}
```

**Transform**: for a conversion that a mapping table cannot express.

```json
"kpoints": {
    "transform": "kpoints_supercell_folding",
    "target": "Hamiltonian.DFTB.KPointsAndWeights"
}
```

The function is declared in `soft.py`: `transforms = {"kpoints_supercell_folding": func}`.

### Filling in equiv.json step by step

1. List the catalog methods and modules the software can run.
2. For each one, put in `set` what enables the method in the software.
3. For each catalog attribute, find the software keyword and write it in
   `target`. Add `values` if value names differ, and `children` if there are
   sub-parameters.
4. In a child entry (`dftb-2`…), only describe what it adds to its parent.
5. Mark what the software cannot do with `"supported": false`.
6. If the software format needs an adjustment that JSON cannot express, do
   it in `collect()` (see `dftbplus/soft.py`).
