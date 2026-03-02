#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDialog

from magazyn.services import MagazynService
from magazyn.log import install_excepthook, get_logger
from magazyn.config import ensure_dirs, REMEMBER_TOKEN_FILE
from magazyn.ui.splash import make_splash
from magazyn.ui.main_window import MainWindow
from magazyn.ui.login_dialog import LoginDialog, AdminBootstrapDialog

log = get_logger("magazyn")

def main() -> int:
    install_excepthook(show_dialog=True)
    ensure_dirs()

    app = QApplication(sys.argv)
    qss = Path(__file__).resolve().parent / "magazyn" / "ui" / "styles" / "app.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    splash = make_splash()
    splash.show()
    app.processEvents()

    svc = MagazynService()
    svc.init_db()

    user = None
    token_file = Path(REMEMBER_TOKEN_FILE)
    # Funkcja „zapamiętaj mnie” celowo wyłączona: zawsze wymagamy logowania.
    try:
        token_file.unlink(missing_ok=True)
    except Exception:
        pass

    if not user:
        # Najpierw pokaż splash, potem przejdź do logowania (bez chowania pod splash screen).
        splash.close()
        if svc.is_initial_admin_setup_required():
            bootstrap = AdminBootstrapDialog(svc)
            if bootstrap.exec() != QDialog.DialogCode.Accepted:
                return 0
        app.processEvents()
        login_dialog = LoginDialog(svc)
        while True:
            if login_dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
            login, password, _remember = login_dialog.credentials()
            user = svc.authenticate_user(login, password)
            if user:
                break
            login_dialog.in_password.clear()
            login_dialog.in_password.setFocus()

    svc.set_current_user(user)

    win = MainWindow(svc)
    win.show()

    if splash.isVisible():
        splash.finish(win)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
