"""Save AMAC results in txt, JSON or SQLite files and read them back."""

from amac.store.store_db import Store, to_record

__all__ = ["Store", "to_record"]
