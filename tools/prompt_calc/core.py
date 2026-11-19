from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "spec_schema.json"
DEFAULTS_PATH = HERE / "defaults.json"

EXIT_OK = 0
EXIT_RUNTIME_FAILURE = 1
EXIT_INVALID_SPEC = 2
EXIT_UNSUPPORTED = 3
EXIT_USER_ABORT = 4

# Failure code -> exit code (design doc, section 8).
CODES: dict[str, int] = {
    "INVALID_SPEC": EXIT_INVALID_SPEC,
    "AMBIGUOUS": EXIT_INVALID_SPEC,
    "UNSUPPORTED_CATALOG": EXIT_UNSUPPORTED,
    "UNSUPPORTED_SOFTWARE": EXIT_UNSUPPORTED,
    "MISSING_DATA": EXIT_UNSUPPORTED,
    "RUNTIME_FAILURE": EXIT_RUNTIME_FAILURE,
    "USER_ABORT": EXIT_USER_ABORT,
}

# Top-level fields a spec may hold.
SPEC_FIELDS = {
    "software",
    "method",
    "module",
    "structure",
    "method_args",
    "module_args",
    "options",
    "handlers",
    "ambiguities",
}

# Methods with SCC cycles: the scc defaults of defaults.json apply to them.
SCC_METHODS = ("dftb-2", "dftb-3", "ci-dftb")

# Dispersion models that need SK-set damping parameters on dftb+ (the DFTB+
# asset refuses a D3/D4 block without them — see amac.asset.dftbplus.soft).
DAMPING_MODELS_DFTBPLUS = ("d3-bj", "d3-zero", "d4")


@dataclass
class SpecError:
    """One validation error with its typed code and an actionable message."""

    field: str
    code: str
    message: str


@dataclass
class Failure(Exception):
    """Typed terminal failure of the pipeline (design doc, section 8)."""

    code: str
    message: str
    field: str | None = None
    workdir: Path | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass
class Resolved:
    """A validated spec completed from defaults.json."""

    spec: dict
    injected: list[str]


@dataclass
class Execution:
    """Outcome of the execute stage: workdir, products, composed inputs."""

    workdir: Path
    products: dict
    inputs: list[str]


@dataclass
class Vote:
    """Outcome of the N-sample vote (design doc, section 3.3)."""

    spec: dict | None
    count: str
    confidence: str
    fields: list[str]
    variants: list[dict]
    ambiguities: list[str]


@dataclass
class _Context:
    """Mutable state carried across pipeline stages for the report."""

    spec: dict | None = None
    injected: list[str] = field(default_factory=list)
    vote: dict | None = None
    ambiguities: list[str] = field(default_factory=list)
    raw: list[dict] = field(default_factory=list)  # raw LLM responses (provenance)
    spec_hash: str | None = None
    workdir: Path | None = None


# ----------------------------------------------------------------------
# Loading and canonical forms
# ----------------------------------------------------------------------


def load_schema() -> dict:
    """Read the generated spec schema (single source of truth: the catalog)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_defaults() -> dict:
    """Read the defaults table (design doc, section 5)."""
    return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))


def canonical_json(obj: dict) -> str:
    """Canonical JSON text (sorted keys, no spaces) used for hashing and voting."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canon_software(name: str, schema: dict) -> str:
    """Return the canonical software name from a name or alias, any case."""
    key = str(name).strip().lower()
    for canonical, entry in schema["software"].items():
        if key == canonical.lower() or key in {a.lower() for a in entry.get("alias", [])}:
            return canonical
    raise Failure(
        "UNSUPPORTED_CATALOG",
        f"AMAC cannot express software {name!r}; supported: {sorted(schema['software'])}",
        field="software",
    )


def spec_hash(spec: dict) -> str:
    """10-hex sha256 of the canonical resolved spec (workdir name)."""
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()[:10]


def _sk_set(basis, defaults: dict) -> dict | None:
    """The defaults sk-sets entry matching the basis directory, if any."""
    directory = ""
    if isinstance(basis, dict):
        directory = str(basis.get("directory") or "")
    elif isinstance(basis, str):
        directory = basis
    # Dots are mapped to dashes so a "mio-1.1.0" basis matches "mio-1-1".
    normalized = directory.replace("\\", "/").replace(".", "-").lower()
    if not normalized:
        return None
    for entry in defaults.get("sk-sets", {}).values():
        if any(token.lower() in normalized for token in entry.get("match", [])):
            return entry
    return None


def _dispersion_value(value) -> str | None:
    """The dispersion model of a dispersion attribute (string or object)."""
    if isinstance(value, dict):
        return value.get("value")
    return value
