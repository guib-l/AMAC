from __future__ import annotations

from core import SPEC_FIELDS, SpecError, _sk_set
from support import _canon_name, _schema_names, allowed_dispersion, supporting_software_for

# ----------------------------------------------------------------------
# Stage 2 — VALIDATE
# ----------------------------------------------------------------------


def validate(
    spec: dict,
    schema: dict,
    software: str,
    defaults: dict | None = None,
    config: dict | None = None,
) -> list[SpecError]:
    """Check a spec against the catalog-derived schema. Pure function.

    Canonicalizes method/module/handler names in place. Returns the list of
    SpecErrors (empty when the spec is valid); missing mandatory attributes
    resolvable from defaults/config are not errors.
    """
    errors: list[SpecError] = []
    for key in sorted(set(spec) - SPEC_FIELDS):
        errors.append(SpecError(key, "INVALID_SPEC", f"unknown spec field {key!r}"))
    _check_software(spec, schema, errors)
    software = spec.get("software", software)  # canonical once checked
    _check_named_entry(spec, "method", "methods", schema, software, errors)
    _check_named_entry(spec, "module", "modules", schema, software, errors)
    _check_handlers(spec, schema, software, errors)
    _check_structure(spec, errors)
    _check_method_args(spec, schema, software, defaults, config, errors)
    _check_module_args(spec, schema, errors)
    _check_options(spec, schema, errors)
    _check_cross_rules(spec, software, errors)
    return errors


def _check_software(spec: dict, schema: dict, errors: list[SpecError]) -> None:
    """The software field must be a known software (name or alias)."""
    name = spec.get("software")
    if name is None:
        return
    canonical = _canon_name(name, "software", schema)
    if canonical is None:
        errors.append(
            SpecError(
                "software",
                "UNSUPPORTED_CATALOG",
                f"AMAC cannot express software {name!r}; supported: {sorted(schema['software'])}",
            )
        )
    else:
        spec["software"] = canonical


def _check_named_entry(
    spec: dict, key: str, section: str, schema: dict, software: str, errors: list[SpecError]
) -> None:
    """Check and canonicalize spec[key]; flag software-unsupported entries."""
    name = spec.get(key)
    if name is None:
        return
    canonical = _canon_name(name, section, schema)
    if canonical is None:
        errors.append(
            SpecError(
                key,
                "UNSUPPORTED_CATALOG",
                f"AMAC cannot express {key} {name!r}; supported: {sorted(schema[section])}",
            )
        )
        return
    spec[key] = canonical
    if software not in schema["software"]:
        # Unknown software is reported on its own field: no cross-checks.
        return
    found = _schema_names(supporting_software_for(section, canonical, schema), schema)
    if software not in found:
        others = [n for n in found if n != software]
        if others:
            hint = next((n for n in others if n in schema["software"]), others[0])
            errors.append(
                SpecError(
                    key,
                    "UNSUPPORTED_SOFTWARE",
                    f"{canonical} is supported only by {', '.join(others)} "
                    f"— rerun with --software {hint}?",
                )
            )
        else:
            errors.append(
                SpecError(
                    key,
                    "UNSUPPORTED_CATALOG",
                    f"AMAC cannot express {key} {canonical!r}: no supported software",
                )
            )


def _check_handlers(spec: dict, schema: dict, software: str, errors: list[SpecError]) -> None:
    """Each handler must belong to the software (per-software handler lists)."""
    if software not in schema["software"]:
        return
    handlers = spec.get("handlers")
    if handlers is None:
        return
    if not isinstance(handlers, list):
        errors.append(SpecError("handlers", "INVALID_SPEC", "handlers must be a list of names"))
        return
    available = schema["software"][software]["handlers"]
    for handler in handlers:
        key = str(handler).strip().lower().replace("_", "-")
        if key in available:
            continue
        others = [s for s in schema["software"] if key in schema["software"][s]["handlers"]]
        if others:
            errors.append(
                SpecError(
                    "handlers",
                    "UNSUPPORTED_SOFTWARE",
                    f"{handler!r} is supported only by {', '.join(others)} "
                    f"— rerun with --software {others[0]}?",
                )
            )
        else:
            errors.append(
                SpecError(
                    "handlers",
                    "INVALID_SPEC",
                    f"{handler!r} is not a handler of {software}; available: {available}",
                )
            )


def _check_structure(spec: dict, errors: list[SpecError]) -> None:
    """structure is one of {name}, {xyz}, {file} or a periodic cell block."""
    structure = spec.get("structure")
    if not isinstance(structure, dict):
        errors.append(
            SpecError(
                "structure",
                "INVALID_SPEC",
                "structure must be one of {name}, {xyz}, {file} or {cell, pbc, positions}",
            )
        )
        return
    keys = set(structure)
    simple = keys & {"name", "xyz", "file"}
    if simple:
        if len(simple) != 1 or any(not isinstance(structure[k], str) for k in simple):
            errors.append(
                SpecError(
                    "structure",
                    "INVALID_SPEC",
                    'structure: exactly one of {"name"}, {"xyz"}, {"file"} with a string value',
                )
            )
        return
    if {"cell", "positions"} <= keys:
        missing = [
            k
            for k in ("cell", "positions", "pbc", "symbols")
            if not isinstance(structure.get(k), list)
        ]
        if missing:
            errors.append(
                SpecError(
                    "structure",
                    "INVALID_SPEC",
                    f"periodic structure: missing or not a list: {missing}",
                )
            )
    else:
        errors.append(
            SpecError(
                "structure",
                "INVALID_SPEC",
                "structure must be one of {name}, {xyz}, {file} or {cell, pbc, positions, symbols}",
            )
        )


def _resolvable_mandatory(
    method: str | None, software: str, defaults: dict | None, config: dict | None
) -> set[str]:
    """Mandatory method attributes that resolve() can fill from defaults/config."""
    if defaults is None or config is None:
        return set()
    resolvable: set[str] = set()
    config_basis = ((config.get("software") or {}).get(software) or {}).get("basis")
    if config_basis:
        resolvable.add("basis")
    if method == "dftb-3" and config_basis:
        sk = _sk_set({"directory": config_basis}, defaults)
        if sk is not None and "hubbard-derivs" in sk:
            resolvable.add("hubbard-derivs")
    return resolvable


def _check_entry(
    entry: dict,
    args: dict,
    path: str,
    label: str,
    resolvable: set[str],
    schema: dict,
    software: str,
    errors: list[SpecError],
    check_mandatory: bool = True,
) -> None:
    """Check a method_args/module_args/options dict against its entry rules."""
    mandatory = entry.get("mandatory-attribute") or {}
    allowed = entry.get("allowed-attribute") or {}
    rules = {**mandatory, **allowed}
    for key, value in args.items():
        where = f"{path}.{key}"
        if key not in rules:
            errors.append(
                SpecError(
                    where, "INVALID_SPEC", f"{where}: unknown attribute (allowed: {sorted(rules)})"
                )
            )
            continue
        if key == "dispersion":
            _check_dispersion(value, where, software, rules[key], schema, errors)
        else:
            _check_value(rules[key], value, where, schema, errors)
    for key in mandatory:
        if key in args or key in resolvable or not check_mandatory:
            continue
        # Method mandates are resolvable from defaults.json (MISSING_DATA);
        # module/option mandates have no such source (INVALID_SPEC).
        code = "MISSING_DATA" if path == "method_args" else "INVALID_SPEC"
        message = (
            f"{path}.{key}: required for {label}; not in defaults.json"
            if code == "MISSING_DATA"
            else f"{path}.{key}: mandatory attribute missing"
        )
        errors.append(SpecError(f"{path}.{key}", code, message))


def _check_value(cspec: dict, value, where: str, schema: dict, errors: list[SpecError]) -> None:
    """Check one attribute value: type, choices, range, then its children."""
    from amac.engine.validate import _is_type

    children = cspec.get("children")
    sub_args: dict = {}
    if children is not None and isinstance(value, dict):
        sub_args = {k: v for k, v in value.items() if k != "value"}
        value = value.get("value")
    if value is not None:
        if "type" in cspec and not _is_type(value, cspec["type"]):
            errors.append(
                SpecError(
                    where, "INVALID_SPEC", f"{where}: {value!r} is not of type {cspec['type']}"
                )
            )
            return
        if "choices" in cspec and not _choice_ok(cspec, value, where, schema, errors):
            return
        if "range" in cspec and isinstance(value, (int, float)) and not isinstance(value, bool):
            low, high = cspec["range"]
            if (low is not None and value < low) or (high is not None and value > high):
                errors.append(
                    SpecError(
                        where, "INVALID_SPEC", f"{where}: {value!r} out of range {cspec['range']}"
                    )
                )
                return
    if children is not None:
        _check_children(cspec["children"], sub_args, where, value, schema, errors)


def _choice_ok(cspec: dict, value, where: str, schema: dict, errors: list[SpecError]) -> bool:
    """Check a value against choices, with alias tolerance for data lists."""
    choices = cspec["choices"]
    if cspec.get("choices-from"):
        # Data list (basis-sets, functionals): canonical name or alias, any case.
        data = schema["data"][cspec["choices-from"]["list"].lower()]
        for canonical, aliases in data.items():
            if value.lower() == canonical or value.lower() in (a.lower() for a in aliases):
                return True
        errors.append(SpecError(where, "INVALID_SPEC", f"{where}: {value!r} not in {choices}"))
        return False
    if not isinstance(value, str) or value.lower() not in {c.lower() for c in choices}:
        errors.append(SpecError(where, "INVALID_SPEC", f"{where}: {value!r} not in {choices}"))
        return False
    return True


def _check_children(
    children: dict,
    sub_args: dict,
    where: str,
    parent_value,
    schema: dict,
    errors: list[SpecError],
) -> None:
    """Check the sub-attributes of a value with children (e.g. dispersion)."""
    rules = {
        **(children.get("mandatory-attribute") or {}),
        **(children.get("allowed-attribute") or {}),
    }
    for key, value in sub_args.items():
        sub = f"{where}.{key}"
        spec = rules.get(key)
        if spec is None:
            errors.append(
                SpecError(
                    sub, "INVALID_SPEC", f"{sub}: unknown attribute (allowed: {sorted(rules)})"
                )
            )
            continue
        if "authorized-with" in spec and parent_value not in spec["authorized-with"]:
            errors.append(
                SpecError(
                    sub,
                    "INVALID_SPEC",
                    f"{sub}: not authorized with {parent_value!r} (only with {spec['authorized-with']})",
                )
            )
            continue
        _check_value(spec, value, sub, schema, errors)
    for key in children.get("mandatory-attribute") or {}:
        if key not in sub_args:
            errors.append(
                SpecError(
                    f"{where}.{key}", "INVALID_SPEC", f"{where}.{key}: mandatory attribute missing"
                )
            )


def _check_dispersion(
    value, where: str, software: str, cspec: dict, schema: dict, errors: list[SpecError]
) -> None:
    """Dispersion cross-rules: per-software models, 'none', then damping keys."""
    model = value.get("value") if isinstance(value, dict) else value
    choices = cspec.get("choices") or []
    if model is None:
        errors.append(
            SpecError(
                where, "INVALID_SPEC", f"{where}: a dispersion model is required (one of {choices})"
            )
        )
        return
    if model == "none":
        if software != "dftb+":
            errors.append(
                SpecError(
                    where,
                    "UNSUPPORTED_SOFTWARE",
                    f"{where}: 'none' not supported by {software} "
                    "(its dispersion is a program default, it cannot be disabled)",
                )
            )
        return
    if not isinstance(model, str) or model.lower() not in {c.lower() for c in choices}:
        errors.append(SpecError(where, "INVALID_SPEC", f"{where}: {model!r} not in {choices}"))
        return
    supported = {s.lower() for s in allowed_dispersion(software)}
    if model.lower() not in supported:
        others = [
            s
            for s in schema["software"]
            if model.lower() in {x.lower() for x in allowed_dispersion(s)}
        ]
        if others:
            errors.append(
                SpecError(
                    where,
                    "UNSUPPORTED_SOFTWARE",
                    f"{model!r} is supported only by {', '.join(others)} — rerun with --software {others[0]}?",
                )
            )
        else:
            errors.append(
                SpecError(
                    where, "UNSUPPORTED_CATALOG", f"{model!r} is not supported by any software"
                )
            )
        return
    if isinstance(value, dict) and cspec.get("children"):
        sub_args = {k: v for k, v in value.items() if k != "value"}
        _check_children(cspec["children"], sub_args, where, model, schema, errors)


def _check_method_args(
    spec: dict, schema: dict, software: str, defaults: dict | None, config: dict | None, errors
) -> None:
    """method_args against the merged rules of the resolved method."""
    method = spec.get("method")
    if method is None or method not in schema["methods"]:
        # The method itself is already reported: no rules to check against.
        return
    args = spec.get("method_args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        errors.append(SpecError("method_args", "INVALID_SPEC", "method_args must be an object"))
        return
    resolvable = _resolvable_mandatory(method, software, defaults, config)
    # Unknown software is reported on its own field: no mandate checks.
    _check_entry(
        schema["methods"][method],
        args,
        "method_args",
        method,
        resolvable,
        schema,
        software,
        errors,
        check_mandatory=software in schema["software"],
    )


def _check_module_args(spec: dict, schema: dict, errors: list[SpecError]) -> None:
    """module_args against the merged rules of the resolved module."""
    module = spec.get("module")
    if module is None or module not in schema["modules"]:
        # The module itself is already reported: no rules to check against.
        return
    args = spec.get("module_args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        errors.append(SpecError("module_args", "INVALID_SPEC", "module_args must be an object"))
        return
    _check_entry(schema["modules"][module], args, "module_args", module, set(), schema, "", errors)


def _check_options(spec: dict, schema: dict, errors: list[SpecError]) -> None:
    """Each option (e.g. solvation) against its merged rules."""
    options = spec.get("options")
    if options is None:
        return
    if not isinstance(options, dict):
        errors.append(SpecError("options", "INVALID_SPEC", "options must be an object"))
        return
    for name, args in options.items():
        canonical = _canon_name(name, "options", schema)
        if canonical is None:
            errors.append(
                SpecError(
                    f"options.{name}",
                    "UNSUPPORTED_CATALOG",
                    f"AMAC cannot express option {name!r}; supported: {sorted(schema['options'])}",
                )
            )
            continue
        if not isinstance(args, dict):
            errors.append(
                SpecError(f"options.{name}", "INVALID_SPEC", f"options.{name} must be an object")
            )
            continue
        _check_entry(
            schema["options"][canonical],
            args,
            f"options.{canonical}",
            name,
            set(),
            schema,
            "",
            errors,
        )


def _check_cross_rules(spec: dict, software: str, errors: list[SpecError]) -> None:
    """Cross-field rules beyond the per-attribute catalog checks."""
    args = spec.get("method_args") or {}
    if not isinstance(args, dict):
        return
    structure = spec.get("structure") or {}
    if "kpoints" in args and not (isinstance(structure, dict) and "cell" in structure):
        errors.append(
            SpecError(
                "method_args.kpoints",
                "INVALID_SPEC",
                "kpoints requires a periodic structure (cell and pbc)",
            )
        )
    # DFTB-3 with dftb+: dispersion is required (design doc, section 13.2,
    # resolved: hard error). 'none' is the explicit no-dispersion value.
    if spec.get("method") == "dftb-3" and software == "dftb+":
        model = args.get("dispersion")
        model = model.get("value") if isinstance(model, dict) else model
        if model is None:
            errors.append(
                SpecError(
                    "method_args.dispersion",
                    "INVALID_SPEC",
                    "method_args.dispersion: required for dftb-3 with dftb+ "
                    "(one of the dispersion choices, or 'none' if no dispersion was asked)",
                )
            )
