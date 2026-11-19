from __future__ import annotations

import json
from pathlib import Path

# ----------------------------------------------------------------------
# Report (design doc, section 9)
# ----------------------------------------------------------------------


def make_report(
    status: str,
    code: str | None = None,
    message: str | None = None,
    vote: dict | None = None,
    ambiguities: list[str] | None = None,
    injected: list[str] | None = None,
    spec_hash_value: str | None = None,
    workdir: Path | str | None = None,
    products: dict | None = None,
) -> dict:
    """Assemble the report dict (written to products.json, printed)."""
    return {
        "status": status,
        "code": code,
        "message": message,
        "vote": vote,
        "ambiguities": ambiguities or [],
        "injected": injected or [],
        "spec_hash": spec_hash_value,
        "workdir": str(workdir) if workdir is not None else None,
        "products": products or {},
    }


def write_report(report: dict, workdir: Path | None) -> Path | None:
    """Write products.json in the workdir; no file when the workdir is absent."""
    if workdir is None:
        return None
    path = Path(workdir) / "products.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def write_llm_samples(samples: list[dict], workdir: Path | str) -> Path:
    """Write the raw LLM responses of the transcribe stage (provenance)."""
    path = Path(workdir) / "llm_samples.json"
    path.write_text(json.dumps(samples, indent=2, default=str) + "\n", encoding="utf-8")
    return path
