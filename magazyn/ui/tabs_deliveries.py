#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, List, Optional

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import DELIVERY_TYPES, ITEM_TYPE_TO_LABEL, MAX_RESULTS_PER_PAGE
from ..utils import today_str, validate_ymd, one_line
from ..log import get_logger
from ..services import MagazynService
from ..utils import one_line, validate_ymd
from .attachments_widget import AttachmentGalleryWidget
from .widgets import fill_table

log = get_logger("magazyn.ui.deliveries")


class OptionalDateEdit(QDateEdit):
    MIN_ALLOWED_DATE = QDate(2025, 1, 1)
    EMPTY_SENTINEL_DATE = QDate(2024, 12, 31)

    def __init__(self) -> None:
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setSpecialValueText("— wybierz datę —")
        self.setDateRange(self.EMPTY_SENTINEL_DATE, QDate(7999, 12, 31))
        self.setMinimumDate(self.EMPTY_SENTINEL_DATE)
        self.setDate(self.minimumDate())
        self.dateChanged.connect(self._clamp_if_needed)

    def _clamp_if_needed(self, value: QDate) -> None:
        if value != self.minimumDate() and value < self.MIN_ALLOWED_DATE:
            self.blockSignals(True)
            self.setDate(self.MIN_ALLOWED_DATE)
            self.blockSignals(False)

    def showPopup(self) -> None:
        if self.date() == self.minimumDate():
            self.setDate(self.MIN_ALLOWED_DATE)
        super().showPopup()


def _make_optional_date_edit() -> QDateEdit:
    return OptionalDateEdit()


def _date_or_empty(w: QDateEdit) -> str:
    return "" if w.date() == w.minimumDate() else w.date().toString("yyyy-MM-dd")


class LinkReceiptsDialog(QDialog):
    def __init__(self, parent: QWidget, svc: MagazynService, delivery_id: int, delivery_date: str, on_done=None):
        super().__init__(parent)
        self.svc = svc
        self.delivery_id = int(delivery_id)
        self.delivery_date = delivery_date
        self.on_done = on_done
        self._settings = QSettings("Magazyn", "DostawyLinkowanieUI")

        self.setWindowTitle(f"Powiąż przyjęcia z dostawą ID={delivery_id}")
        self.resize(980, 560)

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        root.addLayout(top)
        top.addWidget(QLabel(f"Dostawa ID={delivery_id} | Data: {delivery_date}"))
        self.chk_all = QCheckBox("Pokaż wszystkie urządzenia")
        top.addWidget(self.chk_all)
        self.chk_all.setToolTip(
            "Wyłączone: tylko rekordy powiązane z tą dostawą.\n"
            "Włączone: wszystkie urządzenia, od najnowszych."
        )
        top.addWidget(QLabel("Szukaj:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Nazwa / SN / IMEI")
        self.search.setProperty("compact", True)
        top.addWidget(self.search)
        top.addStretch(1)

        self.btn_refresh = QPushButton("Odśwież")
        self.btn_close = QPushButton("Zamknij")
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_close)

        self.btn_close.clicked.connect(self.close)
        self.btn_refresh.clicked.connect(self.refresh)
        self.chk_all.stateChanged.connect(lambda _: self.refresh())
        self.search.textChanged.connect(lambda _: self.refresh())

        self.table = QTableWidget()
        self.table.setStyleSheet("font-size: 12px;")
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.setStyleSheet(
            "QTableWidget {font-size: 12px; selection-background-color: #2563eb; selection-color: #ffffff;}"
        )
        root.addWidget(self.table, 1)
        self.table.horizontalHeader().sectionResized.connect(lambda *_: self._save_column_widths())
        self.table.horizontalHeader().sectionMoved.connect(lambda *_: self._save_header_state())

        self.lbl_legend = QLabel(
            "Legenda: szare = już powiązane z tą dostawą, zielone = wolne do powiązania, pomarańczowe = powiązane z inną dostawą"
        )
        self.lbl_legend.setProperty("subtitle", True)
        root.addWidget(self.lbl_legend)

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

    def _selected_ids(self) -> List[int]:
        ids: List[int] = []
        for idx in self.table.selectionModel().selectedRows():
            try:
                ids.append(int(self.table.item(idx.row(), 0).text()))
            except Exception:
                pass
        return ids

    def refresh(self) -> None:
        rows = self.svc.list_devices_for_delivery_linking(
            self.delivery_id,
            show_all=self.chk_all.isChecked(),
            query=self.search.text().strip(),
        )

        headers = ["ID", "Data", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Powiązanie"]
        out = []
        for r in rows:
            linked = int(r[10] or 0)
            label = "BRAK" if linked == 0 else f"ID={linked}"
            out.append([r[0], r[1] or "", ITEM_TYPE_TO_LABEL.get(r[2], r[2]), r[3] or "", r[4] or "", r[5] or "", r[6] or "", r[7] or "", label])

        fill_table(self.table, headers, out)
        self._restore_column_widths()
        self._restore_header_state()

        for i, r in enumerate(rows):
            linked = int(r[10] or 0)
            if linked == 0:
                bg = QColor("#e2f0d9")
            elif linked == self.delivery_id:
                bg = QColor("#e5e7eb")
            else:
                bg = QColor("#f8cbad")
            for c in range(self.table.columnCount()):
                it = self.table.item(i, c)
                if it:
                    it.setBackground(bg)


    def _restore_column_widths(self) -> None:
        raw = self._settings.value("link_table_widths", "")
        if not raw:
            return
        try:
            widths = [int(x) for x in str(raw).split(",") if x.strip()]
            if len(widths) != self.table.columnCount():
                return
            for i, w in enumerate(widths):
                self.table.setColumnWidth(i, w)
        except Exception:
            pass

    def _save_column_widths(self) -> None:
        try:
            widths = [str(self.table.columnWidth(i)) for i in range(self.table.columnCount())]
            self._settings.setValue("link_table_widths", ",".join(widths))
        except Exception:
            pass

    def _restore_header_state(self) -> None:
        raw = self._settings.value("link_table_header_state")
        if raw is None:
            return
        try:
            self.table.horizontalHeader().restoreState(raw)
        except Exception:
            pass

    def _save_header_state(self) -> None:
        try:
            self._settings.setValue("link_table_header_state", self.table.horizontalHeader().saveState())
        except Exception:
            pass

    def assign_selected(self) -> None:
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

    def unlink_selected(self) -> None:
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
        self._settings = QSettings("Magazyn", "DostawyUI")
        self._build()
        self._install_shortcuts()
        self._apply_permissions()
        if self.svc.has_permission("deliveries.view"):
            self.refresh_lists()
            self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        filt = QHBoxLayout()
        filt.setSpacing(6)
        root.addLayout(filt)
        self.f_from = _make_optional_date_edit()
        self.f_to = _make_optional_date_edit()
        self.f_type = QComboBox()
        self.f_type.addItems([""] + DELIVERY_TYPES)
        self.btn_search = QPushButton("Szukaj")
        self.btn_clear = QPushButton("Wyczyść")
        self.btn_export = QPushButton("Eksport CSV…")
        self.btn_toggle_form = QToolButton()
        self.btn_toggle_form.setCheckable(True)
        self.btn_toggle_form.setChecked(True)
        self.btn_toggle_form.setText("Zwiń formularz")

        for w in (self.f_from, self.f_to, self.f_type, self.btn_search, self.btn_clear, self.btn_export, self.btn_toggle_form):
            w.setProperty("compact", True)

        filt.addWidget(QLabel("Od:"))
        filt.addWidget(self.f_from)
        filt.addWidget(QLabel("Do:"))
        filt.addWidget(self.f_to)
        filt.addWidget(QLabel("Typ:"))
        filt.addWidget(self.f_type)
        filt.addWidget(self.btn_search)
        filt.addWidget(self.btn_clear)
        filt.addWidget(self.btn_export)
        filt.addWidget(self.btn_toggle_form)

        self.btn_search.clicked.connect(self.on_search)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_export.clicked.connect(self.on_export_csv)
        self.btn_toggle_form.toggled.connect(self._toggle_form)

        paging = QHBoxLayout()
        root.addLayout(paging)
        self.lbl_page = QLabel("")
        self.btn_first = QPushButton("⏮")
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.btn_last = QPushButton("⏭")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setFixedWidth(44)

        paging.addWidget(self.btn_first)
        paging.addWidget(self.btn_prev)
        paging.addWidget(self.lbl_page)
        paging.addWidget(self.btn_next)
        paging.addWidget(self.btn_last)
        paging.addStretch(1)

        self.btn_first.clicked.connect(lambda: self._goto(0))
        self.btn_prev.clicked.connect(lambda: self._goto(max(0, self.page - 1)))
        self.btn_next.clicked.connect(lambda: self._goto(min(self.total_pages - 1, self.page + 1)))
        self.btn_last.clicked.connect(lambda: self._goto(max(0, self.total_pages - 1)))

        main_split = QSplitter(Qt.Vertical)
        main_split.setChildrenCollapsible(False)
        root.addWidget(main_split, 1)
        self._main_split = main_split

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        main_split.addWidget(split)
        self._top_split = split

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setStyleSheet("font-size: 12px;")
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        left_l.addWidget(self.table, 1)
        split.addWidget(left)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)

        right_l.addWidget(QLabel("Urządzenia przypisane do dostawy:"))
        self.tbl_linked = QTableWidget()
        self.tbl_linked.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_linked.setSelectionMode(QTableWidget.ExtendedSelection)
        self.tbl_linked.setAlternatingRowColors(True)
        self.tbl_linked.horizontalHeader().setSectionsMovable(True)
        right_l.addWidget(self.tbl_linked, 1)

        right_l.addWidget(QLabel("Załączniki dostawy:"))
        self.attachments = AttachmentGalleryWidget()
        self.list_att = self.attachments.list_widget
        self.btn_attach = self.attachments.btn_add
        self.btn_open_att = self.attachments.btn_preview
        self.btn_del_att = self.attachments.btn_remove
        right_l.addWidget(self.attachments, 1)

        split.addWidget(right)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 1)
        split.setSizes([1360, 280])
        right.setMinimumWidth(260)

        form_card = QFrame()
        self._form_card = form_card
        form_card.setProperty("card", True)
        form_row = QHBoxLayout(form_card)
        form_row.setContentsMargins(12, 10, 12, 10)
        main_split.addWidget(form_card)
        main_split.setStretchFactor(0, 6)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([920, 120])
        self._restore_splitter_state(self._top_split, "top_split_state")
        self._restore_splitter_state(self._main_split, "main_split_state")
        form_expanded = str(self._settings.value("form_expanded", "1")) in ("1", "true", "True")
        self.btn_toggle_form.setChecked(form_expanded)
        self._toggle_form(form_expanded)

        form = QFormLayout()
        form_row.addLayout(form, stretch=2)

        self.in_date = QDateEdit()
        self.in_date.setCalendarPopup(True)
        self.in_date.setDisplayFormat("yyyy-MM-dd")
        self.in_date.setDate(QDate.currentDate())

        self.in_sender = QComboBox()
        self.in_sender.setEditable(True)
        self.in_courier = QComboBox()
        self.in_courier.setEditable(True)
        self.in_type = QComboBox()
        self.in_type.addItems(DELIVERY_TYPES)
        self.in_tracking = QLineEdit()
        self.in_vat = QCheckBox("Faktura VAT")
        self.in_notes = QLineEdit()

        for w in (self.in_date, self.in_sender, self.in_courier, self.in_type, self.in_tracking, self.in_notes):
            w.setProperty("compact", True)

        form.addRow("Data", self.in_date)
        form.addRow("Nadawca", self.in_sender)
        form.addRow("Kurier", self.in_courier)
        form.addRow("Typ", self.in_type)
        form.addRow("Nr przesyłki", self.in_tracking)
        form.addRow("", self.in_vat)
        form.addRow("Uwagi", self.in_notes)

        btns = QVBoxLayout()
        form_row.addLayout(btns, stretch=1)
        self.btn_add = QPushButton("Dodaj")
        self.btn_add.setProperty("role", "primary")
        self.btn_save = QPushButton("Zapisz")
        self.btn_save.setProperty("role", "secondary")
        self.btn_del = QPushButton("Usuń")
        self.btn_del.setProperty("role", "danger")
        self.btn_link = QPushButton("Powiąż przyjęcia…")
        self.btn_clear_form = QPushButton("Wyczyść formularz")

        for b in (self.btn_add, self.btn_save, self.btn_del, self.btn_link, self.btn_clear_form):
            b.setProperty("compact", True)

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_link)
        btns.addWidget(self.btn_clear_form)
        btns.addStretch(1)

        self.btn_clear_form.clicked.connect(self.clear_form)
        self.btn_add.clicked.connect(self.on_add)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_link.clicked.connect(self.on_link)

        self.btn_attach.clicked.connect(self.on_attach)
        self.btn_del_att.clicked.connect(self.on_delete_attachment)
        self.btn_open_att.clicked.connect(self.on_open_attachment)

    def _apply_permissions(self) -> None:
        can_view = bool(self.svc.has_permission("deliveries.view"))
        can_edit = bool(self.svc.has_permission("deliveries.edit"))

        for w in (self.f_from, self.f_to, self.f_type, self.btn_search, self.btn_clear, self.btn_toggle_form):
            w.setEnabled(can_view)
        self.table.setEnabled(can_view)
        self.tbl_linked.setEnabled(can_view)

        for b in (
            self.btn_add,
            self.btn_save,
            self.btn_del,
            self.btn_link,
            self.btn_clear_form,
            self.btn_attach,
            self.btn_del_att,
            self.btn_open_att,
            self.btn_export,
        ):
            b.setEnabled(can_edit)

        self.table.itemSelectionChanged.connect(self.load_selected)
        self.table.itemSelectionChanged.connect(self._update_context_actions)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_sort_clicked)
        self.table.horizontalHeader().sectionResized.connect(lambda *_: self._save_column_widths(self.table, "main_table_widths"))
        self.table.horizontalHeader().sectionMoved.connect(lambda *_: self._save_header_state(self.table, "main_table_header_state"))
        self.tbl_linked.horizontalHeader().sectionResized.connect(lambda *_: self._save_column_widths(self.tbl_linked, "linked_table_widths"))
        self.tbl_linked.horizontalHeader().sectionMoved.connect(lambda *_: self._save_header_state(self.tbl_linked, "linked_table_header_state"))
        self._top_split.splitterMoved.connect(lambda *_: self._save_splitter_state(self._top_split, "top_split_state"))
        self._main_split.splitterMoved.connect(lambda *_: self._save_splitter_state(self._main_split, "main_split_state"))
        self.list_att.itemDoubleClicked.connect(lambda _: self.on_open_attachment())
        self.list_att.itemSelectionChanged.connect(self._update_context_actions)
        self._update_context_actions()

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Delete"), self, self.on_delete)


    def _toggle_form(self, expanded: bool) -> None:
        self._settings.setValue("form_expanded", "1" if expanded else "0")
        if expanded:
            self.btn_toggle_form.setText("Zwiń formularz")
            self._form_card.show()
            sizes = self._main_split.sizes()
            if len(sizes) == 2 and sizes[1] < 80:
                self._main_split.setSizes([920, 120])
        else:
            self.btn_toggle_form.setText("Rozwiń formularz")
            self._form_card.hide()
            self._main_split.setSizes([1000, 0])
        self._save_splitter_state(self._main_split, "main_split_state")

    def _update_context_actions(self) -> None:
        has_delivery = self._selected_delivery_id() is not None
        self.btn_link.setVisible(has_delivery)
        self.btn_save.setEnabled(has_delivery)
        self.btn_del.setEnabled(has_delivery)
        self.btn_attach.setEnabled(has_delivery)

        has_att = self.list_att.currentItem() is not None
        self.btn_open_att.setEnabled(has_att)
        self.btn_del_att.setEnabled(has_att)

    def refresh_lists(self) -> None:
        try:
            self.in_sender.clear()
            self.in_sender.addItems([""] + self.svc.list_senders())
            self.in_courier.clear()
            self.in_courier.addItems([""] + self.svc.list_couriers())
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
        self.f_from.setDate(self.f_from.minimumDate())
        self.f_to.setDate(self.f_to.minimumDate())
        self.f_type.setCurrentText("")
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

    def clear_form(self) -> None:
        self.in_date.setDate(QDate.currentDate())
        self.in_sender.setCurrentText("")
        self.in_courier.setCurrentText("")
        self.in_type.setCurrentIndex(0)
        self.in_tracking.clear()
        self.in_vat.setChecked(False)
        self.in_notes.clear()
        self.list_att.clear()
        fill_table(self.tbl_linked, ["ID", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Uwagi"], [])

    def refresh(self) -> None:
        try:
            df = _date_or_empty(self.f_from)
            dt = _date_or_empty(self.f_to)
            if df:
                validate_ymd(df)
            if dt:
                validate_ymd(dt)

            pr = self.svc.search_deliveries(
                date_from=df,
                date_to=dt,
                sender="",
                courier="",
                delivery_type=self.f_type.currentText().strip(),
                order_by={
                    0: "id",
                    1: "delivery_date",
                    2: "sender_name",
                    3: "courier_name",
                    4: "delivery_type",
                    5: "invoice_vat",
                    6: "notes",
                    7: "created_at",
                    8: "tracking_number",
                }.get(self.sort_col, "delivery_date"),
                order_dir="ASC" if self.sort_dir == Qt.AscendingOrder else "DESC",
                limit=MAX_RESULTS_PER_PAGE,
                offset=self.page * MAX_RESULTS_PER_PAGE,
            )

            self.total = pr.total_count
            self.total_pages = max(1, (self.total + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE)
            self.lbl_page.setText(f"Strona {self.page + 1}/{self.total_pages} | Rekordy: {self.total}")

            headers = ["ID", "Data", "Nadawca", "Kurier", "Typ", "VAT", "Uwagi", "Utworzono", "Nr przesyłki"]
            rows = []
            for r in pr.rows:
                vat = "TAK" if int(r[6] or 0) == 1 else "NIE"
                rows.append([r[0], r[1], r[2] or "", r[3] or "", r[4] or "", vat, one_line(r[7] or ""), r[8] or "", r[5] or ""])
            fill_table(self.table, headers, rows)
            self._restore_column_widths(self.table, "main_table_widths")
            self._restore_header_state(self.table, "main_table_header_state")
            self.table.horizontalHeader().setSortIndicator(self.sort_col, self.sort_dir)
            for i, r in enumerate(pr.rows):
                typ = (r[4] or "").upper()
                it = self.table.item(i, 4)
                if not it:
                    continue
                if typ == "MAGAZYN":
                    it.setBackground(Qt.GlobalColor.green)
                elif typ == "SERWIS":
                    it.setBackground(Qt.GlobalColor.yellow)
                elif typ in ("WYNAJEM", "WYPOŻYCZENIE"):
                    it.setBackground(Qt.GlobalColor.cyan)

            for i, r in enumerate(pr.rows):
                typ = (r[4] or "").upper()
                type_item = self.table.item(i, 4)
                if type_item:
                    if typ == "MAGAZYN":
                        type_item.setBackground(QColor("#dcfce7"))
                    elif typ == "SERWIS":
                        type_item.setBackground(QColor("#fef3c7"))
                    elif typ in ("WYNAJEM", "WYPOŻYCZENIE"):
                        type_item.setBackground(QColor("#cffafe"))

            self.load_selected()
            self._update_context_actions()
        except Exception as e:
            log.exception("refresh deliveries")
            QMessageBox.critical(self, "Błąd", str(e))

    def load_selected(self) -> None:
        did = self._selected_delivery_id()
        self.list_att.clear()
        fill_table(self.tbl_linked, ["ID", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Uwagi"], [])
        if not did:
            self._update_context_actions()
            return

        try:
            row = self.svc.get_delivery(did)
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
            return
        try:
            if not row:
                return
            (_id, d, sender, courier, dtype, tracking, vat, notes, _created) = row
            self.in_date.setDate(QDate.fromString(d, "yyyy-MM-dd") if d else QDate.currentDate())
            self.in_sender.setCurrentText(sender or "")
            self.in_courier.setCurrentText(courier or "")
            self.in_type.setCurrentText(dtype or DELIVERY_TYPES[0])
            self.in_tracking.setText(tracking or "")
            self.in_vat.setChecked(int(vat or 0) == 1)
            self.in_notes.setText(notes or "")

            devs = self.svc.list_devices_for_delivery(did, 2000)
            out: List[List[Any]] = []
            for r in devs:
                def g(i: int, default: str = "") -> Any:
                    return r[i] if len(r) > i and r[i] is not None else default

                out.append([g(0), ITEM_TYPE_TO_LABEL.get(g(2), g(2)), g(3), g(4), g(5), g(6), g(7), g(8)])

            fill_table(self.tbl_linked, ["ID", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Uwagi"], out)
            self._restore_column_widths(self.tbl_linked, "linked_table_widths")
            self._restore_header_state(self.tbl_linked, "linked_table_header_state")

            for row in self.svc.list_delivery_attachments(did):
                att_id = row[0]
                path = row[2] if len(row) > 2 else row[1]
                it = QListWidgetItem(f"{att_id} | {os.path.basename(path)}")
                it.setData(Qt.UserRole, (att_id, path))
                self.list_att.addItem(it)

            self._update_context_actions()
        except Exception:
            log.exception("load selected")

    def on_add(self) -> None:
        try:
            date_text = self.in_date.date().toString("yyyy-MM-dd")
            validate_ymd(date_text)
            new_id = self.svc.add_delivery(
                delivery_date=date_text,
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
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
        except Exception as e:
            log.exception("add delivery")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_save(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę w tabeli.")
            return
        try:
            date_text = self.in_date.date().toString("yyyy-MM-dd")
            validate_ymd(date_text)
            self.svc.update_delivery(
                delivery_id=did,
                delivery_date=date_text,
                sender_name=self.in_sender.currentText().strip(),
                courier_name=self.in_courier.currentText().strip(),
                delivery_type=self.in_type.currentText().strip(),
                tracking_number=self.in_tracking.text().strip(),
                invoice_vat=self.in_vat.isChecked(),
                notes=self.in_notes.text().strip(),
            )
            self.refresh()
            QMessageBox.information(self, "OK", "Zapisano zmiany.")
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
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
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
        except Exception as e:
            log.exception("delete delivery")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_link(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            QMessageBox.information(self, "Info", "Zaznacz dostawę.")
            return
        try:
            row = self.svc.get_delivery(did)
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
            return
        if not row:
            return
        delivery_date = row[1] or ""
        dlg = LinkReceiptsDialog(self, self.svc, did, delivery_date, on_done=self.load_selected)
        dlg.exec()
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
            except PermissionError as e:
                errors.append(f"{p}: {e}")
            except Exception as e:
                errors.append(f"{p}: {e}")
        if errors:
            QMessageBox.warning(self, "Uwaga", "\n".join(errors[:8]))
        self.load_selected()
        self._update_context_actions()

    def on_delete_attachment(self) -> None:
        did = self._selected_delivery_id()
        if not did:
            self._update_context_actions()
            return
        item = self.list_att.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Wybierz zdjęcie na liście.")
            return
        att_id, _path = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Potwierdź", "Usunąć zdjęcie?") != QMessageBox.Yes:
            return
        try:
            self.svc.delete_delivery_attachment(int(att_id), delete_file=True)
            self.load_selected()
            self._update_context_actions()
        except PermissionError as e:
            QMessageBox.warning(self, "Brak uprawnień", str(e))
        except Exception as e:
            log.exception("delete attachment")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_open_attachment(self) -> None:
        item = self.list_att.currentItem()
        if not item:
            return
        _att_id, path = item.data(Qt.UserRole)
        try:
            import subprocess
            import sys

            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Uwaga", f"Nie udało się otworzyć pliku: {e}")

    def _restore_column_widths(self, table: QTableWidget, key: str) -> None:
        raw = self._settings.value(key, "")
        if not raw:
            return
        try:
            widths = [int(x) for x in str(raw).split(",") if x.strip()]
            if len(widths) != table.columnCount():
                return
            for i, w in enumerate(widths):
                table.setColumnWidth(i, w)
        except Exception:
            pass

    def _save_column_widths(self, table: QTableWidget, key: str) -> None:
        try:
            widths = [str(table.columnWidth(i)) for i in range(table.columnCount())]
            self._settings.setValue(key, ",".join(widths))
        except Exception:
            pass

    def _restore_header_state(self, table: QTableWidget, key: str) -> None:
        raw = self._settings.value(key)
        if raw is None:
            return
        try:
            table.horizontalHeader().restoreState(raw)
        except Exception:
            pass

    def _save_header_state(self, table: QTableWidget, key: str) -> None:
        try:
            self._settings.setValue(key, table.horizontalHeader().saveState())
        except Exception:
            pass

    def _restore_splitter_state(self, splitter: QSplitter, key: str) -> None:
        raw = self._settings.value(key)
        if raw is None:
            return
        try:
            splitter.restoreState(raw)
            if key == "main_split_state":
                sizes = splitter.sizes()
                if len(sizes) == 2 and sizes[1] < 20:
                    splitter.setSizes([920, 120])
        except Exception:
            pass

    def _save_splitter_state(self, splitter: QSplitter, key: str) -> None:
        try:
            self._settings.setValue(key, splitter.saveState())
        except Exception:
            pass

    def on_export_csv(self) -> None:
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Eksportuj CSV", "dostawy.csv", "CSV (*.csv)")
            if not path:
                return
            df = _date_or_empty(self.f_from)
            dt = _date_or_empty(self.f_to)
            dtype = self.f_type.currentText().strip()
            import csv

            rows_out: List[List[str]] = []
            offset = 0
            while True:
                pr = self.svc.search_deliveries(
                    date_from=df,
                    date_to=dt,
                    sender="",
                    courier="",
                    delivery_type=dtype,
                    limit=1000,
                    offset=offset,
                )
                if not pr.rows:
                    break
                for r in pr.rows:
                    rows_out.append([str(x or "") for x in r])
                offset += len(pr.rows)
                if offset >= pr.total_count:
                    break

            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["id", "delivery_date", "sender", "courier", "type", "tracking", "vat", "notes", "created_at"])
                w.writerows(rows_out)
            QMessageBox.information(self, "OK", f"Zapisano: {path}")
        except Exception as e:
            log.exception("export deliveries csv")
            QMessageBox.critical(self, "Błąd", str(e))
