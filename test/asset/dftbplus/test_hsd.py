"""Tests of the DFTB+ HSD writer."""

import pytest

from amac.asset.dftbplus.hsd import format_value, to_hsd


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "Yes"), (False, "No"), ("geo.gen", '"geo.gen"'), (1e-5, "1e-05"), (3, "3"),
     ([1, 0, 0.5], "1 0 0.5"), ((True, "a"), 'Yes "a"')],
)
def test_format_value(value, expected):
    """Scalars and lists in HSD syntax."""
    assert format_value(value) == expected


def test_method_choice():
    """A node with a single sub-node is a method choice."""
    assert to_hsd({"Hamiltonian": {"DFTB": {"Scc": True}}}) == (
        "Hamiltonian = DFTB {\n  Scc = Yes\n}"
    )


def test_plain_block():
    """A node with several entries is a plain block."""
    assert to_hsd({"Options": {"WriteResultsTag": True, "Level": 1}}) == (
        "Options {\n  WriteResultsTag = Yes\n  Level = 1\n}"
    )


def test_empty_choice():
    """An empty method choice is written without body."""
    assert to_hsd({"Driver": {"GeometryOptimization": {}}}) == (
        "Driver = GeometryOptimization {\n}"
    )


def test_include_and_bare_value():
    """<<< includes a file; the empty key writes its value bare."""
    tree = {
        "Geometry": {"GenFormat": {"<<<": "geo.gen"}},
        "KPointsAndWeights": {"SupercellFolding": {"": [2, 0, 0, 0, 2, 0, 0, 0, 2, 0.5, 0.5, 0.5]}},
    }
    assert to_hsd(tree) == (
        'Geometry = GenFormat {\n  <<< "geo.gen"\n}\n'
        "KPointsAndWeights = SupercellFolding {\n  2 0 0 0 2 0 0 0 2 0.5 0.5 0.5\n}"
    )


def test_key_with_unit():
    """Keys holding a unit are written as is."""
    assert to_hsd({"TimeStep [fs]": 0.5}) == "TimeStep [fs] = 0.5"
