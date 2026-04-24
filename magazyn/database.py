#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moduł bazy danych - operacje na urządzeniach i dostawach
"""

import os
import sqlite3
import shutil
import hashlib
import hmac
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from .config import DB_PATH, DELIVERY_ATTACH_DIR, DELIVERY_TYPES
from .utils import one_line, validate_ymd, copy_attachment_for_delivery
from .log import get_logger


log = get_logger("magazyn.db")

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 5
RESET_MAX_ATTEMPTS = 5
RESET_LOCKOUT_MINUTES = 10


# =======================
#  POŁĄCZENIE Z BAZĄ
# =======================
def get_conn():
    """Połączenie z bazą danych z timeoutem"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging dla lepszej wydajności
    return conn


# =======================
#  INICJALIZACJA
# =======================
def init_db():
    """Inicjalizacja bazy danych z indeksami"""
    with get_conn() as conn:
        cur = conn.cursor()

        # Tabela urządzeń
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
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
        """)

        # Tabela dostaw
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
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
        """)

        # Tabele słownikowe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS couriers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS senders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        # Załączniki
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delivery_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
            )
        """)

        # Historia wydań (WZ)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS issue_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_date TEXT NOT NULL,
                issue_place TEXT NOT NULL,
                buyer_name TEXT NOT NULL,
                buyer_address TEXT NOT NULL,
                items_json TEXT NOT NULL,
                pdf_path TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Użytkownicy / role / uprawnienia
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                PRIMARY KEY(role_id, permission_id),
                FOREIGN KEY(role_id) REFERENCES app_roles(id) ON DELETE CASCADE,
                FOREIGN KEY(permission_id) REFERENCES app_permissions(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                recovery_email TEXT,
                reset_code_hash TEXT,
                reset_code_expires TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY(role_id) REFERENCES app_roles(id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_auth_state (
                login_key TEXT PRIMARY KEY,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                login_locked_until TEXT,
                failed_reset_attempts INTEGER NOT NULL DEFAULT 0,
                reset_locked_until TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_admin_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
        """)

        # INDEKSY - kluczowe dla wydajności
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_devices_received_date ON devices(received_date)",
            "CREATE INDEX IF NOT EXISTS idx_devices_serial_number ON devices(serial_number)",
            "CREATE INDEX IF NOT EXISTS idx_devices_imei1 ON devices(imei1)",
            "CREATE INDEX IF NOT EXISTS idx_devices_imei2 ON devices(imei2)",
            "CREATE INDEX IF NOT EXISTS idx_devices_item_type ON devices(item_type)",
            "CREATE INDEX IF NOT EXISTS idx_devices_delivery_id ON devices(delivery_id)",
            "CREATE INDEX IF NOT EXISTS idx_deliveries_date ON deliveries(delivery_date)",
            "CREATE INDEX IF NOT EXISTS idx_deliveries_type ON deliveries(delivery_type)",
            "CREATE INDEX IF NOT EXISTS idx_deliveries_sender ON deliveries(sender_name)",
            "CREATE INDEX IF NOT EXISTS idx_delivery_attachments_delivery ON delivery_attachments(delivery_id)",
        ]
        
        for idx_sql in indices:
            try:
                cur.execute(idx_sql)
            except Exception as e:
                from .log import get_logger
                get_logger("magazyn.db").exception("Błąd tworzenia indeksu")

        conn.commit()

    migrate_db()
    seed_auth_defaults()


PBKDF2_ROUNDS = 240000


def normalize_login(login: str) -> str:
    return (login or "").strip().lower()


def _password_hash(password: str, salt: Optional[bytes] = None) -> str:
    s = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), s, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${s.hex()}${digest.hex()}"


def _verify_password(password: str, packed: str) -> bool:
    try:
        alg, rounds, salt_hex, hash_hex = packed.split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def seed_auth_defaults() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    permissions = [
        ("receipts.view", "Przyjęcia: podgląd"),
        ("receipts.edit", "Przyjęcia: edycja"),
        ("deliveries.view", "Dostawy: podgląd"),
        ("deliveries.edit", "Dostawy: edycja"),
        ("reports.export", "Raporty: eksport"),
        ("backup.manage", "Backup: zarządzanie"),
        ("users.manage", "Użytkownicy: zarządzanie"),
    ]
    with get_conn() as conn:
        cur = conn.cursor()
        for key, label in permissions:
            cur.execute("INSERT OR IGNORE INTO app_permissions(key, label) VALUES (?, ?)", (key, label))

        for role_name in ("Administrator", "Gość", "Praktykant"):
            cur.execute("INSERT OR IGNORE INTO app_roles(name, created_at) VALUES(?, ?)", (role_name, now))

        cur.execute("SELECT id, key FROM app_permissions")
        perm_map = {str(key): int(pid) for pid, key in cur.fetchall()}

        cur.execute("SELECT id FROM app_roles WHERE name=?", ("Administrator",))
        admin_role_id = int(cur.fetchone()[0])
        for perm_id in perm_map.values():
            cur.execute(
                "INSERT OR IGNORE INTO app_role_permissions(role_id, permission_id) VALUES (?, ?)",
                (admin_role_id, perm_id),
            )

        # Role startowe, które później można dowolnie skonfigurować z Ustawień.
        cur.execute("SELECT id FROM app_roles WHERE name=?", ("Gość",))
        guest_role_id = int(cur.fetchone()[0])
        for key in ("receipts.view", "deliveries.view"):
            perm_id = perm_map.get(key)
            if perm_id:
                cur.execute(
                    "INSERT OR IGNORE INTO app_role_permissions(role_id, permission_id) VALUES (?, ?)",
                    (guest_role_id, perm_id),
                )

        cur.execute("SELECT id FROM app_roles WHERE name=?", ("Praktykant",))
        trainee_role_id = int(cur.fetchone()[0])
        for key in ("receipts.view", "receipts.edit", "deliveries.view"):
            perm_id = perm_map.get(key)
            if perm_id:
                cur.execute(
                    "INSERT OR IGNORE INTO app_role_permissions(role_id, permission_id) VALUES (?, ?)",
                    (trainee_role_id, perm_id),
                )

        cur.execute("SELECT COUNT(1) FROM app_users")
        if int(cur.fetchone()[0]) == 0:
            log.warning(
                "Brak użytkowników w tabeli app_users. Wymagana jest ręczna konfiguracja konta administratora."
            )
        conn.commit()




def is_initial_admin_setup_required() -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM app_users")
        return int(cur.fetchone()[0]) == 0


def bootstrap_admin_account(login: str, password: str) -> None:
    login_normalized = normalize_login(login)
    if not login_normalized:
        raise ValueError("Login administratora jest wymagany.")
    if len((password or "").strip()) < 8:
        raise ValueError("Hasło administratora musi mieć co najmniej 8 znaków.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM app_users")
        if int(cur.fetchone()[0]) > 0:
            raise RuntimeError("Konto administratora jest już skonfigurowane.")
        cur.execute("SELECT id FROM app_roles WHERE name=?", ("Administrator",))
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Brak roli Administrator.")
        cur.execute(
            "INSERT INTO app_users(login, password_hash, role_id, created_at) VALUES (?, ?, ?, ?)",
            (login_normalized, _password_hash(password), int(row[0]), now),
        )
        conn.commit()


def _now() -> datetime:
    return datetime.now()


def _fmt_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _get_or_create_auth_state(cur: sqlite3.Cursor, login_key: str):
    now = _fmt_dt(_now())
    cur.execute(
        "INSERT OR IGNORE INTO app_auth_state(login_key, updated_at) VALUES (?, ?)",
        (login_key, now),
    )
    cur.execute(
        "SELECT failed_login_attempts, login_locked_until, failed_reset_attempts, reset_locked_until FROM app_auth_state WHERE login_key=?",
        (login_key,),
    )
    return cur.fetchone()


def _is_locked(locked_until: Optional[str]) -> bool:
    lock_dt = _parse_dt(locked_until)
    return bool(lock_dt and lock_dt > _now())


def _register_login_failure(cur: sqlite3.Cursor, login_key: str) -> None:
    state = _get_or_create_auth_state(cur, login_key)
    failed = int(state[0] or 0) + 1
    lock_until = None
    if failed >= LOGIN_MAX_ATTEMPTS:
        lock_until = _fmt_dt(_now() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES))
        failed = 0
    cur.execute(
        "UPDATE app_auth_state SET failed_login_attempts=?, login_locked_until=?, updated_at=? WHERE login_key=?",
        (failed, lock_until, _fmt_dt(_now()), login_key),
    )


def _clear_login_failures(cur: sqlite3.Cursor, login_key: str) -> None:
    cur.execute(
        "UPDATE app_auth_state SET failed_login_attempts=0, login_locked_until=NULL, updated_at=? WHERE login_key=?",
        (_fmt_dt(_now()), login_key),
    )


def _register_reset_failure(cur: sqlite3.Cursor, login_key: str) -> None:
    state = _get_or_create_auth_state(cur, login_key)
    failed = int(state[2] or 0) + 1
    lock_until = None
    if failed >= RESET_MAX_ATTEMPTS:
        lock_until = _fmt_dt(_now() + timedelta(minutes=RESET_LOCKOUT_MINUTES))
        failed = 0
    cur.execute(
        "UPDATE app_auth_state SET failed_reset_attempts=?, reset_locked_until=?, updated_at=? WHERE login_key=?",
        (failed, lock_until, _fmt_dt(_now()), login_key),
    )


def _clear_reset_failures(cur: sqlite3.Cursor, login_key: str) -> None:
    cur.execute(
        "UPDATE app_auth_state SET failed_reset_attempts=0, reset_locked_until=NULL, updated_at=? WHERE login_key=?",
        (_fmt_dt(_now()), login_key),
    )

def authenticate_user(login: str, password: str):
    login_key = normalize_login(login)
    if not login_key:
        return None

    with get_conn() as conn:
        cur = conn.cursor()
        state = _get_or_create_auth_state(cur, login_key)
        if _is_locked(state[1]):
            conn.commit()
            return None

        cur.execute(
            """
            SELECT u.id, u.login, u.password_hash, u.role_id, r.name, u.is_active
            FROM app_users u
            JOIN app_roles r ON r.id=u.role_id
            WHERE LOWER(u.login)=LOWER(?)
            """,
            (login_key,),
        )
        row = cur.fetchone()
        if not row or int(row[5]) != 1 or not _verify_password(password, str(row[2])):
            _register_login_failure(cur, login_key)
            conn.commit()
            return None

        _clear_login_failures(cur, login_key)
        conn.commit()
        return {
            "id": int(row[0]),
            "login": str(row[1]),
            "role_id": int(row[3]),
            "role_name": str(row[4]),
        }


def create_remember_token(user_id: int, days_valid: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now()
    exp = now.timestamp() + (days_valid * 86400)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO app_remember_tokens(user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (
                int(user_id),
                token_hash,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    return token


def authenticate_token(token: str):
    token_hash = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.login, u.role_id, r.name
            FROM app_remember_tokens t
            JOIN app_users u ON u.id=t.user_id
            JOIN app_roles r ON r.id=u.role_id
            WHERE t.token_hash=? AND t.expires_at>=? AND u.is_active=1
            ORDER BY t.id DESC LIMIT 1
            """,
            (token_hash, now),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "login": str(row[1]),
            "role_id": int(row[2]),
            "role_name": str(row[3]),
        }


def list_permissions() -> List[Tuple[int, str, str]]:
    with get_conn() as conn:
        return list(conn.execute("SELECT id, key, label FROM app_permissions ORDER BY id"))


def list_roles() -> List[Tuple[int, str]]:
    with get_conn() as conn:
        return list(conn.execute("SELECT id, name FROM app_roles ORDER BY name"))


def list_users() -> List[Tuple[int, str, str, int]]:
    with get_conn() as conn:
        return list(
            conn.execute(
                """
                SELECT u.id, u.login, r.name, u.is_active
                FROM app_users u
                JOIN app_roles r ON r.id=u.role_id
                ORDER BY u.login
                """
            )
        )


def role_permission_keys(role_id: int) -> List[str]:
    with get_conn() as conn:
        return [
            str(r[0])
            for r in conn.execute(
                """
                SELECT p.key FROM app_role_permissions rp
                JOIN app_permissions p ON p.id=rp.permission_id
                WHERE rp.role_id=?
                """,
                (int(role_id),),
            )
        ]


def create_user(login: str, password: str, role_id: int) -> None:
    login_normalized = normalize_login(login)
    if not login_normalized:
        raise ValueError("Login jest wymagany.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_users(login, password_hash, role_id, created_at) VALUES (?, ?, ?, ?)",
            (login_normalized, _password_hash(password), int(role_id), now),
        )
        conn.commit()


def get_user_permission_keys(user_id: int) -> List[str]:
    with get_conn() as conn:
        return [
            str(r[0])
            for r in conn.execute(
                """
                SELECT DISTINCT p.key
                FROM app_users u
                JOIN app_role_permissions rp ON rp.role_id=u.role_id
                JOIN app_permissions p ON p.id=rp.permission_id
                WHERE u.id=? AND u.is_active=1
                """,
                (int(user_id),),
            )
        ]


def update_role_permissions(role_id: int, permission_keys: List[str]) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM app_role_permissions WHERE role_id=?", (int(role_id),))
        for key in permission_keys:
            cur.execute("SELECT id FROM app_permissions WHERE key=?", (str(key),))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT OR IGNORE INTO app_role_permissions(role_id, permission_id) VALUES (?, ?)",
                    (int(role_id), int(row[0])),
                )
        conn.commit()


def set_user_role(user_id: int, role_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "UPDATE app_users SET role_id=?, updated_at=? WHERE id=?",
            (int(role_id), now, int(user_id)),
        )
        conn.commit()


def set_admin_recovery_email(login: str, email: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "UPDATE app_users SET recovery_email=?, updated_at=? WHERE LOWER(login)=LOWER(?)",
            ((email or "").strip(), now, (login or "").strip()),
        )
        conn.commit()


def get_admin_recovery_email(login: str) -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(recovery_email,'') FROM app_users WHERE LOWER(login)=LOWER(?)", ((login or "").strip(),))
        row = cur.fetchone()
        return str(row[0]) if row else ""


def set_password_reset_code(login: str, email: str, code_hash: str, expires_at: str) -> bool:
    login_key = normalize_login(login)
    with get_conn() as conn:
        cur = conn.cursor()
        state = _get_or_create_auth_state(cur, login_key)
        if _is_locked(state[3]):
            conn.commit()
            return False

        cur.execute(
            """
            UPDATE app_users
            SET reset_code_hash=?, reset_code_expires=?
            WHERE LOWER(login)=LOWER(?) AND LOWER(COALESCE(recovery_email,''))=LOWER(?) AND is_active=1
            """,
            (code_hash, expires_at, login_key, (email or "").strip()),
        )
        ok = cur.rowcount > 0
        if ok:
            _clear_reset_failures(cur, login_key)
        conn.commit()
        return ok


def consume_password_reset_code(login: str, email: str, code_hash: str, new_password_hash: str) -> bool:
    login_key = normalize_login(login)
    now = _fmt_dt(_now())
    with get_conn() as conn:
        cur = conn.cursor()
        state = _get_or_create_auth_state(cur, login_key)
        if _is_locked(state[3]):
            conn.commit()
            return False

        cur.execute(
            """
            UPDATE app_users
            SET password_hash=?, reset_code_hash=NULL, reset_code_expires=NULL, updated_at=?
            WHERE LOWER(login)=LOWER(?)
              AND LOWER(COALESCE(recovery_email,''))=LOWER(?)
              AND COALESCE(reset_code_hash,'')=?
              AND COALESCE(reset_code_expires,'')>=?
              AND is_active=1
            """,
            (new_password_hash, now, login_key, (email or "").strip(), code_hash, now),
        )
        ok = cur.rowcount > 0
        if ok:
            _clear_reset_failures(cur, login_key)
        else:
            _register_reset_failure(cur, login_key)
        conn.commit()
        return ok


def list_admin_recovery_code_hashes(login: str) -> List[str]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.code_hash
            FROM app_admin_recovery_codes c
            JOIN app_users u ON u.id=c.user_id
            WHERE LOWER(u.login)=LOWER(?)
            ORDER BY c.id
            """,
            (normalize_login(login),),
        )
        return [str(r[0]) for r in cur.fetchall()]


def replace_admin_recovery_codes(login: str, code_hashes: List[str]) -> None:
    now = _fmt_dt(_now())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM app_users WHERE LOWER(login)=LOWER(?) AND is_active=1", (normalize_login(login),))
        row = cur.fetchone()
        if not row:
            raise ValueError("Konto administratora nie jest dostępne.")
        user_id = int(row[0])
        cur.execute("DELETE FROM app_admin_recovery_codes WHERE user_id=?", (user_id,))
        for code_hash in code_hashes:
            cur.execute(
                "INSERT INTO app_admin_recovery_codes(user_id, code_hash, created_at) VALUES (?, ?, ?)",
                (user_id, str(code_hash), now),
            )
        conn.commit()


def consume_admin_recovery_code(login: str, code_hash: str, new_password_hash: str) -> bool:
    login_key = normalize_login(login)
    now = _fmt_dt(_now())
    with get_conn() as conn:
        cur = conn.cursor()
        state = _get_or_create_auth_state(cur, login_key)
        if _is_locked(state[3]):
            conn.commit()
            return False

        cur.execute("SELECT id FROM app_users WHERE LOWER(login)=LOWER(?) AND is_active=1", (login_key,))
        row = cur.fetchone()
        if not row:
            _register_reset_failure(cur, login_key)
            conn.commit()
            return False
        user_id = int(row[0])

        cur.execute(
            """
            UPDATE app_admin_recovery_codes
            SET used_at=?
            WHERE user_id=? AND code_hash=? AND used_at IS NULL
            """,
            (now, user_id, code_hash),
        )
        if cur.rowcount < 1:
            _register_reset_failure(cur, login_key)
            conn.commit()
            return False

        cur.execute(
            "UPDATE app_users SET password_hash=?, reset_code_hash=NULL, reset_code_expires=NULL, updated_at=? WHERE id=?",
            (new_password_hash, now, user_id),
        )
        _clear_reset_failures(cur, login_key)
        conn.commit()
        return True


def migrate_db():
    """Migracje bazy danych"""
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_auth_state (
                login_key TEXT PRIMARY KEY,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                login_locked_until TEXT,
                failed_reset_attempts INTEGER NOT NULL DEFAULT 0,
                reset_locked_until TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_admin_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_date TEXT NOT NULL,
                issue_place TEXT NOT NULL,
                buyer_name TEXT NOT NULL,
                buyer_address TEXT NOT NULL,
                items_json TEXT NOT NULL,
                pdf_path TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Devices
        cur.execute("PRAGMA table_info(devices)")
        existing = {row[1] for row in cur.fetchall()}
        needed = {
            "item_type": "TEXT",
            "device_name": "TEXT",
            "serial_number": "TEXT",
            "imei1": "TEXT",
            "imei2": "TEXT",
            "production_code": "TEXT",
            "notes": "TEXT",
            "created_at": "TEXT",
            "delivery_id": "INTEGER",
            "updated_at": "TEXT",
        }
        for col, coltype in needed.items():
            if col not in existing:
                try:
                    cur.execute(f"ALTER TABLE devices ADD COLUMN {col} {coltype}")
                except Exception:
                    log.exception(f"Nie można dodać kolumny {col}")

        cur.execute("UPDATE devices SET item_type='device' WHERE item_type IS NULL OR item_type=''")

        # Deliveries
        cur.execute("PRAGMA table_info(deliveries)")
        dex = {row[1] for row in cur.fetchall()}
        d_needed = {
            "delivery_date": "TEXT",
            "sender_name": "TEXT",
            "courier_name": "TEXT",
            "delivery_type": "TEXT",
            "tracking_number": "TEXT",
            "invoice_vat": "INTEGER",
            "notes": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for col, coltype in d_needed.items():
            if col not in dex:
                try:
                    cur.execute(f"ALTER TABLE deliveries ADD COLUMN {col} {coltype}")
                except Exception:
                    log.exception(f"Nie można dodać kolumny {col}")

        conn.commit()

        # App users
        cur.execute("PRAGMA table_info(app_users)")
        ucols = {row[1] for row in cur.fetchall()}
        u_needed = {
            "recovery_email": "TEXT",
            "reset_code_hash": "TEXT",
            "reset_code_expires": "TEXT",
        }
        for col, coltype in u_needed.items():
            if col not in ucols:
                try:
                    cur.execute(f"ALTER TABLE app_users ADD COLUMN {col} {coltype}")
                except Exception:
                    log.exception(f"Nie można dodać kolumny {col}")

        _normalize_existing_logins(cur)
        _enforce_case_insensitive_login_unique(cur)
        _rebuild_deliveries_with_constraints(cur)
        _rebuild_delivery_attachments_with_constraints(cur)
        _rebuild_devices_with_constraints(cur)
        conn.commit()


def add_issue_history(issue_date: str, issue_place: str, buyer_name: str, buyer_address: str, items, pdf_path: str = "") -> int:
    issue_date = (issue_date or "").strip()
    issue_place = (issue_place or "").strip()
    buyer_name = (buyer_name or "").strip()
    buyer_address = (buyer_address or "").strip()
    pdf_path = (pdf_path or "").strip()
    if not issue_date:
        issue_date = datetime.now().strftime("%Y-%m-%d")
    validate_ymd(issue_date)
    if not issue_place:
        raise ValueError("Miejsce wystawienia jest wymagane.")
    if not buyer_name:
        raise ValueError("Nazwa odbiorcy jest wymagana.")
    if not buyer_address:
        raise ValueError("Adres odbiorcy jest wymagany.")
    if not items:
        raise ValueError("Lista pozycji jest pusta.")

    serialized_items = json.dumps(items, ensure_ascii=False)
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO issue_history(issue_date, issue_place, buyer_name, buyer_address, items_json, pdf_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (issue_date, issue_place, buyer_name, buyer_address, serialized_items, pdf_path, created_at),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_issue_history(limit: int = 200):
    limit = max(1, min(int(limit or 200), 1000))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, issue_date, issue_place, buyer_name, buyer_address, items_json, pdf_path, created_at
            FROM issue_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                items = json.loads(r[5] or "[]")
            except Exception:
                items = []
            out.append((r[0], r[1], r[2], r[3], r[4], items, r[6], r[7]))
        return out


def delete_issue_history(issue_id: int) -> None:
    issue_id = int(issue_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM issue_history WHERE id=?", (issue_id,))
        conn.commit()


def _normalize_existing_logins(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT id, login FROM app_users ORDER BY id")
    for user_id, login in cur.fetchall():
        normalized = normalize_login(str(login or ""))
        if normalized and normalized != (login or ""):
            cur.execute("UPDATE app_users SET login=? WHERE id=?", (normalized, int(user_id)))


def _enforce_case_insensitive_login_unique(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        SELECT LOWER(login), COUNT(1)
        FROM app_users
        GROUP BY LOWER(login)
        HAVING COUNT(1) > 1
        """
    )
    if cur.fetchone():
        raise RuntimeError("Nie można utworzyć indeksu unikalnego LOWER(login): istnieją duplikaty loginów.")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_login_lower_unique ON app_users(LOWER(login))"
    )


def _rebuild_deliveries_with_constraints(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='deliveries'")
    row = cur.fetchone()
    sql = (row[0] or "") if row else ""
    required_fragments = [
        "CHECK (invoice_vat IN (0,1))",
        "CHECK (delivery_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]')",
        "CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*')",
    ]
    if all(fragment in sql for fragment in required_fragments):
        return

    cur.execute("ALTER TABLE deliveries RENAME TO deliveries_old")
    cur.execute(
        """
        CREATE TABLE deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_date TEXT NOT NULL CHECK (delivery_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'),
            sender_name TEXT,
            courier_name TEXT,
            delivery_type TEXT NOT NULL,
            tracking_number TEXT,
            invoice_vat INTEGER NOT NULL DEFAULT 0 CHECK (invoice_vat IN (0,1)),
            notes TEXT,
            created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*'),
            updated_at TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO deliveries(id, delivery_date, sender_name, courier_name, delivery_type, tracking_number, invoice_vat, notes, created_at, updated_at)
        SELECT
            id,
            CASE
                WHEN delivery_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]' THEN delivery_date
                ELSE substr(COALESCE(delivery_date,''), 1, 10)
            END,
            sender_name,
            courier_name,
            delivery_type,
            tracking_number,
            CASE WHEN invoice_vat = 1 THEN 1 ELSE 0 END,
            notes,
            CASE
                WHEN created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*' THEN created_at
                ELSE datetime('now')
            END,
            updated_at
        FROM deliveries_old
        """
    )
    cur.execute("DROP TABLE deliveries_old")


def _rebuild_delivery_attachments_with_constraints(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='delivery_attachments'")
    row = cur.fetchone()
    sql = (row[0] or "") if row else ""
    fk_rows = cur.execute("PRAGMA foreign_key_list(delivery_attachments)").fetchall()
    target_tables = {str(fk[2]) for fk in fk_rows}
    required_fragments = [
        "FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE",
    ]
    if all(fragment in sql for fragment in required_fragments) and target_tables in ({"deliveries"}, set()):
        return

    cur.execute("ALTER TABLE delivery_attachments RENAME TO delivery_attachments_old")
    cur.execute(
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
    cur.execute(
        """
        INSERT INTO delivery_attachments(id, delivery_id, file_path, file_name, created_at)
        SELECT id, delivery_id, file_path, file_name, created_at
        FROM delivery_attachments_old
        """
    )
    cur.execute("DROP TABLE delivery_attachments_old")


def _rebuild_devices_with_constraints(cur: sqlite3.Cursor) -> None:
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='devices'")
    row = cur.fetchone()
    sql = (row[0] or "") if row else ""
    required_fragments = [
        "CHECK (item_type IN ('device','accessory'))",
        "CHECK (received_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]')",
        "CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*')",
    ]
    if all(fragment in sql for fragment in required_fragments):
        return

    cur.execute("ALTER TABLE devices RENAME TO devices_old")
    cur.execute(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_date TEXT NOT NULL CHECK (received_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'),
            item_type TEXT NOT NULL DEFAULT 'device' CHECK (item_type IN ('device','accessory')),
            device_name TEXT,
            serial_number TEXT,
            imei1 TEXT,
            imei2 TEXT,
            production_code TEXT,
            notes TEXT,
            delivery_id INTEGER,
            created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*'),
            updated_at TEXT,
            FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE SET NULL
        )
        """
    )
    cur.execute(
        """
        INSERT INTO devices(id, received_date, item_type, device_name, serial_number, imei1, imei2, production_code, notes, delivery_id, created_at, updated_at)
        SELECT
            id,
            CASE
                WHEN received_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]' THEN received_date
                ELSE substr(COALESCE(received_date,''), 1, 10)
            END,
            CASE WHEN item_type IN ('device','accessory') THEN item_type ELSE 'device' END,
            device_name,
            serial_number,
            imei1,
            imei2,
            production_code,
            notes,
            delivery_id,
            CASE
                WHEN created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*' THEN created_at
                ELSE datetime('now')
            END,
            updated_at
        FROM devices_old
        """
    )
    cur.execute("DROP TABLE devices_old")


# =======================
#  OPERACJE NA URZĄDZENIACH
# =======================
def find_device_duplicates(serial_number: str, imei1: str, imei2: str, exclude_id: int = None):
    """Wyszukiwanie duplikatów"""
    serial_number = (serial_number or "").strip()
    imei1 = (imei1 or "").strip()
    imei2 = (imei2 or "").strip()

    where = []
    params = []

    if serial_number:
        where.append("COALESCE(serial_number,'') = ?")
        params.append(serial_number)

    imeis = [x for x in [imei1, imei2] if x]
    if imeis:
        ph = ",".join(["?"] * len(imeis))
        where.append(f"(COALESCE(imei1,'') IN ({ph}) OR COALESCE(imei2,'') IN ({ph}))")
        params.extend(imeis)
        params.extend(imeis)

    if not where:
        return []

    sql = "SELECT id, received_date, device_name, serial_number, imei1, imei2 FROM devices WHERE (" + " OR ".join(where) + ")"
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    
    sql += " LIMIT 100"  # Ograniczenie wyników

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def add_device(received_date, item_type, device_name, serial_number, imei1, imei2, production_code, delivery_id=None):
    """Dodawanie urządzenia"""
    received_date = (received_date or "").strip()
    item_type = (item_type or "device").strip()
    device_name = (device_name or "").strip()
    serial_number = (serial_number or "").strip()
    imei1 = (imei1 or "").strip()
    imei2 = (imei2 or "").strip()
    production_code = (production_code or "").strip()

    if item_type not in ("device", "accessory"):
        item_type = "device"

    if not received_date:
        raise ValueError("Data przyjęcia jest wymagana (YYYY-MM-DD).")
    validate_ymd(received_date)

    if not device_name and not serial_number:
        raise ValueError("Podaj przynajmniej 'Nazwa' albo 'SN/Kod'.")

    created_at = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO devices (received_date, item_type, device_name, serial_number, imei1, imei2, 
                                production_code, notes, created_at, delivery_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (received_date, item_type, device_name, serial_number, imei1, imei2, 
              production_code, "", created_at, delivery_id, created_at))
        conn.commit()
        return cur.lastrowid


def update_device(device_id, received_date, item_type, device_name, serial_number, imei1, imei2, production_code, notes):
    """Aktualizacja urządzenia"""
    received_date = (received_date or "").strip()
    item_type = (item_type or "device").strip()
    device_name = (device_name or "").strip()
    serial_number = (serial_number or "").strip()
    imei1 = (imei1 or "").strip()
    imei2 = (imei2 or "").strip()
    production_code = (production_code or "").strip()
    notes = (notes or "").strip()

    if item_type not in ("device", "accessory"):
        item_type = "device"

    if not received_date:
        raise ValueError("Data przyjęcia jest wymagana (YYYY-MM-DD).")
    validate_ymd(received_date)

    if not device_name and not serial_number:
        raise ValueError("Podaj przynajmniej 'Nazwa' albo 'SN/Kod'.")

    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE devices
            SET received_date=?, item_type=?, device_name=?, serial_number=?, 
                imei1=?, imei2=?, production_code=?, notes=?, updated_at=?
            WHERE id=?
        """, (received_date, item_type, device_name, serial_number, imei1, imei2, 
              production_code, notes, updated_at, device_id))
        conn.commit()


def delete_device(device_id: int):
    """Usuwanie urządzenia"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM devices WHERE id=?", (device_id,))
        conn.commit()


def get_device(device_id):
    """Pobieranie urządzenia po ID"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, received_date, item_type, device_name, serial_number, imei1, imei2, 
                   production_code, notes, created_at
            FROM devices
            WHERE id=?
        """, (device_id,))
        return cur.fetchone()


def search_devices(
    query="",
    item_type="all",
    date_from="",
    date_to="",
    order_by="received_date",
    order_dir="DESC",
    limit=1000,
    offset=0,
):
    """Wyszukiwanie urządzeń ze stronicowaniem"""
    q = (query or "").strip()
    t = (item_type or "all").strip()

    allowed_order = {
        "received_date": "received_date",
        "created_at": "created_at",
        "id": "id",
        "item_type": "item_type",
        "device_name": "device_name",
        "serial_number": "serial_number",
        "imei1": "imei1",
        "imei2": "imei2",
        "production_code": "production_code",
        "delivery_id": "delivery_id",
        "notes": "notes",
    }
    ob = allowed_order.get(order_by, "received_date")
    od = "DESC" if (order_dir or "").upper() == "DESC" else "ASC"

    df = (date_from or "").strip()
    dt = (date_to or "").strip()

    where = []
    params = []

    if df and dt:
        validate_ymd(df)
        validate_ymd(dt)
        where.append("received_date BETWEEN ? AND ?")
        params.extend([df, dt])
    elif df:
        validate_ymd(df)
        where.append("received_date >= ?")
        params.append(df)
    elif dt:
        validate_ymd(dt)
        where.append("received_date <= ?")
        params.append(dt)

    if t in ("device", "accessory"):
        where.append("item_type = ?")
        params.append(t)

    if q:
        like = f"%{q}%"
        where.append("""
            (
                COALESCE(device_name,'') LIKE ? OR
                COALESCE(serial_number,'') LIKE ? OR
                COALESCE(imei1,'') LIKE ? OR
                COALESCE(imei2,'') LIKE ? OR
                COALESCE(production_code,'') LIKE ? OR
                COALESCE(notes,'') LIKE ?
            )
        """)
        params.extend([like, like, like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with get_conn() as conn:
        cur = conn.cursor()
        
        # Liczba wszystkich wyników
        cur.execute(f"SELECT COUNT(*) FROM devices {where_sql}", params)
        total_count = cur.fetchone()[0]
        
        # Wyniki ze stronicowaniem
        cur.execute(f"""
            SELECT id, received_date, item_type, device_name, serial_number,
                   imei1, imei2, production_code, notes, created_at, delivery_id
            FROM devices
            {where_sql}
            ORDER BY {ob} {od}, id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        
        results = cur.fetchall()
        
        return results, total_count


def get_devices_by_date_range(date_from, date_to, item_type="all"):
    """Pobieranie urządzeń z opcjonalnego zakresu dat"""
    df = (date_from or "").strip()
    dt = (date_to or "").strip()

    t = (item_type or "all").strip()
    where = []
    params = []

    if df and dt:
        validate_ymd(df)
        validate_ymd(dt)
        where.append("received_date BETWEEN ? AND ?")
        params.extend([df, dt])
    elif df:
        validate_ymd(df)
        where.append("received_date >= ?")
        params.append(df)
    elif dt:
        validate_ymd(dt)
        where.append("received_date <= ?")
        params.append(dt)
    if t in ("device", "accessory"):
        where.append("item_type = ?")
        params.append(t)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, received_date, item_type, device_name, serial_number,
                   imei1, imei2, production_code, notes, created_at, delivery_id
            FROM devices
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY received_date ASC, id ASC
            LIMIT 10000
        """, params)
        return cur.fetchall()


# =======================
#  SŁOWNIKI
# =======================
def list_couriers():
    """Lista kurierów"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM couriers ORDER BY name ASC")
        return [r[0] for r in cur.fetchall()]


def list_senders():
    """Lista nadawców"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM senders ORDER BY name ASC")
        return [r[0] for r in cur.fetchall()]


def add_courier(name: str):
    """Dodawanie kuriera"""
    name = (name or "").strip()
    if not name:
        raise ValueError("Podaj nazwę kuriera.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO couriers(name) VALUES(?)", (name,))
        conn.commit()


def remove_courier(name: str):
    """Usuwanie kuriera"""
    name = (name or "").strip()
    if not name:
        raise ValueError("Wybierz kuriera do usunięcia.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM couriers WHERE name=?", (name,))
        conn.commit()


def add_sender(name: str):
    """Dodawanie nadawcy"""
    name = (name or "").strip()
    if not name:
        raise ValueError("Podaj nazwę nadawcy.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO senders(name) VALUES(?)", (name,))
        conn.commit()


def remove_sender(name: str):
    """Usuwanie nadawcy"""
    name = (name or "").strip()
    if not name:
        raise ValueError("Wybierz nadawcę do usunięcia.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM senders WHERE name=?", (name,))
        conn.commit()


# =======================
#  OPERACJE NA DOSTAWACH
# =======================
def add_delivery(delivery_date, sender_name, courier_name, delivery_type, tracking_number, invoice_vat, notes):
    """Dodawanie dostawy"""
    delivery_date = (delivery_date or "").strip()
    sender_name = (sender_name or "").strip()
    courier_name = (courier_name or "").strip()
    delivery_type = (delivery_type or "").strip()
    tracking_number = (tracking_number or "").strip()
    notes = one_line((notes or "").strip())
    invoice_vat = 1 if invoice_vat else 0

    if not delivery_date:
        raise ValueError("Data dostawy jest wymagana (YYYY-MM-DD).")
    validate_ymd(delivery_date)

    if delivery_type not in DELIVERY_TYPES:
        raise ValueError("Nieprawidłowy typ dostawy.")

    created_at = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO deliveries (delivery_date, sender_name, courier_name, delivery_type, 
                                   tracking_number, invoice_vat, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (delivery_date, sender_name, courier_name, delivery_type, tracking_number, 
              invoice_vat, notes, created_at, created_at))
        conn.commit()
        return cur.lastrowid


def update_delivery(delivery_id, delivery_date, sender_name, courier_name, delivery_type, tracking_number, invoice_vat, notes):
    """Aktualizacja dostawy"""
    delivery_date = (delivery_date or "").strip()
    sender_name = (sender_name or "").strip()
    courier_name = (courier_name or "").strip()
    delivery_type = (delivery_type or "").strip()
    tracking_number = (tracking_number or "").strip()
    notes = one_line((notes or "").strip())
    invoice_vat = 1 if invoice_vat else 0

    if not delivery_date:
        raise ValueError("Data dostawy jest wymagana (YYYY-MM-DD).")
    validate_ymd(delivery_date)

    if delivery_type not in DELIVERY_TYPES:
        raise ValueError("Nieprawidłowy typ dostawy.")

    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE deliveries
            SET delivery_date=?, sender_name=?, courier_name=?, delivery_type=?,
                tracking_number=?, invoice_vat=?, notes=?, updated_at=?
            WHERE id=?
        """, (delivery_date, sender_name, courier_name, delivery_type, tracking_number, 
              invoice_vat, notes, updated_at, delivery_id))
        conn.commit()


def delete_delivery(delivery_id: int):
    """Usuwanie dostawy"""
    folder = os.path.join(DELIVERY_ATTACH_DIR, str(delivery_id))
    if os.path.isdir(folder):
        try:
            shutil.rmtree(folder)
        except Exception:
            pass

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM deliveries WHERE id=?", (delivery_id,))
        conn.commit()


def get_delivery(delivery_id: int):
    """Pobieranie dostawy po ID"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, delivery_date, sender_name, courier_name, delivery_type, 
                   tracking_number, invoice_vat, notes, created_at
            FROM deliveries
            WHERE id=?
        """, (delivery_id,))
        return cur.fetchone()


def search_deliveries(
    date_from="",
    date_to="",
    sender="",
    courier="",
    delivery_type="",
    order_by="delivery_date",
    order_dir="DESC",
    limit=1000,
    offset=0,
):
    """Wyszukiwanie dostaw ze stronicowaniem"""
    where = []
    params = []

    df = (date_from or "").strip()
    dt = (date_to or "").strip()
    sender = (sender or "").strip()
    courier = (courier or "").strip()
    delivery_type = (delivery_type or "").strip()

    if df and dt:
        validate_ymd(df)
        validate_ymd(dt)
        where.append("delivery_date BETWEEN ? AND ?")
        params.extend([df, dt])
    elif df:
        validate_ymd(df)
        where.append("delivery_date >= ?")
        params.append(df)
    elif dt:
        validate_ymd(dt)
        where.append("delivery_date <= ?")
        params.append(dt)

    if sender:
        where.append("COALESCE(sender_name,'') = ?")
        params.append(sender)

    if courier:
        where.append("COALESCE(courier_name,'') = ?")
        params.append(courier)

    if delivery_type:
        if delivery_type not in DELIVERY_TYPES:
            raise ValueError("Nieprawidłowy typ dostawy.")
        where.append("delivery_type = ?")
        params.append(delivery_type)

    allowed_order = {
        "delivery_date": "delivery_date",
        "sender_name": "sender_name",
        "courier_name": "courier_name",
        "delivery_type": "delivery_type",
        "tracking_number": "tracking_number",
        "invoice_vat": "invoice_vat",
        "notes": "notes",
        "created_at": "created_at",
        "id": "id",
    }
    ob = allowed_order.get(order_by, "delivery_date")
    od = "DESC" if (order_dir or "").upper() == "DESC" else "ASC"

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with get_conn() as conn:
        cur = conn.cursor()
        
        # Liczba wszystkich wyników
        cur.execute(f"SELECT COUNT(*) FROM deliveries {where_sql}", params)
        total_count = cur.fetchone()[0]
        
        # Wyniki ze stronicowaniem
        cur.execute(f"""
            SELECT id, delivery_date, sender_name, courier_name, delivery_type, 
                   tracking_number, invoice_vat, notes, created_at
            FROM deliveries
            {where_sql}
            ORDER BY {ob} {od}, id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        
        results = cur.fetchall()
        
        return results, total_count


def get_deliveries_by_date_range(date_from, date_to, delivery_type=""):
    """Pobieranie dostaw z opcjonalnego zakresu dat"""
    df = (date_from or "").strip()
    dt = (date_to or "").strip()

    where = []
    params = []

    if df and dt:
        validate_ymd(df)
        validate_ymd(dt)
        where.append("delivery_date BETWEEN ? AND ?")
        params.extend([df, dt])
    elif df:
        validate_ymd(df)
        where.append("delivery_date >= ?")
        params.append(df)
    elif dt:
        validate_ymd(dt)
        where.append("delivery_date <= ?")
        params.append(dt)

    if delivery_type:
        if delivery_type not in DELIVERY_TYPES:
            raise ValueError("Nieprawidłowy typ dostawy.")
        where.append("delivery_type = ?")
        params.append(delivery_type)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, delivery_date, sender_name, courier_name, delivery_type,
                   tracking_number, invoice_vat, notes, created_at
            FROM deliveries
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY delivery_date ASC, id ASC
            LIMIT 10000
        """, params)
        return cur.fetchall()


# =======================
#  POWIĄZANIA I ZAŁĄCZNIKI
# =======================
def list_recent_deliveries(limit=80):
    """Lista ostatnich dostaw"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, delivery_date, sender_name, delivery_type, tracking_number
            FROM deliveries
            ORDER BY delivery_date DESC, id DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()


def list_devices_for_delivery_date(delivery_date: str, include_linked_to_other: bool = False, delivery_id: int = None):
    """Lista urządzeń dla daty dostawy"""
    delivery_date = (delivery_date or "").strip()
    if not delivery_date:
        return []
    validate_ymd(delivery_date)

    params = []
    if delivery_id is None:
        where = ["received_date = ?"]
        params.append(delivery_date)
        if not include_linked_to_other:
            where.append("delivery_id IS NULL")
    else:
        did = int(delivery_id)
        # Zawsze pokazuj rekordy już powiązane z bieżącą dostawą,
        # nawet jeśli mają inną datę niż aktualnie wybrana w filtrze.
        if include_linked_to_other:
            where = ["(received_date = ? OR delivery_id = ?)"]
            params.extend([delivery_date, did])
        else:
            where = ["((received_date = ? AND (delivery_id IS NULL OR delivery_id = ?)) OR delivery_id = ?)"]
            params.extend([delivery_date, did, did])

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, received_date, item_type, device_name, serial_number, imei1, imei2, 
                   production_code, notes, created_at, COALESCE(delivery_id, 0)
            FROM devices
            WHERE {" AND ".join(where)}
            ORDER BY id DESC
            LIMIT 5000
        """, params)
        return cur.fetchall()


def list_devices_for_delivery_linking(delivery_id: int, show_all: bool = False, query: str = "", limit: int = 5000):
    """Lista urządzeń do okna powiązań dostawy.

    - show_all=False: tylko rekordy już powiązane z bieżącą dostawą
    - show_all=True: wszystkie rekordy (najnowsze na górze)
    """
    did = int(delivery_id)
    q = (query or "").strip()
    where = []
    params = []

    if show_all:
        where.append("1=1")
    else:
        where.append("delivery_id = ?")
        params.append(did)

    if q:
        where.append(
            "(" 
            "COALESCE(device_name,'') LIKE ? OR "
            "COALESCE(serial_number,'') LIKE ? OR "
            "COALESCE(imei1,'') LIKE ? OR "
            "COALESCE(imei2,'') LIKE ?"
            ")"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like])

    params.append(int(limit))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, received_date, item_type, device_name, serial_number, imei1, imei2,
                   production_code, notes, created_at, COALESCE(delivery_id, 0)
            FROM devices
            WHERE {' AND '.join(where)}
            ORDER BY received_date DESC, id DESC
            LIMIT ?
            """,
            params,
        )
        return cur.fetchall()


def assign_devices_to_delivery(device_ids, delivery_id: int):
    """Przypisanie urządzeń do dostawy"""
    if not device_ids:
        return
    did = int(delivery_id)
    ids = [int(x) for x in device_ids]
    with get_conn() as conn:
        cur = conn.cursor()
        ph = ",".join(["?"] * len(ids))
        cur.execute(f"UPDATE devices SET delivery_id=? WHERE id IN ({ph})", [did] + ids)
        conn.commit()


def clear_devices_delivery(device_ids):
    """Usunięcie powiązania urządzeń z dostawą"""
    if not device_ids:
        return
    ids = [int(x) for x in device_ids]
    with get_conn() as conn:
        cur = conn.cursor()
        ph = ",".join(["?"] * len(ids))
        cur.execute(f"UPDATE devices SET delivery_id=NULL WHERE id IN ({ph})", ids)
        conn.commit()


def list_devices_for_delivery(delivery_id: int, limit: int = 500):
    """Lista urządzeń dla dostawy"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, received_date, item_type, device_name, serial_number, imei1, imei2, 
                   production_code, created_at
            FROM devices
            WHERE delivery_id = ?
            ORDER BY received_date DESC, id DESC
            LIMIT ?
        """, (delivery_id, limit))
        return cur.fetchall()


def add_delivery_attachment(delivery_id: int, src_path: str):
    """Dodawanie załącznika do dostawy"""
    dest_path = copy_attachment_for_delivery(delivery_id, src_path)
    created_at = datetime.now().isoformat(timespec="seconds")
    file_name = os.path.basename(dest_path)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO delivery_attachments (delivery_id, file_path, file_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (delivery_id, dest_path, file_name, created_at))
        conn.commit()


def list_delivery_attachments(delivery_id: int):
    """Lista załączników dostawy"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, file_name, file_path, created_at
            FROM delivery_attachments
            WHERE delivery_id=?
            ORDER BY created_at DESC
        """, (delivery_id,))
        return cur.fetchall()


def get_first_delivery_image(delivery_id: int):
    """Pobiera pierwszy załącznik graficzny dla dostawy"""
    atts = list_delivery_attachments(delivery_id)
    for att_id, name, path, _ in atts:
        if os.path.exists(path):
            return path
    return None


def delete_delivery_attachment(att_id: int, delete_file: bool = True):
    """Usuwanie załącznika"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM delivery_attachments WHERE id=?", (att_id,))
        row = cur.fetchone()
        if row:
            file_path = row[0]
            cur.execute("DELETE FROM delivery_attachments WHERE id=?", (att_id,))
            conn.commit()
            
            if delete_file and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    
                    # Usuń folder jeśli jest pusty
                    folder = os.path.dirname(file_path)
                    if os.path.isdir(folder) and not os.listdir(folder):
                        os.rmdir(folder)
                except Exception:
                    pass
