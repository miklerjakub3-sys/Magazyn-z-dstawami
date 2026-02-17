#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moduł bazy danych - operacje na urządzeniach i dostawach
"""

import os
import sqlite3
import shutil
from datetime import datetime
from typing import Optional, List, Tuple
from .config import DB_PATH, DELIVERY_ATTACH_DIR, DELIVERY_TYPES
from .utils import one_line, validate_ymd, copy_attachment_for_delivery


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


def migrate_db():
    """Migracje bazy danych"""
    with get_conn() as conn:
        cur = conn.cursor()

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
                except Exception as e:
                    from .log import get_logger
                    get_logger("magazyn.db").exception(f"Nie można dodać kolumny {col}")

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
                except Exception as e:
                    from .log import get_logger
                    get_logger("magazyn.db").exception(f"Nie można dodać kolumny {col}")

        conn.commit()


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

    where = ["received_date = ?"]
    params = [delivery_date]

    if not include_linked_to_other:
        if delivery_id is None:
            where.append("delivery_id IS NULL")
        else:
            where.append("(delivery_id IS NULL OR delivery_id = ?)")
            params.append(int(delivery_id))

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
