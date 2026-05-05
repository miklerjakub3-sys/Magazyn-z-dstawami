from __future__ import annotations

import csv
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
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
        form = QGridLayout(form_box)
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

        fields = [
            ("Producent", self.ed_producer), ("Model", self.ed_model), ("Android", self.ed_android),
            ("Procesor", self.ed_processor), ("RAM", self.ed_ram), ("Wersja", self.ed_antutu_version),
            ("Ogólny", self.ed_score_total), ("CPU", self.ed_score_cpu), ("GPU", self.ed_score_gpu),
            ("MEM", self.ed_score_mem), ("UX", self.ed_score_ux), ("Notatki", self.ed_notes),
        ]
        for i, (label, widget) in enumerate(fields):
            row = (i // 4) * 2
            col = i % 4
            form.addWidget(QLabel(label), row, col)
            form.addWidget(widget, row + 1, col)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Dodaj wpis")
        self.btn_add.clicked.connect(self.on_add)
        self.btn_delete = QPushButton("Usuń zaznaczony")
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_export = QPushButton("Eksport CSV")
        self.btn_export.clicked.connect(self.on_export)
        self.btn_pdf = QPushButton("Generuj PDF")
        self.btn_pdf.clicked.connect(self.on_export_pdf)
        self.btn_import = QPushButton("Importuj dane startowe")
        self.btn_import.clicked.connect(self.on_import_seed)
        for b in [self.btn_add, self.btn_delete, self.btn_export, self.btn_pdf, self.btn_import]:
            btn_row.addWidget(b)
        form.addLayout(btn_row, 6, 0, 1, 4)
        root.addWidget(form_box)

        self.table = QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels([
            "ID", "Producent", "Model", "Android", "Procesor", "RAM", "Wersja", "Ogólny", "CPU", "GPU", "MEM", "UX", "Notatki",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        root.addWidget(self.table, 1)

        apk_box = QGroupBox("Pliki APK AnTuTu")
        apk_l = QVBoxLayout(apk_box)
        self.lbl_apk_dir = QLabel(f"Folder stały: {ANTUTU_APK_DIR}")
        self.btn_apk_add = QPushButton("Dodaj plik APK do folderu")
        self.btn_apk_add.clicked.connect(self.on_add_apk)
        apk_l.addWidget(self.lbl_apk_dir)
        apk_l.addWidget(self.btn_apk_add)
        root.addWidget(apk_box)

    def refresh(self) -> None:
        rows = self.svc.list_antutu_results()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        numeric_cols = {0, 7, 8, 9, 10, 11}
        for row_data in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for col, value in enumerate(row_data[:13]):
                item = QTableWidgetItem("" if value is None else str(value))
                if col in numeric_cols and value not in (None, ""):
                    item.setData(Qt.EditRole, int(value))
                self.table.setItem(row_idx, col, item)
        self.table.setSortingEnabled(True)

    def on_add(self) -> None:
        self.svc.add_antutu_result(
            producer=self.ed_producer.text().strip(), model=self.ed_model.text().strip(),
            android_version=self.ed_android.text().strip(), processor=self.ed_processor.text().strip(),
            ram=self.ed_ram.text().strip(), antutu_version=self.ed_antutu_version.text().strip(),
            score_total=self._to_int(self.ed_score_total.text()), score_cpu=self._to_int(self.ed_score_cpu.text()),
            score_gpu=self._to_int(self.ed_score_gpu.text()), score_mem=self._to_int(self.ed_score_mem.text()),
            score_ux=self._to_int(self.ed_score_ux.text()), notes=self.ed_notes.text().strip(),
        )
        for w in [self.ed_producer, self.ed_model, self.ed_android, self.ed_processor, self.ed_ram, self.ed_antutu_version,
                  self.ed_score_total, self.ed_score_cpu, self.ed_score_gpu, self.ed_score_mem, self.ed_score_ux, self.ed_notes]:
            w.clear()
        self.refresh()

    def on_delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.svc.delete_antutu_result(int(self.table.item(row, 0).text()))
        self.refresh()

    def on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Eksport wyników", "antutu_wyniki.csv", "CSV (*.csv)")
        if not path:
            return
        rows = self.svc.list_antutu_results()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["ID", "Producent", "Model", "Android", "Procesor", "RAM", "Wersja", "Ogólny", "CPU", "GPU", "MEM", "UX", "Notatki"])
            for row in rows:
                writer.writerow(row[:13])

    def on_export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Eksport PDF", "antutu_wyniki.pdf", "PDF (*.pdf)")
        if not path:
            return
        rows = self.svc.list_antutu_results()
        doc = SimpleDocTemplate(path, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        data = [["ID", "Producent", "Model", "Android", "Procesor", "RAM", "Wersja", "Ogólny", "CPU", "GPU", "MEM", "UX", "Notatki"]]
        for row in rows:
            data.append([str(x) if x is not None else "" for x in row[:13]])
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        doc.build([Paragraph("Wyniki AnTuTu", styles["Heading2"]), Spacer(1, 8), table])
        QMessageBox.information(self, "PDF", f"Zapisano PDF: {path}")

    def on_add_apk(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "Wybierz APK", "", "APK (*.apk)")
        if src:
            QMessageBox.information(self, "APK", f"Skopiowano do: {self.svc.copy_antutu_apk(src)}")

    def on_import_seed(self) -> None:
        seed = self._seed_rows()
        for row in seed:
            self.svc.add_antutu_result(**row)
        self.refresh()
        QMessageBox.information(self, "Import", f"Zaimportowano {len(seed)} wpisów.")

    @staticmethod
    def _to_int(value: str) -> Optional[int]:
        txt = (value or "").strip().lower().replace("k", "").replace(",", ".")
        if not txt:
            return None
        return int(float(txt))

    @staticmethod
    def _seed_rows():
        return [
            {"producer": "Chainway", "model": "C90", "android_version": "10", "processor": "Medatek Helio P22", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 76, "score_cpu": 30, "score_gpu": 8, "score_mem": 23, "score_ux": 15, "notes": ""},
            {"producer": "Urovo", "model": "i6310", "android_version": "8.1", "processor": "Snapdragon 435", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 77, "score_cpu": 30, "score_gpu": 7, "score_mem": 28, "score_ux": 12, "notes": ""},
            {"producer": "Chainway", "model": "C6000", "android_version": "10", "processor": "Mediatek Helio P22", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 87, "score_cpu": 34, "score_gpu": 11, "score_mem": 24, "score_ux": 17, "notes": ""},
            {"producer": "Chainway", "model": "C61", "android_version": "9", "processor": "Snapdragon 450", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 89, "score_cpu": 38, "score_gpu": 9, "score_mem": 27, "score_ux": 14, "notes": ""},
            {"producer": "Chainway", "model": "C60", "android_version": "11", "processor": "Mediatek Helio P22", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 91, "score_cpu": 35, "score_gpu": 12, "score_mem": 24, "score_ux": 19, "notes": ""},
            {"producer": "Chainway", "model": "C66", "android_version": "9", "processor": "Snapdragon 450", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 91, "score_cpu": 37, "score_gpu": 9, "score_mem": 29, "score_ux": 15, "notes": ""},
            {"producer": "Urovo", "model": "P8100P", "android_version": "10", "processor": "Snapdragon 660", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 95, "score_cpu": 29, "score_gpu": 23, "score_mem": 26, "score_ux": 17, "notes": ""},
            {"producer": "Urovo", "model": "P8100", "android_version": "9", "processor": "Snapdragon 450", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 96, "score_cpu": 39, "score_gpu": 10, "score_mem": 30, "score_ux": 17, "notes": ""},
            {"producer": "Chainway", "model": "C72", "android_version": "8.1", "processor": "Mediatek Helio P23", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 110, "score_cpu": 46, "score_gpu": 15, "score_mem": 27, "score_ux": 20, "notes": ""},
            {"producer": "Chainway", "model": "C75", "android_version": "11", "processor": "MediaTek Helio P35", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 111, "score_cpu": 43, "score_gpu": 13, "score_mem": 26, "score_ux": 29, "notes": ""},
            {"producer": "Chainway", "model": "C72", "android_version": "11", "processor": "Mediatek Helio P35", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 112, "score_cpu": 43, "score_gpu": 13, "score_mem": 27, "score_ux": 28, "notes": ""},
            {"producer": "Chainway", "model": "C66", "android_version": "11", "processor": "Snapdragon 662", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 155, "score_cpu": 69, "score_gpu": 25, "score_mem": 29, "score_ux": 31, "notes": ""},
            {"producer": "Chainway", "model": "C66", "android_version": "9", "processor": "Snapdragon 662", "ram": "3GB", "antutu_version": "8.3.6", "score_total": 157, "score_cpu": 70, "score_gpu": 25, "score_mem": 30, "score_ux": 32, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "9", "processor": "Snapdragon 660", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 181, "score_cpu": 74, "score_gpu": 36, "score_mem": 34, "score_ux": 32, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "13", "processor": "Snapdragon 662", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 180, "score_cpu": 67, "score_gpu": 33, "score_mem": 45, "score_ux": 33, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "13", "processor": "Snapdragon 662", "ram": "8GB", "antutu_version": "8.3.6", "score_total": 186, "score_cpu": 68, "score_gpu": 30, "score_mem": 50, "score_ux": 23, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "11", "processor": "Snapdragon 662", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 183, "score_cpu": 69, "score_gpu": 35, "score_mem": 47, "score_ux": 31, "notes": ""},
            {"producer": "Chainway", "model": "MC50", "android_version": "12", "processor": "Sanpdragon 750G", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 240, "score_cpu": 90, "score_gpu": 51, "score_mem": 50, "score_ux": 47, "notes": ""},
            {"producer": "Honeywall", "model": "EDA10A", "android_version": "12", "processor": "Saodragon 732G", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 265, "score_cpu": 97, "score_gpu": 51, "score_mem": 61, "score_ux": 56, "notes": ""},
            {"producer": "Gigaset", "model": "GX4 Pro", "android_version": "12", "processor": "MediaTek Helio G99", "ram": "6GB", "antutu_version": "8.3.6", "score_total": 306, "score_cpu": 89, "score_gpu": 78, "score_mem": 82, "score_ux": 55, "notes": ""},
            {"producer": "JD China(DT50)", "model": "HP578G", "android_version": "12", "processor": "MediaTek Dimensity 900", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 320, "score_cpu": 102, "score_gpu": 111, "score_mem": 49, "score_ux": 56, "notes": ""},
            {"producer": "Gigaset", "model": "GX6 Pro", "android_version": "12", "processor": "MediaTek Dimensity 900", "ram": "8GB", "antutu_version": "8.3.6", "score_total": 406, "score_cpu": 126, "score_gpu": 121, "score_mem": 80, "score_ux": 78, "notes": ""},
            {"producer": "Samsung", "model": "A54 5G", "android_version": "13", "processor": "Exynos 1380", "ram": "8GB", "antutu_version": "8.3.6", "score_total": 428, "score_cpu": 140, "score_gpu": 135, "score_mem": 75, "score_ux": 77, "notes": ""},
            {"producer": "Urovo", "model": "DT66", "android_version": "A13", "processor": "QCOM4490", "ram": "4GB", "antutu_version": "8.3.6", "score_total": 302, "score_cpu": 112, "score_gpu": 45, "score_mem": 77, "score_ux": 66, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "13", "processor": "Snapdragon 662", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 244, "score_cpu": 87, "score_gpu": 34, "score_mem": 63, "score_ux": 59, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "13", "processor": "Snapdragon 662", "ram": "8GB", "antutu_version": "10.5.2", "score_total": 256, "score_cpu": 88, "score_gpu": 34, "score_mem": 71, "score_ux": 62, "notes": ""},
            {"producer": "Urovo", "model": "DT50", "android_version": "10", "processor": "Snapdragon 660", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 259, "score_cpu": 98, "score_gpu": 37, "score_mem": 56, "score_ux": 67, "notes": ""},
            {"producer": "Urovo", "model": "DT66", "android_version": "13", "processor": "QCM4490", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 422, "score_cpu": 158, "score_gpu": 50, "score_mem": 106, "score_ux": 108, "notes": ""},
            {"producer": "M3 Mobile", "model": "M3US30", "android_version": "13", "processor": "Snapdragon 680", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 313, "score_cpu": 105, "score_gpu": 40, "score_mem": 96, "score_ux": 71, "notes": ""},
            {"producer": "Chainway", "model": "C61", "android_version": "13", "processor": "Snapdragon 662", "ram": "3GB", "antutu_version": "10.5.2", "score_total": 233, "score_cpu": 87, "score_gpu": 35, "score_mem": 56, "score_ux": 54, "notes": ""},
            {"producer": "Chainway", "model": "MC51 5G", "android_version": "A14", "processor": "QCM4490", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 437, "score_cpu": 164, "score_gpu": 51, "score_mem": 105, "score_ux": 115, "notes": ""},
            {"producer": "Chainway", "model": "MC95", "android_version": "A12", "processor": "Mediatek MT8768CA", "ram": "4GB", "antutu_version": "10.5.2", "score_total": 133, "score_cpu": 45, "score_gpu": 17, "score_mem": 35, "score_ux": 36, "notes": ""},
            {"producer": "Urovo", "model": "DT66", "android_version": "A13", "processor": "QCM4490", "ram": "8GB", "antutu_version": "10.5.2", "score_total": 459, "score_cpu": 168, "score_gpu": 50, "score_mem": 127, "score_ux": 113, "notes": ""},
            {"producer": "Urovo", "model": "DT630", "android_version": "A15", "processor": "Mediatek Dimensity 7300", "ram": "8GB", "antutu_version": "10.5.2", "score_total": 718, "score_cpu": 219, "score_gpu": 152, "score_mem": 184, "score_ux": 161, "notes": ""},
            {"producer": "Chainway", "model": "C63", "android_version": "13", "processor": "QTI SM6115", "ram": "4GB", "antutu_version": "11.0.5", "score_total": 334, "score_cpu": 146, "score_gpu": 29, "score_mem": 88, "score_ux": 76, "notes": ""},
            {"producer": "Chainway", "model": "C61", "android_version": "13", "processor": "QTI SM6115", "ram": "4GB", "antutu_version": "11.0.5", "score_total": 306, "score_cpu": 148, "score_gpu": 24, "score_mem": 80, "score_ux": 54, "notes": ""},
        ]
