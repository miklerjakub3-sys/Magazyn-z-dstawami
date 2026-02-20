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
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from .config import BACKUP_DIR, DB_PATH, AUTO_BACKUP_INTERVAL, ATTACH_DIR, DELIVERY_ATTACH_DIR, BACKUP_ZIP_PASSWORD
from .log import get_logger

try:
    import pyzipper  # type: ignore
except Exception:  # pragma: no cover - fallback środowiskowy
    pyzipper = None

log = get_logger("magazyn.backup")


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

            # przygotuj gzip bazy w temp
            tmp_gz = self.backup_dir / f"_tmp_db_{timestamp}.db.gz"
            with self.db_path.open("rb") as f_in, gzip.open(tmp_gz, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            def add_dir(z: zipfile.ZipFile, folder: Path, arc_root: str) -> None:
                if not folder.exists():
                    return
                for p in folder.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=str(Path(arc_root) / p.relative_to(folder)))

            if pyzipper is not None:
                with pyzipper.AESZipFile(
                    backup_path,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                    encryption=pyzipper.WZ_AES,
                ) as z:
                    z.setpassword(BACKUP_ZIP_PASSWORD.encode("utf-8"))
                    z.write(tmp_gz, arcname="db/magazyn.db.gz")
                    add_dir(z, Path(ATTACH_DIR), "attachments")
                    add_dir(z, Path(DELIVERY_ATTACH_DIR), "delivery_attachments")
            else:
                with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                    z.setpassword(BACKUP_ZIP_PASSWORD.encode("utf-8"))
                    z.write(tmp_gz, arcname="db/magazyn.db.gz")
                    add_dir(z, Path(ATTACH_DIR), "attachments")
                    add_dir(z, Path(DELIVERY_ATTACH_DIR), "delivery_attachments")

            try:
                tmp_gz.unlink(missing_ok=True)
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

            pwd = (password or BACKUP_ZIP_PASSWORD).encode("utf-8")
            if pyzipper is not None:
                with pyzipper.AESZipFile(bp, "r") as z:
                    z.extractall(tmp_dir, pwd=pwd)
            else:
                with zipfile.ZipFile(bp, "r") as z:
                    z.extractall(tmp_dir, pwd=pwd)

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
