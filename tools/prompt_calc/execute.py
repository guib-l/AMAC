from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core import Execution, Failure, Resolved, _dispersion_value, load_schema, spec_hash
from support import _schema_names, supporting_software_for

if TYPE_CHECKING:  # annotation-only imports (both are imported lazily in-code)
    import ase

    import amac.amac


# ----------------------------------------------------------------------
# Stage 4 — BUILD IMAGE
# ----------------------------------------------------------------------


def build_image(structure: dict, aliases: dict | None = None) -> "ase.Atoms":
    """Build the ase.Atoms image of a spec structure. Same spec, same image.

    Raises:
        Failure: INVALID_SPEC when the structure cannot be built.
    """
    import ase
    import ase.build
    import ase.io

    if name := structure.get("name"):
        name = (aliases or {}).get(str(name).lower(), name)
        try:
            return ase.build.molecule(name)
        except (KeyError, ValueError) as error:
            raise Failure("INVALID_SPEC", f"structure.name: unknown molecule {name!r}") from error
    if xyz := structure.get("xyz"):
        try:
            return ase.io.read(io.StringIO(xyz), "xyz")
        except (OSError, ValueError) as error:
            raise Failure("INVALID_SPEC", "structure.xyz: cannot parse xyz text") from error
    if file := structure.get("file"):
        path = Path(file)
        if not path.is_file():
            raise Failure("INVALID_SPEC", f"structure.file: no such file: {path}")
        return ase.io.read(path)
    try:
        return ase.Atoms(
            structure["symbols"],
            positions=structure["positions"],
            cell=structure["cell"],
            pbc=structure["pbc"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise Failure(
            "INVALID_SPEC",
            "structure: a periodic image needs cell, pbc, positions and symbols",
        ) from error


# ----------------------------------------------------------------------
# Stage 5 — EXECUTE
# ----------------------------------------------------------------------


def make_workdir(spec: dict, run_root: Path = Path(".run"), fresh: bool = False) -> Path:
    """Create .run/<software>/<method>/<hash> and write spec.json into it."""
    root = Path(run_root) / spec["software"] / spec["method"]
    if not fresh:
        workdir = root / spec_hash(spec)
    else:
        # Microsecond stamp plus a numeric suffix: two fresh runs in the
        # same instant still get distinct workdirs. (strftime has no
        # %f, so the fractional part comes from time.time().)
        now = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S") + f".{int((now % 1) * 1_000_000):06d}"
        workdir = root / f"{spec_hash(spec)}-{stamp}"
        counter = 1
        while workdir.exists():
            workdir = root / f"{spec_hash(spec)}-{stamp}-{counter}"
            counter += 1
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "spec.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return workdir


def _workdir_inputs(workdir: Path) -> list[str]:
    """Sorted file names composed in the workdir (spec.json aside)."""
    return sorted(p.name for p in workdir.iterdir() if p.name != "spec.json")


def _is_empty_product(value) -> bool:
    """True for a product a handler left empty: None or an empty container."""
    if value is None:
        return True
    try:
        return len(value) == 0
    except TypeError:
        return False


def _unsupported_message(spec: dict, error: Exception) -> str:
    """UNSUPPORTED_SOFTWARE message with a --software suggestion when known."""
    base = str(error)
    schema = load_schema()
    candidates = []
    if spec.get("method"):
        candidates.append(("methods", spec["method"]))
    if spec.get("module"):
        candidates.append(("module", spec["module"]))
    candidates.extend(("options", name) for name in spec.get("options") or ())
    for section, name in candidates:
        found = supporting_software_for(section, name, schema)
        others = [n for n in _schema_names(found, schema) if n != spec.get("software")]
        if others:
            hint = next((n for n in others if n in schema["software"]), None)
            text = f"{name}: {base} Supported only by {', '.join(others)}"
            if hint:
                text += f" — rerun with --software {hint}?"
            return text
    return base


def _new_calc(spec: dict, workdir: Path):
    """Create the AMAC object; an unconfigurable software is RUNTIME_FAILURE."""
    from amac.amac import AMAC

    try:
        return AMAC(
            software=spec["software"], workdir=workdir, label=f"{spec['method']}-{spec_hash(spec)}"
        )
    except ValueError as error:
        raise Failure(
            "RUNTIME_FAILURE",
            f"cannot configure {spec['software']}: {error}",
            workdir=workdir,
        ) from error


def compose(
    resolved: Resolved,
    image: "ase.Atoms",
    config: dict,
    run_root: Path = Path(".run"),
    fresh: bool = False,
) -> tuple[Path, "amac.amac.AMAC"]:
    """Create the AMAC instance and compose the inputs, launch nothing.

    Returns ``(workdir, calc)``. The workdir is created (and kept) even when
    the following steps fail: it is the forensic artifact.

    Raises:
        Failure: typed code for every rejection (see design doc, section 8).
    """
    import amac
    from amac.engine.validate import CatalogError

    spec = resolved.spec
    workdir = make_workdir(spec, run_root, fresh)
    amac.configure(config)
    calc = _new_calc(spec, workdir)
    try:
        # One call with every handler: registering one by one would drop the
        # previous ones (design doc, section 7: handler_register(*handlers)).
        calc.handler_register(*spec.get("handlers") or ())
        args = dict(spec.get("method_args") or {})
        if _dispersion_value(args.get("dispersion")) == "none":
            if spec["software"] != "dftb+":
                raise Failure(
                    "UNSUPPORTED_SOFTWARE",
                    f"method_args.dispersion: 'none' not supported by {spec['software']} "
                    "(its dispersion is a program default, it cannot be disabled)",
                    workdir=workdir,
                )
            args.pop("dispersion")
        calc.parameters_register(
            method=spec["method"],
            method_args=args,
            module=spec.get("module"),
            module_args=spec.get("module_args") or {},
            options=spec.get("options") or {},
        )
        calc.instance.props(image=image)
        calc._soft.parameters = calc._soft.collect(calc.instance)
        calc._soft.prepare(calc.instance)
    except NotImplementedError as error:
        raise Failure(
            "UNSUPPORTED_SOFTWARE", _unsupported_message(spec, error), workdir=workdir
        ) from error
    except CatalogError as error:
        raise Failure("INVALID_SPEC", str(error), workdir=workdir) from error
    except ValueError as error:
        # Asset guards: the software rejects the composed parameters.
        raise Failure(
            "UNSUPPORTED_SOFTWARE", f"{spec['software']}: {error}", workdir=workdir
        ) from error
    except KeyError as error:
        raise Failure("INVALID_SPEC", f"{spec['software']}: {error}", workdir=workdir) from error
    return workdir, calc


def execute(
    resolved: Resolved,
    image,
    config: dict,
    run_root: Path = Path(".run"),
    fresh: bool = False,
    dry_run: bool = False,
) -> Execution:
    """Run the AMAC calculation (or only compose, when ``dry_run``).

    Raises:
        Failure: RUNTIME_FAILURE when the run itself fails (the workdir is
            kept as the forensic artifact), UNSUPPORTED_SOFTWARE, ...
    """
    from amac.utils.exception import AmacError

    spec = resolved.spec
    workdir, calc = compose(resolved, image, config, run_root, fresh)
    if dry_run:
        return Execution(workdir=workdir, products={}, inputs=_workdir_inputs(workdir))
    try:
        calc.run(image)
    except AmacError as error:
        raise Failure(
            "RUNTIME_FAILURE",
            f"{spec['software']}: {error}\nworkdir (inputs + logs kept): {workdir}",
            workdir=workdir,
        ) from error
    except (KeyError, ValueError) as error:
        # The program ran but a handler could not extract its product.
        raise Failure(
            "RUNTIME_FAILURE",
            f"{spec['software']}: no product: {error}\nworkdir (inputs + logs kept): {workdir}",
            workdir=workdir,
        ) from error
    handlers = tuple(spec.get("handlers") or ())
    products = {h: calc.instance.res.product.get(h) for h in handlers}
    empty = [h for h in handlers if _is_empty_product(products.get(h))]
    if empty:
        # Design doc, section 8: a finished run with an empty handler
        # product is a RUNTIME_FAILURE, not a silent "succeeded".
        raise Failure(
            "RUNTIME_FAILURE",
            f"{spec['software']}: the run finished but no product for handler(s): "
            f"{', '.join(empty)}\nworkdir (inputs + logs kept): {workdir}",
            workdir=workdir,
        )
    return Execution(workdir=workdir, products=products, inputs=_workdir_inputs(workdir))
