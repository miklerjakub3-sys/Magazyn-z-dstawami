# magazyn/ui/splash.py
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from PySide6.QtWidgets import QSplashScreen


def _resource_path(rel_path: str) -> str:
    """
    Zwraca ścieżkę do zasobów zarówno w trybie dev, jak i w PyInstaller (onefile).
    """
    if hasattr(sys, "_MEIPASS"):
        base = getattr(sys, "_MEIPASS")  # type: ignore[attr-defined]
        return os.path.join(base, rel_path)
    # dev: plik jest w magazyn/ui/splash.py -> cofamy się do magazyn/ui
    here = os.path.dirname(__file__)
    return os.path.join(here, rel_path)


def make_splash(
    title: str = "Magazyn z dostawami",
    subtitle: str = "Uruchamianie…",
    logo_rel_path=os.path.join("assets","axedserwis.png")
) -> QSplashScreen:
    # rozmiar splash (dopasuj jeśli chcesz)
    w, h = 560, 260

    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # --- logo
    logo_path = _resource_path(logo_rel_path)
    logo = QPixmap(logo_path)
    if not logo.isNull():
        target_h = 90
        scaled = logo.scaledToHeight(target_h, Qt.SmoothTransformation)
        painter.drawPixmap(30, 35, scaled)

    # --- tytuł
    painter.setPen(QColor("#424242"))
    f = QFont("Segoe UI", 22)
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(30, 165, title)

    # --- podtytuł
    painter.setPen(QColor("#424242"))
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(30, 195, subtitle)

    painter.end()

    splash = QSplashScreen(pm)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    splash.setMask(pm.mask())
    return splash
    print("LOGO PATH:", logo_path, "exists:", os.path.exists(logo_path))