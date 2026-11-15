"""Tests of amac.engine.catalog (the real catalog/ is only read)."""

import json

import pytest

from amac.engine.catalog import (
    CATALOG_DIR,
    canonical_name,
    canonical_value,
    inheritance_chain,
    load_catalog,
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_catalog_dir_is_the_repository_catalog():
    """CATALOG_DIR points to catalog/ at the repository root."""
    assert (CATALOG_DIR / "catalog.json").is_file()


def test_load_catalog_sections(catalog):
    """Every section is present, indexed by upper-case name."""
    assert set(catalog) == {"methods", "module", "options", "data"}
    assert {"HF", "DFT", "DFTB", "DFTB-2", "XTB"} <= set(catalog["methods"])
    assert {"SINGLE-POINT", "OPTIMIZATION-GEOMETRY", "MOLECULAR-DYNAMICS"} <= set(
        catalog["module"]
    )
    assert "SOLVATION" in catalog["options"]
    assert {"FUNCTIONALS", "BASIS-SETS"} <= set(catalog["data"])


def test_load_catalog_missing_file(tmp_path):
    """A file listed in catalog.json but absent is an error."""
    (tmp_path / "catalog.json").write_text(json.dumps({"methods": ["nothing"]}))
    with pytest.raises(FileNotFoundError, match="nothing.json"):
        load_catalog(tmp_path)


def test_load_catalog_only_listed_files(tmp_path):
    """Only the files listed in catalog.json are read."""
    (tmp_path / "methods").mkdir()
    (tmp_path / "methods" / "a.json").write_text(json.dumps({"a": {"alias": ["x"]}}))
    (tmp_path / "methods" / "b.json").write_text(json.dumps({"b": {}}))
    (tmp_path / "catalog.json").write_text(json.dumps({"methods": ["a"]}))
    catalog = load_catalog(tmp_path)
    assert catalog["methods"] == {"A": {"alias": ["x"]}}
    assert catalog["module"] == {}


@pytest.mark.parametrize(
    ("name", "expected"),
    [("hf", "HF"), ("SCF", "HF"), ("dftb-1", "DFTB"), ("scc-dftb", "DFTB-2"), ("ks", "DFT")],
)
def test_canonical_name_methods(catalog, name, expected):
    """A canonical name or an alias, any case, gives the canonical name."""
    assert canonical_name(name, catalog["methods"]) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sp", "SINGLE-POINT"),
        ("Opt", "OPTIMIZATION-GEOMETRY"),
        ("td-dftb", "EXCITED-STATES"),
        ("md", "MOLECULAR-DYNAMICS"),
        ("ts", "TRANSITION-STATE"),
        ("freq", "FREQUENCIES"),
    ],
)
def test_canonical_name_modules(catalog, name, expected):
    """Module aliases are resolved."""
    assert canonical_name(name, catalog["module"]) == expected


def test_canonical_name_unknown(catalog):
    """An unknown name raises KeyError."""
    with pytest.raises(KeyError, match="Unknown catalog entry"):
        canonical_name("not-a-method", catalog["methods"])


def test_canonical_value(catalog):
    """A data value is returned in lower case; unknown or non-str gives None."""
    basis_sets = catalog["data"]["BASIS-SETS"]
    assert canonical_value("STO-3G", basis_sets) == "sto-3g"
    assert canonical_value("  sto-3g ", basis_sets) == "sto-3g"
    assert canonical_value("not-a-basis", basis_sets) is None
    assert canonical_value({"directory": "/x"}, basis_sets) is None


def test_inheritance_chain(catalog):
    """The chain goes from the root parent down to the entry."""
    methods = catalog["methods"]
    assert inheritance_chain("DFTB-3", methods) == ["DFTB", "DFTB-2", "DFTB-3"]
    assert inheritance_chain("CCSD(T)", methods) == ["HF", "CCSD", "CCSD(T)"]
    assert inheritance_chain("HF", methods) == ["HF"]
