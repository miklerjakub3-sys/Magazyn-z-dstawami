#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moduł zarządzania backupami bazy danych i zdjęć.

Backup jest plikiem .zip zawierającym:
  - bazę (magazyn.db) spakowaną gzip: db/magazyn.db.gz
  - katalog attachments/: attachments/...
  - katalog delivery_attachments/: delivery_attachments/...

Dzięki temu odtwarzasz pełny stan (rekordy + zdjęcia).
"""

from __future__ import annotations

import os
import time
import threading
import gzip
import shutil
import sqlite3
import stat
import zipfile
import importlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Any

from . import config
from .config import BACKUP_DIR, DB_PATH, AUTO_BACKUP_INTERVAL, ATTACH_DIR, DELIVERY_ATTACH_DIR
from .log import get_logger

log = get_logger("magazyn.backup")
MAX_EXTRACTED_FILE_SIZE = 100 * 1024 * 1024
MAX_EXTRACTED_TOTAL_SIZE = 500 * 1024 * 1024

def get_configured_backup_password() -> str:
    runtime = (os.getenv("MAGAZYN_BACKUP_ZIP_PASSWORD", "") or "").strip()
    if runtime:
        return runtime
    return (getattr(config, "BACKUP_ZIP_PASSWORD", "") or "").strip()


def _get_pyzipper() -> Any:
    try:
        return importlib.import_module("pyzipper")
    except Exception as exc:
        raise RuntimeError(
            "Brak zależności 'pyzipper'. Zainstaluj wymagania: pip install -r requirements.txt"
        ) from exc


def _is_zip_symlink(member: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((member.external_attr >> 16) & 0xFFFF)


def safe_extract(
    zf: zipfile.ZipFile,
    target_dir: Path,
    *,
    max_file_size: int = MAX_EXTRACTED_FILE_SIZE,
    max_total_size: int = MAX_EXTRACTED_TOTAL_SIZE,
) -> None:
    """Bezpiecznie rozpakowuje archiwum ZIP bez ryzyka Zip Slip/symlinków."""
    base = target_dir.resolve()
    total_size = 0

    for member in zf.infolist():
        member_name = member.filename
        if member_name.startswith("/"):
            raise ValueError(f"Niedozwolona ścieżka absolutna w archiwum: {member_name}")

        member_path = Path(member_name)
        if any(part == ".." for part in member_path.parts):
            raise ValueError(f"Niedozwolona ścieżka traversal w archiwum: {member_name}")
        if _is_zip_symlink(member):
            raise ValueError(f"Niedozwolony symlink w archiwum: {member_name}")

        destination = (base / member_path).resolve()
        if not str(destination).startswith(f"{base}{os.sep}") and destination != base:
            raise ValueError(f"Niedozwolona ścieżka docelowa w archiwum: {member_name}")

        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue

        if member.file_size > max_file_size:
            raise ValueError(f"Plik w archiwum przekracza limit rozmiaru: {member_name}")
        total_size += member.file_size
        if total_size > max_total_size:
            raise ValueError("Łączny rozmiar danych w archiwum przekracza limit")

        destination.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member, "r") as src, destination.open("wb") as dst:
            shutil.copyfileobj(src, dst)


class BackupManager:
    def __init__(self) -> None:
        self.backup_dir = Path(BACKUP_DIR)
        self.db_path = Path(DB_PATH)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.interval_seconds = int(AUTO_BACKUP_INTERVAL)

    def create_backup(self, manual: bool = False) -> Optional[str]:
        """Tworzy backup .zip (db + zdjęcia)."""
        try:
            if not self.db_path.exists():
                return None

            self.backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "manual" if manual else "auto"
            backup_name = f"magazyn_backup_{prefix}_{timestamp}.zip"
            backup_path = self.backup_dir / backup_name

            # przygotuj spójny snapshot bazy (bez ryzyka uszkodzeń w trybie WAL)
            tmp_db = self.backup_dir / f"_tmp_db_snapshot_{timestamp}.db"
            tmp_gz = self.backup_dir / f"_tmp_db_{timestamp}.db.gz"
            with sqlite3.connect(str(self.db_path)) as src_conn, sqlite3.connect(str(tmp_db)) as dst_conn:
                src_conn.backup(dst_conn)

            with tmp_db.open("rb") as f_in, gzip.open(tmp_gz, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            def add_dir(z: zipfile.ZipFile, folder: Path, arc_root: str) -> None:
                if not folder.exists():
                    return
                for p in folder.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=str(Path(arc_root) / p.relative_to(folder)))

            with zipfile.ZipFile(
                backup_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as z:
                z.write(tmp_gz, arcname="db/magazyn.db.gz")
                add_dir(z, Path(ATTACH_DIR), "attachments")
                add_dir(z, Path(DELIVERY_ATTACH_DIR), "delivery_attachments")

            try:
                tmp_gz.unlink(missing_ok=True)
                tmp_db.unlink(missing_ok=True)
            except Exception:
                pass

            self._cleanup_old_backups(30)
            return str(backup_path)
        except Exception:
            log.exception("Błąd podczas tworzenia backupu")
            return None

    def _cleanup_old_backups(self, keep_count: int) -> None:
        try:
            if not self.backup_dir.exists():
                return
            backups: List[Tuple[float, Path]] = []
            for p in self.backup_dir.glob("magazyn_backup_*.zip"):
                backups.append((p.stat().st_mtime, p))
            backups.sort(reverse=True)
            for _, p in backups[keep_count:]:
                try:
                    p.unlink()
                except Exception:
                    pass
        except Exception:
            log.exception("Błąd podczas czyszczenia backupów")

    def auto_backup_loop(self) -> None:
        while self.running:
            interrupted = self._stop_event.wait(max(30, int(self.interval_seconds)))
            if interrupted:
                break
            if self.running:
                self.create_backup(manual=False)

    def start_auto_backup(self) -> None:
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self.auto_backup_loop, daemon=True)
        self.thread.start()

    def stop_auto_backup(self) -> None:
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)


    def set_interval_seconds(self, seconds: int) -> None:
        self.interval_seconds = max(30, int(seconds))
        # restart pętli oczekiwania, żeby nowa wartość zadziałała od razu
        if self.running:
            self._stop_event.set()
            self._stop_event.clear()

    def restore_backup(self, backup_path: str, password: str = "") -> bool:
        """Przywraca bazę + zdjęcia z backupu .zip"""
        try:
            bp = Path(backup_path)
            if not bp.exists():
                return False

            # backup bieżącego stanu przed przywróceniem
            self.create_backup(manual=True)

            # rozpakuj do temp
            tmp_dir = self.backup_dir / f"_restore_tmp_{int(time.time())}"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            effective_password = (password or get_configured_backup_password()).strip()
            extracted = False
            if effective_password:
                try:
                    pyzipper = _get_pyzipper()
                    with pyzipper.AESZipFile(bp, "r") as z:
                        z.setpassword(effective_password.encode("utf-8"))
                        safe_extract(z, tmp_dir)
                    extracted = True
                except Exception:
                    extracted = False
            if not extracted:
                with zipfile.ZipFile(bp, "r") as z:
                    safe_extract(z, tmp_dir)

            # restore db
            gz = tmp_dir / "db" / "magazyn.db.gz"
            if gz.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(gz, "rb") as f_in, self.db_path.open("wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # restore dirs (merge/overwrite)
            def restore_dir(src: Path, dst: Path) -> None:
                if not src.exists():
                    return
                dst.mkdir(parents=True, exist_ok=True)
                for p in src.rglob("*"):
                    if p.is_file():
                        out = dst / p.relative_to(src)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, out)

            restore_dir(tmp_dir/"attachments", Path(ATTACH_DIR))
            restore_dir(tmp_dir/"delivery_attachments", Path(DELIVERY_ATTACH_DIR))

            shutil.rmtree(tmp_dir, ignore_errors=True)
            return True
        except Exception:
            log.exception("Błąd podczas przywracania backupu")
            return False

    def list_backups(self) -> List[Tuple[str, str, int]]:
        try:
            if not self.backup_dir.exists():
                return []
            out: List[Tuple[str, str, int]] = []
            for p in sorted(self.backup_dir.glob("magazyn_backup_*.zip"), reverse=True):
                out.append((p.name, str(p), p.stat().st_size))
            return out
        except Exception:
            return []


backup_manager = BackupManager()
