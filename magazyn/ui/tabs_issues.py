#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHeaderView,
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
        self.refresh_history()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.card_form = QFrame()
        self.card_form.setProperty("card", True)
        card_l = QVBoxLayout(self.card_form)
        card_l.setContentsMargins(12, 12, 12, 12)
        root.addWidget(self.card_form)

        top = QHBoxLayout()
        card_l.addLayout(top)

        seller_box = QGroupBox("Wystawca (stałe dane)")
        seller_l = QVBoxLayout(seller_box)
        seller_l.addWidget(QLabel(
            "AXED serwis s.c.\n"
            "ul. Wagrowska 2\n"
            "61-369 Poznań\n"
            "email: biuro@axedserwis.com.pl\n"
            "tel: 600 373 202\n\n"
            "NIP: 7822837756\n"
            "Regon: 381387430"
        ))
        top.addWidget(seller_box, 1)

        buyer_box = QGroupBox("Odbiorca (firma kupująca)")
        buyer_form = QFormLayout(buyer_box)
        self.in_company = QLineEdit()
        self.in_address = QLineEdit()
        self.in_place = QLineEdit("Poznań")
        self.in_company.setPlaceholderText("Np. Firma XYZ Sp. z o.o.")
        self.in_address.setPlaceholderText("Np. ul. Jasnogórska 15/14, 42-200 Częstochowa")
        buyer_form.addRow("Nazwa firmy", self.in_company)
        buyer_form.addRow("Ulica / adres", self.in_address)
        buyer_form.addRow("Miejsce wystawienia", self.in_place)
        top.addWidget(buyer_box, 2)

        row = QHBoxLayout()
        card_l.addLayout(row)
        self.in_item_code = QLineEdit()
        self.in_item_name = QLineEdit()
        self.in_item_qty = QSpinBox()
        self.in_item_qty.setRange(1, 1_000_000)
        self.in_item_qty.setValue(1)
        self.btn_add_item = QPushButton("Dodaj pozycję")
        self.btn_remove_item = QPushButton("Usuń zaznaczoną")
        row.addWidget(QLabel("Kod:"))
        row.addWidget(self.in_item_code)
        row.addWidget(QLabel("Nazwa towaru:"))
        row.addWidget(self.in_item_name, 1)
        row.addWidget(QLabel("Ilość (szt.):"))
        row.addWidget(self.in_item_qty)
        row.addWidget(self.btn_add_item)
        row.addWidget(self.btn_remove_item)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Kod towaru", "Nazwa towaru", "Ilość (szt.)"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        card_l.addWidget(self.table, 1)

        self.btn_generate = QPushButton("Generuj PDF WZ")
        self.btn_generate.setEnabled(PDF_AVAILABLE)
        card_l.addWidget(self.btn_generate)

        if not PDF_AVAILABLE:
            card_l.addWidget(QLabel("Brak reportlab – generowanie WZ PDF wyłączone. Zainstaluj: pip install reportlab"))

        hist_card = QFrame()
        hist_card.setProperty("card", True)
        hist_l = QVBoxLayout(hist_card)
        hist_l.setContentsMargins(12, 12, 12, 12)
        hist_l.addWidget(QLabel("Historia wydań"))
        self.hist_table = QTableWidget(0, 6)
        self.hist_table.setHorizontalHeaderLabels(["ID", "Data", "Miejsce", "Odbiorca", "Pozycji", "PDF"])
        self.hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.hist_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.hist_table.setSelectionMode(QTableWidget.SingleSelection)
        hist_l.addWidget(self.hist_table)
        self.hist_preview = QLabel("Podgląd wpisu: wybierz dokument z historii, aby zobaczyć szczegóły.")
        self.hist_preview.setWordWrap(True)
        self.hist_preview.setProperty("subtitle", True)
        hist_l.addWidget(self.hist_preview)
        self.hist_items = QTableWidget(0, 3)
        self.hist_items.setHorizontalHeaderLabels(["Kod", "Nazwa", "Ilość"])
        self.hist_items.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hist_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.hist_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hist_l.addWidget(self.hist_items)
        self.btn_delete_history = QPushButton("Usuń zaznaczony wpis historii")
        hist_l.addWidget(self.btn_delete_history)
        root.addWidget(hist_card, 1)

        self.btn_add_item.clicked.connect(self.on_add_item)
        self.btn_remove_item.clicked.connect(self.on_remove_item)
        self.btn_generate.clicked.connect(self.on_generate_pdf)
        self.hist_table.itemSelectionChanged.connect(self.on_history_selected)
        self.btn_delete_history.clicked.connect(self.on_delete_history)

    def on_add_item(self) -> None:
        name = self.in_item_name.text().strip()
        qty = int(self.in_item_qty.value())
        if not name:
            QMessageBox.information(self, "Info", "Wpisz nazwę pozycji.")
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(self.in_item_code.text().strip()))
        self.table.setItem(row, 1, QTableWidgetItem(name))
        self.table.setItem(row, 2, QTableWidgetItem(str(qty)))
        self.in_item_code.clear()
        self.in_item_name.clear()
        self.in_item_name.setFocus()

    def on_remove_item(self) -> None:
        current = self.table.currentRow()
        if current >= 0:
            self.table.removeRow(current)

    def _collect_items(self):
        items = []
        for row in range(self.table.rowCount()):
            code_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            qty_item = self.table.item(row, 2)
            code = (code_item.text() if code_item else "").strip()
            name = (name_item.text() if name_item else "").strip()
            qty_raw = (qty_item.text() if qty_item else "1").strip()
            if not name:
                continue
            try:
                qty = max(1, int(qty_raw))
            except ValueError:
                qty = 1
            items.append({"code": code, "name": name, "qty": qty})
        return items

    def refresh_history(self) -> None:
        try:
            rows = self.svc.list_issue_history(limit=300)
        except Exception:
            log.exception("issue history load failed")
            rows = []

        self.hist_table.setRowCount(0)
        for r in rows:
            row = self.hist_table.rowCount()
            self.hist_table.insertRow(row)
            self.hist_table.setItem(row, 0, QTableWidgetItem(str(r[0])))
            self.hist_table.setItem(row, 1, QTableWidgetItem(r[1] or ""))
            self.hist_table.setItem(row, 2, QTableWidgetItem(r[2] or ""))
            self.hist_table.setItem(row, 3, QTableWidgetItem(r[3] or ""))
            self.hist_table.setItem(row, 4, QTableWidgetItem(str(len(r[5] or []))))
            self.hist_table.setItem(row, 5, QTableWidgetItem(r[6] or ""))

    def on_history_selected(self) -> None:
        idx = self.hist_table.currentRow()
        if idx < 0:
            return
        try:
            issue_id = int(self.hist_table.item(idx, 0).text())
        except Exception:
            return
        rows = self.svc.list_issue_history(limit=300)
        selected = None
        for r in rows:
            if int(r[0]) == issue_id:
                selected = r
                break
        if not selected:
            return
        self.hist_preview.setText(
            f"ID: {selected[0]} | Data: {selected[1]} | Miejsce: {selected[2]}\n"
            f"Odbiorca: {selected[3]}\nAdres: {selected[4]}\nPDF: {selected[6] or 'brak'}"
        )
        self.hist_items.setRowCount(0)
        for item in (selected[5] or []):
            row = self.hist_items.rowCount()
            self.hist_items.insertRow(row)
            self.hist_items.setItem(row, 0, QTableWidgetItem(str(item.get("code", ""))))
            self.hist_items.setItem(row, 1, QTableWidgetItem(str(item.get("name", ""))))
            self.hist_items.setItem(row, 2, QTableWidgetItem(str(item.get("qty", ""))))

    def on_delete_history(self) -> None:
        idx = self.hist_table.currentRow()
        if idx < 0:
            QMessageBox.information(self, "Info", "Zaznacz wpis historii do usunięcia.")
            return
        issue_id = self.hist_table.item(idx, 0).text()
        prompts = [
            "Potwierdzenie 1/3: na pewno usunąć wpis historii?",
            "Potwierdzenie 2/3: ta operacja jest nieodwracalna. Kontynuować?",
            f"Potwierdzenie 3/3: usuń wpis ID={issue_id}?",
        ]
        for msg in prompts:
            if QMessageBox.question(self, "Potwierdzenie usunięcia", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        self.svc.delete_issue_history(int(issue_id))
        self.refresh_history()
        self.hist_items.setRowCount(0)
        self.hist_preview.setText("Wpis usunięty.")

    def on_generate_pdf(self) -> None:
        try:
            company = self.in_company.text().strip()
            address = self.in_address.text().strip()
            place = self.in_place.text().strip()
            items = self._collect_items()

            if not company:
                QMessageBox.information(self, "Info", "Podaj nazwę firmy odbiorcy.")
                return
            if not address:
                QMessageBox.information(self, "Info", "Podaj adres firmy odbiorcy.")
                return
            if not place:
                QMessageBox.information(self, "Info", "Podaj miejsce wystawienia.")
                return
            if not items:
                QMessageBox.information(self, "Info", "Dodaj minimum jedną pozycję.")
                return

            if QMessageBox.question(
                self,
                "Potwierdzenie",
                "Czy na pewno chcesz wygenerować PDF WZ i zapisać dokument w historii wydań?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            ) != QMessageBox.Yes:
                return

            issue_date = date.today().isoformat()
            default_name = f"WZ_{company}_{issue_date}.pdf".replace(" ", "_")
            path, _ = QFileDialog.getSaveFileName(self, "Zapisz dokument WZ", default_name, "PDF (*.pdf)")
            if not path:
                return

            export_wz_to_pdf(path, company, address, place, items, issue_date=issue_date)
            self.svc.add_issue_history(issue_date, place, company, address, items, pdf_path=path)
            self.refresh_history()
            QMessageBox.information(self, "OK", f"WZ zapisano: {path}\nDokument dodano do historii.")
        except Exception as e:
            log.exception("wz export failed")
            QMessageBox.critical(self, "Błąd", str(e))
