"""CSV reading and writing for numeric tables."""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from quanta.util.iterutil import coerce_cell

log = logging.getLogger(__name__)


@dataclass
class Table:
    """A rectangular table with named columns; cells are int, float or str."""

    columns: List[str]
    rows: List[List[object]]

    def column(self, name: str) -> List[object]:
        idx = self.columns.index(name)
        return [row[idx] for row in self.rows]

    def float_column(self, name: str) -> List[float]:
        return [float(v) for v in self.column(name)]

    def __len__(self) -> int:
        return len(self.rows)


def write_table(path: str, table: Table) -> int:
    """Write `table` as CSV and return the number of data rows written."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(table.columns)
        for row in table.rows:
            writer.writerow(["%.6f" % v if isinstance(v, float) else v for v in row])
    return len(table.rows)


def read_table(path: str) -> Table:
    """Read a CSV file with a header row; numeric-looking cells become int or float."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)
        except StopIteration:
            raise ValueError(f"{path}: empty file") from None
        rows = []
        for lineno, raw in enumerate(reader, start=2):
            if len(raw) != len(columns):
                log.warning("%s:%d has %d cells, expected %d; skipped", path, lineno, len(raw), len(columns))
                continue
            rows.append([coerce_cell(cell) for cell in raw])
    return Table(columns, rows)


def describe_columns(table: Table) -> Dict[str, str]:
    """Column name -> 'int', 'float' or 'text', judged from the first row."""
    kinds: Dict[str, str] = {}
    if not table.rows:
        return {name: "text" for name in table.columns}
    for name, cell in zip(table.columns, table.rows[0]):
        kinds[name] = "int" if isinstance(cell, int) else "float" if isinstance(cell, float) else "text"
    return kinds


def column_means(table: Table, names: Iterable[str]) -> Dict[str, float]:
    """Mean of each named numeric column."""
    means = {}
    for name in names:
        values = table.float_column(name)
        means[name] = sum(values) / len(values) if values else 0.0
    return means


def rows_as_lines(rows: Sequence[Sequence[object]], sep: str = ",") -> List[str]:
    """Format rows without the csv module (used for quick previews)."""
    return [sep.join(str(c) for c in row) for row in rows]
