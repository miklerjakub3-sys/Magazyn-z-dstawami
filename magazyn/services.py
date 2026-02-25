#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Warstwa usług (model) – cienka otoczka na funkcje z database.py.

Cel:
- jedna powierzchnia API dla UI (łatwiej testować i migrować)
- type hints
- centralne logowanie wyjątków
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List, Optional, Tuple, Sequence, Any

from . import database
from .backup import backup_manager
from .config import MAIN_ADMIN_LOGIN, RESET_CODE_TTL_MINUTES, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_TLS
from .log import get_logger

log = get_logger("magazyn.services")

# --- DTO / typy ---
DeviceRow = Tuple[int, str, str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], str, Optional[int]]
DeliveryRow = Tuple[int, str, Optional[str], Optional[str], str, Optional[str], int, Optional[str], str]


@dataclass(frozen=True)
class PagedResult:
    rows: List[Tuple[Any, ...]]
    total_count: int


class MagazynService:
    def __init__(self) -> None:
        self.current_user = None
        self._permission_cache = set()

    def init_db(self) -> None:
        database.init_db()

    # --- Auth / users ---
    def authenticate_user(self, login: str, password: str):
        return database.authenticate_user(login, password)

    def create_remember_token(self, user_id: int, days_valid: int = 30) -> str:
        return database.create_remember_token(user_id, days_valid=days_valid)

    def authenticate_token(self, token: str):
        return database.authenticate_token(token)

    def list_permissions(self):
        self._require("users.manage")
        return database.list_permissions()

    def list_roles(self):
        self._require("users.manage")
        return database.list_roles()

    def list_users(self):
        self._require("users.manage")
        return database.list_users()

    def role_permission_keys(self, role_id: int):
        self._require("users.manage")
        return database.role_permission_keys(role_id)

    def create_user(self, login: str, password: str, role_id: int) -> None:
        self._require("users.manage")
        database.create_user(login, password, role_id)


    def set_current_user(self, user) -> None:
        self.current_user = user
        if user and user.get("id"):
            self._permission_cache = set(database.get_user_permission_keys(int(user["id"])))
        else:
            self._permission_cache = set()

    def has_permission(self, key: str) -> bool:
        return str(key) in self._permission_cache

    def _require(self, key: str) -> None:
        if not self.has_permission(key):
            raise PermissionError(f"Brak uprawnienia: {key}")

    def get_user_permission_keys(self, user_id: int):
        self._require("users.manage")
        return database.get_user_permission_keys(user_id)

    def update_role_permissions(self, role_id: int, permission_keys):
        self._require("users.manage")
        database.update_role_permissions(role_id, list(permission_keys))

    def set_user_role(self, user_id: int, role_id: int) -> None:
        self._require("users.manage")
        database.set_user_role(user_id, role_id)


    def get_backup_interval_seconds(self) -> int:
        return int(getattr(backup_manager, "interval_seconds", 30 * 60))

    def set_backup_interval_seconds(self, seconds: int) -> None:
        self._require("backup.manage")
        backup_manager.set_interval_seconds(seconds)

    def create_backup(self, manual: bool = True):
        self._require("backup.manage")
        return backup_manager.create_backup(manual=manual)

    def list_backups(self):
        self._require("backup.manage")
        return backup_manager.list_backups()

    def restore_backup(self, backup_path: str, password: str = "") -> bool:
        self._require("backup.manage")
        return bool(backup_manager.restore_backup(backup_path, password=password))

    def get_devices_report_rows(self, date_from: str = "", date_to: str = "", item_type: str = "all"):
        self._require("reports.export")
        return database.get_devices_by_date_range(date_from, date_to, item_type)

    def get_deliveries_report_rows(self, date_from: str = "", date_to: str = "", delivery_type: str = ""):
        self._require("reports.export")
        return database.get_deliveries_by_date_range(date_from, date_to, delivery_type)


    def set_admin_recovery_email(self, email: str) -> None:
        self._require("users.manage")
        database.set_admin_recovery_email(MAIN_ADMIN_LOGIN, email)

    def get_admin_recovery_email(self) -> str:
        self._require("users.manage")
        return database.get_admin_recovery_email(MAIN_ADMIN_LOGIN)

    def send_admin_reset_code(self, email: str) -> None:
        code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        exp = (datetime.now() + timedelta(minutes=max(5, int(RESET_CODE_TTL_MINUTES)))).strftime("%Y-%m-%d %H:%M:%S")
        ok = database.set_password_reset_code(MAIN_ADMIN_LOGIN, email, code_hash, exp)
        if not ok:
            raise ValueError("Podany e-mail nie jest przypisany do konta administratora.")

        if not SMTP_HOST or not SMTP_FROM:
            raise RuntimeError("SMTP nie jest skonfigurowane. Uzupełnij zmienne MAGAZYN_SMTP_*.")

        msg = EmailMessage()
        msg["Subject"] = "Magazyn – kod odzyskiwania hasła administratora"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.set_content(
            "Kod odzyskiwania hasła administratora: "
            + code
            + "\nKod jest ważny przez "
            + str(max(5, int(RESET_CODE_TTL_MINUTES)))
            + " minut."
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

    def reset_admin_password_with_code(self, email: str, code: str, new_password: str) -> None:
        if len((new_password or "").strip()) < 8:
            raise ValueError("Nowe hasło musi mieć co najmniej 8 znaków.")
        code_hash = hashlib.sha256((code or "").strip().encode("utf-8")).hexdigest()
        packed = database._password_hash(new_password)
        ok = database.consume_password_reset_code(MAIN_ADMIN_LOGIN, email, code_hash, packed)
        if not ok:
            raise ValueError("Kod jest nieprawidłowy lub wygasł.")

    # --- Devices ---
    def search_devices(
        self,
        query: str = "",
        item_type: str = "all",
        date_from: str = "",
        date_to: str = "",
        order_by: str = "received_date",
        order_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> PagedResult:
        self._require("receipts.view")
        rows, total = database.search_devices(
            query,
            item_type,
            date_from,
            date_to,
            order_by,
            order_dir,
            limit,
            offset,
        )
        return PagedResult(list(rows), int(total))

    def add_device(
        self,
        received_date: str,
        item_type: str,
        device_name: str,
        serial_number: str,
        imei1: str,
        imei2: str,
        production_code: str,
        delivery_id: Optional[int] = None,
    ) -> int:
        self._require("receipts.edit")
        return int(database.add_device(
            received_date=received_date,
            item_type=item_type,
            device_name=device_name,
            serial_number=serial_number,
            imei1=imei1,
            imei2=imei2,
            production_code=production_code,
            delivery_id=delivery_id,
        ))

    def delete_device(self, device_id: int) -> None:
        self._require("receipts.edit")
        database.delete_device(device_id)

    def get_device(self, device_id: int):
        self._require("receipts.view")
        return database.get_device(device_id)

    def update_device(self, *args, **kwargs) -> None:
        self._require("receipts.edit")
        database.update_device(*args, **kwargs)

    def find_device_duplicates(self, serial_number: str, imei1: str, imei2: str, exclude_id: Optional[int] = None):
        return database.find_device_duplicates(serial_number, imei1, imei2, exclude_id=exclude_id)

    # --- Deliveries ---
    def search_deliveries(
        self,
        date_from: str = "",
        date_to: str = "",
        sender: str = "",
        courier: str = "",
        delivery_type: str = "",
        order_by: str = "delivery_date",
        order_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> PagedResult:
        self._require("deliveries.view")
        rows, total = database.search_deliveries(
            date_from,
            date_to,
            sender,
            courier,
            delivery_type,
            order_by,
            order_dir,
            limit,
            offset,
        )
        return PagedResult(list(rows), int(total))

    def add_delivery(self, *args, **kwargs) -> int:
        self._require("deliveries.edit")
        return int(database.add_delivery(*args, **kwargs))

    def update_delivery(self, *args, **kwargs) -> None:
        self._require("deliveries.edit")
        database.update_delivery(*args, **kwargs)

    def delete_delivery(self, delivery_id: int) -> None:
        self._require("deliveries.edit")
        database.delete_delivery(delivery_id)

    def get_delivery(self, delivery_id: int):
        self._require("deliveries.view")
        return database.get_delivery(delivery_id)

    def list_senders(self) -> List[str]:
        return database.list_senders()

    def list_couriers(self) -> List[str]:
        return database.list_couriers()

    def add_sender(self, name: str) -> None:
        database.add_sender(name)

    def add_courier(self, name: str) -> None:
        database.add_courier(name)

    def remove_sender(self, name: str) -> None:
        database.remove_sender(name)

    def remove_courier(self, name: str) -> None:
        database.remove_courier(name)

    def list_recent_deliveries(self, limit: int = 80):
        self._require("deliveries.view")
        return database.list_recent_deliveries(limit)

    def list_devices_for_delivery(self, delivery_id: int, limit: int = 500):
        self._require("deliveries.view")
        return database.list_devices_for_delivery(delivery_id, limit)

    def list_devices_for_delivery_date(self, delivery_date: str, include_linked_to_other: bool = False, delivery_id: Optional[int] = None):
        self._require("deliveries.view")
        return database.list_devices_for_delivery_date(delivery_date, include_linked_to_other, delivery_id)

    def assign_devices_to_delivery(self, device_ids, delivery_id: int) -> None:
        self._require("deliveries.edit")
        database.assign_devices_to_delivery(device_ids, delivery_id)

    def clear_devices_delivery(self, device_ids) -> None:
        self._require("deliveries.edit")
        database.clear_devices_delivery(device_ids)

    def add_delivery_attachment(self, delivery_id: int, src_path: str) -> None:
        self._require("deliveries.edit")
        database.add_delivery_attachment(delivery_id, src_path)

    def list_delivery_attachments(self, delivery_id: int):
        self._require("deliveries.view")
        return database.list_delivery_attachments(delivery_id)

    def delete_delivery_attachment(self, att_id: int, delete_file: bool = True) -> None:
        self._require("deliveries.edit")
        database.delete_delivery_attachment(att_id, delete_file=delete_file)

    def get_first_delivery_image(self, delivery_id: int):
        self._require("deliveries.view")
        return database.get_first_delivery_image(delivery_id)
