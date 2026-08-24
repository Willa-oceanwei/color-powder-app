"""Turso-first customer master data with aliases and Sheet outbox events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class CustomerError(RuntimeError):
    pass


class CustomerAlreadyExists(CustomerError):
    pass


class CustomerNotFound(CustomerError):
    pass


@dataclass(frozen=True)
class CustomerInput:
    customer_id: str
    name: str
    notes: str = ""

    def normalized(self) -> "CustomerInput":
        return CustomerInput(str(self.customer_id or "").strip(), str(self.name or "").strip(),
                             str(self.notes or "").strip())


def _mapping(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip((column[0] for column in cursor.description), row))


def _mappings(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def customer_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "客戶編號": str(entity.get("customer_id") or ""),
        "客戶簡稱": str(entity.get("name") or ""),
        "備註": str(entity.get("notes") or ""),
        "生命週期": str(entity.get("lifecycle_status") or "active"),
        "停用時間": str(entity.get("deleted_at") or ""),
        "停用原因": str(entity.get("delete_reason") or ""),
    }


def list_customers(config: DatabaseConfig, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(
            f"""SELECT customer_id, name, notes, lifecycle_status, deleted_at, delete_reason,
                       version, updated_at, last_synced_at FROM customers {where} ORDER BY customer_id"""
        ))


def _validate(data: CustomerInput) -> CustomerInput:
    data = data.normalized()
    if not data.customer_id:
        raise CustomerError("請輸入客戶編號")
    if not data.name:
        raise CustomerError("請輸入客戶簡稱")
    return data


def _ensure_alias(conn, name: str, customer_id: str) -> None:
    owner = _mapping(conn.execute("SELECT customer_id FROM customer_aliases WHERE alias=?", (name,)))
    if owner and owner["customer_id"] != customer_id:
        raise CustomerError(f"客戶簡稱／別名 {name} 已由 {owner['customer_id']} 使用")


def create_customer(config: DatabaseConfig, data: CustomerInput) -> dict[str, Any]:
    data, now = _validate(data), utc_now_iso()
    with connect_from_config(config) as conn:
        if _mapping(conn.execute("SELECT 1 FROM customers WHERE customer_id=?", (data.customer_id,))):
            raise CustomerAlreadyExists(f"客戶編號 {data.customer_id} 已存在")
        _ensure_alias(conn, data.name, data.customer_id)
        conn.execute("""INSERT INTO customers(customer_id,name,notes,source,version,created_at,updated_at)
                        VALUES (?,?,?,'app',1,?,?)""", (data.customer_id, data.name, data.notes, now, now))
        conn.execute("INSERT INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                     (data.name, data.customer_id, now))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (data.customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=data.customer_id, operation="insert",
                           payload=customer_sheet_payload(entity), entity_version=1)
        return entity


def update_customer(config: DatabaseConfig, data: CustomerInput) -> dict[str, Any]:
    data, now = _validate(data), utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (data.customer_id,)))
        if not existing:
            raise CustomerNotFound(f"找不到客戶編號 {data.customer_id}")
        if existing["lifecycle_status"] != "active":
            raise CustomerError("已停用客戶不可修改")
        _ensure_alias(conn, data.name, data.customer_id)
        version = int(existing["version"]) + 1
        conn.execute("UPDATE customers SET name=?,notes=?,source='app',version=?,updated_at=? WHERE customer_id=?",
                     (data.name, data.notes, version, now, data.customer_id))
        conn.execute("INSERT OR IGNORE INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                     (data.name, data.customer_id, now))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (data.customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=data.customer_id, operation="update",
                           payload=customer_sheet_payload(entity), entity_version=version)
        return entity


def set_customer_active(config: DatabaseConfig, customer_id: str, *, active: bool, reason: str = "") -> dict[str, Any]:
    customer_id, now = str(customer_id or "").strip(), utc_now_iso()
    if not active and not str(reason or "").strip():
        raise CustomerError("請輸入停用原因")
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,)))
        if not existing:
            raise CustomerNotFound(f"找不到客戶編號 {customer_id}")
        conn.execute("""UPDATE customers SET lifecycle_status=?,deleted_at=?,delete_reason=?,
                        version=version+1,updated_at=? WHERE customer_id=?""",
                     ("active" if active else "inactive", None if active else now,
                      None if active else str(reason).strip(), now, customer_id))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=customer_id,
                           operation="update" if active else "delete",
                           payload=customer_sheet_payload(entity) if active else None,
                           entity_version=int(entity["version"]))
        return entity
