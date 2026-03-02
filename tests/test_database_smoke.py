import pytest
import importlib
import sqlite3
import tempfile
from pathlib import Path


def _setup_temp_env(monkeypatch):
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
    return td, config, db


def test_init_db_creates_tables(monkeypatch):
    td, config, db = _setup_temp_env(monkeypatch)
    try:
        with db.get_conn() as conn:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"devices", "deliveries", "app_users", "app_roles", "app_permissions"}.issubset(names)
    finally:
        td.cleanup()


def test_seed_auth_defaults_no_hardcoded_password(monkeypatch):
    td, config, db = _setup_temp_env(monkeypatch)
    try:
        with db.get_conn() as conn:
            row = conn.execute("SELECT login, password_hash FROM app_users ORDER BY id LIMIT 1").fetchone()
        assert row is not None
        assert row[0] == "admin"
        assert row[1] in (None, "")
    finally:
        td.cleanup()


def test_case_insensitive_unique_login(monkeypatch):
    td, config, db = _setup_temp_env(monkeypatch)
    try:
        with db.get_conn() as conn:
            admin_role_id = int(conn.execute("SELECT id FROM app_roles WHERE name='Administrator'").fetchone()[0])
        db.create_user("UserOne", "VeryStrongPass1", admin_role_id)
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user("userone", "VeryStrongPass2", admin_role_id)
    finally:
        td.cleanup()


def test_basic_deliveries_devices_crud(monkeypatch):
    td, config, db = _setup_temp_env(monkeypatch)
    try:
        delivery_id = db.add_delivery(
            delivery_date="2026-02-05",
            sender_name="Nadawca",
            courier_name="DPD",
            delivery_type="MAGAZYN",
            tracking_number="TRK-1",
            invoice_vat=1,
            notes="uwagi",
        )
        assert delivery_id > 0

        device_id = db.add_device(
            received_date="2026-02-05",
            item_type="device",
            device_name="Test",
            serial_number="SN1",
            imei1="",
            imei2="",
            production_code="",
            delivery_id=delivery_id,
        )
        row = db.get_device(device_id)
        assert row is not None

        linked_rows = db.list_devices_for_delivery(delivery_id)
        assert any(int(r[0]) == device_id for r in linked_rows)

        db.clear_devices_delivery([device_id])
        linked_rows_after = db.list_devices_for_delivery(delivery_id)
        assert all(int(r[0]) != device_id for r in linked_rows_after)

        db.delete_device(device_id)
        assert db.get_device(device_id) is None
    finally:
        td.cleanup()
