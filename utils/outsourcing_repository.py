"""Turso-first outsourcing orders, delivery/return ledgers, and Sheet outbox."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class OutsourcingError(RuntimeError):
    """Raised when an outsourcing command violates a business invariant."""


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


def _number(value: Any, default: float = 0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _payload(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): "" if value is None else str(value).strip()
        for key, value in row.items() if not str(key).startswith("_")
    }


def list_outsourcing_orders(
    config: DatabaseConfig, *, include_inactive: bool = False
) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        rows = _mappings(conn.execute(
            f"SELECT payload_json, lifecycle_status, deleted_at, delete_reason "
            f"FROM outsourcing_orders {where} ORDER BY created_at, outsourcing_order_id"
        ))
    result = []
    for row in rows:
        item = json.loads(row["payload_json"])
        item.update({
            "生命週期": row["lifecycle_status"],
            "停用時間": str(row.get("deleted_at") or ""),
            "停用原因": str(row.get("delete_reason") or ""),
        })
        result.append(item)
    return result


def list_outsourcing_events(config: DatabaseConfig, kind: str) -> list[dict[str, str]]:
    table = {"delivery": "outsourcing_deliveries", "return": "outsourcing_returns"}.get(kind)
    if table is None:
        raise ValueError("kind must be 'delivery' or 'return'")
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(f"SELECT payload_json FROM {table} ORDER BY created_at"))
    return [json.loads(row["payload_json"]) for row in rows]


def _save_order(config: DatabaseConfig, row: dict[str, Any], *, create: bool) -> dict[str, str]:
    payload = _payload(row)
    order_id = payload.get("代工單號", "")
    if not order_id:
        raise OutsourcingError("缺少代工單號")
    quantity = _number(payload.get("代工數量"))
    target = _number(payload.get("目標載回數量"), quantity)
    multiplier = _number(payload.get("轉換倍率"), 1) or 1
    if quantity <= 0 or target <= 0:
        raise OutsourcingError("代工數量與目標載回數量必須大於 0")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)
        ))
        if create and existing:
            raise OutsourcingError(f"代工單號 {order_id} 已存在")
        if not create and not existing:
            raise OutsourcingError(f"找不到代工單號 {order_id}")
        if existing and existing["lifecycle_status"] != "active":
            raise OutsourcingError("已停用的代工單不可修改")
        version = 1 if not existing else int(existing["version"]) + 1
        created_at = now if not existing else existing["created_at"]
        payload.setdefault("建立時間", str(created_at))
        conn.execute(
            """INSERT INTO outsourcing_orders(
                   outsourcing_order_id, production_order_id, recipe_id, customer_name,
                   quantity, target_return_quantity, conversion_multiplier, vendor_name,
                   notes, status, delivered, delivery_notes, payload_json, source, version,
                   created_at, updated_at, last_synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'app', ?, ?, ?, NULL)
               ON CONFLICT(outsourcing_order_id) DO UPDATE SET
                   production_order_id=excluded.production_order_id, recipe_id=excluded.recipe_id,
                   customer_name=excluded.customer_name, quantity=excluded.quantity,
                   target_return_quantity=excluded.target_return_quantity,
                   conversion_multiplier=excluded.conversion_multiplier,
                   vendor_name=excluded.vendor_name, notes=excluded.notes, status=excluded.status,
                   delivered=excluded.delivered, delivery_notes=excluded.delivery_notes,
                   payload_json=excluded.payload_json, source='app', version=excluded.version,
                   updated_at=excluded.updated_at""",
            (order_id, payload.get("生產單號") or None, payload.get("配方編號") or None,
             payload.get("客戶名稱", ""), quantity, target, multiplier,
             payload.get("代工廠商", ""), payload.get("備註", ""),
             payload.get("狀態", "🏭 在廠內"), 1 if payload.get("已交貨") else 0,
             payload.get("交貨備註", ""), json.dumps(payload, ensure_ascii=False), version,
             created_at, now),
        )
        enqueue_sheet_sync(conn, sheet_name="代工管理", row_key=order_id,
                           operation="insert" if create else "update", payload=payload,
                           entity_version=version)
    return payload


def create_outsourcing_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save_order(config, row, create=True)


def update_outsourcing_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save_order(config, row, create=False)


def upsert_outsourcing_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    order_id = str(row.get("代工單號") or "").strip()
    with connect_from_config(config) as conn:
        exists = conn.execute("SELECT 1 FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)).fetchone()
    return _save_order(config, row, create=not bool(exists))


def _queue_outsourcing_event_tombstones(conn, order_id: str, *, restore: bool) -> dict[str, int]:
    counts = {"deliveries": 0, "returns": 0}
    for table, id_column, sheet_name, count_key in (
        ("outsourcing_deliveries", "delivery_id", "代工送達記錄", "deliveries"),
        ("outsourcing_returns", "return_id", "代工載回記錄", "returns"),
    ):
        events = _mappings(conn.execute(
            f"SELECT {id_column}, payload_json, version FROM {table} WHERE outsourcing_order_id=?",
            (order_id,),
        ))
        for event in events:
            version = int(event["version"]) + 1
            conn.execute(
                f"UPDATE {table} SET version=?, updated_at=? WHERE {id_column}=?",
                (version, utc_now_iso(), event[id_column]),
            )
            enqueue_sheet_sync(
                conn, sheet_name=sheet_name, row_key=event[id_column],
                operation="insert" if restore else "delete",
                payload=json.loads(event["payload_json"]) if restore else None,
                entity_version=version,
            )
            counts[count_key] += 1
    return counts


def archive_outsourcing_order(
    config: DatabaseConfig, order_id: str, *, reason: str
) -> dict[str, int]:
    """Archive an order and tombstone all Sheet copies while retaining Turso history."""
    order_id, reason = str(order_id).strip(), str(reason).strip()
    if not reason:
        raise OutsourcingError("請輸入停用原因")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        row = _mapping(conn.execute("SELECT * FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)))
        if not row or row["lifecycle_status"] != "active":
            raise OutsourcingError("找不到有效代工單")
        version = int(row["version"]) + 1
        conn.execute("UPDATE outsourcing_orders SET lifecycle_status='inactive', deleted_at=?, delete_reason=?, version=?, updated_at=? WHERE outsourcing_order_id=?",
                     (now, reason, version, now, order_id))
        enqueue_sheet_sync(conn, sheet_name="代工管理", row_key=order_id,
                           operation="delete", payload=None, entity_version=version)
        counts = _queue_outsourcing_event_tombstones(conn, order_id, restore=False)
    return counts


def deactivate_outsourcing_order(config: DatabaseConfig, order_id: str, *, reason: str) -> None:
    """Backward-compatible alias for lifecycle archival."""
    archive_outsourcing_order(config, order_id, reason=reason)


def restore_outsourcing_order(config: DatabaseConfig, order_id: str) -> dict[str, int]:
    """Restore an archived order and requeue its original Sheet copies atomically."""
    order_id = str(order_id or "").strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        row = _mapping(conn.execute(
            "SELECT * FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)
        ))
        if not row or row["lifecycle_status"] != "inactive":
            raise OutsourcingError("找不到已封存代工單")
        version = int(row["version"]) + 1
        conn.execute(
            """UPDATE outsourcing_orders
               SET lifecycle_status='active', deleted_at=NULL, delete_reason=NULL,
                   version=?, updated_at=? WHERE outsourcing_order_id=?""",
            (version, now, order_id),
        )
        enqueue_sheet_sync(
            conn, sheet_name="代工管理", row_key=order_id, operation="insert",
            payload=json.loads(row["payload_json"]), entity_version=version,
        )
        counts = _queue_outsourcing_event_tombstones(conn, order_id, restore=True)
    return counts


def _add_event(config: DatabaseConfig, order_id: str, date: str, quantity: float, *, kind: str) -> dict[str, str]:
    table, sheet_name, date_key, quantity_key, prefix = {
        "delivery": ("outsourcing_deliveries", "代工送達記錄", "送達日期", "送達數量", "delivery"),
        "return": ("outsourcing_returns", "代工載回記錄", "載回日期", "載回數量", "return"),
    }[kind]
    date_column = "delivery_date" if kind == "delivery" else "return_date"
    quantity = _number(quantity)
    if quantity < 0 or (kind == "delivery" and quantity <= 0):
        raise OutsourcingError("數量必須大於 0")
    event_id, now = f"{prefix}:{uuid4()}", utc_now_iso()
    payload = {"_sync_id": event_id, "代工單號": str(order_id), date_key: str(date), quantity_key: str(quantity), "建立時間": now}
    id_column = "delivery_id" if kind == "delivery" else "return_id"
    with connect_from_config(config) as conn:
        order = _mapping(conn.execute("SELECT lifecycle_status FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)))
        if not order or order["lifecycle_status"] != "active":
            raise OutsourcingError("找不到有效代工單")
        conn.execute(f"INSERT INTO {table}({id_column}, outsourcing_order_id, {date_column}, quantity, payload_json, source, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'app', 1, ?, ?)",
                     (event_id, order_id, str(date), quantity, json.dumps(payload, ensure_ascii=False), now, now))
        enqueue_sheet_sync(conn, sheet_name=sheet_name, row_key=event_id, operation="insert", payload=payload, entity_version=1)
    return payload


def add_outsourcing_delivery(config: DatabaseConfig, order_id: str, date: str, quantity: float) -> dict[str, str]:
    return _add_event(config, order_id, date, quantity, kind="delivery")


def add_outsourcing_return(config: DatabaseConfig, order_id: str, date: str, quantity: float) -> dict[str, str]:
    return _add_event(config, order_id, date, quantity, kind="return")


def correct_outsourcing_return(
    config: DatabaseConfig,
    return_id: str,
    date: str,
    quantity: float,
    *,
    reason: str,
) -> dict[str, str]:
    """Correct a return ledger entry while retaining its permanent sync ID and versions."""
    return_id, reason = str(return_id or "").strip(), str(reason or "").strip()
    quantity = _number(quantity)
    if not return_id:
        raise OutsourcingError("請選擇要更正的載回紀錄")
    if not reason:
        raise OutsourcingError("請輸入更正原因")
    if quantity < 0:
        raise OutsourcingError("載回數量不可小於 0")

    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM outsourcing_returns WHERE return_id=?", (return_id,)
        ))
        if not existing:
            raise OutsourcingError("找不到載回紀錄")
        order = _mapping(conn.execute(
            "SELECT lifecycle_status FROM outsourcing_orders WHERE outsourcing_order_id=?",
            (existing["outsourcing_order_id"],),
        ))
        if not order or order["lifecycle_status"] != "active":
            raise OutsourcingError("已封存代工單的載回紀錄不可更正")

        version = int(existing["version"]) + 1
        payload = json.loads(existing["payload_json"])
        payload.update({
            "_sync_id": return_id,
            "載回日期": str(date),
            "載回數量": str(quantity),
            "更正原因": reason,
            "更正時間": now,
        })
        conn.execute(
            """UPDATE outsourcing_returns
               SET return_date=?, quantity=?, payload_json=?, source='app',
                   version=?, updated_at=? WHERE return_id=?""",
            (str(date), quantity, json.dumps(payload, ensure_ascii=False), version, now, return_id),
        )
        enqueue_sheet_sync(
            conn, sheet_name="代工載回記錄", row_key=return_id,
            operation="update", payload=payload, entity_version=version,
        )
    return payload
