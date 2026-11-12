from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amac.engine.catalog import CATALOG_DIR, canonical_name, load_catalog

type HandlerFunction = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class HandlerSpec:
    """A registered handler: extracts one product from the raw results.

    Attributes:
        name: Normalized handler name (``lowest-energy``).
        function: Function taking the raw results, returning the product.
        software: Name of the software the handler belongs to.
        requires_files: Output files the handler needs.
        modules: Modules (canonical, upper-case) the handler is valid
            for; ``None`` means every module.
        drivers: Drivers the handler is valid for; ``None`` means every
            driver.
    """

    name: str
    function: HandlerFunction
    software: str
    requires_files: tuple[str, ...] = ()
    modules: tuple[str, ...] | None = None
    drivers: tuple[str, ...] | None = None

    def __call__(self, results: dict[str, Any]) -> Any:
        return self.function(results)


# Registry: {SOFTWARE: {handler-name: HandlerSpec}}
_REGISTRY: dict[str, dict[str, HandlerSpec]] = {}


def normalize_name(name: str) -> str:
    """Return the handler name in lower case, with ``-`` as separator."""
    return name.strip().lower().replace("_", "-")


def handler(
    software: str,
    name: str | None = None,
    *,
    requires_files: tuple[str, ...] = (),
    modules: tuple[str, ...] | None = None,
    drivers: tuple[str, ...] | None = None,
) -> Callable[[HandlerFunction], HandlerFunction]:
    """Register the decorated function as a handler of ``software``.

    The function is returned unchanged and can still be called directly.

    Args:
        software: Name of the software (``Software.name``).
        name: Handler name; the function name if None.
        requires_files: Output files the handler needs.
        modules: Modules the handler is valid for; every module if None.
        drivers: Drivers the handler is valid for; every driver if None.

    Raises:
        ValueError: If the handler is already registered for ``software``.
    """

    def decorator(func: HandlerFunction) -> HandlerFunction:
        spec = HandlerSpec(
            name=normalize_name(name or func.__name__),
            function=func,
            software=software,
            requires_files=tuple(requires_files),
            modules=(None if modules is None else tuple(module.upper() for module in modules)),
            drivers=None if drivers is None else tuple(drivers),
        )
        handlers = _REGISTRY.setdefault(software.upper(), {})
        if spec.name in handlers:
            raise ValueError(f"Handler {spec.name!r} already registered for {software}")
        handlers[spec.name] = spec
        return func

    return decorator


def registered_handlers(software: str) -> dict[str, HandlerSpec]:
    """Return the handlers registered for ``software``, by name."""
    return dict(_REGISTRY.get(software.upper(), {}))


class HandlerSet:
    """Handlers registered for one software (under its name or aliases).

    Args:
        names: Name and aliases of the software.
        catalog_dir: The canonical ``catalog/`` directory, used to resolve
            module aliases.
    """

    def __init__(
        self,
        names: Sequence[str],
        catalog_dir: str | Path = CATALOG_DIR,
    ):
        self.names = tuple(names)
        self.catalog_dir = Path(catalog_dir)

    def available(self) -> dict[str, HandlerSpec]:
        """Return the handlers registered under the name or an alias."""
        handlers = {}
        for key in self.names:
            handlers.update(registered_handlers(key))
        return handlers

    def check_module(self, module: str) -> None:
        """Check that the software has the handlers required by ``module``.

        Args:
            module: Module of the calculation (name or alias).

        Raises:
            KeyError: If ``module`` is unknown to the catalog.
            NotImplementedError: If a ``mandatory-handler`` of the module
                is not registered for the software.
        """
        catalog = load_catalog(self.catalog_dir)["module"]
        module = canonical_name(module, catalog)
        required = catalog[module].get("mandatory-handler") or ()
        available = self.available()
        missing = [name for name in required if normalize_name(name) not in available]
        if missing:
            raise NotImplementedError(
                f"{self.names[0]} cannot run module {module}: missing handlers {missing}"
            )

    def resolve(
        self,
        names: Sequence[str],
        module: str | None = None,
    ) -> tuple[HandlerSpec, ...]:
        """Return the handler specs of ``names``, checked for ``module``.

        Args:
            names: Handler names, any case, ``-`` or ``_`` as separator.
            module: Module of the calculation (name or alias); not checked
                if None.

        Raises:
            KeyError: If a handler is unknown to the software.
            ValueError: If a handler is not valid for ``module``.
        """
        available = self.available()
        if module is not None:
            catalog = load_catalog(self.catalog_dir)["module"]
            module = canonical_name(module, catalog)

        specs = []
        for name in names:
            key = normalize_name(name)
            if key not in available:
                raise KeyError(
                    f"Unknown handler {name!r} for {self.names[0]}; available: {sorted(available)}"
                )
            spec = available[key]
            if module and spec.modules is not None and module not in spec.modules:
                raise ValueError(f"Handler {spec.name!r} is not valid for module {module}")
            specs.append(spec)
        return tuple(specs)

    def apply(self, instance, results: dict[str, Any] | None) -> dict:
        """Run the handlers of ``instance`` on the raw ``results``.

        The products are stored in ``instance.res.product`` by handler name.

        Returns:
            The products of this call, by handler name.
        """
        specs = self.resolve(instance.props.handler, instance.props.module)
        if results is not None:
            product = {spec.name: spec(results) for spec in specs}
        else:
            product = {}
        instance.res.product.update(product)
        return product
