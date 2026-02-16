from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel


class SidebarNav(QFrame):
    page_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(210)
        self._buttons: Dict[str, QPushButton] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(8)

        logo = QLabel("📦 Magazyn")
        logo.setProperty("title", True)
        logo.setStyleSheet("color: white; font-size: 18px;")
        root.addWidget(logo)

        for key, text in [
            ("dashboard", "🏠  Dashboard"),
            ("receipts", "📥  Przyjęcia"),
            ("deliveries", "🚚  Dostawy"),
            ("reports", "📄  Raporty"),
            ("settings", "⚙️  Ustawienia"),
        ]:
            btn = QPushButton(text)
            btn.setProperty("nav", True)
            btn.clicked.connect(lambda _=False, name=key: self.page_selected.emit(name))
            root.addWidget(btn)
            self._buttons[key] = btn

        root.addStretch(1)

    def set_active(self, page: str) -> None:
        for name, button in self._buttons.items():
            button.setProperty("active", name == page)
            button.style().unpolish(button)
            button.style().polish(button)
