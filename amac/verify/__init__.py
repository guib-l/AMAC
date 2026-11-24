"""Diagnose whether AMAC can run on this machine.

``check()`` is the entry point. The actual checks are added step by step:
the core checks and the configuration schema in 1.2, the per-software
checks in 1.3.
"""

from __future__ import annotations

import json
from pathlib import Path

from amac.utils.exception import ConfigError
from amac.verify.core import check_core
from amac.verify.report import Check, Report
from amac.verify.smoke import run_smoke

__all__ = ["Check", "Report", "check", "load_config"]

DEFAULT_PATH = "config-amac.json"


def load_config(path: str | Path = DEFAULT_PATH) -> dict:
    """Read a JSON configuration file.

    Raises:
        ConfigError: The file is missing, unreadable, or not a JSON object.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"no configuration file at {path.resolve()}")
    try:
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    if not isinstance(config, dict):
        raise ConfigError(f"{path}: the configuration must be a JSON object")
    return config


def check(
    config: dict | None = None,
    *,
    path: str | Path = DEFAULT_PATH,
    run: bool = False,
    workdir: str | Path | None = None,
) -> Report:
    """Run the installation checks and return the report.

    Args:
        config: AMAC configuration dict; read from ``path`` when None.
        path: Configuration file used when ``config`` is None.
        run: Also run one H2 single point per software that passed the
            static checks (submitted to the scheduler when one is configured).
        workdir: Parent directory of those runs; a new hidden directory in
            the current one when None.

    Raises:
        ConfigError: ``config`` is None and ``path`` cannot be read.
    """
    if config is None:
        config = load_config(path)
    report = Report()
    check_core(report, config)
    if run:
        if any(c.scope == "core" and c.status == "fail" for c in report.checks):
            report.add("core", "run", "skip", "core checks failed")
        else:
            run_smoke(report, config, workdir=workdir)
    return report
