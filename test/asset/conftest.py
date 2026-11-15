"""Fixtures shared by the tests of the assets."""

import pytest

import amac.config
from amac.amac import AMAC

BINARY_SOFTWARE = ("dftb+", "deMonNano", "orca")


@pytest.fixture
def offline_config(fake_executable, tmp_path, monkeypatch) -> dict:
    """Configuration with a fake executable and an empty basis directory.

    Binary software can then be created and translate parameters without
    the real program (nothing is run).
    """
    basis = tmp_path / "basis"
    basis.mkdir()
    config = {
        "software": {
            name: {"executable": str(fake_executable), "basis": str(basis)}
            for name in BINARY_SOFTWARE
        }
    }
    monkeypatch.setattr(amac.config, "CONFIGURE", config)
    return config


@pytest.fixture
def run_calc(tmp_path):
    """Return a function running one calculation through AMAC in ``tmp_path``.

    The function returns the calculated Instance.
    """

    def run(
        software,
        image,
        method,
        method_args,
        module,
        module_args=None,
        handlers=(),
        options=None,
        software_args=None,
    ):
        calc = AMAC(software=software, workdir=tmp_path / "run")
        if handlers:
            calc.handler_register(*handlers)
        calc.parameters_register(
            method=method,
            method_args=method_args,
            module=module,
            module_args=module_args or {},
            options=options,
            software_args=software_args,
        )
        calc.run(image)
        return calc.instance

    return run
