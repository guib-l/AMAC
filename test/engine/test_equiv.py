"""Tests of amac.engine.equiv: canonical parameters -> software parameters."""

import pytest

from amac.engine.equiv import Equivalence, build_entry_parameters, load_equiv, set_path
from amac.engine.validate import CatalogError
from engine.conftest import FAKE_EQUIV

DOUBLE = {"double": lambda value: 2 * value}


@pytest.fixture
def equivalence():
    return Equivalence(FAKE_EQUIV, DOUBLE)


# ----------------------------------------------------------------------
# set_path
# ----------------------------------------------------------------------


def test_set_path_creates_nodes():
    """Missing nodes of a dotted path are created."""
    tree = {}
    set_path(tree, "Hamiltonian.DFTB.Scc", True)
    assert tree == {"Hamiltonian": {"DFTB": {"Scc": True}}}


def test_set_path_merges_dicts():
    """A dict value is merged into an existing dict node."""
    tree = {"a": {"b": 1}}
    set_path(tree, "a", {"c": 2})
    assert tree == {"a": {"b": 1, "c": 2}}


def test_set_path_replaces_scalar():
    """A scalar value replaces the existing one."""
    tree = {"a": {"b": 1}}
    set_path(tree, "a.b", 2)
    assert tree == {"a": {"b": 2}}


def test_set_path_copies_the_value():
    """The stored value is a copy: later changes do not leak."""
    value = {"x": [1]}
    tree = {}
    set_path(tree, "a", value)
    value["x"].append(2)
    assert tree == {"a": {"x": [1]}}


# ----------------------------------------------------------------------
# load_equiv
# ----------------------------------------------------------------------


def test_load_equiv_flattens_families():
    """Entries grouped under a family are flattened, names upper-case."""
    equiv = load_equiv(FAKE_EQUIV)
    assert {"HF", "DFT", "MP2", "DFTB-1", "DFTB-2"} == set(equiv["methods"])
    assert "DFTB" not in equiv["methods"]
    assert equiv["default"]["set"] == {"general.title": "fake", "general.level": 0}


# ----------------------------------------------------------------------
# Equivalence.build with the real catalog
# ----------------------------------------------------------------------


def test_build_default_method_module(equivalence):
    """Default, method and module values are written; arguments translated."""
    params = equivalence.build("hf", {"basis": "STO-3G", "charge": 1.0}, "sp", {})
    assert params == {
        "general": {"title": "fake", "level": 0},
        "method": "hf",
        "basis": "sto-3g",
        "system": {"charge": 1.0},
        "run": "sp",
    }


def test_build_inheritance(equivalence):
    """DFT inherits the HF attributes and overrides its set values."""
    params = equivalence.build("ks", {"basis": "sto-3g", "functional": "pbe"})
    assert params["method"] == "dft"
    assert params["basis"] == "sto-3g"
    assert params["xc"] == "pbe"


def test_build_family_and_group(equivalence):
    """dftb-2 inherits dftb-1 (a family entry) and its grouped attribute."""
    params = equivalence.build("scc-dftb", {"basis": {"directory": "/sk"}})
    assert params["method"] == "dftb"
    assert params["scc"] is True
    assert params["sk"] == {"dir": "/sk"}


def test_build_children(equivalence):
    """A value with children becomes a node holding the children."""
    args = {"basis": {"directory": "/sk"}, "mixer": {"value": "broyden", "mixing-parameter": 0.1}}
    params = equivalence.build("dftb-2", args)
    assert params["mixer"] == {"Broyden": {"Mixing": 0.1}}


def test_build_transform(equivalence):
    """The transform named by the spec is applied."""
    params = equivalence.build("hf", {"basis": "sto-3g", "scf-max": 10})
    assert params["scf"]["max"] == 20


def test_build_values(equivalence):
    """Values are translated by the "values" table."""
    params = equivalence.build("hf", {"basis": "sto-3g", "reference": "unrestricted"})
    assert params["scf"]["ref"] == "U"


def test_build_strict_values(equivalence):
    """A value valid for the catalog but without translation is refused."""
    with pytest.raises(ValueError, match="restricted-open"):
        equivalence.build("hf", {"basis": "sto-3g", "reference": "restricted-open"})


def test_build_module_arguments(equivalence):
    """Module arguments are translated."""
    params = equivalence.build("hf", {"basis": "sto-3g"}, "opt", {"max-step": 3})
    assert params["run"] == "opt"
    assert params["opt"] == {"step": 3}


def test_build_unsupported_method(equivalence):
    """A method marked "supported": false is refused."""
    with pytest.raises(NotImplementedError, match="MP2 is not supported"):
        equivalence.build("mp2", {"basis": "sto-3g"})


def test_build_unsupported_module(equivalence):
    """A module marked "supported": false is refused."""
    with pytest.raises(NotImplementedError, match="FREQUENCIES is not supported"):
        equivalence.build("hf", {"basis": "sto-3g"}, "freq")


def test_build_entry_without_equivalence(equivalence):
    """A catalog method absent from equiv.json writes nothing but is accepted."""
    params = equivalence.build("xtb", {})
    assert params == {"general": {"title": "fake", "level": 0}}


def test_build_argument_without_equivalence(equivalence):
    """A catalog argument without translation raises KeyError."""
    with pytest.raises(KeyError, match="level-shift"):
        equivalence.build("hf", {"basis": "sto-3g", "level-shift": 0.1})


def test_build_catalog_error(equivalence):
    """Arguments are checked against the catalog first."""
    with pytest.raises(CatalogError):
        equivalence.build("hf", {})


def test_build_option(equivalence):
    """An option is translated after the method and the module."""
    options = {"solvation": {"model": "cpcm", "solvent": "water"}}
    params = equivalence.build("hf", {"basis": "sto-3g"}, "sp", {}, options)
    assert params["solv"] == {"model": "cpcm", "name": "water"}


def test_build_option_unknown_to_software(tmp_path):
    """An option without entry in equiv.json is refused."""
    path = tmp_path / "equiv.json"
    path.write_text('{"methods": {"hf": {"attributes": {"basis": {"target": "basis"}}}}}')
    with pytest.raises(NotImplementedError, match="option SOLVATION"):
        Equivalence(path).build("hf", {"basis": "sto-3g"}, options={"solvent": {"model": "cpcm"}})


# ----------------------------------------------------------------------
# build_entry_parameters with an inline catalog
# ----------------------------------------------------------------------


def test_build_entry_parameters_alias_in_equiv():
    """The equiv entry can be written under an alias of the catalog entry."""
    catalog = {"A": {"alias": ["first"], "allowed-attribute": {"x": {"type": "int"}}}}
    equiv = {"FIRST": {"set": {"name": "a"}, "attributes": {"x": {"target": "deep.x"}}}}
    params = build_entry_parameters("a", {"x": 3}, equiv, catalog)
    assert params == {"name": "a", "deep": {"x": 3}}


def test_build_entry_parameters_completes_params():
    """Existing parameters are kept and completed."""
    catalog = {"A": {}}
    equiv = {"A": {"set": {"b": 2}}}
    params = build_entry_parameters("a", None, equiv, catalog, params={"a": 1})
    assert params == {"a": 1, "b": 2}
