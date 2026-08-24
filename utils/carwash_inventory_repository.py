"""Turso-first wash-facility inventory movement ledger."""

from __future__ import annotations

import uuid
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class CarwashInventoryError(RuntimeError):
    """Raised when a wash-facility inventory write is invalid or unsafe."""


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


def carwash_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "類型": str(entity.get("movement_type") or ""),
        "初始庫存日期": str(entity.get("initial_date") or ""),
        "初始數量": str(entity.get("initial_quantity") if entity.get("initial_quantity") is not None else ""),
        "貨品編號": str(entity.get("product_id") or ""),
        "入庫日期": str(entity.get("inbound_date") or ""),
        "出庫日期": str(entity.get("outbound_date") or ""),
        "數量": str(entity.get("quantity") if entity.get("quantity") is not None else ""),
        "單位": str(entity.get("unit") or ""),
        "登記人": str(entity.get("registrar") or ""),
        "備註": str(entity.get("notes") or ""),
        "_sync_id": str(entity.get("movement_id") or ""),
    }


def list_carwash_inventory_movements(config: DatabaseConfig, *, include_inactive: bool = False):
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(
            f"SELECT * FROM carwash_inventory_movements {where} ORDER BY created_at,movement_id"
        ))


def save_carwash_inventory_movement(
    config: DatabaseConfig, row: dict[str, Any], *, create: bool
):
    movement_id = str(row.get("_sync_id") or "").strip() or f"carwash-{uuid.uuid4().hex}"
    movement_type = str(row.get("類型") or "").strip()
    product_id = str(row.get("貨品編號") or "").strip()
    unit = str(row.get("單位") or "").strip()
    if movement_type not in {"初始庫存", "入庫", "出庫"}:
        raise CarwashInventoryError("類型必須是初始庫存、入庫或出庫")
    if not product_id or not unit:
        raise CarwashInventoryError("貨品編號與單位為必填")
    quantity_key = "初始數量" if movement_type == "初始庫存" else "數量"
    try:
        amount = float(row.get(quantity_key, 0))
    except (TypeError, ValueError) as exc:
        raise CarwashInventoryError("數量必須是數字") from exc
    if amount < 0 or (movement_type != "初始庫存" and amount == 0):
        raise CarwashInventoryError("初始數量不可小於 0，入出庫數量必須大於 0")
    initial_date = str(row.get("初始庫存日期") or "").strip()
    inbound_date = str(row.get("入庫日期") or "").strip()
    outbound_date = str(row.get("出庫日期") or "").strip()
    required_date = {"初始庫存": initial_date, "入庫": inbound_date, "出庫": outbound_date}[movement_type]
    if not required_date:
        raise CarwashInventoryError("請填寫對應的庫存日期")

    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute(
            "SELECT * FROM carwash_inventory_movements WHERE movement_id=?", (movement_id,)
        ))
        if create and old:
            raise CarwashInventoryError("此洗車廠庫存永久 ID 已存在")
        if not create and not old:
            raise CarwashInventoryError("找不到要修改的洗車廠庫存記錄")
        if old and old["lifecycle_status"] != "active":
            raise CarwashInventoryError("已封存記錄不可修改")
        version = 1 if old is None else int(old["version"]) + 1
        created_at = now if old is None else old["created_at"]
        conn.execute(
            """INSERT INTO carwash_inventory_movements(
                   movement_id,movement_type,initial_date,initial_quantity,product_id,
                   inbound_date,outbound_date,quantity,unit,registrar,notes,
                   source,version,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'app',?,?,?)
               ON CONFLICT(movement_id) DO UPDATE SET
                   movement_type=excluded.movement_type,initial_date=excluded.initial_date,
                   initial_quantity=excluded.initial_quantity,product_id=excluded.product_id,
                   inbound_date=excluded.inbound_date,outbound_date=excluded.outbound_date,
                   quantity=excluded.quantity,unit=excluded.unit,registrar=excluded.registrar,
                   notes=excluded.notes,source='app',version=excluded.version,updated_at=excluded.updated_at""",
            (movement_id, movement_type, initial_date or None,
             amount if movement_type == "初始庫存" else None, product_id,
             inbound_date or None, outbound_date or None,
             amount if movement_type != "初始庫存" else None, unit,
             str(row.get("登記人") or "").strip(), str(row.get("備註") or "").strip(),
             version, created_at, now),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM carwash_inventory_movements WHERE movement_id=?", (movement_id,)
        ))
        enqueue_sheet_sync(
            conn, sheet_name="洗車廠庫存", row_key=movement_id,
            operation="insert" if create else "update",
            payload=carwash_sheet_payload(entity), entity_version=version,
        )
        return entity


def archive_carwash_inventory_movement(
    config: DatabaseConfig, movement_id: str, *, reason: str = "使用者封存"
):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute(
            "SELECT * FROM carwash_inventory_movements WHERE movement_id=?", (str(movement_id).strip(),)
        ))
        if not old or old["lifecycle_status"] != "active":
            raise CarwashInventoryError("找不到有效的洗車廠庫存記錄")
        version = int(old["version"]) + 1
        conn.execute(
            """UPDATE carwash_inventory_movements SET lifecycle_status='inactive',deleted_at=?,
               delete_reason=?,version=?,updated_at=? WHERE movement_id=?""",
            (now, str(reason).strip(), version, now, old["movement_id"]),
        )
        enqueue_sheet_sync(
            conn, sheet_name="洗車廠庫存", row_key=old["movement_id"], operation="delete",
            payload=None, entity_version=version,
        )
