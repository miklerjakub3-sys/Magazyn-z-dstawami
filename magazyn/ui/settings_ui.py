from __future__ import annotations

from datetime import datetime
import os

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..backup import backup_manager
from ..config import BACKUP_DIR, DB_PATH


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("Ustawienia")
        title.setProperty("title", True)
        root.addWidget(title)

        info_card = QFrame()
        info_card.setProperty("card", True)
        info_l = QVBoxLayout(info_card)
        info_l.addWidget(QLabel(f"Ścieżka bazy: {DB_PATH}"))
        info_l.addWidget(QLabel(f"Folder backupów: {BACKUP_DIR}"))
        root.addWidget(info_card)

        backup_card = QFrame()
        backup_card.setProperty("card", True)
        backup_l = QVBoxLayout(backup_card)
        backup_l.addWidget(QLabel("Backup"))

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Autozapis co:"))
        self.cmb_interval = QComboBox()
        self.cmb_interval.addItem("15 minut", 15 * 60)
        self.cmb_interval.addItem("30 minut", 30 * 60)
        self.cmb_interval.addItem("60 minut", 60 * 60)
        self.cmb_interval.addItem("120 minut", 120 * 60)
        interval_row.addWidget(self.cmb_interval)
        self.btn_apply_interval = QPushButton("Zastosuj")
        self.btn_apply_interval.setProperty("role", "secondary")
        interval_row.addWidget(self.btn_apply_interval)
        interval_row.addStretch(1)
        backup_l.addLayout(interval_row)

        list_row = QHBoxLayout()
        self.lst_backups = QListWidget()
        list_row.addWidget(self.lst_backups, 1)

        side_btns = QVBoxLayout()
        self.btn_refresh = QPushButton("Odśwież listę")
        self.btn_create = QPushButton("Utwórz backup teraz")
        self.btn_create.setProperty("role", "primary")
        self.btn_restore = QPushButton("Przywróć zaznaczony backup")
        self.btn_restore.setProperty("role", "danger")
        side_btns.addWidget(self.btn_refresh)
        side_btns.addWidget(self.btn_create)
        side_btns.addWidget(self.btn_restore)
        side_btns.addStretch(1)
        list_row.addLayout(side_btns)

        backup_l.addLayout(list_row)
        root.addWidget(backup_card, 1)

        root.addStretch(1)

        self.btn_refresh.clicked.connect(self.refresh_backups)
        self.btn_create.clicked.connect(self.create_backup)
        self.btn_restore.clicked.connect(self.restore_selected_backup)
        self.btn_apply_interval.clicked.connect(self.apply_interval)

        self._sync_interval_combo()
        self.refresh_backups()

    def _sync_interval_combo(self) -> None:
        sec = int(getattr(backup_manager, "interval_seconds", 30 * 60))
        best_idx = 1
        for i in range(self.cmb_interval.count()):
            if int(self.cmb_interval.itemData(i)) == sec:
                best_idx = i
                break
        self.cmb_interval.setCurrentIndex(best_idx)

    def apply_interval(self) -> None:
        seconds = int(self.cmb_interval.currentData())
        backup_manager.set_interval_seconds(seconds)
        QMessageBox.information(self, "Backup", f"Ustawiono autozapis co {seconds // 60} minut.")

    def refresh_backups(self) -> None:
        self.lst_backups.clear()
        for name, path, size in backup_manager.list_backups():
            mb = size / (1024 * 1024)
            dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            self.lst_backups.addItem(f"{name} | {mb:.2f} MB | {dt} | {path}")

    def create_backup(self) -> None:
        path = backup_manager.create_backup(manual=True)
        if path:
            QMessageBox.information(self, "Backup", f"Utworzono backup:\n{path}")
            self.refresh_backups()
        else:
            QMessageBox.warning(self, "Backup", "Nie udało się utworzyć backupu.")

    def restore_selected_backup(self) -> None:
        item = self.lst_backups.currentItem()
        if not item:
            QMessageBox.information(self, "Backup", "Wybierz backup z listy.")
            return

        path = item.text().split(" | ")[-1]
        q = QMessageBox.question(
            self,
            "Potwierdź przywracanie",
            "Przywrócić wybrany backup?\nAplikacja może wymagać ponownego uruchomienia.",
        )
        if q != QMessageBox.Yes:
            return

        if backup_manager.restore_backup(path):
            QMessageBox.information(self, "Backup", "Przywrócono backup. Dla pewności uruchom aplikację ponownie.")
        else:
            QMessageBox.critical(self, "Backup", "Nie udało się przywrócić backupu.")
