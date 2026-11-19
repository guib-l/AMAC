from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# ----------------------------------------------------------------------
# Equivalence tables of the assets (support suggestions, dispersion models)
# ----------------------------------------------------------------------


@lru_cache(maxsize=None)
def _equiv_tables() -> dict[str, dict]:
    """Equiv table of every asset, keyed by the "software" name of its file."""
    import amac
    from amac.engine.equiv import load_equiv

    root = Path(amac.__file__).resolve().parent / "asset"
    tables = {}
    for path in sorted(root.glob("*/equiv.json")):
        with open(path, encoding="utf-8") as stream:
            name = json.load(stream).get("software", path.parent.name)
        tables[name] = load_equiv(path)
    return tables


def _table_for(software: str) -> dict | None:
    """Equiv table of a schema software (name or alias, any case)."""
    key = software.lower()
    for name, table in _equiv_tables().items():
        if name.lower() == key:
            return table
    return None


def allowed_dispersion(software: str) -> list[str]:
    """Dispersion models of a software, from the dftb family of its equiv."""
    table = _table_for(software)
    if table is None:
        return []
    for entry in table["methods"].values():
        dispersion = (entry.get("attributes") or {}).get("dispersion")
        if isinstance(dispersion, dict) and dispersion.get("values"):
            return sorted(dispersion["values"])
    return []


def _equiv_lookup(table: dict, section: str, name: str, aliases: tuple[str, ...]) -> dict | None:
    """The equiv entry of name or one of its aliases, None if absent."""
    for lookup in (name.upper(), *(a.upper() for a in aliases)):
        if (entry := table[section].get(lookup)) is not None:
            return entry
    return None


def supporting_software_for(section: str, name: str, schema: dict) -> list[str]:
    """Software names (as in their equiv files) supporting section:name."""
    from amac.engine.catalog import inheritance_chain, load_catalog

    catalog = load_catalog()
    catalog_section = {"modules": "module"}.get(section, section)
    entry = catalog[catalog_section].get(str(name).strip().upper())
    if entry is None:
        return []
    table_section = catalog_section
    chain: list[str] = []
    if section == "methods":
        # A method with no exact equiv entry is expressible only when its
        # family (inheritance chain) is known to the software.
        canonical = str(name).strip().upper()
        chain = [k for k in inheritance_chain(canonical, catalog[catalog_section])]
    found = []
    for asset_name, table in _equiv_tables().items():
        exact = _equiv_lookup(table, table_section, name, tuple(entry.get("alias") or ()))
        if section == "options":
            # An option without an equiv entry is refused by the engine.
            supported = exact is not None and exact.get("supported") is not False
        elif section == "methods":
            if exact is not None:
                supported = exact.get("supported") is not False
            else:
                supported = any(
                    _equiv_lookup(
                        table,
                        table_section,
                        key,
                        tuple(catalog[catalog_section][key].get("alias") or ()),
                    )
                    is not None
                    for key in chain
                )
        else:
            # A module without an equiv entry is a no-op: supported.
            supported = exact is None or exact.get("supported") is not False
        if supported:
            found.append(asset_name)
    return found


def _schema_names(asset_names: list[str], schema: dict) -> list[str]:
    """Map asset names (any case) onto the schema software names."""
    result = []
    for name in asset_names:
        for canonical, entry in schema["software"].items():
            if name.lower() == canonical.lower() or name.lower() in {
                a.lower() for a in entry.get("alias", [])
            }:
                result.append(canonical)
                break
        else:
            result.append(name)
    return result


def _canon_name(name: str, section: str, schema: dict) -> str | None:
    """Lower-case canonical name from a name or alias; None if unknown."""
    key = str(name).strip().lower()
    if section == "software":
        for canonical, entry in schema["software"].items():
            if key == canonical.lower() or key in {a.lower() for a in entry.get("alias", [])}:
                return canonical
        return None
    if key in schema[section]:
        return key
    target = schema["aliases"].get(key)
    if target in schema[section]:
        return target
    return None
