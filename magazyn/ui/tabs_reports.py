#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QComboBox, QMessageBox, QLabel, QFileDialog, QRadioButton, QButtonGroup
)

from ..config import DELIVERY_TYPES
from ..services import MagazynService
from ..utils import today_str, validate_ymd
from ..pdf_export import PDF_AVAILABLE, export_devices_to_pdf, export_deliveries_to_pdf
from ..database import get_devices_by_date_range, get_deliveries_by_date_range
from ..log import get_logger

log = get_logger("magazyn.ui.reports")


class ReportsTab(QWidget):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        if not PDF_AVAILABLE:
            root.addWidget(QLabel("Brak reportlab – raporty PDF wyłączone. Zainstaluj: pip install reportlab"))

        mode_row = QHBoxLayout()
        root.addLayout(mode_row)
        self.bg = QButtonGroup(self)
        self.rb_receipts = QRadioButton("Przyjęcia")
        self.rb_deliveries = QRadioButton("Dostawy")
        self.rb_receipts.setChecked(True)
        self.bg.addButton(self.rb_receipts)
        self.bg.addButton(self.rb_deliveries)
        mode_row.addWidget(self.rb_receipts)
        mode_row.addWidget(self.rb_deliveries)
        mode_row.addStretch(1)

        form = QFormLayout()
        root.addLayout(form)

        self.in_from = QLineEdit()
        self.in_to = QLineEdit(today_str())
        self.in_receipt_type = QComboBox(); self.in_receipt_type.addItems(["Wszystkie","Urządzenie","Akcesorium"])
        self.in_delivery_type = QComboBox(); self.in_delivery_type.addItems([""] + DELIVERY_TYPES)

        form.addRow("Od (YYYY-MM-DD)", self.in_from)
        form.addRow("Do (YYYY-MM-DD)", self.in_to)
        form.addRow("Przyjęcia: typ", self.in_receipt_type)
        form.addRow("Dostawy: typ", self.in_delivery_type)

        self.btn_export = QPushButton("Eksportuj PDF")
        self.btn_export.clicked.connect(self.on_export)
        if not PDF_AVAILABLE:
            self.btn_export.setEnabled(False)

        root.addWidget(self.btn_export)
        root.addStretch(1)

    def on_export(self) -> None:
        try:
            df = self.in_from.text().strip()
            dt = self.in_to.text().strip()
            if not df or not dt:
                raise ValueError("Podaj zakres dat: Od i Do.")
            validate_ymd(df); validate_ymd(dt)

            if self.rb_receipts.isChecked():
                ftype = self.in_receipt_type.currentText()
                item_type = {"Wszystkie":"all","Urządzenie":"device","Akcesorium":"accessory"}.get(ftype, "all")
                rows = get_devices_by_date_range(df, dt, item_type)
                if not rows:
                    QMessageBox.information(self, "Info", "Brak danych w tym zakresie.")
                    return
                path, _ = QFileDialog.getSaveFileName(self, "Zapisz raport", f"raport_przyjecia_{df}_do_{dt}.pdf", "PDF (*.pdf)")
                if not path:
                    return
                export_devices_to_pdf(path, rows, df, dt, ftype)
                QMessageBox.information(self, "OK", f"Zapisano: {path}")
            else:
                dtype = self.in_delivery_type.currentText().strip()
                rows = get_deliveries_by_date_range(df, dt, dtype)
                if not rows:
                    QMessageBox.information(self, "Info", "Brak danych w tym zakresie.")
                    return
                path, _ = QFileDialog.getSaveFileName(self, "Zapisz raport", f"raport_dostawy_{df}_do_{dt}.pdf", "PDF (*.pdf)")
                if not path:
                    return
                export_deliveries_to_pdf(path, rows, df, dt, dtype)
                QMessageBox.information(self, "OK", f"Zapisano: {path}")
        except Exception as e:
            log.exception("export failed")
            QMessageBox.critical(self, "Błąd", str(e))
