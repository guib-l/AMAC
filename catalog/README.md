# catalog/

The canonical AMAC catalog: it lists the **methods** (DFTB, DFTB-2…) and the
**modules** (single-point, optimization…) a user can request, with the
parameters each one accepts. It does not depend on any software.

Each software package (`amac/asset/<software>/equiv.json`) then translates
these canonical names and parameters into its own syntax.

## Structure

```
catalog/
├── catalog.json     # index of the files to read, by section
├── methods/*.json   # one or more methods per file
├── module/*.json    # one or more modules per file
├── options/*.json   # cross-cutting options (solvation), usable with any module
└── data/*.json      # value lists (functionals, basis sets), one list per file
```

Only the files listed in `catalog.json` are loaded. Names are
case-insensitive. User arguments are checked against these rules before any
calculation.

## Entry format

```json
{
    "NAME": {
        "alias": ["OTHER-NAME"],
        "inherits": ["PARENT"],
        "mandatory-attribute": {},
        "allowed-attribute": {},
        "forbidden-attribute": []
    }
}
```

| Key                   | Role                                                                     |
|-----------------------|--------------------------------------------------------------------------|
| `alias`               | Other accepted names for the entry                                       |
| `inherits`            | Parent entries (name or alias) whose attributes are inherited (methods)  |
| `mandatory-handler`   | Results the software must be able to extract (modules)                   |
| `mandatory-attribute` | Required parameters                                                      |
| `allowed-attribute`   | Optional parameters                                                      |
| `forbidden-attribute` | Forbidden parameters                                                     |

An attribute accepts the following keys:

| Key               | Role                                                          |
|-------------------|---------------------------------------------------------------|
| `type`            | `str`, `int`, `float`, `bool`, `list[int]`, `dict[str,...]`…  |
| `description`     | Short text, unit in parentheses                               |
| `choices`         | Allowed values                                                |
| `range`           | `[min, max]`, `null` for an open bound                        |
| `children`        | Sub-attributes (same format: mandatory/allowed/forbidden)     |
| `authorized-with` | The sub-attribute is only valid with these parent values      |
| `choices-from`    | Values taken from a `data/` list (see below)                  |
| `forbidden-if`    | Refused when a sibling value has a property (see below)       |

## Value lists (`data/`)

Each file of `data/` is one list, `{name: {"alias": [...], ...properties}}`,
listed under `"data"` in `catalog.json`. Names and aliases are
case-insensitive; a value is turned into its canonical name before
translation.

- `functionals.json`: `family`, `builtin-dispersion`.
- `basis-sets.json`: `family`, `role` (`orbital`, `auxiliary-j`,
  `auxiliary-jk`, `auxiliary-c`), `ecp`.

```json
"functional": {"type": "str", "choices-from": {"list": "functionals", "strict": true}},
"basis": {"type": "str", "choices-from": {"list": "basis-sets", "role": ["orbital"], "strict": false}},
"dispersion": {"type": "str", "forbidden-if": {"attribute": "functional", "property": "builtin-dispersion"}}
```

`strict: true` refuses a value missing from the list; `strict: false`
passes it unchanged to the software. In an `equiv.json`, a spec with
`"strict-values": true` refuses any value missing from its `values`.

## Options (`options/`)

An option adds to any method and module. It is given as
`options={"<option>": {arguments}}` to `parameters_register`, checked like a
method, and translated by the `"options"` section of each `equiv.json`; a
software without that entry refuses the option.

`solvation`: `model` (`cpcm|smd|gbsa`) with either `solvent` or `epsilon`
(cpcm only). The solvent list is open and kept per software: the `values` of
the `solvent` spec in each `equiv.json` map a canonical name to the software
name, and a name missing there is passed unchanged. To add a solvent, add a
line to those `values`.

## Adding a method or a module

1. Create or extend a file in `methods/` or `module/`.
2. Add the file name (without `.json`) to `catalog.json`: only the listed
   files are read.
3. Add its translation to the `equiv.json` of each software that supports it.

Minimal example:

```json
{
    "single-point": {
        "alias": ["sp"],
        "mandatory-handler": ["lowest-energy"],
        "mandatory-attribute": null,
        "allowed-attribute": null,
        "forbidden-attribute": null
    }
}
```
