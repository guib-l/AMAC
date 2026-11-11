from __future__ import annotations

import copy
import sys
from abc import ABC, abstractmethod
from dataclasses import fields
from pathlib import Path
from typing import Any, Callable, ClassVar, Mapping, Self, Sequence

from amac import config
from amac.engine.equiv import Equivalence, set_path
from amac.engine.handler import HandlerSet, HandlerSpec
from amac.engine.profile import Program, checked_executable


class Software(ABC):
    """
    Base class for every software supported by AMAC.
    """

    name: ClassVar[str] = ""
    alias: ClassVar[tuple[str, ...]] = ()
    doc: ClassVar[str | None] = None
    handlers: ClassVar[Mapping[str, Any]] = {}
    driver: ClassVar[tuple[str, ...]] = ()
    composer: ClassVar[Any | None] = None
    requires_executable: ClassVar[bool] = False
    equiv: ClassVar[str] = "equiv.json"
    transforms: ClassVar[Mapping[str, Callable]] = {}

    _registry: ClassVar[dict[str, type[Software]]] = {}

    # Kept on the class: used by assets (e.g. dftbplus ``self.set_path``).
    set_path = staticmethod(set_path)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init_subclass__(cls, **kwargs):
        """Register every asset under its name and aliases."""
        super().__init_subclass__(**kwargs)
        for key in (cls.name, *cls.alias):
            Software._registry[key.upper()] = cls

    @classmethod
    def create(cls, name: str, **options) -> Software:
        """Build the software registered under ``name`` or an alias, any case."""
        try:
            soft_cls = Software._registry[name.upper()]
        except KeyError:
            raise KeyError(
                f"Unknown software {name!r}; available: {sorted(Software._registry)}"
            ) from None
        return soft_cls(**options)

    def __init__(
        self,
        *,
        process: str = "inprocess",
        process_unit: int = 1,
        executable: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        **options,
    ) -> None:
        section = self.config_section()
        # Software-specific settings (e.g. deMonNano "basis"): config, then overrides.
        self.options = {**section, **options}
        self.parameters: dict = {}
        env = env if env is not None else section.get("env", {})
        self.program = Program(
            name=self.name,
            executable=checked_executable(
                self.name,
                executable or section.get("executable"),
                self.requires_executable,
            ),
            process=process,
            process_unit=process_unit,
            env={key: str(value) for key, value in env.items()},
            launcher=list(self.options.get("launcher", [])),
            timeout=self.options.get("timeout"),
        )
        self.equivalence = Equivalence(self.equiv_path(), self.transforms)
        self.handler_set = HandlerSet((self.name, *self.alias))

    # Read-only access kept for assets (deMonNano uses self.executable).
    @property
    def executable(self) -> Path | None:
        return self.program.executable

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @classmethod
    def config_section(cls) -> dict:
        """Return the software section of the configuration, empty if none."""
        softwares = getattr(config, "CONFIGURE", {}).get("software", {})
        for key in (cls.name, *cls.alias):
            if key in softwares:
                return dict(softwares[key])
        return {}

    # ------------------------------------------------------------------
    # Basics functions
    # ------------------------------------------------------------------

    # Template: assets override only what differs.
    def run(self, instance) -> dict:
        self.parameters = self.collect(instance)
        # Raw user parameters of this software have the last word.
        names = {key.upper() for key in (self.name, *self.alias)}
        for software, args in (instance.props.software_args or {}).items():
            if software.upper() in names:
                for path, value in args.items():
                    set_path(self.parameters, path, value)
        self.prepare(instance)
        results = self.calculate(instance)
        self.callback(instance, results)
        return results

    def collect(self, instance) -> dict:
        return self.resolved_parameters(instance)

    def prepare(self, instance) -> None:
        pass

    @abstractmethod
    def calculate(self, instance) -> dict:
        """Run the program and return the raw results."""

    def callback(self, instance, results) -> None:
        self.apply_handlers(instance, results)

    def resolved_parameters(self, instance):
        dct = instance.props.to_dict()

        dct.pop("image")
        dct.pop("handler")
        dct.pop("software_args", None)

        if dct.get("module"):
            self.handler_set.check_module(dct["module"])
        params = self.build_parameters(**dct)
        return params

    # ------------------------------------------------------------------
    # Delegations
    # ------------------------------------------------------------------

    def execute_program(
        self,
        workdir: str | Path,
        *args: str,
        output: str = "output.log",
    ):
        """Run the executable in ``workdir`` (see :meth:`Program.execute`)."""
        return self.program.execute(workdir, *args, output=output)

    def build_parameters(
        self,
        method: str,
        method_args: Mapping[str, Any] | None = None,
        module: str | None = None,
        module_args: Mapping[str, Any] | None = None,
    ) -> dict:
        """Translate the canonical parameters into the software parameters."""
        return self.equivalence.build(method, method_args, module, module_args)

    def resolved_handlers(
        self,
        names: Sequence[str],
        module: str | None = None,
    ) -> tuple[HandlerSpec, ...]:
        """Return the handler specs of ``names`` (see :meth:`HandlerSet.resolve`)."""
        return self.handler_set.resolve(names, module)

    def apply_handlers(self, instance, results: dict[str, Any]) -> dict:
        """Run the handlers of ``instance`` (see :meth:`HandlerSet.apply`)."""
        return self.handler_set.apply(instance, results)

    @classmethod
    def equiv_path(cls) -> Path:
        """Path of the equiv.json file next to the asset module."""
        return Path(sys.modules[cls.__module__].__file__).with_name(cls.equiv)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        program = self.program
        return {
            "name": self.name,
            "alias": self.alias,
            "process": program.process,
            "process_unit": program.process_unit,
            "executable": program.executable,
            "env": program.env,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a result from the output of :meth:`to_dict`.

        Raises:
            ValueError: If ``data`` contains unknown keys.
        """
        known = {f.name for f in fields(cls)} - {"context"}
        if unknown := data.keys() - known:
            raise ValueError(f"Unknown Result keys: {sorted(unknown)}")
        return cls(**copy.deepcopy(data))

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def pretty_print(self, files=sys.stdout):
        """Pretty-print parsed results as indented JSON.

        The output is encoded with :class:`~deMonPy.encoder.AseEncoder`
        so that NumPy arrays and ASE objects are serialisable.

        Args:
            files: Writable text stream that receives the JSON output.
                Defaults to :data:`sys.stdout`.
        """
        import json

        from amac.utils.encoder import AseEncoder

        print(
            json.dumps(
                self.to_dict(),
                indent=4,
                ensure_ascii=True,
                cls=AseEncoder,
            ),
            file=files,
        )
