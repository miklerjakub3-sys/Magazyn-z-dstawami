from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QListWidgetItem


class AttachmentGalleryWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(96, 96))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setSpacing(8)
        self.list_widget.setWordWrap(True)
        root.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        self.btn_add = QPushButton("Dodaj zdjęcie")
        self.btn_preview = QPushButton("Podgląd")
        self.btn_remove = QPushButton("Usuń zdjęcie")
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_preview)
        row.addWidget(self.btn_remove)
        row.addStretch(1)
        root.addLayout(row)

    def add_attachment_item(self, att_id: int, path: str) -> None:
        item = QListWidgetItem(path.split("/")[-1])
        pix = QPixmap(path)
        if not pix.isNull():
            item.setIcon(QIcon(pix.scaled(96, 96)))
        item.setData(256, (att_id, path))
        self.list_widget.addItem(item)
