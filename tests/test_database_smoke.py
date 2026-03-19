import importlib
import sqlite3
import tempfile
from pathlib import Path

import pytest


def _setup_tmp(monkeypatch):
    td = tempfile.TemporaryDirectory()
    tmp = Path(td.name)
    import magazyn.config as config

    monkeypatch.setattr(config, "APP_DIR", tmp)
    monkeypatch.setattr(config, "DB_PATH", tmp / "magazyn_test.db")
    monkeypatch.setattr(config, "ATTACH_DIR", tmp / "attachments")
    monkeypatch.setattr(config, "DELIVERY_ATTACH_DIR", tmp / "delivery_attachments")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp / "backups")
    monkeypatch.setattr(config, "LOG_FILE", tmp / "magazyn_errors.log")

    import magazyn.database as db

    importlib.reload(db)
    config.ensure_dirs()
    db.init_db()
    return td, db


def test_init_db_creates_tables(monkeypatch):
    td, db = _setup_tmp(monkeypatch)
    try:
        with db.get_conn() as conn:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"devices", "deliveries", "app_users", "app_roles", "app_permissions"}.issubset(names)
    finally:
        td.cleanup()


def test_seed_auth_defaults_does_not_create_hardcoded_admin(monkeypatch):
    td, db = _setup_tmp(monkeypatch)
    try:
        with db.get_conn() as conn:
            users = list(conn.execute("SELECT login, password_hash FROM app_users"))
        assert users == []
        assert db.is_initial_admin_setup_required() is True
    finally:
        td.cleanup()


def test_case_insensitive_unique_login(monkeypatch):
    td, db = _setup_tmp(monkeypatch)
    try:
        db.bootstrap_admin_account("Admin", "BezpieczneHaslo1")
        with db.get_conn() as conn:
            role_id = conn.execute("SELECT id FROM app_roles WHERE name='Gość'").fetchone()[0]
        db.create_user("TestUser", "SilneHaslo123", role_id)
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user("testuser", "SilneHaslo123", role_id)
    finally:
        td.cleanup()


def test_basic_crud_deliveries_and_devices(monkeypatch):
    td, db = _setup_tmp(monkeypatch)
    try:
        delivery_id = db.add_delivery(
            delivery_date="2026-02-05",
            sender_name="Nadawca",
            courier_name="DPD",
            delivery_type="MAGAZYN",
            tracking_number="TRK123",
            invoice_vat=1,
            notes="ok",
        )
        assert db.get_delivery(delivery_id) is not None

        did = db.add_device(
            received_date="2026-02-05",
            item_type="device",
            device_name="Test",
            serial_number="SN1",
            imei1="",
            imei2="",
            production_code="",
            delivery_id=delivery_id,
        )
        assert db.get_device(did) is not None

        db.update_delivery(delivery_id, "2026-02-06", "Nadawca2", "DHL", "SERWIS", "TRK2", 0, "upd")
        db.update_device(did, "2026-02-06", "accessory", "Case", "SN2", "", "", "PC", "note")

        db.delete_device(did)
        db.delete_delivery(delivery_id)
        assert db.get_device(did) is None
        assert db.get_delivery(delivery_id) is None
    finally:
        td.cleanup()


def test_migration_keeps_delivery_attachment_fk_on_deliveries(monkeypatch):
    td, db = _setup_tmp(monkeypatch)
    try:
        with db.get_conn() as conn:
            conn.execute("DROP TABLE delivery_attachments")
            conn.execute("DROP TABLE devices")
            conn.execute("DROP TABLE deliveries")
            conn.execute(
                """
                CREATE TABLE deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_date TEXT NOT NULL,
                    sender_name TEXT,
                    courier_name TEXT,
                    delivery_type TEXT NOT NULL,
                    tracking_number TEXT,
                    invoice_vat INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_date TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'device',
                    device_name TEXT,
                    serial_number TEXT,
                    imei1 TEXT,
                    imei2 TEXT,
                    production_code TEXT,
                    notes TEXT,
                    delivery_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE delivery_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()

        db.migrate_db()

        with db.get_conn() as conn:
            fk_rows = conn.execute("PRAGMA foreign_key_list(delivery_attachments)").fetchall()
            assert {row[2] for row in fk_rows} == {"deliveries"}

        delivery_id = db.add_delivery(
            delivery_date="2026-03-19",
            sender_name="Nadawca",
            courier_name="DHL",
            delivery_type="MAGAZYN",
            tracking_number="",
            invoice_vat=0,
            notes="",
        )
        attachment_src = Path(td.name) / "foto.jpg"
        attachment_src.write_bytes(b"fake image bytes")
        db.add_delivery_attachment(delivery_id, str(attachment_src))

        attachments = db.list_delivery_attachments(delivery_id)
        assert len(attachments) == 1
    finally:
        td.cleanup()
