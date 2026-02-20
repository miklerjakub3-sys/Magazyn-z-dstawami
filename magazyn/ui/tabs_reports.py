#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import DELIVERY_TYPES
from ..database import get_deliveries_by_date_range, get_devices_by_date_range
from ..log import get_logger
from ..pdf_export import PDF_AVAILABLE, export_deliveries_to_pdf, export_devices_to_pdf
from ..services import MagazynService
from ..utils import validate_ymd

log = get_logger("magazyn.ui.reports")


class OptionalDateEdit(QDateEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setMinimumDate(QDate(1900, 1, 1))
        self.setSpecialValueText("— wybierz datę —")
        self.setDate(self.minimumDate())

    def showPopup(self) -> None:
        if self.date() == self.minimumDate():
            self.setDate(QDate.currentDate())
        super().showPopup()


class ReportsTab(QWidget):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self._build()
        self._apply_permissions()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

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

        self.in_from = OptionalDateEdit()
        self.in_to = OptionalDateEdit()

        self.btn_clear_from = QToolButton()
        self.btn_clear_from.setText("✕")
        self.btn_clear_to = QToolButton()
        self.btn_clear_to.setText("✕")

        self.in_receipt_type = QComboBox()
        self.in_receipt_type.addItems(["Wszystkie", "Urządzenie", "Akcesorium"])
        self.in_delivery_type = QComboBox()
        self.in_delivery_type.addItems([""] + DELIVERY_TYPES)

        od_row = QHBoxLayout()
        od_row.addWidget(self.in_from)
        od_row.addWidget(self.btn_clear_from)
        do_row = QHBoxLayout()
        do_row.addWidget(self.in_to)
        do_row.addWidget(self.btn_clear_to)

        form.addRow("Od", od_row)
        form.addRow("Do", do_row)
        form.addRow("Przyjęcia: typ", self.in_receipt_type)
        form.addRow("Dostawy: typ", self.in_delivery_type)

        self.btn_export = QPushButton("Eksportuj PDF")
        for w in (self.in_from, self.in_to, self.in_receipt_type, self.in_delivery_type, self.btn_export):
            w.setProperty("compact", True)
        self.btn_clear_from.clicked.connect(lambda: self.in_from.setDate(self.in_from.minimumDate()))
        self.btn_clear_to.clicked.connect(lambda: self.in_to.setDate(self.in_to.minimumDate()))
        self.btn_export.clicked.connect(self.on_export)
        if not PDF_AVAILABLE:
            self.btn_export.setEnabled(False)

        root.addWidget(self.btn_export)
        root.addStretch(1)

    def _apply_permissions(self) -> None:
        can_export = bool(self.svc.has_permission("reports.export"))
        for w in (self.in_from, self.in_to, self.in_receipt_type, self.in_delivery_type, self.btn_export):
            w.setEnabled(can_export)

    @staticmethod
    def _date_text(w: QDateEdit) -> str:
        return "" if w.date() == w.minimumDate() else w.date().toString("yyyy-MM-dd")

    def on_export(self) -> None:
        try:
            df = self._date_text(self.in_from)
            dt = self._date_text(self.in_to)
            if df:
                validate_ymd(df)
            if dt:
                validate_ymd(dt)
            if df and dt and df > dt:
                raise ValueError("Zakres dat jest niepoprawny: „Od” musi być mniejsze lub równe „Do”.")

            from_label = df or "brak"
            to_label = dt or "brak"

            if self.rb_receipts.isChecked():
                ftype = self.in_receipt_type.currentText()
                item_type = {"Wszystkie": "all", "Urządzenie": "device", "Akcesorium": "accessory"}.get(ftype, "all")
                rows = get_devices_by_date_range(df, dt, item_type)
                if not rows:
                    QMessageBox.information(self, "Info", "Brak danych w tym zakresie.")
                    return
                path, _ = QFileDialog.getSaveFileName(self, "Zapisz raport", f"raport_przyjecia_{from_label}_do_{to_label}.pdf", "PDF (*.pdf)")
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
                path, _ = QFileDialog.getSaveFileName(self, "Zapisz raport", f"raport_dostawy_{from_label}_do_{to_label}.pdf", "PDF (*.pdf)")
                if not path:
                    return
                export_deliveries_to_pdf(path, rows, df, dt, dtype)
                QMessageBox.information(self, "OK", f"Zapisano: {path}")
        except Exception as e:
            log.exception("export failed")
            QMessageBox.critical(self, "Błąd", str(e))
