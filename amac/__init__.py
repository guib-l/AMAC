from amac.config import configure, configure_from_file

__version__ = "0.0.1"

__all__ = [
    "AMAC",
    "configure",
    "configure_from_file",
]


def __getattr__(name):
    # Lazy import: loading AMAC imports every asset (deMonPy, ...).
    if name == "AMAC":
        from amac.amac import AMAC

        return AMAC
    raise AttributeError(f"module 'amac' has no attribute {name!r}")
