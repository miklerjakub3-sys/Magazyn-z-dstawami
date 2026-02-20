#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..backup import backup_manager
from ..config import BACKUP_DIR, DB_PATH, VERSION
from ..log import get_logger
from ..services import MagazynService
from .dashboard import DashboardPage
from .deliveries_ui import DeliveriesTab
from .receipts_ui import ReceiptsTab
from .report_ui import ReportsTab
from .settings_ui import SettingsPage
from .sidebar import SidebarNav

log = get_logger("magazyn.ui.main")


class MainWindow(QMainWindow):
    def __init__(self, svc: MagazynService):
        super().__init__()
        self.svc = svc
        self.setWindowTitle(f"Magazyn – Przyjęcia i Dostawy v{VERSION}")
        self.resize(1500, 880)

        self._build_layout()
        self._build_menu()
        self._apply_theme()
        self.showMaximized()

        backup_manager.start_auto_backup()

    def _build_layout(self) -> None:
        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = SidebarNav()
        self.sidebar.page_selected.connect(self.show_page)
        root.addWidget(self.sidebar)

        content = QWidget()
        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(16, 12, 16, 16)
        content_l.setSpacing(10)

        header = QFrame()
        header.setProperty("card", True)
        header_l = QVBoxLayout(header)
        header_l.setContentsMargins(16, 12, 16, 12)
        self.lbl_title = QLabel("Pulpit")
        self.lbl_title.setProperty("title", True)
        self.lbl_breadcrumbs = QLabel("Start / Pulpit")
        self.lbl_breadcrumbs.setProperty("subtitle", True)
        header_l.addWidget(self.lbl_title)
        header_l.addWidget(self.lbl_breadcrumbs)
        content_l.addWidget(header)

        self.stack = QStackedWidget()
        self.pages = {
            "dashboard": DashboardPage(self.svc),
            "receipts": ReceiptsTab(self.svc),
            "deliveries": DeliveriesTab(self.svc),
            "reports": ReportsTab(self.svc),
            "settings": SettingsPage(self.svc),
        }
        for key in ["dashboard", "receipts", "deliveries", "reports", "settings"]:
            self.stack.addWidget(self.pages[key])

        content_l.addWidget(self.stack, 1)
        root.addWidget(content, 1)

        self.setCentralWidget(shell)
        self.show_page("dashboard")

    def _apply_theme(self) -> None:
        qss = Path(__file__).with_name("styles").joinpath("app.qss")
        if qss.exists():
            self.setStyleSheet(qss.read_text(encoding="utf-8"))

    def show_page(self, key: str) -> None:
        titles = {
            "dashboard": "Pulpit",
            "receipts": "Przyjęcia",
            "deliveries": "Dostawy",
            "reports": "Raporty",
            "settings": "Ustawienia",
        }
        page = self.pages.get(key)
        if not page:
            return
        self.stack.setCurrentWidget(page)
        self.lbl_title.setText(titles.get(key, key))
        self.lbl_breadcrumbs.setText(f"Start / {titles.get(key, key)}")
        self.sidebar.set_active(key)

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
        act_help_manual = QAction("Instrukcja obsługi", self)
        act_help_manual.triggered.connect(self.on_help_manual)
        m_help.addAction(act_help_manual)

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

    def on_help_manual(self) -> None:
        QMessageBox.information(
            self,
            "Instrukcja obsługi",
            "1. Przyjęcia: wybierz typ, zeskanuj SN/Kod i zatwierdź Enter lub Dodaj.\n"
            "2. Dostawy: użyj filtrów Od/Do i zaznacz dostawę, aby zarządzać zdjęciami.\n"
            "3. Raporty: wybierz zakres dat i typ raportu, następnie Eksportuj PDF.\n"
            "4. Ustawienia: utwórz lub przywróć backup oraz ustaw interwał autozapisu.\n"
            "5. Skróty: Delete usuwa zaznaczony rekord, Ctrl+C kopiuje SN/Kod w Przyjęciach.",
        )

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
