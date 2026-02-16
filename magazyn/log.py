#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""magazyn.log

Proste logowanie aplikacji (RotatingFileHandler) + globalny handler wyjątków.
Działa zarówno z CLI, jak i z PySide6 (QMessageBox).
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
import threading
from logging.handlers import RotatingFileHandler
from typing import Optional

from .config import LOG_FILE, MAX_LOG_SIZE, ensure_dirs


_LOGGER: Optional[logging.Logger] = None
_THREAD_HOOK_INSTALLED = False
_QT_HOOK_INSTALLED = False


def get_logger(name: str = "magazyn") -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    ensure_dirs()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # unikaj duplikowania handlerów
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=5,
            encoding="utf-8",
        )
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        logger.addHandler(console)

    _LOGGER = logger
    return logger


def install_thread_excepthook() -> None:
    """Loguje nieobsłużone wyjątki z wątków (Python 3.8+)."""
    global _THREAD_HOOK_INSTALLED

    if _THREAD_HOOK_INSTALLED or not hasattr(threading, "excepthook"):
        return

    logger = get_logger("magazyn")

    def _thread_hook(args):
        try:
            logger.error(
                "Unhandled thread exception in %s",
                getattr(args.thread, "name", "unknown"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        except Exception:
            pass

    threading.excepthook = _thread_hook
    _THREAD_HOOK_INSTALLED = True


def install_qt_message_handler() -> None:
    """Przekierowuje komunikaty Qt do loga aplikacji."""
    global _QT_HOOK_INSTALLED

    if _QT_HOOK_INSTALLED:
        return

    try:
        from PySide6.QtCore import qInstallMessageHandler
    except Exception:
        return

    logger = get_logger("magazyn.qt")

    def _qt_handler(mode, context, message):
        try:
            logger.warning("Qt message: %s", message)
        except Exception:
            pass

    qInstallMessageHandler(_qt_handler)
    _QT_HOOK_INSTALLED = True


def install_excepthook(show_dialog: bool = True) -> None:
    """Instaluje globalny sys.excepthook, zapisuje stacktrace do loga.
    Jeśli show_dialog=True i PySide6 jest dostępny, pokaże QMessageBox.
    """
    logger = get_logger("magazyn")
    install_thread_excepthook()
    install_qt_message_handler()

    def _hook(exc_type, exc, tb):
        try:
            logger.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        except Exception:
            # ostatnia deska ratunku
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 80 + "\n")
                    traceback.print_exception(exc_type, exc, tb, file=f)
            except Exception:
                pass

        if show_dialog:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    None,
                    "Błąd programu",
                    f"Wystąpił błąd. Szczegóły zapisano w pliku:\n{os.path.abspath(LOG_FILE)}\n\nBłąd: {exc}",
                )
            except Exception:
                # fallback: stderr
                try:
                    sys.stderr.write(f"Unhandled exception: {exc}\n")
                except Exception:
                    pass

    sys.excepthook = _hook
