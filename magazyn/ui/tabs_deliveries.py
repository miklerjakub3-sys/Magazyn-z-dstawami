#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Any, Optional, Sequence
import os
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QComboBox, QMessageBox, QTableWidget, QLabel, QCheckBox, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QDialog
)
from magazyn.config import DELIVERY_TYPES, ITEM_TYPE_TO_LABEL
from ..config import MAX_RESULTS_PER_PAGE, DELIVERY_TYPES, ITEM_TYPE_TO_LABEL
from ..services import MagazynService
from ..utils import today_str, validate_ymd, one_line
from ..log import get_logger
from .widgets import fill_table
from PySide6.QtWidgets import QDateEdit
from PySide6.QtCore import QDate

log = get_logger("magazyn.ui.deliveries")


class LinkReceiptsDialog(QDialog):
    def __init__(self, parent: QWidget, svc: MagazynService, delivery_id: int, delivery_date: str, on_done=None):
        super().__init__(parent)
        self.svc = svc
        self.delivery_id = int(delivery_id)
        self.delivery_date = delivery_date
        self.on_done = on_done

        self.setWindowTitle(f"Powiąż przyjęcia z dostawą ID={delivery_id}")
        self.resize(1100, 650)

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        root.addLayout(top)
        top.addWidget(QLabel(f"Dostawa ID={delivery_id} | Data: {delivery_date}"))
        top.addWidget(QLabel(f"Dostawa ID={delivery_id} | Data: {delivery_date}"))

        top.addWidget(QLabel("Przyjęcia z dnia:"))
        self.dt_pick = QDateEdit()
        self.dt_pick.setCalendarPopup(True)
        self.dt_pick.setDisplayFormat("yyyy-MM-dd")
        top.addWidget(QLabel("Przyjęcia z dnia:"))

        self.dt_pick = QDateEdit()
        self.dt_pick.setCalendarPopup(True)
        self.dt_pick.setDisplayFormat("yyyy-MM-dd")

        try:
            y, m, d = [int(x) for x in (delivery_date or "").split("-")]
            self.dt_pick.setDate(QDate(y, m, d))
        except Exception:
            self.dt_pick.setDate(QDate.currentDate())

        top.addWidget(self.dt_pick)

        
        self.btn_set_delivery_date = QPushButton("↩ Data dostawy")
        top.addWidget(self.btn_set_delivery_date)
        self.btn_set_delivery_date.clicked.connect(
            lambda: self._set_date(self.delivery_date)
        )

        # ustaw domyślnie na datę dostawy
        try:
            y, m, d = [int(x) for x in (delivery_date or "").split("-")]
            self.dt_pick.setDate(QDate(y, m, d))
        except Exception:
            self.dt_pick.setDate(QDate.currentDate())

        top.addWidget(self.dt_pick)

        self.chk_all = QCheckBox("Pokaż wszystkie z dnia (również powiązane z inną dostawą)")
        top.addWidget(self.chk_all)
        top.addStretch(1)

        self.btn_refresh = QPushButton("Odśwież")
        self.btn_close = QPushButton("Zamknij")
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_close)
        self.btn_close.clicked.connect(self.close)
        self.btn_refresh.clicked.connect(self.refresh)
        self.chk_all.stateChanged.connect(lambda _: self.refresh())
        self.dt_pick.dateChanged.connect(lambda _: self.refresh())

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        root.addLayout(btns)
        self.btn_assign = QPushButton("Powiąż zaznaczone")
        self.btn_unlink = QPushButton("Odłącz zaznaczone")
        btns.addWidget(self.btn_assign)
        btns.addWidget(self.btn_unlink)
        btns.addStretch(1)

        self.btn_assign.clicked.connect(self.assign_selected)
        self.btn_unlink.clicked.connect(self.unlink_selected)

        self.refresh()

    def _set_date(self, s: str):
        try:
            y, m, d = [int(x) for x in (s or "").split("-")]
            self.dt_pick.setDate(QDate(y, m, d))
        except Exception:
            pass

    def _selected_ids(self) -> List[int]:
        ids: List[int] = []
        for idx in self.table.selectionModel().selectedRows():
            try:
                ids.append(int(self.table.item(idx.row(), 0).text()))
            except Exception:
                pass
        return ids

    def refresh(self):
        picked = self.dt_pick.date().toString("yyyy-MM-dd")
        rows = self.svc.list_devices_for_delivery_date(
            picked,
            include_linked_to_other=self.chk_all.isChecked(),
            delivery_id=self.delivery_id
        )

        headers = ["ID","Typ","Nazwa","SN/Kod","IMEI1","IMEI2","Kod prod.","Powiązanie"]
        out = []
        for r in rows:
            linked = int(r[10] or 0)
            if linked == 0:
                label = "BRAK"
            else:
                label = f"ID={linked}"
            out.append([r[0], ITEM_TYPE_TO_LABEL.get(r[2], r[2]), r[3] or "", r[4] or "", r[5] or "", r[6] or "", r[7] or "", label]),
        fill_table(self.table, headers, out)

        # colors: none=greenish, ok=blue, other=orange
        from PySide6.QtGui import QColor
        for i, r in enumerate(rows):
            linked = int(r[10] or 0)
            if linked == 0:
                bg = QColor("#e2f0d9")  # light green
            elif linked == self.delivery_id:
                bg = QColor("#ddebf7")  # light blue
            else:
                bg = QColor("#f8cbad")  # orange
            for c in range(self.table.columnCount()):
                it = self.table.item(i, c)
                if it:
                    it.setBackground(bg)

    def assign_selected(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Info", "Zaznacz przyjęcia do przypisania.")
            return
        try:
            self.svc.assign_devices_to_delivery(ids, self.delivery_id)
            self.refresh()
            if callable(self.on_done):
                self.on_done()
        except Exception as e:
            log.exception("assign failed")
            QMessageBox.critical(self, "Błąd", str(e))

    def unlink_selected(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Info", "Zaznacz przyjęcia do odłączenia.")
            return
        if QMessageBox.question(self, "Potwierdź", f"Usunąć powiązanie dla: {len(ids)} rekordów?") != QMessageBox.Yes:
            return
        try:
            self.svc.clear_devices_delivery(ids)
            self.refresh()
            if callable(self.on_done):
                self.on_done()
        except Exception as e:
            log.exception("unlink failed")
            QMessageBox.critical(self, "Błąd", str(e))


class DeliveriesTab(QWidget):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self.page = 0
        self.total_pages = 1
        self.total = 0
        self.sort_col = 1
        self.sort_dir = Qt.DescendingOrder
        self._build()
        self._install_shortcuts()
        self.refresh_lists()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        # filter
        filt = QHBoxLayout()
        root.addLayout(filt)
        self.f_from = QLineEdit()
        self.f_to = QLineEdit()
        self.f_type = QComboBox(); self.f_type.addItems([""] + DELIVERY_TYPES)
        self.btn_search = QPushButton("Szukaj")
        self.btn_clear = QPushButton("Wyczyść")
        self.btn_export = QPushButton("Eksport CSV…")
        filt.addWidget(QLabel("Od:")); filt.addWidget(self.f_from)
        filt.addWidget(QLabel("Do:")); filt.addWidget(self.f_to)
        filt.addWidget(QLabel("Typ:")); filt.addWidget(self.f_type)
        filt.addWidget(self.btn_search); filt.addWidget(self.btn_clear); filt.addWidget(self.btn_export)
        self.btn_search.clicked.connect(self.on_search)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_export.clicked.connect(self.on_export_csv)

        paging = QHBoxLayout()
        root.addLayout(paging)
        self.lbl_page = QLabel("")
        self.btn_first = QPushButton("⏮"); self.btn_prev = QPushButton("◀"); self.btn_next = QPushButton("▶"); self.btn_last = QPushButton("⏭")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setFixedWidth(44)
        paging.addWidget(self.btn_first); paging.addWidget(self.btn_prev); paging.addWidget(self.lbl_page); paging.addWidget(self.btn_next); paging.addWidget(self.btn_last)
        paging.addStretch(1)
        self.btn_first.clicked.connect(lambda: self._goto(0))
        self.btn_prev.clicked.connect(lambda: self._goto(max(0, self.page - 1)))
        self.btn_next.clicked.connect(lambda: self._goto(min(self.total_pages - 1, self.page + 1)))
        self.btn_last.clicked.connect(lambda: self._goto(max(0, self.total_pages - 1)))

        # splitter: left deliveries table, right attachments + linked devices
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        left = QWidget()
        left_l = QVBoxLayout(left)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSortingEnabled(True)
        left_l.addWidget(self.table, 1)
        split.addWidget(left)

        right = QWidget()
        right_l = QVBoxLayout(right)

        # linked devices panel
        right_l.addWidget(QLabel("Urządzenia przypisane do dostawy:"))
        self.tbl_linked = QTableWidget()
        self.tbl_linked.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_linked.setSelectionMode(QTableWidget.ExtendedSelection)
        right_l.addWidget(self.tbl_linked, 1)

        # attachments panel
        right_l.addWidget(QLabel("Zdjęcia dostawy:"))
        self.list_att = QListWidget()
        right_l.addWidget(self.list_att, 1)

        att_btns = QHBoxLayout()
        right_l.addLayout(att_btns)
        self.btn_attach = QPushButton("Dodaj zdjęcia…")
        self.btn_del_att = QPushButton("Usuń zdjęcie")
        self.btn_open_att = QPushButton("Podgląd")
        att_btns.addWidget(self.btn_attach)
        att_btns.addWidget(self.btn_open_att)
        att_btns.addWidget(self.btn_del_att)
        att_btns.addStretch(1)

        split.addWidget(right)
        split.setSizes([800, 600])

        # form
        form_row = QHBoxLayout()
        root.addLayout(form_row)

        form = QFormLayout()
        form_row.addLayout(form, stretch=3)

        self.in_date = QLineEdit(today_str())
        self.in_sender = QComboBox(); self.in_sender.setEditable(True)
        self.in_courier = QComboBox()
        self.in_courier.setEditable(True)
        self.in_type = QComboBox(); self.in_type.addItems(DELIVERY_TYPES)
        self.in_tracking = QLineEdit()
        self.in_vat = QCheckBox("Faktura VAT")
        self.in_notes = QLineEdit()

        form.addRow("Data (YYYY-MM-DD)", self.in_date)
        form.addRow("Nadawca", self.in_sender)
        form.addRow("Kurier", self.in_courier)
        form.addRow("Typ", self.in_type)
        form.addRow("Nr przesyłki", self.in_tracking)
        form.addRow("", self.in_vat)
        form.addRow("Uwagi", self.in_notes)

        btns = QVBoxLayout()
        form_row.addLayout(btns, stretch=1)
        self.btn_add = QPushButton("Dodaj")
        self.btn_save = QPushButton("Zapisz")
        self.btn_del = QPushButton("Usuń")
        self.btn_link = QPushButton("Powiąż przyjęcia…")
        self.btn_clear_form = QPushButton("Wyczyść formularz")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_link)
        btns.addWidget(self.btn_clear_form)  # 👈 przenieś nad stretch
        btns.addStretch(1)
        self.btn_clear_form.clicked.connect(self.clear_form)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_link.clicked.connect(self.on_link)

        self.btn_attach.clicked.connect(self.on_attach)
        self.btn_del_att.clicked.connect(self.on_delete_attachment)
        self.btn_open_att.clicked.connect(self.on_open_attachment)

        self.table.itemSelectionChanged.connect(self.load_selected)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_sort_clicked)
        self.list_att.itemDoubleClicked.connect(lambda _: self.on_open_attachment())

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Delete"), self, self.on_delete)

    def refresh_lists(self) -> None:
        try:
            senders = [""] + self.svc.list_senders()
            couriers = [""] + self.svc.list_couriers()
            self.in_sender.clear(); self.in_sender.addItems(senders)
            self.in_courier.clear(); self.in_courier.addItems(couriers)
        except Exception:
            log.exception("refresh lists")

    def _goto(self, page: int) -> None:
        self.page = page
        self.refresh()

    def _selected_delivery_id(self) -> Optional[int]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        try:
            return int(self.table.item(rows[0].row(), 0).text())
        except Exception:
            return None

    def on_search(self) -> None:
        self.page = 0
        self.refresh()

    def on_clear(self) -> None:
        self.f_from.clear(); self.f_to.clear(); self.f_type.setCurrentText("")
        self.page = 0
        self.refresh()

    def on_header_sort_clicked(self, col: int) -> None:
        if self.sort_col == col:
            self.sort_dir = Qt.AscendingOrder if self.sort_dir == Qt.DescendingOrder else Qt.DescendingOrder
        else:
            self.sort_col = col
            self.sort_dir = Qt.AscendingOrder
        self.page = 0
        self.refresh()

    def clear_form(self):
        """Czyści formularz dostawy (bez usuwania z bazy)"""
        self.in_date.setText(today_str())
        self.in_sender.setCurrentText("")
        self.in_courier.setCurrentText("")
        self.in_type.setCurrentIndex(0)
        self.in_tracking.clear()
        self.in_vat.setChecked(False)
        self.in_notes.clear()

        # czyść panele boczne
        self.list_att.clear()
        fill_table(
            self.tbl_linked,
            ["ID","Typ","Nazwa","SN/Kod","IMEI1","IMEI2","Kod prod.","Uwagi"],
            []
        )

    def refresh(self) -> None:
        try:
            df = self.f_from.text().strip()
            dt = self.f_to.text().strip()
            if (df and not dt) or (dt and not df):
                raise ValueError("Podaj oba pola zakresu dat (Od i Do) albo zostaw puste.")
            if df and dt:
                validate_ymd(df); validate_ymd(dt)

            offset = self.page * MAX_RESULTS_PER_PAGE
            pr = self.svc.search_deliveries(
                date_from=df,
                date_to=dt,
                delivery_type=self.f_type.currentText().strip(),
                order_by={
                    0: "id",
                    1: "delivery_date",
                    2: "sender_name",
                    3: "courier_name",
                    4: "delivery_type",
                    5: "tracking_number",
                    6: "invoice_vat",
                    7: "notes",
                    8: "created_at",
                }.get(self.sort_col, "delivery_date"),
                order_dir="ASC" if self.sort_dir == Qt.AscendingOrder else "DESC",
                limit=MAX_RESULTS_PER_PAGE,
                offset=offset,
            )
            self.total = pr.total_count
            self.total_pages = max(1, (self.total + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE)
            self.lbl_page.setText(f"Strona {self.page+1}/{self.total_pages} | Rekordy: {self.total}")

            headers = ["ID","Data","Nadawca","Kurier","Typ","Nr","VAT","Uwagi","Utworzono"]
            rows = []
            for r in pr.rows:
                vat = "TAK" if int(r[6] or 0) == 1 else "NIE"
                rows.append([r[0], r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", vat, one_line(r[7] or ""), r[8] or ""])
            fill_table(self.table, headers, rows)
            self.table.horizontalHeader().setSortIndicator(self.sort_col, self.sort_dir)

            # after refresh, load selected
            self.load_selected()
        except Exception as e:
            log.exception("refresh deliveries")
            QMessageBox.critical(self, "Błąd", str(e))

    def load_selected(self) -> None:
        did = self._selected_delivery_id()
        # clear side panels
        self.list_att.clear()
        fill_table(self.tbl_linked, ["ID","Typ","Nazwa","SN/Kod","IMEI1","IMEI2","Kod prod.","Uwagi"], [])
        if not did:
            return
        try:
            row = self.svc.get_delivery(did)
            if not row:
                return
            (_id, d, sender, courier, dtype, tracking, vat, notes, created) = row
            self.in_date.setText(d or "")
            self.in_sender.setCurrentText(sender or "")
            self.in_courier.setCurrentText(courier or "")
            self.in_type.setCurrentText(dtype or DELIVERY_TYPES[0])
            self.in_tracking.setText(tracking or "")
            self.in_vat.setChecked(int(vat or 0) == 1)
            self.in_notes.setText(notes or "")

            # linked devices table
            devs = self.svc.list_devices_for_delivery(did, 2000)
            out = []

            for r in devs:
                def g(i, default=""):
                    return r[i] if len(r) > i and r[i] is not None else default

                out.append([
                    g(0),  # ID
                    ITEM_TYPE_TO_LABEL.get(g(2), g(2)),  # Typ
                    g(3),  # Nazwa
                    g(4),  # SN/Kod
                    g(5),  # IMEI1
                    g(6),  # IMEI2
                    g(7),  # Kod prod.
                    g(8),  # Uwagi
                ])

            fill_table(
                self.tbl_linked,
                ["ID","Typ","Nazwa","SN/Kod","IMEI1","IMEI2","Kod prod.","Uwagi"],
                out
            )

            fill_table(self.tbl_linked, ["ID","Typ","Nazwa","SN/Kod","IMEI1","IMEI2","Kod prod.","Uwagi"], out)

            # attachments list
            atts = self.svc.list_delivery_attachments(did)
            for row in atts:
                # obsługa niezależnie ile kolumn zwraca baza
                att_id = row[0]
                # path zwykle jest w kolumnie 2, ale jak masz inny układ – łapiemy elastycznie
                path = row[2] if len(row) > 2 else row[1]
                created_at = row[-1]

                it = QListWidgetItem(f"{att_id} | {os.path.basename(path)}")
                it.setData(Qt.UserRole, (att_id, path))
                self.list_att.addItem(it)

        except Exception:
            log.exception("load selected")

    def on_add(self) -> None:
        try:
            validate_ymd(self.in_date.text().strip())
            new_id = self.svc.add_delivery(
                delivery_date=self.in_date.text().strip(),
                sender_name=self.in_sender.currentText().strip(),
                courier_name=self.in_courier.currentText().strip(),
                delivery_type=self.in_type.currentText().strip(),
                tracking_number=self.in_tracking.text().strip(),
                invoice_vat=self.in_vat.isChecked(),
                notes=self.in_notes.text().strip(),
            )
            self.refresh_lists()
            self.refresh()
            QMessageBox.information(self, "OK", f"Dodano dostawę ID={new_id}")
        except Exception as e:
            log.exception("add delivery")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_save(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę w tabeli.")
            return
        try:
            validate_ymd(self.in_date.text().strip())
            self.svc.update_delivery(
                delivery_id=did,
                delivery_date=self.in_date.text().strip(),
                sender_name=self.in_sender.currentText().strip(),
                courier_name=self.in_courier.currentText().strip(),
                delivery_type=self.in_type.currentText().strip(),
                tracking_number=self.in_tracking.text().strip(),
                invoice_vat=self.in_vat.isChecked(),
                notes=self.in_notes.text().strip(),
            )
            self.refresh()
            QMessageBox.information(self, "OK", "Zapisano zmiany.")
        except Exception as e:
            log.exception("save delivery")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_delete(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę w tabeli.")
            return
        if QMessageBox.question(self, "Potwierdź", f"Usunąć dostawę ID={did}?") != QMessageBox.Yes:
            return
        try:
            self.svc.delete_delivery(did)
            self.refresh()
        except Exception as e:
            log.exception("delete delivery")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_link(self):
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę.")
            return
        row = self.svc.get_delivery(did)
        if not row:
            return
        delivery_date = row[1] or ""
        dlg = LinkReceiptsDialog(self, self.svc, did, delivery_date, on_done=self.load_selected)
        dlg.exec()
        # refresh linked after close
        self.load_selected()

    def on_attach(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę w tabeli.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Wybierz zdjęcia", "", "Zdjęcia (*.jpg *.jpeg *.png)")
        if not paths:
            return
        errors = []
        for p in paths:
            try:
                self.svc.add_delivery_attachment(did, p)
            except Exception as e:
                errors.append(f"{p}: {e}")
        if errors:
            QMessageBox.warning(self, "Uwaga", "\n".join(errors[:8]))
        self.load_selected()

    def on_delete_attachment(self):
        did = self._selected_delivery_id()
        if not did:
            return
        item = self.list_att.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Wybierz zdjęcie na liście.")
            return
        att_id, path = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Potwierdź", "Usunąć zdjęcie?") != QMessageBox.Yes:
            return
        try:
            self.svc.delete_delivery_attachment(int(att_id), delete_file=True)
            self.load_selected()
        except Exception as e:
            log.exception("delete attachment")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_open_attachment(self):
        item = self.list_att.currentItem()
        if not item:
            return
        att_id, path = item.data(Qt.UserRole)
        # open with default OS viewer
        try:
            import subprocess, sys
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Uwaga", f"Nie udało się otworzyć pliku: {e}")

    def on_export_csv(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Eksportuj CSV", "dostawy.csv", "CSV (*.csv)")
            if not path:
                return
            df = self.f_from.text().strip()
            dt = self.f_to.text().strip()
            dtype = self.f_type.currentText().strip()
            import csv
            rows_out: List[List[str]] = []
            offset = 0
            while True:
                pr = self.svc.search_deliveries(date_from=df, date_to=dt, sender="", courier="", delivery_type=dtype, limit=1000, offset=offset)
                if not pr.rows:
                    break
                for r in pr.rows:
                    rows_out.append([str(x or "") for x in r])
                offset += len(pr.rows)
                if offset >= pr.total_count:
                    break
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["id","delivery_date","sender","courier","type","tracking","vat","notes","created_at"])
                w.writerows(rows_out)
            QMessageBox.information(self, "OK", f"Zapisano: {path}")
        except Exception as e:
            log.exception("export deliveries csv")
            QMessageBox.critical(self, "Błąd", str(e))
