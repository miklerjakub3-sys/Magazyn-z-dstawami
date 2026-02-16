#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Funkcje pomocnicze
"""

import os
import uuid
import shutil
from datetime import datetime
from .config import DELIVERY_ATTACH_DIR, ensure_dirs


def safe_filename(name: str) -> str:
    """Bezpieczna nazwa pliku"""
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip()


def copy_attachment_for_delivery(delivery_id: int, src_path: str) -> str:
    """Kopiuje załącznik dla dostawy"""
    ensure_dirs()
    if not os.path.isfile(src_path):
        raise ValueError("Wybrany plik nie istnieje.")

    ext = os.path.splitext(src_path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        raise ValueError("Dozwolone formaty: JPG/JPEG/PNG.")

    dest_folder = os.path.join(DELIVERY_ATTACH_DIR, str(delivery_id))
    os.makedirs(dest_folder, exist_ok=True)

    base = safe_filename(os.path.splitext(os.path.basename(src_path))[0])
    uniq = uuid.uuid4().hex[:8]
    dest_name = f"{base}_{uniq}{ext}"
    dest_path = os.path.join(dest_folder, dest_name)

    shutil.copy2(src_path, dest_path)
    return dest_path


def one_line(text: str, sep: str = " | ") -> str:
    """Konwersja tekstu do jednej linii"""
    if text is None:
        return ""
    s = str(text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", sep)
    s = s.replace("\t", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def today_str():
    """Dzisiejsza data w formacie YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def validate_ymd(s: str):
    """Walidacja formatu daty"""
    datetime.strptime(s, "%Y-%m-%d")


def parse_line_fields(line: str):
    """Parsowanie linii importu"""
    ln = (line or "").strip()
    if not ln:
        return []
    ln = ln.replace("\t", ";")
    if ";" not in ln and "," in ln:
        ln = ln.replace(",", ";")
    parts = [p.strip() for p in ln.split(";")]
    return [p for p in parts if p != ""]


def format_size(size_bytes: int) -> str:
    """Formatowanie rozmiaru pliku"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
