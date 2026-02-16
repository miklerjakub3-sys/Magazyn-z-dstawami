#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QTabWidget, QApplication, QMessageBox

from ..config import VERSION, DB_PATH, BACKUP_DIR
from ..backup import backup_manager
from ..log import get_logger
from ..services import MagazynService

from .tabs_receipts import ReceiptsTab
from .tabs_deliveries import DeliveriesTab
from .tabs_reports import ReportsTab

log = get_logger("magazyn.ui.main")


class MainWindow(QMainWindow):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self.setWindowTitle(f"Magazyn – Przyjęcia i Dostawy v{VERSION}")
        self.resize(1400, 820)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_receipts = ReceiptsTab(svc)
        self.tab_deliveries = DeliveriesTab(svc)
        self.tab_reports = ReportsTab(svc)

        self.tabs.addTab(self.tab_receipts, "Przyjęcia")
        self.tabs.addTab(self.tab_deliveries, "Dostawy")
        self.tabs.addTab(self.tab_reports, "Raport PDF")

        self._build_menu()
        backup_manager.start_auto_backup()

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        m_file = menubar.addMenu("Plik")
        act_backup = QAction("Backup ręczny", self)
        act_backup.triggered.connect(self.on_manual_backup)
        m_file.addAction(act_backup)

        act_quit = QAction("Zamknij", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        m_file.addAction(act_quit)

        m_help = menubar.addMenu("Pomoc")
        act_about = QAction("O programie", self)
        act_about.triggered.connect(self.on_about)
        m_help.addAction(act_about)

    def on_manual_backup(self) -> None:
        try:
            path = backup_manager.create_backup(manual=True)
            if path:
                QMessageBox.information(self, "Backup", f"Utworzono:\n{path}\n\nFolder: {BACKUP_DIR}")
            else:
                QMessageBox.warning(self, "Backup", "Nie udało się utworzyć backupu.")
        except Exception as e:
            log.exception("manual backup failed")
            QMessageBox.critical(self, "Błąd", str(e))

    def on_about(self) -> None:
        QMessageBox.information(
            self,
            "O programie",
            f"Magazyn\nWersja {VERSION}\n\nBaza: {DB_PATH}\nBackupy: {BACKUP_DIR}",
        )

    def closeEvent(self, event):
        try:
            backup_manager.create_backup(manual=True)
        except Exception:
            log.exception("Backup on close failed")
        finally:
            try:
                backup_manager.stop_auto_backup()
            except Exception:
                log.exception("Stop auto backup failed")

        event.accept()
