from __future__ import annotations

import copy

from core import (
    DAMPING_MODELS_DFTBPLUS,
    SCC_METHODS,
    Failure,
    Resolved,
    _dispersion_value,
    _sk_set,
)

# ----------------------------------------------------------------------
# Stage 3 — RESOLVE
# ----------------------------------------------------------------------


def resolve(
    spec: dict,
    defaults: dict,
    config: dict,
    aliases: dict | None = None,
) -> Resolved:
    """Fill a validated spec from defaults.json (design doc, section 5).

    Priority: user spec > defaults table > hard error. Every value injected
    is listed in ``Resolves.injected``. Raises Failure(MISSING_DATA) when a
    mandatory value has no table entry.
    """
    aliases = aliases or {}
    resolved = copy.deepcopy(spec)
    injected: list[str] = []
    for key in ("method", "module"):
        name = resolved.get(key)
        if isinstance(name, str):
            resolved[key] = aliases.get(name.strip().lower()) or name.strip().lower()
    software = resolved["software"]
    method = resolved.get("method")
    args = resolved.setdefault("method_args", {})
    _resolve_structure(resolved, defaults, injected)
    _resolve_basis(args, software, config, injected)
    sk = _sk_set(args.get("basis"), defaults)
    if method == "dftb-3":
        _resolve_dftb3(args, sk, defaults, injected)
    _resolve_scc(args, method, defaults, injected)
    _resolve_dispersion(args, software, sk, defaults, injected)
    return Resolved(spec=resolved, injected=sorted(injected))


def _resolve_structure(resolved: dict, defaults: dict, injected: list[str]) -> None:
    """Map a structure name through molecule-aliases (eau -> H2O, ...)."""
    structure = resolved.get("structure") or {}
    name = structure.get("name")
    if isinstance(name, str):
        formula = defaults.get("molecule-aliases", {}).get(name.lower(), name)
        if formula != name:
            structure["name"] = formula
            injected.append("structure.name")


def _resolve_basis(args: dict, software: str, config: dict, injected: list[str]) -> None:
    """The basis directory defaults to the configured software's basis."""
    config_basis = ((config.get("software") or {}).get(software) or {}).get("basis")
    basis = args.get("basis")
    if basis is None:
        if not config_basis:
            raise Failure(
                "MISSING_DATA",
                f"method_args.basis required for {software}; no 'basis' in the configuration",
                field="method_args.basis",
            )
        args["basis"] = {"directory": config_basis}
        injected.append("method_args.basis.directory")
    elif isinstance(basis, dict) and "directory" not in basis and config_basis:
        basis["directory"] = config_basis
        injected.append("method_args.basis.directory")


def _resolve_dftb3(args: dict, sk: dict | None, defaults: dict, injected: list[str]) -> None:
    """DFTB-3 conventions: hubbard-derivs from the SK table, h-correction."""
    if "hubbard-derivs" not in args:
        if sk is None or "hubbard-derivs" not in sk:
            raise Failure(
                "MISSING_DATA",
                "method_args.hubbard-derivs required for dftb-3; not in defaults.json "
                "(unknown SK set — never guess U-derivatives)",
                field="method_args.hubbard-derivs",
            )
        args["hubbard-derivs"] = copy.deepcopy(sk["hubbard-derivs"])
        injected.append("method_args.hubbard-derivs")
    if "h-correction" not in args:
        conventions = defaults.get("dftb-3-conventions", {})
        if "h-correction" in conventions:
            args["h-correction"] = copy.deepcopy(conventions["h-correction"])
            injected.append("method_args.h-correction")


def _resolve_scc(args: dict, method: str | None, defaults: dict, injected: list[str]) -> None:
    """scc defaults (scc-max, filling) for the SCC methods."""
    if method not in SCC_METHODS:
        return
    for key, value in defaults.get("scc", {}).items():
        if key not in args:
            args[key] = copy.deepcopy(value)
            injected.append(f"method_args.{key}")


def _resolve_dispersion(
    args: dict, software: str, sk: dict | None, defaults: dict, injected: list[str]
) -> None:
    """Inject the SK-set damping parameters of a D3/D4 dispersion."""
    raw = args.get("dispersion")
    if raw is None:
        return
    model = _dispersion_value(raw)
    if model is None or model == "none":
        # 'none' stays as-is: the executor omits the dispersion attribute.
        return
    damping = (sk or {}).get("dispersion-damping", {}).get(model)
    if damping is None:
        if software == "dftb+" and model in DAMPING_MODELS_DFTBPLUS:
            raise Failure(
                "MISSING_DATA",
                f"method_args.dispersion.damping required for {model} with {software}; "
                "not in defaults.json (unknown SK set)",
                field="method_args.dispersion",
            )
        return
    if isinstance(raw, str):
        args["dispersion"] = {"value": model, **copy.deepcopy(damping)}
        injected.append("method_args.dispersion.damping")
    elif isinstance(raw, dict):
        merged = False
        for key, value in damping.items():
            if key not in raw:
                raw[key] = value
                merged = True
        if merged:
            injected.append("method_args.dispersion.damping")
