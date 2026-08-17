"""Turso-first inventory movement persistence keyed by permanent Sheet sync IDs."""

from __future__ import annotations

import uuid
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class InventoryError(RuntimeError):
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


def inventory_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "類型": str(entity.get("movement_type") or ""),
        "色粉編號": str(entity.get("colorpowder_id") or ""),
        "日期": str(entity.get("movement_date") or ""),
        "數量": str(entity.get("quantity") if entity.get("quantity") is not None else ""),
        "單位": str(entity.get("unit") or ""),
        "備註": str(entity.get("notes") or ""),
        "廠商編號": str(entity.get("supplier_id") or ""),
        "廠商名稱": str(entity.get("supplier_name") or ""),
        "_sync_id": str(entity.get("sheet_row_key") or ""),
    }


def list_inventory_movements(config: DatabaseConfig) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        entities = _mappings(conn.execute(
            """SELECT movement.*,
                      reversal.sheet_row_key AS reversal_sync_id
               FROM inventory_movements AS movement
               LEFT JOIN inventory_movements AS reversal
                 ON reversal.reversal_of_movement_key = movement.movement_key
               WHERE movement.sheet_name='庫存記錄'
               ORDER BY movement.movement_date, movement.movement_id"""
        ))
    result = []
    for entity in entities:
        row = inventory_sheet_payload(entity)
        row.update({
            "沖銷原始ID": str(entity.get("reversal_of_movement_key") or ""),
            "沖銷記錄ID": str(entity.get("reversal_sync_id") or ""),
            "沖銷時間": str(entity.get("reversed_at") or ""),
            "沖銷狀態": "沖銷記錄" if entity.get("reversal_of_movement_key") else (
                "已沖銷" if entity.get("reversed_at") else "有效"
            ),
        })
        result.append(row)
    return result


def _validate_refs(conn, powder_id: str, supplier_id: str) -> None:
    if not powder_id:
        raise InventoryError("請輸入色粉編號")
    if _mapping(conn.execute("SELECT colorpowder_id FROM color_powders WHERE colorpowder_id=?", (powder_id,))) is None:
        raise InventoryError(f"找不到色粉編號 {powder_id}")
    if supplier_id and _mapping(conn.execute("SELECT supplier_id FROM suppliers WHERE supplier_id=?", (supplier_id,))) is None:
        raise InventoryError(f"找不到供應商編號 {supplier_id}")


def create_inventory_movement(
    config: DatabaseConfig, row: dict[str, Any], *, sync_id: str | None = None,
) -> dict[str, str]:
    sync_id = str(sync_id or row.get("_sync_id") or uuid.uuid4().hex).strip()
    powder_id = str(row.get("色粉編號") or "").strip()
    supplier_id = str(row.get("廠商編號") or "").strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        _validate_refs(conn, powder_id, supplier_id)
        if _mapping(conn.execute(
            "SELECT movement_id FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?",
            (sync_id,),
        )) is not None:
            raise InventoryError(f"庫存 _sync_id {sync_id} 已存在")
        conn.execute(
            """INSERT INTO inventory_movements(
                   movement_key, sheet_name, sheet_row_key, movement_type, colorpowder_id,
                   movement_date, quantity, unit, notes, supplier_id, supplier_name,
                   source, version, created_at, updated_at, last_synced_at)
               VALUES (?, '庫存記錄', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'app', 1, ?, ?, NULL)""",
            (
                f"sheet:庫存記錄:{sync_id}", sync_id, str(row.get("類型") or "").strip(), powder_id,
                str(row.get("日期") or "").strip(), float(row.get("數量") or 0),
                str(row.get("單位") or "g").strip(), str(row.get("備註") or "").strip(),
                supplier_id, str(row.get("廠商名稱") or "").strip(), now, now,
            ),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?", (sync_id,)
        ))
        payload = inventory_sheet_payload(entity)
        enqueue_sheet_sync(
            conn, sheet_name="庫存記錄", row_key=sync_id, operation="insert",
            payload=payload, entity_version=1,
        )
        return payload


def update_inventory_movement(config: DatabaseConfig, sync_id: str, row: dict[str, Any]) -> dict[str, str]:
    sync_id = str(sync_id or "").strip()
    powder_id = str(row.get("色粉編號") or "").strip()
    supplier_id = str(row.get("廠商編號") or "").strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        _validate_refs(conn, powder_id, supplier_id)
        existing = _mapping(conn.execute(
            "SELECT * FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?", (sync_id,)
        ))
        if existing is None:
            raise InventoryError(f"找不到庫存 _sync_id {sync_id}")
        if existing.get("reversal_of_movement_key"):
            raise InventoryError("沖銷記錄不可修改")
        if existing.get("reversed_at"):
            raise InventoryError("已沖銷的庫存記錄不可修改")
        version = int(existing["version"]) + 1
        conn.execute(
            """UPDATE inventory_movements SET movement_type=?, colorpowder_id=?, movement_date=?,
                      quantity=?, unit=?, notes=?, supplier_id=?, supplier_name=?, source='app',
                      version=?, updated_at=? WHERE sheet_name='庫存記錄' AND sheet_row_key=?""",
            (
                str(row.get("類型") or "").strip(), powder_id, str(row.get("日期") or "").strip(),
                float(row.get("數量") or 0), str(row.get("單位") or "g").strip(),
                str(row.get("備註") or "").strip(), supplier_id,
                str(row.get("廠商名稱") or "").strip(), version, now, sync_id,
            ),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?", (sync_id,)
        ))
        payload = inventory_sheet_payload(entity)
        enqueue_sheet_sync(
            conn, sheet_name="庫存記錄", row_key=sync_id, operation="update",
            payload=payload, entity_version=version,
        )
        return payload


def reverse_inventory_movement(
    config: DatabaseConfig,
    sync_id: str,
    *,
    reason: str,
    reversal_sync_id: str | None = None,
) -> dict[str, str]:
    """Append an inverse movement and mark the original as reversed atomically."""
    sync_id = str(sync_id or "").strip()
    reason = str(reason or "").strip()
    if not sync_id:
        raise InventoryError("請選擇要沖銷的庫存記錄")
    if not reason:
        raise InventoryError("請輸入沖銷原因")
    reversal_sync_id = str(reversal_sync_id or f"reversal-{uuid.uuid4().hex}").strip()
    now = utc_now_iso()

    with connect_from_config(config) as conn:
        original = _mapping(conn.execute(
            "SELECT * FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?",
            (sync_id,),
        ))
        if original is None:
            raise InventoryError(f"找不到庫存 _sync_id {sync_id}")
        if original.get("reversal_of_movement_key"):
            raise InventoryError("沖銷記錄不可再次沖銷")
        if original.get("reversed_at") or _mapping(conn.execute(
            "SELECT movement_id FROM inventory_movements WHERE reversal_of_movement_key=?",
            (original["movement_key"],),
        )):
            raise InventoryError("此庫存記錄已沖銷")
        if _mapping(conn.execute(
            "SELECT movement_id FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?",
            (reversal_sync_id,),
        )):
            raise InventoryError(f"庫存 _sync_id {reversal_sync_id} 已存在")

        reversal_notes = f"沖銷原因：{reason}"
        conn.execute(
            """INSERT INTO inventory_movements(
                   movement_key, sheet_name, sheet_row_key, movement_type, colorpowder_id,
                   movement_date, quantity, unit, notes, supplier_id, supplier_name,
                   reversal_of_movement_key, source, version, created_at, updated_at, last_synced_at)
               VALUES (?, '庫存記錄', ?, '沖銷', ?, ?, ?, ?, ?, ?, ?, ?, 'app', 1, ?, ?, NULL)""",
            (
                f"sheet:庫存記錄:{reversal_sync_id}", reversal_sync_id,
                original["colorpowder_id"], original["movement_date"],
                -float(original["quantity"]), original["unit"], reversal_notes,
                original.get("supplier_id") or "", original.get("supplier_name") or "",
                original["movement_key"], now, now,
            ),
        )
        conn.execute(
            """UPDATE inventory_movements
               SET reversed_at=?, updated_at=?, version=version+1
               WHERE movement_id=? AND reversed_at IS NULL""",
            (now, now, original["movement_id"]),
        )
        reversal = _mapping(conn.execute(
            "SELECT * FROM inventory_movements WHERE sheet_name='庫存記錄' AND sheet_row_key=?",
            (reversal_sync_id,),
        ))
        payload = inventory_sheet_payload(reversal)
        enqueue_sheet_sync(
            conn, sheet_name="庫存記錄", row_key=reversal_sync_id, operation="insert",
            payload=payload, entity_version=1,
        )
        return payload
