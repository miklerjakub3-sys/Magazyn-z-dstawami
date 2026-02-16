from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

from ..config import DB_PATH, BACKUP_DIR


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Ustawienia")
        title.setProperty("title", True)
        root.addWidget(title)

        card = QFrame()
        card.setProperty("card", True)
        cl = QVBoxLayout(card)
        cl.addWidget(QLabel(f"Ścieżka bazy: {DB_PATH}"))
        cl.addWidget(QLabel(f"Folder backupów: {BACKUP_DIR}"))
        cl.addWidget(QLabel("Ustawienia zaawansowane będą rozszerzane w kolejnych iteracjach UI."))
        root.addWidget(card)
        root.addStretch(1)
