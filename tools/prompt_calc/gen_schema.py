#!/usr/bin/env python3
"""One-shot generator: the AMAC catalog and asset handlers -> spec_schema.json.

Run once from the AMAC repository root:

    python tools/prompt_calc/gen_schema.py

The catalog (``catalog/``) is the single source of truth: methods, modules
and options are read from it (with inheritance merged exactly as AMAC does),
the handler lists come from the registered assets. Re-run after every catalog
change and commit the output.
"""

import json
from pathlib import Path

import amac.asset  # noqa: F401  # registers every asset and its handlers
from amac.engine.catalog import load_catalog
from amac.engine.handler import registered_handlers
from amac.engine.software import Software
from amac.engine.validate import merged_attributes

HERE = Path(__file__).resolve().parent
# The two assets prompt_calc targets (design doc, gen_schema scope).
SOFTWARES = ("dftb+", "deMonNano")
# Keys kept from a raw catalog attribute spec.
_ATTR_KEYS = (
    "type",
    "choices",
    "range",
    "authorized-with",
    "choices-from",
    "description",
    "children",
)


def attribute_spec(raw: dict, data: dict) -> dict:
    """Keep the schema-relevant keys of one catalog attribute spec."""
    entry = {key: raw[key] for key in _ATTR_KEYS if key in raw and raw[key] is not None}
    if rule := raw.get("choices-from"):
        # Expand the data list into plain canonical names for the schema.
        entry["choices-from"] = dict(rule)
        entry["choices"] = sorted(data.get(rule["list"].upper(), {}))
    if "children" in entry:
        children = raw["children"]
        entry["children"] = {
            section: {
                name: attribute_spec(spec, data)
                for name, spec in (children.get(section) or {}).items()
            }
            for section in ("mandatory-attribute", "allowed-attribute")
        }
    return entry


def entry_schema(section: dict, name: str, data: dict) -> dict:
    """Schema of one method/module/option: aliases + merged attribute rules."""
    merged = merged_attributes(name, section)
    schema = {
        "alias": list(section[name].get("alias") or ()),
        "mandatory-attribute": {
            name: attribute_spec(spec, data)
            for name, spec in (merged["mandatory-attribute"] or {}).items()
        },
        "allowed-attribute": {
            name: attribute_spec(spec, data)
            for name, spec in (merged["allowed-attribute"] or {}).items()
        },
    }
    if handler := section[name].get("mandatory-handler"):
        schema["mandatory-handler"] = list(handler)
    return schema


def build_schema() -> dict:
    """Assemble the full spec schema from the catalog and the asset registry."""
    catalog = load_catalog()
    data = catalog["data"]
    sections = {
        "methods": {
            name.lower(): entry_schema(catalog["methods"], name, data)
            for name in catalog["methods"]
        },
        "modules": {
            name.lower(): entry_schema(catalog["module"], name, data) for name in catalog["module"]
        },
        "options": {
            name.lower(): entry_schema(catalog["options"], name, data)
            for name in catalog["options"]
        },
    }
    aliases: dict[str, str] = {}
    for section in sections.values():
        for canonical, entry in section.items():
            for alias in entry["alias"]:
                aliases[alias.lower()] = canonical
    tables = {
        stem.lower(): {
            name.lower(): list(spec.get("alias") or ()) for name, spec in entries.items()
        }
        for stem, entries in data.items()
    }
    software = {}
    for name in SOFTWARES:
        cls = Software._registry[name.upper()]
        software[name] = {
            "alias": list(cls.alias),
            "handlers": sorted(registered_handlers(name)),
        }
    return {**sections, "aliases": aliases, "data": tables, "software": software}


def main() -> None:
    """Write the generated spec_schema.json next to this script."""
    schema = build_schema()
    out = HERE / "spec_schema.json"
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
