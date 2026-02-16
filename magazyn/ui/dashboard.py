from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QGridLayout


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QLabel("Dashboard")
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

        root.addStretch(1)
