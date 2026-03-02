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
