from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


def _resource_candidates(rel_path: str) -> list[str]:
    candidates: list[str] = []
    if hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
        candidates.append(str(base / rel_path))
        candidates.append(str(base / "magazyn" / "ui" / rel_path))

    here = Path(__file__).resolve().parent
    candidates.append(str(here / rel_path))
    candidates.append(str(here / "assets" / "axedserwis.png"))
    return candidates


def _resolve_logo_path(default_rel: str) -> str:
    for p in _resource_candidates(default_rel):
        if os.path.exists(p):
            return p
    return ""


def get_logo_pixmap(
    logo_rel_path: str = os.path.join("assets", "axedserwis.png"),
    height: int = 90,
) -> QPixmap:
    logo_path = _resolve_logo_path(logo_rel_path)
    logo = QPixmap(logo_path) if logo_path else QPixmap()
    if logo.isNull():
        return QPixmap()
    return logo.scaledToHeight(height, Qt.SmoothTransformation)


def make_splash(
    title: str = "Magazyn z dostawami",
    subtitle: str = "Uruchamianie…",
    logo_rel_path: str = os.path.join("assets", "axedserwis.png"),
) -> QSplashScreen:
    w, h = 560, 260

    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    scaled = get_logo_pixmap(logo_rel_path=logo_rel_path, height=90)
    if not scaled.isNull():
        painter.drawPixmap(30, 35, scaled)

    painter.setPen(QColor("#424242"))
    f = QFont("Segoe UI", 22)
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(30, 165, title)

    painter.setPen(QColor("#424242"))
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(30, 195, subtitle)

    painter.end()

    splash = QSplashScreen(pm)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    splash.setMask(pm.mask())
    return splash
