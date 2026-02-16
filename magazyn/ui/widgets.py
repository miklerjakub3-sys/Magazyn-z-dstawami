#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Sequence, List, Any
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt


def fill_table(table: QTableWidget, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    was_sorting_enabled = table.isSortingEnabled()
    table.setSortingEnabled(False)

    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setRowCount(len(rows))

    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = QTableWidgetItem("" if val is None else str(val))
            if c == 0:
                item.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, c, item)

    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    table.setSortingEnabled(was_sorting_enabled)
