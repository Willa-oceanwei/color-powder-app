"""Turso-first individual customer inventory records."""

from __future__ import annotations

import uuid
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class CustomerInventoryError(RuntimeError):
    """Raised when an individual customer inventory operation is unsafe."""


def _mapping(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip((column[0] for column in cursor.description), row))


def _mappings(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def customer_inventory_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "_sync_id": str(entity.get("record_id") or ""),
        "客戶名稱": str(entity.get("customer_name") or ""),
        "配方編號": str(entity.get("recipe_id") or ""),
        "顏色": str(entity.get("color") or ""),
        "數量": str(entity.get("quantity") if entity.get("quantity") is not None else ""),
        "單位": str(entity.get("unit") or ""),
        "備註": str(entity.get("notes") or ""),
        "建立時間": str(entity.get("sheet_created_at") or ""),
        "更新時間": str(entity.get("sheet_updated_at") or ""),
    }


def list_customer_inventory_records(config: DatabaseConfig, *, include_inactive: bool = False):
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(
            f"SELECT * FROM customer_inventory_records {where} ORDER BY updated_at, record_id"
        ))


def save_customer_inventory_record(
    config: DatabaseConfig, row: dict[str, Any], *, create: bool
):
    record_id = str(row.get("_sync_id") or "").strip() or f"customer-stock-{uuid.uuid4().hex}"
    customer_name = str(row.get("客戶名稱") or "").strip()
    recipe_id = str(row.get("配方編號") or "").strip()
    color = str(row.get("顏色") or "").strip()
    unit = str(row.get("單位") or "").strip()
    if not customer_name or not recipe_id or not color or not unit:
        raise CustomerInventoryError("客戶名稱、配方編號、顏色與單位皆為必填")
    try:
        quantity = float(row.get("數量", 0))
    except (TypeError, ValueError) as exc:
        raise CustomerInventoryError("數量必須是數字") from exc
    if quantity < 0:
        raise CustomerInventoryError("數量不可小於 0")

    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute(
            "SELECT * FROM customer_inventory_records WHERE record_id=?", (record_id,)
        ))
        if create and old:
            raise CustomerInventoryError("此庫存永久 ID 已存在")
        if not create and not old:
            raise CustomerInventoryError("找不到要修改的客戶庫存")
        if old and old["lifecycle_status"] != "active":
            raise CustomerInventoryError("已封存的客戶庫存不可修改")
        version = 1 if old is None else int(old["version"]) + 1
        created_at = now if old is None else old["created_at"]
        sheet_created_at = str(row.get("建立時間") or "").strip() or (
            old["sheet_created_at"] if old else now
        )
        sheet_updated_at = str(row.get("更新時間") or "").strip() or now
        conn.execute(
            """INSERT INTO customer_inventory_records(
                   record_id,customer_name,recipe_id,color,quantity,unit,notes,
                   sheet_created_at,sheet_updated_at,source,version,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,'app',?,?,?)
               ON CONFLICT(record_id) DO UPDATE SET
                   customer_name=excluded.customer_name, recipe_id=excluded.recipe_id,
                   color=excluded.color, quantity=excluded.quantity, unit=excluded.unit,
                   notes=excluded.notes, sheet_updated_at=excluded.sheet_updated_at,
                   source='app', version=excluded.version, updated_at=excluded.updated_at""",
            (record_id, customer_name, recipe_id, color, quantity, unit,
             str(row.get("備註") or "").strip(), sheet_created_at, sheet_updated_at,
             version, created_at, now),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM customer_inventory_records WHERE record_id=?", (record_id,)
        ))
        enqueue_sheet_sync(
            conn, sheet_name="個別客戶庫存", row_key=record_id,
            operation="insert" if create else "update",
            payload=customer_inventory_sheet_payload(entity), entity_version=version,
        )
        return entity


def archive_customer_inventory_record(
    config: DatabaseConfig, record_id: str, *, reason: str = "使用者刪除"
):
    record_id = str(record_id).strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute(
            "SELECT * FROM customer_inventory_records WHERE record_id=?", (record_id,)
        ))
        if not old or old["lifecycle_status"] != "active":
            raise CustomerInventoryError("找不到有效的客戶庫存")
        version = int(old["version"]) + 1
        conn.execute(
            """UPDATE customer_inventory_records
               SET lifecycle_status='inactive',deleted_at=?,delete_reason=?,version=?,updated_at=?
               WHERE record_id=?""",
            (now, str(reason).strip(), version, now, record_id),
        )
        enqueue_sheet_sync(
            conn, sheet_name="個別客戶庫存", row_key=record_id,
            operation="delete", payload=None, entity_version=version,
        )
