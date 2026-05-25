# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Tiny ODS reader on top of odfpy.

ODS uses ``table:number-columns-repeated`` to compress runs of identical
cells (most often blanks) — naively calling ``getElementsByType(TableCell)``
loses positional alignment because a single cell node might stand in for N
columns. We expand those runs so callers see a dense ``list[str]`` per row.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

from odf.opendocument import load
from odf.table import Table, TableCell, TableRow
from odf.text import P


def _cell_text(cell: TableCell) -> str:
    parts: list[str] = []
    for p in cell.getElementsByType(P):
        parts.append(str(p))
    return " ".join(parts).strip()


def _row_cells(row: TableRow, max_cols: int = 16) -> list[str]:
    out: list[str] = []
    for cell in row.getElementsByType(TableCell):
        repeat_attr = cell.getAttribute("numbercolumnsrepeated")
        try:
            repeat = int(repeat_attr) if repeat_attr else 1
        except (TypeError, ValueError):
            repeat = 1
        text = _cell_text(cell)
        # Avoid blowing up on giant repeat counts on padding cells.
        if repeat > 256:
            repeat = 1
        for _ in range(repeat):
            out.append(text)
            if len(out) >= max_cols:
                return out
    return out


def iter_rows(data: bytes, *, sheet_index: int = 0, max_cols: int = 16) -> Iterator[list[str]]:
    """Yield each row as a list of cell text values (length up to max_cols)."""
    doc = load(BytesIO(data))
    sheets = doc.spreadsheet.getElementsByType(Table)
    if not sheets or sheet_index >= len(sheets):
        return
    for row in sheets[sheet_index].getElementsByType(TableRow):
        yield _row_cells(row, max_cols=max_cols)
