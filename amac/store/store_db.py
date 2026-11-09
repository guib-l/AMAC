"""Save AMAC results in txt, JSON or SQLite files and read them back."""

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from ase import Atoms

from amac.utils.encoder import AseEncoder

FORMATS = {".txt": "txt", ".json": "json", ".db": "sqlite", ".sqlite": "sqlite"}
ATOMS_KEYS = {"symbols", "positions", "cell", "pbc"}


def _encode_atoms(atoms: Atoms) -> dict[str, Any]:
    return {
        "symbols": atoms.get_chemical_symbols(),
        "positions": atoms.positions.tolist(),
        "cell": atoms.cell.tolist(),
        "pbc": atoms.pbc.tolist(),
    }


def _decode(value: Any) -> Any:
    """Turn a stored value back into a Python value (ase.Atoms included)."""
    if isinstance(value, str) and value[:1] in "[{":
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, dict) and value.keys() == ATOMS_KEYS:
        return Atoms(**value)
    return value


def _software_name(instance) -> str | None:
    # ctx.software is a Software, or its dict after Instance re-creation.
    software = instance.ctx.software
    if isinstance(software, dict):
        return software.get("name")
    return getattr(software, "name", software)


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts with dotted keys; ase.Atoms become dicts."""
    flat = {}
    for key, value in data.items():
        key = f"{prefix}{key}"
        if isinstance(value, Atoms):
            flat[key] = _encode_atoms(value)
        elif isinstance(value, dict):
            flat.update(_flatten(value, f"{key}."))
        else:
            flat[key] = value
    return flat


def to_record(instance) -> dict[str, Any]:
    """Return the flat record of an Instance.

    Args:
        instance: Calculated ``Instance``.

    Returns:
        Dict of one level: metadata, image and products (dotted keys).
    """
    props, image = instance.props, instance.props.image
    record = {
        "id": str(instance.id),
        "name": instance.name,
        "software": _software_name(instance),
        "method": props.method,
        "module": props.module,
        "formula": image.get_chemical_formula() if image is not None else None,
        "success": instance.res.success,
        "complet": instance.res.complet,
        "date": instance.duree.date_begin,
        "duration": instance.duree.duree,
        "image": image,
        **instance.res.product,
    }
    # Round trip through AseEncoder: numpy, Path, date... become JSON types.
    return json.loads(json.dumps(_flatten(record), cls=AseEncoder))


class Store:
    """Save AMAC results in a file and read them back.

    The format is deduced from the suffix: ``.txt`` (columns), ``.json``
    or ``.db``/``.sqlite`` (SQLite).

    Args:
        path: File of the store.
        format: ``"txt"``, ``"json"`` or ``"sqlite"``; deduced from the
            suffix if None.
        columns: Products written as columns (txt only, required).
        calc_file: txt only; if True, write ``calc.json`` next to the txt
            file with the description of the calculation (no molecule).

    Raises:
        ValueError: If the format is unknown or ``columns`` is missing
            for a txt store.
    """

    def __init__(
            self,
            path: str | Path,
            format: str | None = None,
            columns: list[str] | None = None,
            calc_file: bool = False,
        ):
        self.path = Path(path)
        self.format = format or FORMATS.get(self.path.suffix.lower())
        if self.format not in FORMATS.values():
            raise ValueError(f"Unknown store format for {self.path}")
        if self.format == "txt" and not columns:
            raise ValueError("A txt store needs 'columns'.")
        self.columns = list(columns or [])
        self.calc_file = calc_file

    def save(self, instance) -> None:
        """Add the results of ``instance`` to the store."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = to_record(instance)
        getattr(self, f"_save_{self.format}")(record)
        if self.format == "txt" and self.calc_file:
            self._save_calc(instance)

    def load(self, **filters) -> list[dict[str, Any]]:
        """Return the stored records equal to every ``filters`` item."""
        if not self.path.exists():
            return []
        records = getattr(self, f"_load_{self.format}")()
        return [
            record for record in records
            if all(record.get(key) == value for key, value in filters.items())
        ]

    # ------------------------------------------------------------------
    # txt
    # ------------------------------------------------------------------

    def _save_txt(self, record: dict[str, Any]) -> None:
        values = []
        for column in self.columns:
            value = record.get(column)
            if value is None:
                value = math.nan
            if not isinstance(value, (int, float)):
                raise ValueError(f"Column {column!r} isn't a scalar: {value!r}")
            values.append(f"{value:>20.10g}")

        new = not self.path.exists()
        index = 0 if new else len(self._load_txt())
        with self.path.open("a") as file:
            if new:
                header = "".join(f"{column:>20s}" for column in self.columns)
                file.write(f"# {'index':>6s}  {'formula':<16s}{header}\n")
            file.write(f"{index:>8d}  {record['formula'] or '-':<16s}"
                       f"{''.join(values)}\n")

    def _load_txt(self) -> list[dict[str, Any]]:
        lines = self.path.read_text().splitlines()
        header = lines[0].lstrip("#").split()
        records = []
        for line in lines[1:]:
            index, formula, *values = line.split()
            records.append({
                "index": int(index),
                "formula": formula,
                **{key: float(value) for key, value in zip(header[2:], values)},
            })
        return records

    def _save_calc(self, instance) -> None:
        props = instance.props
        calc = {
            "software": _software_name(instance),
            "method": props.method,
            "method_args": props.method_args,
            "module": props.module,
            "module_args": props.module_args,
            "handler": props.handler,
            "columns": self.columns,
        }
        (self.path.parent / "calc.json").write_text(
            json.dumps(calc, indent=4, ensure_ascii=False, cls=AseEncoder)
        )

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _save_json(self, record: dict[str, Any]) -> None:
        records = json.loads(self.path.read_text()) if self.path.exists() else []
        records.append(record)
        self.path.write_text(json.dumps(records, indent=4))

    def _load_json(self) -> list[dict[str, Any]]:
        return [
            {key: _decode(value) for key, value in record.items()}
            for record in json.loads(self.path.read_text())
        ]

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------

    def _save_sqlite(self, record: dict[str, Any]) -> None:
        # Numbers and strings are stored as is, the rest as JSON text.
        row = {
            key: value if isinstance(value, (int, float, str)) or value is None
            else json.dumps(value)
            for key, value in record.items()
        }
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS results ("id" TEXT)')
            known = {line[1] for line in db.execute("PRAGMA table_info(results)")}
            for key in row.keys() - known:
                db.execute(f'ALTER TABLE results ADD COLUMN "{key}"')
            keys = ", ".join(f'"{key}"' for key in row)
            marks = ", ".join("?" for _ in row)
            db.execute(f"INSERT INTO results ({keys}) VALUES ({marks})",
                       list(row.values()))
        db.close()

    def _load_sqlite(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM results").fetchall()
        db.close()
        return [
            {key: _decode(row[key]) for key in row.keys() if row[key] is not None}
            for row in rows
        ]
