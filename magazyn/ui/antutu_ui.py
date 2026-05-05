from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import ANTUTU_APK_DIR


class AntutuTab(QWidget):
    def __init__(self, svc):
        super().__init__()
        self.svc = svc
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        form_box = QGroupBox("Dodaj wynik AnTuTu")
        form = QFormLayout(form_box)
        self.ed_producer = QLineEdit()
        self.ed_model = QLineEdit()
        self.ed_android = QLineEdit()
        self.ed_processor = QLineEdit()
        self.ed_ram = QLineEdit()
        self.ed_antutu_version = QLineEdit()
        self.ed_score_total = QLineEdit()
        self.ed_score_cpu = QLineEdit()
        self.ed_score_gpu = QLineEdit()
        self.ed_score_mem = QLineEdit()
        self.ed_score_ux = QLineEdit()
        self.ed_notes = QLineEdit()

        form.addRow("Producent", self.ed_producer)
        form.addRow("Model", self.ed_model)
        form.addRow("Android", self.ed_android)
        form.addRow("Procesor", self.ed_processor)
        form.addRow("RAM", self.ed_ram)
        form.addRow("Wersja AnTuTu", self.ed_antutu_version)
        form.addRow("Wynik ogólny", self.ed_score_total)
        form.addRow("CPU", self.ed_score_cpu)
        form.addRow("GPU", self.ed_score_gpu)
        form.addRow("MEM", self.ed_score_mem)
        form.addRow("UX", self.ed_score_ux)
        form.addRow("Notatki", self.ed_notes)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Dodaj wpis")
        self.btn_add.clicked.connect(self.on_add)
        self.btn_delete = QPushButton("Usuń zaznaczony")
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_export = QPushButton("Eksportuj do CSV (Excel)")
        self.btn_export.clicked.connect(self.on_export)
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_delete)
        buttons.addWidget(self.btn_export)
        form.addRow(buttons)

        root.addWidget(form_box)

        apk_box = QGroupBox("Pliki APK AnTuTu")
        apk_l = QVBoxLayout(apk_box)
        self.lbl_apk_dir = QLabel(f"Folder stały: {ANTUTU_APK_DIR}")
        self.btn_apk_add = QPushButton("Dodaj plik APK do folderu")
        self.btn_apk_add.clicked.connect(self.on_add_apk)
        self.lbl_apk_hint = QLabel("Tu możesz trzymać instalatory APK, żeby zawsze były pod ręką.")
        self.lbl_apk_hint.setWordWrap(True)
        apk_l.addWidget(self.lbl_apk_dir)
        apk_l.addWidget(self.btn_apk_add)
        apk_l.addWidget(self.lbl_apk_hint)
        root.addWidget(apk_box)

        self.table = QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels([
            "ID", "Producent", "Model", "Android", "Procesor", "RAM", "Wersja", "Ogólny", "CPU", "GPU", "MEM", "UX", "Notatki",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

    def refresh(self) -> None:
        rows = self.svc.list_antutu_results()
        self.table.setRowCount(0)
        for row_data in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for col, value in enumerate(row_data[:13]):
                item = QTableWidgetItem("" if value is None else str(value))
                if col == 0:
                    item.setData(Qt.UserRole, int(value))
                self.table.setItem(row_idx, col, item)

    def on_add(self) -> None:
        try:
            self.svc.add_antutu_result(
                producer=self.ed_producer.text().strip(),
                model=self.ed_model.text().strip(),
                android_version=self.ed_android.text().strip(),
                processor=self.ed_processor.text().strip(),
                ram=self.ed_ram.text().strip(),
                antutu_version=self.ed_antutu_version.text().strip(),
                score_total=self._to_int(self.ed_score_total.text()),
                score_cpu=self._to_int(self.ed_score_cpu.text()),
                score_gpu=self._to_int(self.ed_score_gpu.text()),
                score_mem=self._to_int(self.ed_score_mem.text()),
                score_ux=self._to_int(self.ed_score_ux.text()),
                notes=self.ed_notes.text().strip(),
            )
            for w in [self.ed_producer, self.ed_model, self.ed_android, self.ed_processor, self.ed_ram, self.ed_antutu_version,
                      self.ed_score_total, self.ed_score_cpu, self.ed_score_gpu, self.ed_score_mem, self.ed_score_ux, self.ed_notes]:
                w.clear()
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Błąd", str(e))

    def on_delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        record_id = int(self.table.item(row, 0).text())
        self.svc.delete_antutu_result(record_id)
        self.refresh()

    def on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Eksport wyników", "antutu_wyniki.csv", "CSV (*.csv)")
        if not path:
            return
        rows = self.svc.list_antutu_results()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["ID", "Producent", "Model", "Android", "Procesor", "RAM", "Wersja AnTuTu", "Wynik", "CPU", "GPU", "MEM", "UX", "Notatki"])
            for row in rows:
                writer.writerow(row[:13])
        QMessageBox.information(self, "Eksport", f"Zapisano plik: {path}")

    def on_add_apk(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "Wybierz APK", "", "APK (*.apk)")
        if not src:
            return
        dest = self.svc.copy_antutu_apk(src)
        QMessageBox.information(self, "APK", f"Skopiowano do: {dest}")

    @staticmethod
    def _to_int(value: str) -> Optional[int]:
        txt = (value or "").strip()
        if not txt:
            return None
        return int(txt)
