import tempfile
from pathlib import Path
import importlib

def test_init_and_basic_crud(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

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

        did = db.add_device(
            received_date="2026-02-05",
            item_type="device",
            device_name="Test",
            serial_number="SN1",
            imei1="",
            imei2="",
            production_code="",
            delivery_id=None,
        )
        assert db.get_device(did) is not None

        db.delete_device(did)
        assert db.get_device(did) is None
