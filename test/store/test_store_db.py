"""Tests of amac.store: txt, JSON and SQLite stores."""

import json

import numpy as np
import pytest
from ase import Atoms

from amac.instance import Instance
from amac.store import Store, to_record


@pytest.fixture
def instance(tmp_path, water):
    instance = Instance.factory_instance(
        name="water", image=water, workdir=tmp_path, method="hf", module="single-point"
    )
    instance.res(complet=True, success=True)
    instance.res.product.update(
        {
            "lowest-energy": -75.0,
            "energy-resume": {"energy": -75.0, "scf_energy": -74.9},
            "forces": np.zeros((3, 3)),
        }
    )
    return instance


def test_to_record_flat(instance):
    """The record is flat (dotted keys) and JSON-serializable."""
    record = to_record(instance)
    assert record["name"] == "water"
    assert record["method"] == "hf"
    assert record["formula"] == "H2O"
    assert record["lowest-energy"] == -75.0
    assert record["energy-resume.scf_energy"] == -74.9
    assert record["forces"] == [[0.0] * 3] * 3
    assert record["image"]["symbols"] == ["O", "H", "H"]
    json.dumps(record)


@pytest.mark.parametrize("suffix", [".json", ".db", ".sqlite"])
def test_round_trip(tmp_path, instance, suffix):
    """Saved records are read back, image included, and filtered."""
    store = Store(tmp_path / f"results{suffix}")
    store.save(instance)
    store.save(instance)
    records = store.load()
    assert len(records) == 2
    assert records[0]["lowest-energy"] == -75.0
    assert isinstance(records[0]["image"], Atoms)
    assert records[0]["image"].get_chemical_formula() == "H2O"
    assert len(store.load(formula="H2O")) == 2
    assert store.load(formula="CH4") == []


def test_txt_store(tmp_path, instance):
    """A txt store writes one line per record with the chosen columns."""
    store = Store(tmp_path / "energies.txt", columns=["lowest-energy"], calc_file=True)
    store.save(instance)
    store.save(instance)
    assert store.load() == [
        {"index": 0, "formula": "H2O", "lowest-energy": -75.0},
        {"index": 1, "formula": "H2O", "lowest-energy": -75.0},
    ]
    calc = json.loads((tmp_path / "calc.json").read_text())
    assert calc["method"] == "hf"
    assert calc["columns"] == ["lowest-energy"]


def test_txt_store_missing_column_is_nan(tmp_path, instance):
    """A missing product is written as NaN."""
    store = Store(tmp_path / "energies.txt", columns=["dipole"])
    store.save(instance)
    assert np.isnan(store.load()[0]["dipole"])


def test_txt_store_non_scalar(tmp_path, instance):
    """A non-scalar column is refused."""
    store = Store(tmp_path / "energies.txt", columns=["forces"])
    with pytest.raises(ValueError, match="isn't a scalar"):
        store.save(instance)


def test_txt_store_needs_columns(tmp_path):
    """A txt store without columns is refused."""
    with pytest.raises(ValueError, match="needs 'columns'"):
        Store(tmp_path / "energies.txt")


def test_unknown_format(tmp_path):
    """An unknown suffix is refused."""
    with pytest.raises(ValueError, match="Unknown store format"):
        Store(tmp_path / "results.csv")


def test_load_missing_file(tmp_path):
    """Loading a store that does not exist gives no record."""
    assert Store(tmp_path / "results.json").load() == []
