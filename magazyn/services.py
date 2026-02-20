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
from typing import List, Optional, Tuple, Sequence, Any

from . import database
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
        return database.list_permissions()

    def list_roles(self):
        return database.list_roles()

    def list_users(self):
        return database.list_users()

    def role_permission_keys(self, role_id: int):
        return database.role_permission_keys(role_id)

    def create_user(self, login: str, password: str, role_id: int) -> None:
        database.create_user(login, password, role_id)


    def set_current_user(self, user) -> None:
        self.current_user = user
        if user and user.get("id"):
            self._permission_cache = set(database.get_user_permission_keys(int(user["id"])))
        else:
            self._permission_cache = set()

    def has_permission(self, key: str) -> bool:
        return str(key) in self._permission_cache

    def get_user_permission_keys(self, user_id: int):
        return database.get_user_permission_keys(user_id)

    def update_role_permissions(self, role_id: int, permission_keys):
        database.update_role_permissions(role_id, list(permission_keys))

    def set_user_role(self, user_id: int, role_id: int) -> None:
        database.set_user_role(user_id, role_id)

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
        database.delete_device(device_id)

    def get_device(self, device_id: int):
        return database.get_device(device_id)

    def update_device(self, *args, **kwargs) -> None:
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
        return int(database.add_delivery(*args, **kwargs))

    def update_delivery(self, *args, **kwargs) -> None:
        database.update_delivery(*args, **kwargs)

    def delete_delivery(self, delivery_id: int) -> None:
        database.delete_delivery(delivery_id)

    def get_delivery(self, delivery_id: int):
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
        return database.list_recent_deliveries(limit)

    def list_devices_for_delivery(self, delivery_id: int, limit: int = 500):
        return database.list_devices_for_delivery(delivery_id, limit)

    def list_devices_for_delivery_date(self, delivery_date: str, include_linked_to_other: bool = False, delivery_id: Optional[int] = None):
        return database.list_devices_for_delivery_date(delivery_date, include_linked_to_other, delivery_id)

    def assign_devices_to_delivery(self, device_ids, delivery_id: int) -> None:
        database.assign_devices_to_delivery(device_ids, delivery_id)

    def clear_devices_delivery(self, device_ids) -> None:
        database.clear_devices_delivery(device_ids)

    def add_delivery_attachment(self, delivery_id: int, src_path: str) -> None:
        database.add_delivery_attachment(delivery_id, src_path)

    def list_delivery_attachments(self, delivery_id: int):
        return database.list_delivery_attachments(delivery_id)

    def delete_delivery_attachment(self, att_id: int, delete_file: bool = True) -> None:
        database.delete_delivery_attachment(att_id, delete_file=delete_file)

    def get_first_delivery_image(self, delivery_id: int):
        return database.get_first_delivery_image(delivery_id)
