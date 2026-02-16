#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from magazyn.services import MagazynService
from magazyn.log import install_excepthook, get_logger
from magazyn.config import ensure_dirs
from magazyn.ui.splash import make_splash
from magazyn.ui.main_window import MainWindow

log = get_logger("magazyn")

def main() -> int:
    install_excepthook(show_dialog=True)
    ensure_dirs()

    app = QApplication(sys.argv)

    splash = make_splash()
    splash.show()
    app.processEvents()

    svc = MagazynService()
    svc.init_db()

    win = MainWindow(svc)
    win.show()

    splash.finish(win)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
