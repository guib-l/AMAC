"""Tests of amac.engine.validate: arguments checked against the catalog."""

import pytest

from amac.engine.catalog import load_catalog
from amac.engine.validate import CatalogError, _is_type, _split, merged_attributes, validate


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def check(name, args, catalog, section="methods"):
    validate(name, args, catalog[section], catalog["data"])


def test_valid_arguments(catalog):
    """Valid arguments pass without error."""
    check("hf", {"basis": "sto-3g", "charge": 0.0, "multiplicity": 1}, catalog)
    check("dft", {"basis": "def2-svp", "functional": "B3LYP", "dispersion": "d3-bj"}, catalog)


def test_unknown_name(catalog):
    """An unknown method is a KeyError."""
    with pytest.raises(KeyError):
        check("not-a-method", {}, catalog)


def test_missing_mandatory(catalog):
    """A missing mandatory attribute is reported."""
    with pytest.raises(CatalogError, match="basis: mandatory attribute missing"):
        check("hf", {}, catalog)


def test_inherited_mandatory(catalog):
    """A mandatory attribute of a parent is mandatory for the child."""
    with pytest.raises(CatalogError, match="basis: mandatory attribute missing"):
        check("dft", {"functional": "pbe"}, catalog)


def test_unknown_attribute(catalog):
    """An attribute absent from the catalog is reported."""
    with pytest.raises(CatalogError, match="bogus: unknown attribute"):
        check("hf", {"basis": "sto-3g", "bogus": 1}, catalog)


def test_every_error_is_listed(catalog):
    """All errors are reported in one message."""
    with pytest.raises(CatalogError) as error:
        check("hf", {"bogus": 1, "multiplicity": 0}, catalog)
    message = str(error.value)
    assert "basis: mandatory attribute missing" in message
    assert "bogus: unknown attribute" in message
    assert "multiplicity: 0 out of range" in message


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"charge": "zero"}, "is not of type float"),
        ({"multiplicity": 1.0}, "is not of type int"),
        ({"multiplicity": True}, "is not of type int"),
        ({"reference": "rohf"}, "not in"),
        ({"scf-tol": -1.0}, "out of range"),
    ],
)
def test_wrong_values(catalog, args, message):
    """Type, choices and range are checked."""
    with pytest.raises(CatalogError, match=message):
        check("hf", {"basis": "sto-3g", **args}, catalog)


def test_forbidden_attribute(catalog):
    """An attribute forbidden by a child (CI-DFTB: shell-dep) is refused."""
    args = {"basis": {"directory": "/x"}, "size-ci": 2, "fragments": [3, 3], "shell-dep": True}
    with pytest.raises(CatalogError, match="shell-dep: forbidden attribute"):
        check("ci-dftb", args, catalog)


def test_children_checked(catalog):
    """Children of a value are checked, with authorized-with."""
    basis = {"basis": {"directory": "/x"}}
    check("dftb-2", {**basis, "mixer": {"value": "broyden", "mixing-parameter": 0.2}}, catalog)
    with pytest.raises(CatalogError, match="not authorized with 'broyden'"):
        check("dftb-2", {**basis, "mixer": {"value": "broyden", "generations": 3}}, catalog)


def test_children_mandatory(catalog):
    """A mandatory child (basis.directory) is required."""
    with pytest.raises(CatalogError, match="basis.directory: mandatory attribute missing"):
        check("dftb-1", {"basis": {"ptype": "BIO"}}, catalog)


def test_choices_from_strict(catalog):
    """A strict data list refuses unknown values (functional)."""
    with pytest.raises(CatalogError, match="not in the functionals list"):
        check("dft", {"basis": "sto-3g", "functional": "not-a-functional"}, catalog)


def test_choices_from_not_strict(catalog):
    """A non-strict data list accepts unknown values (basis)."""
    check("hf", {"basis": "my-own-basis"}, catalog)


def test_choices_from_role(catalog):
    """An auxiliary basis is refused as orbital basis."""
    with pytest.raises(CatalogError, match="only \\['orbital'\\]"):
        check("hf", {"basis": "def2/j"}, catalog)


def test_forbidden_if(catalog):
    """A dispersion is refused with a functional that already has one."""
    with pytest.raises(CatalogError, match="forbidden with functional"):
        check("dft", {"basis": "sto-3g", "functional": "wb97x-d3", "dispersion": "d3-bj"}, catalog)


def test_module_arguments(catalog):
    """Module arguments are checked the same way."""
    check("md", {"steps": 10, "time-step": 0.5}, catalog, "module")
    with pytest.raises(CatalogError, match="steps: mandatory attribute missing"):
        check("md", {"time-step": 0.5}, catalog, "module")


def test_merged_attributes(catalog):
    """Rules are merged along the inheritance; a child forbids a parent attribute."""
    rules = merged_attributes("CI-DFTB", catalog["methods"])
    assert {"basis", "size-ci", "fragments"} <= set(rules["mandatory-attribute"])
    assert "scc-tol" in rules["allowed-attribute"]
    assert "shell-dep" not in rules["allowed-attribute"]
    assert rules["forbidden-attribute"] == ["shell-dep"]


@pytest.mark.parametrize(
    ("value", "type_name", "expected"),
    [
        (1, "int", True),
        (1, "float", True),
        (1.5, "int", False),
        (True, "bool", True),
        (True, "float", False),
        ("a", "str", True),
        ([1, 2], "list[int]", True),
        ([1, "a"], "list[int]", False),
        ({"H": 1.0}, "dict[str,float]", True),
        ({"H": [1.0]}, "dict[str,float|list[float]]", True),
        ("a", "int|str", True),
    ],
)
def test_is_type(value, type_name, expected):
    """Catalog types, including nested and union types."""
    assert _is_type(value, type_name) is expected


def test_is_type_unknown():
    """An unknown catalog type is an error."""
    with pytest.raises(ValueError, match="Unknown catalog type"):
        _is_type(1, "complex")


def test_split_ignores_brackets():
    """The separator inside brackets does not split."""
    assert _split("str,list[int|float]", ",") == ["str", "list[int|float]"]
    assert _split("int|list[int|float]", "|") == ["int", "list[int|float]"]
