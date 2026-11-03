"""Translation of canonical parameters through an ``equiv.json`` file."""

import copy
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from amac.engine.catalog import (
    CATALOG_DIR,
    canonical_name,
    inheritance_chain,
    load_catalog,
)

# Keys describing how an attribute is translated. A spec holding none of
# them is a group: its keys are sub-attributes (e.g. deMonNano "basis").
_SPEC_KEYS = {"target", "transform", "values", "unit", "children", "available"}
# Keys describing an equiv entry. A node holding none of them is a family
# grouping several entries (e.g. deMonNano "dftb" -> "dftb-1", "dftb-2").
_ENTRY_KEYS = {"set", "attributes", "supported"}


def load_equiv(path: str | Path) -> dict[str, dict[str, dict]]:
    """Read an equiv.json file and index its entries by upper-case name.

    Families are flattened, so ``methods.dftb.dftb-2`` becomes
    ``methods["DFTB-2"]``.

    Args:
        path: Path to the equiv.json file.

    Returns:
        A dict ``{section: {NAME: entry}}`` for the sections
        ``methods``, ``module`` and ``options``, plus the ``default``
        entry as is (its ``set`` is written before any method).
    """
    with open(path, encoding="utf-8") as stream:
        raw = json.load(stream)

    def flatten(node: Mapping[str, Any]) -> dict[str, dict]:
        flat = {}
        for name, entry in node.items():
            if _ENTRY_KEYS & entry.keys() or not entry:
                flat[name.upper()] = entry
            else:
                flat.update(flatten(entry))
        return flat

    return {
        **{
            section: flatten(raw.get(section) or {})
            for section in ("methods", "module", "options")
        },
        "default": raw.get("default") or {},
    }


def set_path(tree: dict, path: str, value: Any) -> None:
    """Set ``value`` at the dotted ``path`` of ``tree``, creating nodes.

    A dict value is merged into an existing dict node.
    """
    *parents, leaf = path.split(".")
    node = tree
    for key in parents:
        node = node.setdefault(key, {})
    if isinstance(value, dict) and isinstance(node.get(leaf), dict):
        node[leaf].update(copy.deepcopy(value))
    else:
        node[leaf] = copy.deepcopy(value)


def _find_equiv(name: str, aliases, equiv: Mapping[str, dict]) -> dict:
    """Return the equiv entry named ``name`` or one of its aliases."""
    for key in (name, *(alias.upper() for alias in aliases)):
        if key in equiv:
            return equiv[key]
    return {}


def _apply_attributes(
        params: dict,
        specs: Mapping[str, dict],
        args: Mapping[str, Any],
        transforms: Mapping[str, Callable],
        prefix: str | None = None,
    ) -> None:
    """Write each user argument at the target given by its spec."""
    for key, value in args.items():
        if key not in specs:
            raise KeyError(f"Attribute {key!r} has no equivalence")
        spec = specs[key]

        # Group without its own target: recurse on the sub-attributes.
        if not _SPEC_KEYS & spec.keys():
            _apply_attributes(params, spec, value, transforms, prefix)
            continue

        target = spec.get("target")
        if target and prefix:
            target = f"{prefix}.{target}"

        children = {}
        if "children" in spec and isinstance(value, dict):
            children = {k: v for k, v in value.items() if k != "value"}
            value = value.get("value")

        if "values" in spec:
            value = spec["values"].get(value, value)
        if "transform" in spec:
            value = transforms[spec["transform"]](value)

        # A value of a spec with children becomes a node, even without
        # children given: Mixer = Broyden { ... }
        if target and value is not None and "children" in spec:
            set_path(params, f"{target}.{value}", {})
            target = f"{target}.{value}"
        elif target and value is not None:
            set_path(params, target, value)
        if children:
            _apply_attributes(
                params, spec["children"], children, transforms, target,
            )


def build_entry_parameters(
        name: str,
        args: Mapping[str, Any] | None,
        equiv: Mapping[str, dict],
        catalog: Mapping[str, dict],
        transforms: Mapping[str, Callable] | None = None,
        params: dict | None = None,
    ) -> dict:
    """Build the software parameter dict of a method or a module.

    Every entry of the inheritance chain (e.g. ``DFTB`` then ``DFTB-2``)
    contributes its ``set`` values and its ``attributes`` specs; then each
    user argument is written at its target.

    Args:
        name: Method or module name, canonical or alias, any case.
        args: User arguments (``method_args`` or ``module_args``).
        equiv: One section of :func:`load_equiv` (e.g. ``"methods"``).
        catalog: The same section of :func:`load_catalog`.
        transforms: Functions named by the ``transform`` key of a spec.
        params: Existing parameter dict to complete; a new one if None.

    Returns:
        The nested parameter dict, ready for the software composer.

    Raises:
        KeyError: Unknown name or argument without equivalence.
        NotImplementedError: Entry marked ``"supported": false``.
    """
    params = {} if params is None else params
    specs: dict = {}
    name = canonical_name(name, catalog)
    for canonical in inheritance_chain(name, catalog):
        aliases = catalog[canonical].get("alias") or ()
        entry = _find_equiv(canonical, aliases, equiv)
        if entry.get("supported") is False:
            raise NotImplementedError(f"{canonical} is not supported")
        for path, value in (entry.get("set") or {}).items():
            set_path(params, path, value)
        specs.update(entry.get("attributes") or {})

    _apply_attributes(params, specs, args or {}, transforms or {})
    return params


class Equivalence:
    """Translate canonical parameters into the parameters of one software.

    Args:
        path: The equiv.json file of the software.
        transforms: Functions named by the ``transform`` key of a spec.
        catalog_dir: The canonical ``catalog/`` directory.
    """

    def __init__(
            self,
            path: str | Path,
            transforms: Mapping[str, Callable] | None = None,
            catalog_dir: str | Path = CATALOG_DIR,
        ):
        self.path = Path(path)
        self.transforms = dict(transforms or {})
        self.catalog_dir = Path(catalog_dir)

    def build(
            self,
            method: str,
            method_args: Mapping[str, Any] | None = None,
            module: str | None = None,
            module_args: Mapping[str, Any] | None = None,
        ) -> dict:
        """Return the nested parameter dict of the method and the module."""
        equiv = load_equiv(self.path)
        catalog = load_catalog(self.catalog_dir)
        # Written first: method, module and user arguments override it.
        params: dict = {}
        for path, value in (equiv["default"].get("set") or {}).items():
            set_path(params, path, value)
        build_entry_parameters(
            method, method_args, equiv["methods"], catalog["methods"],
            self.transforms, params=params,
        )
        if module:
            build_entry_parameters(
                module, module_args, equiv["module"], catalog["module"],
                self.transforms, params=params,
            )
        return params
