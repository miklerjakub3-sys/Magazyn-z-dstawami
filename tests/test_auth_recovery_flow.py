import importlib
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


def _setup_env(monkeypatch):
    td = tempfile.TemporaryDirectory()
    tmp = Path(td.name)

    import magazyn.config as config

    monkeypatch.setattr(config, "APP_DIR", tmp)
    monkeypatch.setattr(config, "DB_PATH", tmp / "magazyn_test.db")
    monkeypatch.setattr(config, "ATTACH_DIR", tmp / "attachments")
    monkeypatch.setattr(config, "DELIVERY_ATTACH_DIR", tmp / "delivery_attachments")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp / "backups")
    monkeypatch.setattr(config, "LOG_FILE", tmp / "magazyn_errors.log")
    monkeypatch.setattr(config, "MAIN_ADMIN_LOGIN", "admin")

    _install_fake_pyzipper()
    import magazyn.database as db
    import magazyn.services as services

    importlib.reload(db)
    importlib.reload(services)

    config.ensure_dirs()

    svc = services.MagazynService()
    svc.init_db()
    svc.bootstrap_admin_account("admin", "StartHaslo123")
    user = svc.authenticate_user("admin", "StartHaslo123")
    assert user is not None
    svc.set_current_user(user)

    return td, db, svc


def test_offline_recovery_code_is_single_use_and_resets_password(monkeypatch):
    td, db, svc = _setup_env(monkeypatch)
    try:
        codes = svc.generate_admin_recovery_codes()
        assert len(codes) == 10

        stored_hashes = db.list_admin_recovery_code_hashes("admin")
        assert len(stored_hashes) == 10
        assert codes[0] not in stored_hashes

        svc.reset_admin_password_with_recovery_code(codes[0], "NoweHaslo456")
        assert svc.authenticate_user("admin", "NoweHaslo456") is not None

        with pytest.raises(ValueError):
            svc.reset_admin_password_with_recovery_code(codes[0], "InneHaslo789")
    finally:
        td.cleanup()


def test_login_lockout_blocks_even_valid_password_temporarily(monkeypatch):
    td, db, svc = _setup_env(monkeypatch)
    try:
        for _ in range(db.LOGIN_MAX_ATTEMPTS):
            assert svc.authenticate_user("admin", "zlehaslo") is None

        assert svc.authenticate_user("admin", "StartHaslo123") is None

        with db.get_conn() as conn:
            conn.execute(
                "UPDATE app_auth_state SET login_locked_until='2000-01-01 00:00:00' WHERE login_key='admin'"
            )
            conn.commit()

        assert svc.authenticate_user("admin", "StartHaslo123") is not None
    finally:
        td.cleanup()


def test_reset_code_attempt_rate_limit(monkeypatch):
    td, db, svc = _setup_env(monkeypatch)
    try:
        ok = db.set_password_reset_code("admin", "", "abc", "2999-01-01 00:00:00")
        assert ok is True

        for _ in range(db.RESET_MAX_ATTEMPTS):
            assert db.consume_admin_recovery_code("admin", "bad-hash", db._password_hash("XyZ123456")) is False

        assert db.consume_admin_recovery_code("admin", "bad-hash", db._password_hash("XyZ123456")) is False

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT reset_locked_until FROM app_auth_state WHERE login_key='admin'"
            ).fetchone()
        assert row is not None and row[0]
    finally:
        td.cleanup()
