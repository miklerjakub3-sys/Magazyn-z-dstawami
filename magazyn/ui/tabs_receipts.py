#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QTableWidget,
    QLabel,
    QCheckBox,
    QFileDialog,
    QDialog,
    QTextEdit,
)

from ..config import MAX_RESULTS_PER_PAGE, ITEM_TYPE_TO_LABEL
from ..services import MagazynService
from ..utils import today_str, validate_ymd, parse_line_fields
from ..log import get_logger
from .widgets import fill_table

log = get_logger("magazyn.ui.receipts")


class ImportDialog(QDialog):
    def __init__(self, parent: QWidget, svc: MagazynService, on_done) -> None:
        super().__init__(parent)
        self.svc = svc
        self.on_done = on_done

        self.setWindowTitle("Import przyjęć")
        self.resize(860, 520)

        root = QVBoxLayout(self)

        top = QFormLayout()
        root.addLayout(top)

        self.var_date = QLineEdit(today_str())
        self.var_type = QComboBox()
        self.var_type.addItems(["Urządzenie", "Akcesorium"])
        self.var_name = QLineEdit()
        self.var_prod = QLineEdit()

        top.addRow("Data (YYYY-MM-DD)", self.var_date)
        top.addRow("Typ", self.var_type)
        top.addRow("Nazwa (dla urządzeń)", self.var_name)
        top.addRow("Kod prod. (opcjonalnie)", self.var_prod)

        self.txt = QTextEdit()
        self.txt.setPlaceholderText(
    "URZĄDZENIA: 1 linia = Nazwa;SN;IMEI1;IMEI2;KodProd (średnik/komma/tab)\n"
    "AKCESORIA:  1 linia = SN/Kod\n"
)
        root.addWidget(self.txt, 1)

        btns = QHBoxLayout()
        root.addLayout(btns)

        self.btn_import = QPushButton("Importuj")
        self.btn_close = QPushButton("Zamknij")
        btns.addWidget(self.btn_import)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)

        self.btn_close.clicked.connect(self.close)
        self.btn_import.clicked.connect(self.do_import)

    def do_import(self) -> None:
        raw = (self.txt.toPlainText() or "").strip()
        if not raw:
            QMessageBox.information(self, "Info", "Wklej przynajmniej jedną linię.")
            return

        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            QMessageBox.information(self, "Info", "Nie znaleziono poprawnych linii.")
            return

        try:
            validate_ymd(self.var_date.text().strip())
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Niepoprawna data: {e}")
            return

        item_type = "device" if self.var_type.currentText() == "Urządzenie" else "accessory"
        received_date = self.var_date.text().strip()
        name_default = self.var_name.text().strip()
        prod_default = self.var_prod.text().strip()

        ok = 0
        errors: List[str] = []

        for ln in lines:
            try:
                parts = parse_line_fields(ln)

                if item_type == "accessory":
                    sn = parts[0] if parts else ""
                    if not sn:
                        raise ValueError("Brak SN/Kod")
                    self.svc.add_device(received_date, "accessory", "", sn, "", "", "", None)
                else:
                    # name; sn; imei1; imei2; prod
                    nm = parts[0] if len(parts) > 0 and parts[0] else name_default
                    sn = parts[1] if len(parts) > 1 else ""
                    i1 = parts[2] if len(parts) > 2 else ""
                    i2 = parts[3] if len(parts) > 3 else ""
                    pr = parts[4] if len(parts) > 4 else prod_default

                    if not nm:
                        raise ValueError("Brak nazwy")

                    self.svc.add_device(received_date, "device", nm, sn, i1, i2, pr, None)

                ok += 1
            except Exception as e:
                errors.append(f"{ln} -> {e}")

        if errors:
            QMessageBox.warning(
                self,
                "Import – częściowo",
                f"Zaimportowano: {ok}\nBłędy: {len(errors)}\n\n" + "\n".join(errors[:10]),
            )
        else:
            QMessageBox.information(self, "OK", f"Zaimportowano: {ok}")

        if callable(self.on_done):
            self.on_done()
        self.close()


class EditDeviceDialog(QDialog):
    def __init__(self, parent: QWidget, svc: MagazynService, device_id: int, on_done) -> None:
        super().__init__(parent)
        self.svc = svc
        self.device_id = int(device_id)
        self.on_done = on_done

        self.setWindowTitle(f"Edycja przyjęcia ID={device_id}")
        self.resize(520, 360)

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.in_date = QLineEdit()
        self.in_type = QComboBox()
        self.in_type.addItems(["Urządzenie", "Akcesorium"])
        self.in_name = QLineEdit()
        self.in_sn = QLineEdit()
        self.in_imei1 = QLineEdit()
        self.in_imei2 = QLineEdit()
        self.in_prod = QLineEdit()
        self.in_notes = QLineEdit()

        form.addRow("Data (YYYY-MM-DD)", self.in_date)
        form.addRow("Typ", self.in_type)
        form.addRow("Nazwa", self.in_name)
        form.addRow("SN/Kod", self.in_sn)
        form.addRow("IMEI1", self.in_imei1)
        form.addRow("IMEI2", self.in_imei2)
        form.addRow("Kod prod.", self.in_prod)
        form.addRow("Uwagi", self.in_notes)

        btns = QHBoxLayout()
        root.addLayout(btns)
        self.btn_save = QPushButton("Zapisz")
        self.btn_cancel = QPushButton("Anuluj")
        btns.addWidget(self.btn_save)
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)

        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self.save)

        self.load()

    def load(self) -> None:
        row = self.svc.get_device(self.device_id)
        if not row:
            QMessageBox.critical(self, "Błąd", "Nie znaleziono rekordu.")
            self.close()
            return

        self.in_date.setText(row[1] or "")
        self.in_type.setCurrentText("Urządzenie" if row[2] == "device" else "Akcesorium")
        self.in_name.setText(row[3] or "")
        self.in_sn.setText(row[4] or "")
        self.in_imei1.setText(row[5] or "")
        self.in_imei2.setText(row[6] or "")
        self.in_prod.setText(row[7] or "")
        self.in_notes.setText(row[8] or "")

    def save(self) -> None:
        try:
            validate_ymd(self.in_date.text().strip())
            item_type = "device" if self.in_type.currentText() == "Urządzenie" else "accessory"

            self.svc.update_device(
                device_id=self.device_id,
                received_date=self.in_date.text().strip(),
                item_type=item_type,
                device_name=self.in_name.text().strip(),
                serial_number=self.in_sn.text().strip(),
                imei1=self.in_imei1.text().strip(),
                imei2=self.in_imei2.text().strip(),
                production_code=self.in_prod.text().strip(),
                notes=self.in_notes.text().strip(),
            )

            if callable(self.on_done):
                self.on_done()
            self.close()
        except Exception as e:
            log.exception("edit save failed")
            QMessageBox.critical(self, "Błąd", str(e))


class ReceiptsTab(QWidget):
    def __init__(self, svc: MagazynService) -> None:
        super().__init__()
        self.svc = svc
        self.page = 0
        self.total_pages = 1
        self.total = 0

        self._build()
        self._install_shortcuts()
        self.refresh()

        QTimer.singleShot(50, self._focus_scan_start)

    def _build(self) -> None:
        root = QVBoxLayout(self)

        # --- Top controls (form + options + buttons)
        top = QHBoxLayout()
        root.addLayout(top)

        form = QFormLayout()
        top.addLayout(form, stretch=4)

        self.in_date = QLineEdit(today_str())
        self.in_mode = QComboBox()
        self.in_mode.addItems(["Urządzenie", "Akcesorium"])
        self.in_name = QLineEdit()
        self.in_sn = QLineEdit()
        self.in_imei1 = QLineEdit()
        self.in_imei2 = QLineEdit()
        self.in_prod = QLineEdit()

        form.addRow("Data (YYYY-MM-DD)", self.in_date)
        form.addRow("Typ", self.in_mode)
        form.addRow("Nazwa", self.in_name)
        form.addRow("SN/Kod", self.in_sn)
        form.addRow("IMEI1", self.in_imei1)
        form.addRow("IMEI2", self.in_imei2)
        form.addRow("Kod prod.", self.in_prod)

        opts = QVBoxLayout()
        top.addLayout(opts, stretch=2)
        self.chk_scan = QCheckBox("Tryb skanowania (fokus na SN)")
        self.chk_cont = QCheckBox("Ciągłe (Enter=Dodaj)")
        self.chk_scan.setChecked(True)
        opts.addWidget(self.chk_scan)
        opts.addWidget(self.chk_cont)
        opts.addStretch(1)

        btns = QVBoxLayout()
        top.addLayout(btns, stretch=2)

        self.btn_add = QPushButton("Dodaj")
        self.btn_edit = QPushButton("Edytuj")
        self.btn_del = QPushButton("Usuń")
        self.btn_import = QPushButton("Import…")
        self.btn_export = QPushButton("Eksport CSV…")
        self.btn_copy = QPushButton("Kopiuj SN")

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_import)
        btns.addWidget(self.btn_export)
        btns.addWidget(self.btn_copy)
        btns.addStretch(1)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_import.clicked.connect(self.on_open_import)
        self.btn_export.clicked.connect(self.on_export_csv)
        self.btn_copy.clicked.connect(self.copy_selected_sn)

        self.in_mode.currentTextChanged.connect(self.apply_mode)

        # enter flow like improved
        for w in (self.in_name, self.in_sn, self.in_imei1, self.in_imei2, self.in_prod):
            w.returnPressed.connect(self._scan_next)
        self.in_name.returnPressed.connect(self._scan_full_line)

        # --- Search row
        search_row = QHBoxLayout()
        root.addLayout(search_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj (nazwa, SN, IMEI, uwagi...)")

        self.filter_type = QComboBox()
        self.filter_type.addItems(["Wszystkie", "Urządzenie", "Akcesorium"])

        self.btn_search = QPushButton("Szukaj")
        self.btn_clear = QPushButton("Wyczyść")

        search_row.addWidget(QLabel("Szukaj:"))
        search_row.addWidget(self.search, stretch=2)
        search_row.addWidget(QLabel("Filtr:"))
        search_row.addWidget(self.filter_type)
        search_row.addWidget(self.btn_search)
        search_row.addWidget(self.btn_clear)

        self.btn_search.clicked.connect(self.on_search)
        self.btn_clear.clicked.connect(self.on_clear)

        # --- Table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        root.addWidget(self.table, stretch=1)

        self.table.cellDoubleClicked.connect(lambda r, c: self.on_edit())

        # --- Paging
        paging_row = QHBoxLayout()
        root.addLayout(paging_row)

        self.lbl_page = QLabel("")
        self.btn_first = QPushButton("⏮")
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.btn_last = QPushButton("⏭")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setFixedWidth(44)

        paging_row.addWidget(self.btn_first)
        paging_row.addWidget(self.btn_prev)
        paging_row.addWidget(self.lbl_page)
        paging_row.addWidget(self.btn_next)
        paging_row.addWidget(self.btn_last)
        paging_row.addStretch(1)

        self.btn_first.clicked.connect(lambda: self._goto(0))
        self.btn_prev.clicked.connect(lambda: self._goto(max(0, self.page - 1)))
        self.btn_next.clicked.connect(lambda: self._goto(min(self.total_pages - 1, self.page + 1)))
        self.btn_last.clicked.connect(lambda: self._goto(max(0, self.total_pages - 1)))

        self.apply_mode()

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_selected_sn)
        QShortcut(QKeySequence("Delete"), self, self.on_delete)

    def apply_mode(self) -> None:
        is_accessory = self.in_mode.currentText() == "Akcesorium"
        self.in_name.setEnabled(not is_accessory)
        self.in_imei1.setEnabled(not is_accessory)
        self.in_imei2.setEnabled(not is_accessory)
        self.in_prod.setEnabled(not is_accessory)

    def _focus_scan_start(self):
        if self.chk_scan.isChecked():
            self.in_name.setFocus()
            self.in_name.selectAll()
        else:
            self.in_name.setFocus()
            self.in_name.selectAll()

    def _scan_next(self) -> None:
        if self.chk_cont.isChecked():
            if self.in_mode.currentText() == "Akcesorium":
                self.on_add()
                return

            if not self.in_imei1.text().strip():
                self.in_imei1.setFocus()
                self.in_imei1.selectAll()
                return
            if not self.in_imei2.text().strip():
                self.in_imei2.setFocus()
                self.in_imei2.selectAll()
                return
            if not self.in_prod.text().strip():
                self.in_prod.setFocus()
                self.in_prod.selectAll()
                return

            self.on_add()
            return

        w = self.focusWidget()
        if w == self.in_name:
            self.in_sn.setFocus()
            self.in_sn.selectAll()
        elif w == self.in_sn:
            if self.in_mode.currentText() == "Akcesorium":
                self.on_add()
            else:
                self.in_imei1.setFocus()
                self.in_imei1.selectAll()
        elif w == self.in_imei1:
            self.in_imei2.setFocus()
            self.in_imei2.selectAll()
        elif w == self.in_imei2:
            self.in_prod.setFocus()
            self.in_prod.selectAll()
        elif w == self.in_prod:
            self.on_add()

    def _scan_full_line(self):
        """
        Pełny skan z jednego kodu:
        NAZWA;SN;IMEI1;IMEI2;DATA_PROD
        separator: ; , TAB lub |
        """
        if not self.chk_cont.isChecked():
            return

        raw = self.in_name.text().strip()
        if not raw:
            return

        try:
            parts = parse_line_fields(raw)

            if len(parts) >= 1:
                self.in_name.setText(parts[0])
            if len(parts) >= 2:
                self.in_sn.setText(parts[1])
            if len(parts) >= 3:
                self.in_imei1.setText(parts[2])
            if len(parts) >= 4:
                self.in_imei2.setText(parts[3])
            if len(parts) >= 5:
                self.in_prod.setText(parts[4])

            self.on_add()

        except Exception as e:
            QMessageBox.critical(self, "Błąd skanowania", str(e))

    def _goto(self, page: int) -> None:
        self.page = page
        self.refresh()

    def _selected_ids(self) -> List[int]:
        ids: List[int] = []
        for idx in self.table.selectionModel().selectedRows():
            try:
                ids.append(int(self.table.item(idx.row(), 0).text()))
            except Exception:
                pass
        return ids

    def _find_duplicates(self, rows: Sequence[Sequence[Any]]):
        sn_count: Dict[str, int] = {}
        imei_count: Dict[str, int] = {}

        def add_count(d: Dict[str, int], k: str) -> None:
            if not k:
                return
            d[k] = d.get(k, 0) + 1

        for r in rows:
            sn = (r[4] or "").strip()
            i1 = (r[5] or "").strip()
            i2 = (r[6] or "").strip()
            add_count(sn_count, sn)
            add_count(imei_count, i1)
            add_count(imei_count, i2)

        dup_sn = {k for k, v in sn_count.items() if k and v > 1}
        dup_imei = {k for k, v in imei_count.items() if k and v > 1}
        return dup_sn, dup_imei

    def on_add(self) -> None:
        try:
            validate_ymd(self.in_date.text().strip())
            item_type = "device" if self.in_mode.currentText() == "Urządzenie" else "accessory"

            dups = self.svc.find_device_duplicates(
                self.in_sn.text(), self.in_imei1.text(), self.in_imei2.text()
            )
            if dups:
                if (
                    QMessageBox.question(
                        self,
                        "Możliwy duplikat",
                        f"Znaleziono {len(dups)} podobnych rekordów (SN/IMEI). Dodać mimo to?",
                    )
                    != QMessageBox.Yes
                ):
                    return

            self.svc.add_device(
                received_date=self.in_date.text().strip(),
                item_type=item_type,
                device_name=self.in_name.text().strip(),
                serial_number=self.in_sn.text().strip(),
                imei1=self.in_imei1.text().strip(),
                imei2=self.in_imei2.text().strip(),
                production_code=self.in_prod.text().strip(),
            )

            self.in_sn.clear()
            self.in_imei1.clear()
            self.in_imei2.clear()
            self.in_prod.clear()

            self.refresh()
            self._focus_scan_start()
        except Exception as e:
            log.exception("Add device failed")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_edit(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "Info", "Zaznacz dokładnie 1 rekord do edycji.")
            return
        dlg = EditDeviceDialog(self, self.svc, ids[0], on_done=self.refresh)
        dlg.exec()

    def on_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Info", "Zaznacz rekord(y) do usunięcia.")
            return
        if QMessageBox.question(self, "Potwierdź", f"Usunąć {len(ids)} rekordów?") != QMessageBox.Yes:
            return
        try:
            for did in ids:
                self.svc.delete_device(did)
            self.refresh()
        except Exception as e:
            log.exception("Delete device failed")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_open_import(self) -> None:
        dlg = ImportDialog(self, self.svc, on_done=self.refresh)
        dlg.exec()

    def on_export_csv(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Eksportuj CSV", "przyjecia.csv", "CSV (*.csv)"
            )
            if not path:
                return

            item_type = {
                "Wszystkie": "all",
                "Urządzenie": "device",
                "Akcesorium": "accessory",
            }.get(self.filter_type.currentText(), "all")

            q = self.search.text()

            rows_out: List[List[str]] = []
            offset = 0
            while True:
                pr = self.svc.search_devices(q, item_type, "received_date", "DESC", 1000, offset)
                if not pr.rows:
                    break
                for r in pr.rows:
                    rows_out.append([str(x or "") for x in r])
                offset += len(pr.rows)
                if offset >= pr.total_count:
                    break

            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(
                    [
                        "id",
                        "received_date",
                        "item_type",
                        "device_name",
                        "serial_number",
                        "imei1",
                        "imei2",
                        "production_code",
                        "notes",
                        "created_at",
                        "delivery_id",
                    ]
                )
                w.writerows(rows_out)

            QMessageBox.information(self, "OK", f"Zapisano: {path}")
        except Exception as e:
            log.exception("export csv failed")
            QMessageBox.critical(self, "Błąd", str(e))

    def copy_selected_sn(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Info", "Zaznacz rekordy w tabeli.")
            return

        sns: List[str] = []
        for idx in rows:
            try:
                sn = (self.table.item(idx.row(), 4).text() or "").strip()
                if sn:
                    sns.append(sn)
            except Exception:
                pass

        if not sns:
            QMessageBox.information(self, "Info", "Brak SN/Kod do skopiowania.")
            return

        QGuiApplication.clipboard().setText("\n".join(sns))
        QMessageBox.information(self, "OK", f"Skopiowano {len(sns)} SN/Kod do schowka.")

    def on_search(self) -> None:
        self.page = 0
        self.refresh()

    def on_clear(self) -> None:
        self.search.clear()
        self.filter_type.setCurrentText("Wszystkie")
        self.page = 0
        self.refresh()

    def refresh(self) -> None:
        try:
            offset = self.page * MAX_RESULTS_PER_PAGE
            item_type = {
                "Wszystkie": "all",
                "Urządzenie": "device",
                "Akcesorium": "accessory",
            }.get(self.filter_type.currentText(), "all")

            pr = self.svc.search_devices(
                query=self.search.text(),
                item_type=item_type,
                order_by="received_date",
                order_dir="DESC",
                limit=MAX_RESULTS_PER_PAGE,
                offset=offset,
            )

            self.total = pr.total_count
            self.total_pages = max(1, (self.total + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE)
            self.lbl_page.setText(f"Strona {self.page+1}/{self.total_pages} | Rekordy: {self.total}")

            dup_sn, dup_imei = self._find_duplicates(pr.rows)

            headers = ["ID", "Data", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Dostawa", "Uwagi", "Utworzono"]
            rows = []
            for r in pr.rows:
                rr = list(r)
                rr[2] = ITEM_TYPE_TO_LABEL.get(rr[2], rr[2])
                rr.insert(8, ("—" if (rr[10] is None) else f"ID={rr[10]}"))
                rows.append([rr[0], rr[1], rr[2], rr[3], rr[4], rr[5], rr[6], rr[7], rr[8], rr[9], rr[10]])

            fill_table(self.table, headers, rows)

            for i, r in enumerate(pr.rows):
                item_type_raw = r[2]
                has_notes = bool((r[8] or "").strip())
                missing_imei = (item_type_raw == "device" and not (r[5] or "").strip())

                sn = (r[4] or "").strip()
                i1 = (r[5] or "").strip()
                i2 = (r[6] or "").strip()

                is_dup = (sn and sn in dup_sn) or (i1 and i1 in dup_imei) or (i2 and i2 in dup_imei)

                if is_dup:
                    bg = QColor("#f8cbad")
                elif missing_imei:
                    bg = QColor("#fff2cc")
                elif has_notes:
                    bg = QColor("#ddebf7")
                elif item_type_raw == "accessory":
                    bg = QColor("#f3f3f3")
                else:
                    bg = None

                if bg is not None:
                    for c in range(self.table.columnCount()):
                        it = self.table.item(i, c)
                        if it:
                            it.setBackground(bg)

        except Exception as e:
            log.exception("Refresh receipts failed")
            QMessageBox.critical(self, "Błąd", str(e))
