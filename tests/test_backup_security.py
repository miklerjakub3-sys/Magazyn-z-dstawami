import importlib
import sqlite3
import sys
import tempfile
import types
from pathlib import Path

import pytest


def _install_fake_pyzipper():
    fake = types.SimpleNamespace()

    class FakeAESZipFile:
        def __init__(self, *args, **kwargs):
            kwargs.pop("encryption", None)
            self._zf = __import__("zipfile").ZipFile(*args, **kwargs)

        def setpassword(self, pwd):
            self._zf.setpassword(pwd)

        def write(self, *args, **kwargs):
            return self._zf.write(*args, **kwargs)

        def writestr(self, *args, **kwargs):
            return self._zf.writestr(*args, **kwargs)

        def infolist(self):
            return self._zf.infolist()

        def open(self, *args, **kwargs):
            return self._zf.open(*args, **kwargs)

        def __enter__(self):
            self._zf.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._zf.__exit__(exc_type, exc, tb)

    fake.AESZipFile = FakeAESZipFile
    fake.WZ_AES = object()
    sys.modules["pyzipper"] = fake


def _setup_backup(monkeypatch):
    td = tempfile.TemporaryDirectory()
    tmp = Path(td.name)

    import magazyn.config as config

    monkeypatch.setattr(config, "APP_DIR", tmp)
    monkeypatch.setattr(config, "DB_PATH", tmp / "magazyn_test.db")
    monkeypatch.setattr(config, "ATTACH_DIR", tmp / "attachments")
    monkeypatch.setattr(config, "DELIVERY_ATTACH_DIR", tmp / "delivery_attachments")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp / "backups")
    monkeypatch.setattr(config, "LOG_FILE", tmp / "magazyn_errors.log")
    monkeypatch.setattr(config, "BACKUP_ZIP_PASSWORD", "test-secret")

    _install_fake_pyzipper()
    import magazyn.database as db
    import magazyn.backup as backup

    importlib.reload(db)
    importlib.reload(backup)

    config.ensure_dirs()
    db.init_db()

    return td, db, backup


def test_create_backup_uses_snapshot_and_succeeds(monkeypatch):
    td, db, backup = _setup_backup(monkeypatch)
    try:
        with db.get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        db.add_delivery(
            delivery_date="2026-01-01",
            sender_name="Test",
            courier_name="DHL",
            delivery_type="MAGAZYN",
            tracking_number="TRK",
            invoice_vat=0,
            notes="",
        )

        path = backup.BackupManager().create_backup(manual=True)
        assert path is not None
        assert Path(path).exists()
    finally:
        td.cleanup()


def test_safe_extract_blocks_zip_traversal(tmp_path):
    _install_fake_pyzipper()
    import magazyn.backup as backup

    zip_path = tmp_path / "bad.zip"
    with backup.pyzipper.AESZipFile(zip_path, "w", compression=backup.zipfile.ZIP_DEFLATED, encryption=backup.pyzipper.WZ_AES) as zf:
        zf.setpassword(b"x")
        zf.writestr("../evil.txt", "boom")

    with backup.pyzipper.AESZipFile(zip_path, "r") as zf:
        zf.setpassword(b"x")
        with pytest.raises(ValueError):
            backup.safe_extract(zf, tmp_path / "out")
