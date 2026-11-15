"""Tests of amac.amac.AMAC with the fake software of the engine tests."""

import pytest
from engine.conftest import FAKE_ENERGY

from amac.amac import AMAC


@pytest.fixture
def calc(tmp_path):
    return AMAC(software="fake-amac", workdir=tmp_path / "run", label="water")


def test_amac_creates_software_and_instance(calc, tmp_path):
    """The software and the active instance are created."""
    assert calc._soft.name == "fake-amac"
    assert calc.instance.ctx.workdir == tmp_path / "run"


def test_handler_register(calc):
    """Handler names are normalized and stored on the instance."""
    calc.handler_register("Lowest_Energy")
    assert calc.instance.props.handler == ("lowest-energy",)


def test_handler_register_unknown(calc):
    """An unknown handler is refused."""
    with pytest.raises(KeyError):
        calc.handler_register("dipole")


def test_parameters_register_new_instance(calc):
    """Registering parameters creates a new instance and keeps the handlers."""
    calc.handler_register("lowest-energy")
    first = calc.instance
    calc.parameters_register(method="hf", method_args={"basis": "sto-3g"}, module="sp")
    assert calc.instance is not first
    assert calc.instance.props.method == "hf"
    assert calc.instance.props.handler == ("lowest-energy",)
    assert calc.instance.props.software_args == {}
    assert calc.instance.props.options == {}


def test_run(calc, water):
    """run() executes the active instance and fills its products."""
    calc.handler_register("lowest-energy")
    calc.parameters_register(method="hf", method_args={"basis": "sto-3g"}, module="sp")
    calc.run(water)
    instance = calc.instance
    assert instance.res.complet
    assert instance.res.product == {"lowest-energy": FAKE_ENERGY}
    assert instance.props.image is water
    assert instance.duree.duree is not None
