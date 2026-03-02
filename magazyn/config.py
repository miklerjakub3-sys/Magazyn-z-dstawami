#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konfiguracja aplikacji Magazyn
"""

import os
from pathlib import Path

# ======================
# Wersja aplikacji
# ======================
VERSION = "2.1.1"

# ======================
# Katalogi aplikacji
# ======================
APP_DIR = Path.home() / "MagazynData"
DB_PATH = APP_DIR / "magazyn.db"

ATTACH_DIR = APP_DIR / "attachments"              # zdjęcia do przyjęć
DELIVERY_ATTACH_DIR = APP_DIR / "delivery_attachments"  # zdjęcia do dostaw
BACKUP_DIR = APP_DIR / "backups"
LOG_FILE = APP_DIR / "magazyn_errors.log"

# ======================
# Limity
# ======================
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_RESULTS_PER_PAGE = 100

# ======================
# Backup
# ======================
AUTO_BACKUP_INTERVAL = int(os.getenv("MAGAZYN_AUTO_BACKUP_INTERVAL", "1800"))  # 30 minut (sekundy)
BACKUP_ZIP_PASSWORD = os.getenv("MAGAZYN_BACKUP_ZIP_PASSWORD", "")
MAIN_ADMIN_LOGIN = os.getenv("MAGAZYN_MAIN_ADMIN_LOGIN", "admin")
MAIN_ADMIN_PASSWORD = os.getenv("MAGAZYN_MAIN_ADMIN_PASSWORD", "")
REMEMBER_TOKEN_FILE = APP_DIR / "remember_token.txt"

# SMTP (odzyskiwanie hasła administratora)
SMTP_HOST = os.getenv("MAGAZYN_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("MAGAZYN_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("MAGAZYN_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("MAGAZYN_SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("MAGAZYN_SMTP_USE_TLS", "1") == "1"
SMTP_FROM = os.getenv("MAGAZYN_SMTP_FROM", SMTP_USERNAME or "")
RESET_CODE_TTL_MINUTES = int(os.getenv("MAGAZYN_RESET_CODE_TTL_MINUTES", "15"))

# ======================
# Typy pozycji (PRZYJĘCIA)
# ======================
ITEM_TYPE_TO_LABEL = {
    "device": "Urządzenie",
    "accessory": "Akcesorium",
}
ITEM_LABEL_TO_TYPE = {v: k for k, v in ITEM_TYPE_TO_LABEL.items()}

# ======================
# Typy dostaw
# ======================
DELIVERY_TYPES = [
    "MAGAZYN",
    "SERWIS",
    "WYNAJEM",
    "WYPOŻYCZENIE",
]

# ======================
# Kurierzy (domyślni)
# ======================
COURIERS = [
    "DPD",
    "DHL",
    "Poczta Polska",
    "InPost",
    "UPS",
    "FedEx",
    "Kurier",
    "Nova pochta"
    "Osobiście"
    "Kurier miastowy"
    "Inne",
]

# ======================
# Narzędzia
# ======================
def ensure_dirs() -> None:
    """Tworzy wymagane katalogi jeśli nie istnieją"""
    for directory in (
        APP_DIR,
        ATTACH_DIR,
        DELIVERY_ATTACH_DIR,
        BACKUP_DIR,
    ):
        os.makedirs(directory, exist_ok=True)
