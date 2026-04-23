#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..log import get_logger
from ..pdf_export import PDF_AVAILABLE, export_wz_to_pdf
from ..services import MagazynService

log = get_logger("magazyn.ui.issues")


class IssuesTab(QWidget):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        form = QFormLayout()
        root.addLayout(form)

        self.in_company = QLineEdit()
        self.in_address = QLineEdit()
        self.in_place = QLineEdit()
        self.in_place.setText("Bielsko-Biała")

        self.in_company.setPlaceholderText("Np. Firma XYZ Sp. z o.o.")
        self.in_address.setPlaceholderText("Np. ul. Przykładowa 10, 43-300 Bielsko-Biała")
        self.in_place.setPlaceholderText("Miejsce wystawienia")

        form.addRow("Nazwa firmy", self.in_company)
        form.addRow("Ulica / adres", self.in_address)
        form.addRow("Miejsce", self.in_place)

        row = QHBoxLayout()
        root.addLayout(row)

        self.in_item_name = QLineEdit()
        self.in_item_qty = QSpinBox()
        self.in_item_qty.setRange(1, 1_000_000)
        self.in_item_qty.setValue(1)
        self.btn_add_item = QPushButton("Dodaj pozycję")
        self.btn_remove_item = QPushButton("Usuń zaznaczoną")

        row.addWidget(QLabel("Nazwa pozycji:"))
        row.addWidget(self.in_item_name, 1)
        row.addWidget(QLabel("Ilość sztuk:"))
        row.addWidget(self.in_item_qty)
        row.addWidget(self.btn_add_item)
        row.addWidget(self.btn_remove_item)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nazwa towaru", "Ilość (szt.)"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().Stretch)
        self.table.setColumnWidth(1, 130)
        root.addWidget(self.table, 1)

        self.btn_generate = QPushButton("Generuj PDF WZ")
        self.btn_generate.setEnabled(PDF_AVAILABLE)
        root.addWidget(self.btn_generate)

        if not PDF_AVAILABLE:
            root.addWidget(QLabel("Brak reportlab – generowanie WZ PDF wyłączone. Zainstaluj: pip install reportlab"))

        self.btn_add_item.clicked.connect(self.on_add_item)
        self.btn_remove_item.clicked.connect(self.on_remove_item)
        self.btn_generate.clicked.connect(self.on_generate_pdf)

    def on_add_item(self) -> None:
        name = self.in_item_name.text().strip()
        qty = int(self.in_item_qty.value())
        if not name:
            QMessageBox.information(self, "Info", "Wpisz nazwę pozycji.")
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
        self.in_item_name.clear()
        self.in_item_name.setFocus()

    def on_remove_item(self) -> None:
        current = self.table.currentRow()
        if current >= 0:
            self.table.removeRow(current)

    def _collect_items(self):
        items = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            qty_item = self.table.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            qty_raw = (qty_item.text() if qty_item else "1").strip()
            if not name:
                continue
            try:
                qty = max(1, int(qty_raw))
            except ValueError:
                qty = 1
            items.append({"name": name, "qty": qty})
        return items

    def on_generate_pdf(self) -> None:
        try:
            company = self.in_company.text().strip()
            address = self.in_address.text().strip()
            place = self.in_place.text().strip()
            items = self._collect_items()

            if not company:
                QMessageBox.information(self, "Info", "Podaj nazwę firmy.")
                return
            if not address:
                QMessageBox.information(self, "Info", "Podaj adres firmy.")
                return
            if not place:
                QMessageBox.information(self, "Info", "Podaj miejsce wystawienia.")
                return
            if not items:
                QMessageBox.information(self, "Info", "Dodaj minimum jedną pozycję.")
                return

            default_name = f"WZ_{company}_{date.today().isoformat()}.pdf".replace(" ", "_")
            path, _ = QFileDialog.getSaveFileName(self, "Zapisz dokument WZ", default_name, "PDF (*.pdf)")
            if not path:
                return

            export_wz_to_pdf(path, company, address, place, items)
            QMessageBox.information(self, "OK", f"WZ zapisano: {path}")
        except Exception as e:
            log.exception("wz export failed")
            QMessageBox.critical(self, "Błąd", str(e))
