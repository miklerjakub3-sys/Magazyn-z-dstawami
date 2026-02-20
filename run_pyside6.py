#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from magazyn.services import MagazynService
from magazyn.log import install_excepthook, get_logger
from magazyn.config import ensure_dirs, REMEMBER_TOKEN_FILE
from magazyn.ui.splash import make_splash
from magazyn.ui.main_window import MainWindow
from magazyn.ui.login_dialog import LoginDialog

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

    user = None
    token_file = Path(REMEMBER_TOKEN_FILE)
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                user = svc.authenticate_token(token)
        except Exception:
            user = None

    if not user:
        login_dialog = LoginDialog()
        while True:
            if login_dialog.exec() != login_dialog.Accepted:
                splash.close()
                return 0
            login, password, remember = login_dialog.credentials()
            user = svc.authenticate_user(login, password)
            if user:
                if remember:
                    token = svc.create_remember_token(int(user["id"]))
                    token_file.write_text(token, encoding="utf-8")
                else:
                    try:
                        token_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                break
            login_dialog.in_password.clear()
            login_dialog.in_password.setFocus()

    win = MainWindow(svc)
    win.show()

    splash.finish(win)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
