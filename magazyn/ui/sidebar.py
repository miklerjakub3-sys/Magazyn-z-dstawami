from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


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

        # Trzymamy referencję pod jednoznaczną nazwą, żeby uniknąć literówek typu
        # `logo`/`logos` podczas ręcznych merge'y i edycji.
        logo_label = QLabel("📦  MAGAZYN")
        logo_label.setProperty("title", True)
        logo_label.setStyleSheet(
            "color: #ffffff; font-size: 18px; font-weight: 700; "
            "background: #1d4ed8; border-radius: 8px; padding: 8px;"
        )
        root.addWidget(logo_label)

        for key, text in [
            ("dashboard", "🏠  Pulpit"),
            ("receipts", "📥  Przyjęcia"),
            ("deliveries", "🚚  Dostawy"),
            ("issues", "🧾  Wydania (WZ)"),
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
