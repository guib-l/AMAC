"""Canonical catalog of methods and modules (``catalog/``)."""

import json
from pathlib import Path
from typing import Any, Mapping

import amac

# Canonical catalog, at the root of the repository.
CATALOG_DIR = Path(amac.__file__).resolve().parents[1] / "catalog"


def load_catalog(directory: str | Path = CATALOG_DIR) -> dict[str, dict[str, dict]]:
    """Read the canonical catalog, indexed by upper-case canonical name.

    Only the files listed in ``catalog.json`` are read, e.g.
    ``"methods": ["dftb"]`` reads ``methods/dftb.json``.

    Args:
        directory: The ``catalog/`` directory.

    Returns:
        A dict ``{section: {NAME: entry}}`` for ``methods``, ``module``,
        ``options`` and ``data`` (value lists such as functionals, indexed
        ``{LIST: {NAME: entry}}``).

    Raises:
        FileNotFoundError: If a file listed in ``catalog.json`` is missing.
    """
    with open(Path(directory, "catalog.json"), encoding="utf-8") as stream:
        index = json.load(stream)
    catalog = {}
    for section in ("methods", "module", "options", "data"):
        entries = {}
        for stem in index.get(section) or ():
            file = Path(directory, section, f"{stem}.json")
            if not file.is_file():
                raise FileNotFoundError(f"{file} is listed in catalog.json but does not exist")
            with open(file, encoding="utf-8") as stream:
                content = {name.upper(): entry for name, entry in json.load(stream).items()}
            # A data file is one value list, kept under its own name.
            if section == "data":
                entries[stem.upper()] = content
            else:
                entries.update(content)
        catalog[section] = entries
    return catalog


def canonical_value(value: Any, entries: Mapping[str, dict]) -> str | None:
    """Return the canonical (lower-case) name of a value of a data list.

    Args:
        value: User value, canonical name or alias, any case.
        entries: One list of the ``data`` section (e.g. functionals).

    Returns:
        The canonical name, or None if ``value`` is not in the list.
    """
    if not isinstance(value, str):
        return None
    key = value.strip().upper()
    for canonical, entry in entries.items():
        aliases = {alias.upper() for alias in entry.get("alias") or ()}
        if key == canonical or key in aliases:
            return canonical.lower()
    return None


def canonical_name(name: str, catalog: Mapping[str, dict]) -> str:
    """Return the canonical (upper-case) name of ``name`` or of an alias.

    Raises:
        KeyError: If ``name`` is unknown to the catalog.
    """
    key = name.upper()
    for canonical, entry in catalog.items():
        aliases = {alias.upper() for alias in entry.get("alias") or ()}
        if key == canonical or key in aliases:
            return canonical
    raise KeyError(f"Unknown catalog entry: {name!r}")


def inheritance_chain(name: str, catalog: Mapping[str, dict]) -> list[str]:
    """Return the canonical names from the root parent down to ``name``."""
    chain = []
    for parent in catalog[name].get("inherits") or ():
        parent = canonical_name(parent, catalog)
        for item in inheritance_chain(parent, catalog):
            if item not in chain:
                chain.append(item)
    chain.append(name)
    return chain
