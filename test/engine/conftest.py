"""Fake software used to test the engine without any external program."""

import copy
from pathlib import Path

import pytest

from amac.engine.handler import handler
from amac.engine.software import Software

FAKE_EQUIV = Path(__file__).with_name("data") / "fake_equiv.json"
FAKE_ENERGY = -1.5


class software_fake(Software):
    """Software that runs nothing: it returns its translated parameters."""

    name = "fake-amac"
    alias = ("fake",)
    requires_executable = False
    transforms = {"double": lambda value: 2 * value}

    @classmethod
    def equiv_path(cls) -> Path:
        return FAKE_EQUIV

    def calculate(self, instance):
        return {"energy": FAKE_ENERGY, "parameters": copy.deepcopy(self.parameters)}


@handler(software="fake-amac", name="lowest_energy")
def fake_lowest_energy(results):
    return results["energy"]


@handler(software="fake-amac", name="parameters")
def fake_parameters(results):
    return results["parameters"]


@pytest.fixture
def fake_soft():
    """A new fake software."""
    return Software.create("fake-amac")
