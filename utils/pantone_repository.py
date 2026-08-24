"""Turso-first Pantone reference records keyed by permanent formula ID."""

from __future__ import annotations

from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class PantoneError(RuntimeError):
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


def pantone_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {"Pantone色號": str(entity.get("pantone_code") or ""),
            "配方編號": str(entity.get("formula_id") or ""),
            "客戶名稱": str(entity.get("customer_name") or ""),
            "料號": str(entity.get("material_no") or ""),
            "生命週期": str(entity.get("lifecycle_status") or "active"),
            "停用時間": str(entity.get("deleted_at") or ""),
            "停用原因": str(entity.get("delete_reason") or "")}


def list_pantone_records(config: DatabaseConfig, *, include_inactive=False) -> list[dict[str, Any]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(f"SELECT * FROM pantone_records {where} ORDER BY formula_id"))


def create_pantone_record(config: DatabaseConfig, *, formula_id: str, pantone_code: str,
                          customer_name: str = "", material_no: str = "") -> dict[str, Any]:
    formula_id, pantone_code = str(formula_id).strip(), str(pantone_code).strip()
    if not formula_id or not pantone_code:
        raise PantoneError("Pantone 色號與配方編號必填")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        if _mapping(conn.execute("SELECT 1 FROM pantone_records WHERE formula_id=?", (formula_id,))):
            raise PantoneError(f"配方編號 {formula_id} 已存在於 Pantone 色號表")
        conn.execute("""INSERT INTO pantone_records(
            formula_id,pantone_code,customer_name,material_no,source,version,created_at,updated_at)
            VALUES (?,?,?,?,'app',1,?,?)""",
            (formula_id, pantone_code, str(customer_name).strip(), str(material_no).strip(), now, now))
        entity = _mapping(conn.execute("SELECT * FROM pantone_records WHERE formula_id=?", (formula_id,)))
        enqueue_sheet_sync(conn, sheet_name="Pantone色號表", row_key=formula_id, operation="insert",
                           payload=pantone_sheet_payload(entity), entity_version=1)
        return entity
