"""Tests of amac.engine.software: registry, configuration and run template."""

from pathlib import Path

import pytest

import amac
from amac.asset import Software
from engine.conftest import FAKE_ENERGY, software_fake


def test_create_by_name_alias_any_case():
    """A software is created from its name or an alias, any case."""
    for name in ("fake-amac", "FAKE-AMAC", "fake", "Fake"):
        assert isinstance(Software.create(name), software_fake)


def test_create_unknown():
    """An unknown software is a KeyError listing the known ones."""
    with pytest.raises(KeyError, match="Unknown software 'nothing'"):
        Software.create("nothing")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("deMonNano", "deMonNano"), ("demon-nano", "deMonNano"), ("dftbplus", "dftb+"),
     ("DFTB+", "dftb+"), ("ORCA", "orca"), ("PySCF", "pyscf")],
)
def test_assets_registered(name, expected):
    """Every AMAC asset is registered with its aliases."""
    assert Software._registry[name.upper()].name == expected


def test_config_section_empty():
    """Without configuration, the section is empty."""
    assert software_fake.config_section() == {}


def test_config_section_by_alias():
    """The section can be written under an alias."""
    amac.configure(config={"software": {"fake": {"basis": "/b"}}})
    assert software_fake.config_section() == {"basis": "/b"}


def test_options_from_config_and_overrides(fake_executable):
    """Configuration options are kept; constructor arguments override them."""
    amac.configure(
        config={
            "software": {
                "fake-amac": {
                    "executable": str(fake_executable),
                    "basis": "/config",
                    "env": {"A": 1},
                    "timeout": 10,
                }
            }
        }
    )
    soft = Software.create("fake", basis="/argument")
    assert soft.options["basis"] == "/argument"
    assert soft.executable == fake_executable
    assert soft.program.env == {"A": "1"}
    assert soft.program.timeout == 10


def test_explicit_executable_and_env(fake_executable):
    """executable= and env= arguments win over the configuration."""
    amac.configure(config={"software": {"fake-amac": {"executable": "/config/exe", "env": {"A": "1"}}}})
    soft = Software.create("fake", executable=fake_executable, env={"B": "2"})
    assert soft.executable == fake_executable
    assert soft.program.env == {"B": "2"}


def test_relative_executable_refused():
    """A relative executable from the configuration is refused."""
    amac.configure(config={"software": {"fake-amac": {"executable": "fake-program"}}})
    with pytest.raises(ValueError, match="must be absolute"):
        Software.create("fake")


@pytest.mark.parametrize("name", ["dftb+", "deMonNano", "orca"])
def test_binary_assets_need_an_executable(name):
    """Binary software cannot be created without a configured executable."""
    with pytest.raises(ValueError, match="no executable configured"):
        Software.create(name)


def test_pyscf_needs_no_executable():
    """PySCF runs in process: no executable."""
    assert Software.create("pyscf").executable is None


def test_equiv_path_next_to_the_asset():
    """equiv.json is read next to the module of the asset."""
    path = Software._registry["DFTB+"].equiv_path()
    assert path == Path(amac.__file__).parent / "asset" / "dftbplus" / "equiv.json"
    assert path.is_file()


def test_run_template(fake_soft, make_instance):
    """run() translates, calculates and applies the handlers."""
    instance = make_instance(
        fake_soft,
        method="hf",
        method_args={"basis": "sto-3g"},
        module="sp",
        handler=("lowest-energy", "parameters"),
    )
    results = fake_soft.run(instance)
    assert results["energy"] == FAKE_ENERGY
    assert instance.res.product["lowest-energy"] == FAKE_ENERGY
    assert instance.res.product["parameters"]["run"] == "sp"


def test_run_software_args_last(fake_soft, make_instance):
    """Raw software arguments of this software (name or alias) are written last."""
    instance = make_instance(
        fake_soft,
        method="hf",
        method_args={"basis": "sto-3g"},
        handler=("parameters",),
        software_args={
            "FAKE": {"basis": "raw-basis", "extra.key": 1},
            "other-software": {"basis": "ignored"},
        },
    )
    fake_soft.run(instance)
    parameters = instance.res.product["parameters"]
    assert parameters["basis"] == "raw-basis"
    assert parameters["extra"] == {"key": 1}


def test_run_module_needs_handlers(fake_soft, make_instance):
    """A module whose mandatory handlers are missing is refused."""
    instance = make_instance(fake_soft, method="hf", method_args={"basis": "sto-3g"}, module="freq")
    with pytest.raises(NotImplementedError, match="missing handlers"):
        fake_soft.run(instance)


def test_to_dict(fake_soft):
    """to_dict describes the program and the options."""
    data = fake_soft.to_dict()
    assert data["name"] == "fake-amac"
    assert data["alias"] == ("fake",)
    assert data["process"] == "inprocess"
    assert data["process_unit"] == 1
    assert data["executable"] is None
