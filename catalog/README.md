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
└── module/*.json    # one or more modules per file
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
