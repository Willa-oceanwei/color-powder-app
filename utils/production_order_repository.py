"""Turso-first production orders with recipe snapshots and Sheet outbox events."""

from __future__ import annotations

import json
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class ProductionOrderError(RuntimeError):
    pass


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


def _number(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _payload(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): "" if value is None else str(value).strip()
        for key, value in row.items()
        if not str(key).startswith("_")
    }


def merge_production_order_packages(
    existing: dict[str, Any], delta: dict[str, Any], *, note: str = ""
) -> dict[str, Any]:
    """Return one production-order payload containing old and added packages.

    Package slots are matched by numeric package weight instead of slot number.  This
    is intentionally independent of persistence so the caller can update the linked
    outsourcing order only after the complete merged payload has been validated.
    """
    merged = dict(existing)
    counts_by_weight: dict[float, float] = {}
    weight_order: list[float] = []

    for source in (existing, delta):
        for position in range(1, 5):
            weight = _number(source.get(f"包裝重量{position}"))
            count = _number(source.get(f"包裝份數{position}"))
            if weight <= 0 or count <= 0:
                continue
            if weight not in counts_by_weight:
                counts_by_weight[weight] = 0
                weight_order.append(weight)
            counts_by_weight[weight] += count

    if len(weight_order) > 4:
        raise ProductionOrderError("合併後超過 4 種包裝重量，無法完整保存生產單")

    def format_number(value: float) -> str:
        return str(int(value)) if value.is_integer() else str(value)

    for position in range(1, 5):
        merged[f"包裝重量{position}"] = ""
        merged[f"包裝份數{position}"] = ""
    for position, weight in enumerate(weight_order, start=1):
        merged[f"包裝重量{position}"] = format_number(weight)
        merged[f"包裝份數{position}"] = format_number(counts_by_weight[weight])

    if note.strip():
        merged["備註"] = "\n".join(
            part for part in (str(existing.get("備註") or "").strip(), note.strip()) if part
        )
    return merged


def _recipe_snapshot(conn, recipe_id: str) -> tuple[int | None, str | None]:
    if not recipe_id:
        return None, None
    recipe = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
    if recipe is None:
        raise ProductionOrderError(f"找不到配方編號 {recipe_id}")
    components = _mappings(conn.execute(
        """SELECT position, colorpowder_id, weight FROM recipe_components
           WHERE recipe_id=? ORDER BY position""",
        (recipe_id,),
    ))
    snapshot = dict(recipe)
    snapshot["components"] = components
    return int(recipe["version"]), json.dumps(snapshot, ensure_ascii=False, default=str)


def list_production_orders(
    config: DatabaseConfig, *, include_cancelled: bool = False,
) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        where = "" if include_cancelled else "WHERE cancelled_at IS NULL"
        rows = _mappings(conn.execute(
            f"""SELECT payload_json, cancelled_at, cancel_reason
                FROM production_orders {where}
                ORDER BY production_date, production_order_id"""
        ))
    result = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update({
            "取消狀態": "已取消" if row.get("cancelled_at") else "有效",
            "取消時間": str(row.get("cancelled_at") or ""),
            "取消原因": str(row.get("cancel_reason") or ""),
        })
        result.append(payload)
    return result


def _save(config: DatabaseConfig, row: dict[str, Any], *, create: bool) -> dict[str, str]:
    payload = _payload(row)
    order_id = payload.get("生產單號", "")
    if not order_id:
        raise ProductionOrderError("缺少生產單號")
    recipe_id = payload.get("配方編號", "")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM production_orders WHERE production_order_id=?", (order_id,)
        ))
        if create and existing is not None:
            raise ProductionOrderError(f"生產單號 {order_id} 已存在")
        if not create and existing is None:
            raise ProductionOrderError(f"找不到生產單號 {order_id}")
        if existing is not None and existing.get("cancelled_at"):
            raise ProductionOrderError("已取消的生產單不可修改；請先恢復生產單")
        recipe_version, snapshot_json = _recipe_snapshot(conn, recipe_id)
        version = 1 if existing is None else int(existing["version"]) + 1
        created_at = now if existing is None else existing["created_at"]
        conn.execute(
            """INSERT INTO production_orders(
                   production_order_id, production_date, recipe_id, color, customer_name,
                   status, payload_json, recipe_version, recipe_snapshot_json, source,
                   version, created_at, updated_at, last_synced_at)
               VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, 'app', ?, ?, ?, NULL)
               ON CONFLICT(production_order_id) DO UPDATE SET
                   production_date=excluded.production_date, recipe_id=excluded.recipe_id,
                   color=excluded.color, customer_name=excluded.customer_name,
                   payload_json=excluded.payload_json, recipe_version=excluded.recipe_version,
                   recipe_snapshot_json=excluded.recipe_snapshot_json, source='app',
                   version=excluded.version, updated_at=excluded.updated_at""",
            (
                order_id, payload.get("生產日期", ""), recipe_id or None,
                payload.get("顏色", ""), payload.get("客戶名稱", ""),
                json.dumps(payload, ensure_ascii=False), recipe_version, snapshot_json,
                version, created_at, now,
            ),
        )
        conn.execute("DELETE FROM production_order_packages WHERE production_order_id=?", (order_id,))
        for position in range(1, 5):
            weight = _number(payload.get(f"包裝重量{position}"))
            count = _number(payload.get(f"包裝份數{position}"))
            if not weight and not count:
                continue
            conn.execute(
                """INSERT INTO production_order_packages(
                       production_order_id, position, package_weight, package_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, position, weight, count, now, now),
            )
        enqueue_sheet_sync(
            conn, sheet_name="生產單", row_key=order_id,
            operation="insert" if create else "update", payload=payload, entity_version=version,
        )
    return payload


def create_production_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save(config, row, create=True)


def update_production_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save(config, row, create=False)


def upsert_production_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    order_id = str(row.get("生產單號") or "").strip()
    with connect_from_config(config) as conn:
        exists = _mapping(conn.execute(
            "SELECT production_order_id FROM production_orders WHERE production_order_id=?", (order_id,)
        )) is not None
    return _save(config, row, create=not exists)


def set_production_order_cancelled(
    config: DatabaseConfig,
    order_id: str,
    *,
    cancelled: bool,
    reason: str = "",
) -> dict[str, str]:
    """Cancel or restore an order without deleting its payload or recipe snapshot."""
    order_id = str(order_id or "").strip()
    reason = str(reason or "").strip()
    if not order_id:
        raise ProductionOrderError("缺少生產單號")
    if cancelled and not reason:
        raise ProductionOrderError("請輸入取消原因")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM production_orders WHERE production_order_id=?", (order_id,)
        ))
        if existing is None:
            raise ProductionOrderError(f"找不到生產單號 {order_id}")
        if cancelled and existing.get("cancelled_at"):
            raise ProductionOrderError("此生產單已取消")
        if not cancelled and not existing.get("cancelled_at"):
            raise ProductionOrderError("此生產單目前未取消")

        payload = json.loads(existing["payload_json"])
        payload.update({
            "取消狀態": "已取消" if cancelled else "有效",
            "取消時間": now if cancelled else "",
            "取消原因": reason if cancelled else "",
        })
        version = int(existing["version"]) + 1
        conn.execute(
            """UPDATE production_orders
               SET status=?, cancelled_at=?, cancel_reason=?, payload_json=?,
                   source='app', version=?, updated_at=?
               WHERE production_order_id=?""",
            (
                "cancelled" if cancelled else "draft", now if cancelled else None,
                reason if cancelled else None, json.dumps(payload, ensure_ascii=False),
                version, now, order_id,
            ),
        )
        enqueue_sheet_sync(
            conn, sheet_name="生產單", row_key=order_id,
            operation="delete" if cancelled else "update",
            payload=None if cancelled else payload, entity_version=version,
        )
        return payload
