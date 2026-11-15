"""Tests of amac.engine.handler: registry and HandlerSet."""

import pytest

from amac.engine.handler import HandlerSet, handler, normalize_name, registered_handlers


@pytest.fixture
def fake_handlers():
    return HandlerSet(("fake-amac", "fake"))


@pytest.mark.parametrize(
    ("name", "expected"),
    [("lowest_energy", "lowest-energy"), (" Lowest-Energy ", "lowest-energy"), ("dipole", "dipole")],
)
def test_normalize_name(name, expected):
    """Names are lower-case with "-" as separator."""
    assert normalize_name(name) == expected


def test_handler_registered():
    """The decorator registers the handler under its normalized name."""
    handlers = registered_handlers("FAKE-AMAC")
    assert {"lowest-energy", "parameters"} <= set(handlers)
    assert handlers["lowest-energy"]({"energy": 2.0}) == 2.0
    assert handlers["lowest-energy"].software == "fake-amac"


def test_handler_returns_the_function():
    """The decorated function is returned unchanged."""

    def product(results):
        return results["x"]

    assert handler(software="amac-test-unique", name="product")(product) is product
    assert registered_handlers("amac-test-unique")["product"]({"x": 1}) == 1


def test_handler_registered_twice():
    """Registering the same name twice for a software is an error."""
    with pytest.raises(ValueError, match="already registered"):
        handler(software="fake-amac", name="lowest-energy")(lambda results: None)


def test_available_by_alias():
    """Handlers registered under an alias are found."""
    handler(software="amac-test-alias", name="only_alias")(lambda results: 1)
    assert "only-alias" in HandlerSet(("amac-test-name", "amac-test-alias")).available()


def test_resolve(fake_handlers):
    """Names in any form give the handler specs, in order."""
    specs = fake_handlers.resolve(["Parameters", "lowest_energy"])
    assert [spec.name for spec in specs] == ["parameters", "lowest-energy"]


def test_resolve_unknown(fake_handlers):
    """An unknown handler is a KeyError listing the available ones."""
    with pytest.raises(KeyError, match="Unknown handler 'dipole'"):
        fake_handlers.resolve(["dipole"])


def test_resolve_module_restriction():
    """A handler limited to some modules is refused for another module."""
    handler(software="amac-test-modules", name="opt_only", modules=("optimization-geometry",))(
        lambda results: 1
    )
    handlers = HandlerSet(("amac-test-modules",))
    assert handlers.resolve(["opt-only"], "opt")
    with pytest.raises(ValueError, match="not valid for module SINGLE-POINT"):
        handlers.resolve(["opt-only"], "sp")


def test_check_module_ok(fake_handlers):
    """single-point needs lowest-energy, which the fake software has."""
    fake_handlers.check_module("sp")


def test_check_module_optimization(fake_handlers):
    """optimization only needs lowest-energy (forces are optional)."""
    fake_handlers.check_module("optimization-geometry")


def test_check_module_missing_handler(fake_handlers):
    """frequencies needs the frequencies handler, which the fake software lacks."""
    with pytest.raises(NotImplementedError, match="missing handlers \\['frequencies'\\]"):
        fake_handlers.check_module("freq")


def test_check_module_unknown(fake_handlers):
    """An unknown module is a KeyError."""
    with pytest.raises(KeyError):
        fake_handlers.check_module("not-a-module")


def test_apply(fake_handlers, fake_soft, make_instance):
    """Products are stored in instance.res.product by handler name."""
    instance = make_instance(fake_soft, module="sp", handler=("lowest-energy",))
    product = fake_handlers.apply(instance, {"energy": -3.0})
    assert product == {"lowest-energy": -3.0}
    assert instance.res.product == {"lowest-energy": -3.0}


def test_apply_without_results(fake_handlers, fake_soft, make_instance):
    """No raw results: no product, but the names are still checked."""
    instance = make_instance(fake_soft, handler=("lowest-energy",))
    assert fake_handlers.apply(instance, None) == {}
    instance = make_instance(fake_soft, handler=("dipole",))
    with pytest.raises(KeyError):
        fake_handlers.apply(instance, None)
