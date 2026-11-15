"""Tests of amac.instance and amac.context."""

import copy
import uuid
from pathlib import Path

import pytest

from amac.context import Duration, Properties, Result
from amac.instance import Instance


@pytest.fixture
def instance(tmp_path, water):
    return Instance.factory_instance(
        name="water",
        image=water,
        workdir=tmp_path,
        method="hf",
        method_args={"basis": "sto-3g"},
        module="sp",
        handler=("lowest-energy",),
    )


def test_factory_defaults(tmp_path):
    """The factory fills every part with empty values."""
    instance = Instance.factory_instance(workdir=tmp_path)
    assert instance.name == "default_name"
    assert instance.ctx.workdir == tmp_path
    assert instance.props.method_args == {}
    assert instance.props.software_args == {}
    assert instance.props.options == {}
    assert instance.res.product == {}
    assert not instance.res.complet
    assert instance.duree.duree == 0.0


def test_workdir_is_a_path(tmp_path):
    """A str workdir is converted to a Path."""
    instance = Instance.factory_instance(workdir=str(tmp_path))
    assert isinstance(instance.ctx.workdir, Path)


def test_properties_update_known_keys_only(instance):
    """Calling a part updates its known attributes and ignores the others."""
    instance.properties(method="dft", unknown=1)
    assert instance.props.method == "dft"
    assert not hasattr(instance.props, "unknown")


def test_equality(instance):
    """An instance equals its name, its id (str or UUID) and itself."""
    assert instance == "water"
    assert instance == str(instance.id)
    assert instance == instance.id
    assert instance == copy.deepcopy(instance)
    assert not instance == "other"
    assert not instance == uuid.uuid4()


def test_equality_wrong_type(instance):
    """Comparing with another type is an error."""
    with pytest.raises(TypeError):
        instance == 1  # noqa: B015


def test_new_instance(instance):
    """A new instance copies context and properties, with empty results."""
    instance.res.product["lowest-energy"] = -1.0
    new = instance.new_instance(name="next")
    assert new.name == "next"
    assert new.id != instance.id
    assert new.props.method == "hf"
    assert new.props is not instance.props
    assert new.res.product == {}


def test_deepcopy_independent(instance):
    """A deep copy shares nothing mutable."""
    clone = copy.deepcopy(instance)
    clone.props.method_args["basis"] = "def2-svp"
    assert instance.props.method_args["basis"] == "sto-3g"


def test_open_close_duration(instance):
    """Opening then closing measures the duration."""
    instance.open_instance()
    instance.close_instance()
    assert instance.duree.duree >= 0.0
    assert instance.duree.date_begin is not None


def test_open_without_duration(tmp_path):
    """An instance without Duration cannot be opened or closed."""
    instance = Instance(ctx=None)
    with pytest.raises(RuntimeError):
        instance.open_instance()
    with pytest.raises(RuntimeError):
        instance.close_instance()


def test_add_step():
    """Steps record the wall time by function name."""
    duration = Duration()
    duration.add_step("calculate", 1.5)
    assert duration.steps == {"calculate": 1.5}


def test_part_round_trip():
    """to_dict / from_dict give back the same part."""
    result = Result(complet=True, success=True, product={"a": 1})
    assert Result.from_dict(result.to_dict()) == result


def test_part_from_dict_unknown_key():
    """Unknown keys are refused."""
    with pytest.raises(ValueError, match="Unknown Result keys"):
        Properties.from_dict({"method": "hf", "nothing": 1})


def test_instance_to_dict(instance):
    """to_dict gives every part as a dict."""
    data = instance.to_dict()
    assert data["name"] == "water"
    assert data["props"]["method"] == "hf"
    assert data["ctx"]["workdir"] == instance.ctx.workdir


def test_repr(instance):
    """The representation shows the name and the workdir."""
    text = repr(instance)
    assert "water" in text
    assert str(instance.ctx.workdir) in text
