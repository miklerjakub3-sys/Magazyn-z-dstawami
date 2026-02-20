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
AUTO_BACKUP_INTERVAL = 1800  # 30 minut (sekundy)
BACKUP_ZIP_PASSWORD = "Mikler2000praca"
MAIN_ADMIN_LOGIN = "Jakub"
MAIN_ADMIN_PASSWORD = "Mikler2000praca"
REMEMBER_TOKEN_FILE = APP_DIR / "remember_token.txt"

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
