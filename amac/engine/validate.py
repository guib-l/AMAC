"""Check user arguments against the canonical catalog (``catalog/``)."""

from typing import Any, Mapping

from amac.engine.catalog import canonical_name, inheritance_chain

_BASIC_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool}


class CatalogError(ValueError):
    """Arguments not allowed by the catalog."""


def merged_attributes(name: str, catalog: Mapping[str, dict]) -> dict:
    """Return the attribute rules of ``name``, merged along its inheritance.

    A child overrides its parents; an attribute forbidden by a child is
    removed from the inherited ones.
    """
    mandatory: dict = {}
    allowed: dict = {}
    forbidden: set = set()
    for canonical in inheritance_chain(name, catalog):
        entry = catalog[canonical]
        for key in entry.get("forbidden-attribute") or ():
            mandatory.pop(key, None)
            allowed.pop(key, None)
            forbidden.add(key)
        own_mandatory = entry.get("mandatory-attribute") or {}
        own_allowed = entry.get("allowed-attribute") or {}
        mandatory.update(own_mandatory)
        allowed.update(own_allowed)
        forbidden -= own_mandatory.keys() | own_allowed.keys()
    return {
        "mandatory-attribute": mandatory,
        "allowed-attribute": allowed,
        "forbidden-attribute": sorted(forbidden),
    }


def validate(
        name: str, args: Mapping[str, Any] | None, catalog: Mapping[str, dict],
    ) -> None:
    """Check the arguments of a method or a module against the catalog.

    Args:
        name: Method or module name, canonical or alias, any case.
        args: User arguments (``method_args`` or ``module_args``).
        catalog: One section of :func:`amac.engine.catalog.load_catalog`.

    Raises:
        KeyError: If ``name`` is unknown to the catalog.
        CatalogError: If an argument is missing, unknown, forbidden or
            has a wrong value; every error is listed.
    """
    name = canonical_name(name, catalog)
    errors: list[str] = []
    _check_attributes(merged_attributes(name, catalog), args or {}, errors)
    if errors:
        raise CatalogError(f"{name}: " + "; ".join(errors))


def _check_attributes(
        rules: Mapping[str, Any],
        args: Mapping[str, Any],
        errors: list[str],
        path: str = "",
        parent: Any = None,
    ) -> None:
    """Check ``args`` against mandatory/allowed/forbidden ``rules``."""
    mandatory = rules.get("mandatory-attribute") or {}
    allowed = rules.get("allowed-attribute") or {}
    forbidden = set(rules.get("forbidden-attribute") or ())

    for key in mandatory:
        if key not in args:
            errors.append(f"{path}{key}: mandatory attribute missing")

    for key, value in args.items():
        where = f"{path}{key}"
        if key in forbidden:
            errors.append(f"{where}: forbidden attribute")
            continue
        spec = mandatory[key] if key in mandatory else allowed.get(key)
        if spec is None:
            errors.append(f"{where}: unknown attribute")
            continue
        authorized = spec.get("authorized-with")
        if authorized is not None and parent not in authorized:
            errors.append(
                f"{where}: not authorized with {parent!r} "
                f"(only with {authorized})"
            )
            continue
        _check_value(spec, value, errors, where)


def _check_value(
        spec: Mapping[str, Any], value: Any, errors: list[str], where: str,
    ) -> None:
    """Check one value: type, choices, range, then its children."""
    children = spec.get("children")
    sub_args: dict = {}
    if children is not None and isinstance(value, Mapping):
        sub_args = {k: v for k, v in value.items() if k != "value"}
        value = value.get("value")

    if value is not None:
        if "type" in spec and not _is_type(value, spec["type"]):
            errors.append(f"{where}: {value!r} is not of type {spec['type']}")
            return
        if "choices" in spec and value not in spec["choices"]:
            errors.append(f"{where}: {value!r} not in {spec['choices']}")
            return
        if "range" in spec and isinstance(value, (int, float)):
            low, high = spec["range"]
            if (low is not None and value < low) or (
                    high is not None and value > high):
                errors.append(f"{where}: {value!r} out of range {spec['range']}")
                return

    if children is not None:
        _check_attributes(children, sub_args, errors, f"{where}.", value)


def _is_type(value: Any, type_name: str) -> bool:
    """Return True if ``value`` matches a catalog type such as
    ``float``, ``list[int]`` or ``dict[str,float|list[float]]``."""
    type_name = type_name.replace(" ", "")
    options = _split(type_name, "|")
    if len(options) > 1:
        return any(_is_type(value, option) for option in options)
    if type_name.startswith("list[") and type_name.endswith("]"):
        item = type_name[5:-1]
        return isinstance(value, (list, tuple)) and all(
            _is_type(v, item) for v in value
        )
    if type_name.startswith("dict[") and type_name.endswith("]"):
        key_type, value_type = _split(type_name[5:-1], ",")
        return isinstance(value, Mapping) and all(
            _is_type(k, key_type) and _is_type(v, value_type)
            for k, v in value.items()
        )
    if type_name not in _BASIC_TYPES:
        raise ValueError(f"Unknown catalog type: {type_name!r}")
    # bool is a subclass of int: accepted only where a bool is expected.
    if isinstance(value, bool) and type_name != "bool":
        return False
    return isinstance(value, _BASIC_TYPES[type_name])


def _split(text: str, separator: str) -> list[str]:
    """Split ``text`` on ``separator`` outside of square brackets."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(text):
        depth += (char == "[") - (char == "]")
        if char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts
