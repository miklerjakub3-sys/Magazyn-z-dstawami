from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import ITEM_TYPE_TO_LABEL
from ..services import MagazynService
from .widgets import fill_table


class DashboardPage(QWidget):
    def __init__(self, svc: MagazynService) -> None:
        super().__init__()
        self.svc = svc

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QLabel("Pulpit")
        title.setProperty("title", True)
        root.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)
        root.addLayout(grid)

        for i, (name, value) in enumerate([
            ("Przyjęcia", "Zarządzaj urządzeniami i akcesoriami"),
            ("Dostawy", "Powiązania, załączniki i statusy"),
            ("Raporty", "Eksport PDF i analityka zakresu dat"),
        ]):
            card = QFrame()
            card.setProperty("card", True)
            card_l = QVBoxLayout(card)
            lbl1 = QLabel(name)
            lbl1.setStyleSheet("font-size: 16px; font-weight: 600;")
            lbl2 = QLabel(value)
            lbl2.setProperty("subtitle", True)
            card_l.addWidget(lbl1)
            card_l.addWidget(lbl2)
            grid.addWidget(card, 0, i)

        previews = QGridLayout()
        previews.setSpacing(12)
        root.addLayout(previews, 1)

        self.tbl_recent_receipts = QTableWidget()
        self.tbl_recent_deliveries = QTableWidget()

        receipts_card = self._make_table_card("Podgląd: ostatnie przyjęcia", self.tbl_recent_receipts)
        deliveries_card = self._make_table_card("Podgląd: ostatnie dostawy", self.tbl_recent_deliveries)

        previews.addWidget(receipts_card, 0, 0)
        previews.addWidget(deliveries_card, 0, 1)

        self.refresh_previews()

    def _make_table_card(self, title: str, table: QTableWidget) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        lay = QVBoxLayout(card)
        lay.addWidget(QLabel(title))
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        lay.addWidget(table, 1)
        return card

    def refresh_previews(self) -> None:
        receipts = self.svc.search_devices(limit=8, offset=0).rows
        receipt_rows = []
        for r in receipts:
            receipt_rows.append([
                r[0],
                r[1],
                ITEM_TYPE_TO_LABEL.get(r[2], r[2]),
                r[3] or "",
                r[4] or "",
            ])
        fill_table(self.tbl_recent_receipts, ["ID", "Data", "Typ", "Nazwa", "SN/Kod"], receipt_rows)

        deliveries = self.svc.list_recent_deliveries(8)
        delivery_rows = []
        for r in deliveries:
            delivery_rows.append([r[0], r[1], r[2] or "", r[3] or "", r[4] or ""])
        fill_table(self.tbl_recent_deliveries, ["ID", "Data", "Nadawca", "Kurier", "Typ"], delivery_rows)
