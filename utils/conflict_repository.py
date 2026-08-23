"""Administrative access to synchronization conflict records."""

from __future__ import annotations

import json
from typing import Any

from .database import DatabaseConfig, connect_from_config, utc_now_iso


class ConflictError(RuntimeError):
    pass


OUTBOX_ENTITY_SHEETS = {
    "color_powder": "色粉管理",
    "supplier": "供應商管理",
    "recipe": "配方管理",
    "inventory_movement": "庫存記錄",
    "production_order": "生產單",
}


def _mappings(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _decode_payload(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def list_sync_conflicts(
    config: DatabaseConfig, *, status: str = "open", limit: int = 100
) -> list[dict[str, Any]]:
    if status not in {"open", "resolved", "all"}:
        raise ValueError("status must be open, resolved, or all")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    where = "" if status == "all" else "WHERE status=?"
    parameters: tuple[Any, ...] = (limit,) if status == "all" else (status, limit)
    with connect_from_config(config) as conn:
        conflicts = _mappings(conn.execute(
            f"""SELECT id, entity_type, entity_id, sqlite_payload_json,
                       sheet_payload_json, reason, status, detected_at,
                       resolved_at, resolution_notes
                FROM sync_conflicts {where}
                ORDER BY detected_at DESC, id DESC LIMIT ?""",
            parameters,
        ))
    for conflict in conflicts:
        conflict["turso_payload"] = _decode_payload(conflict.pop("sqlite_payload_json"))
        conflict["sheet_payload"] = _decode_payload(conflict.pop("sheet_payload_json"))
    return conflicts


def resolve_sync_conflict(
    config: DatabaseConfig,
    conflict_id: int,
    *,
    notes: str,
    resolution: str = "acknowledge",
) -> int:
    notes = str(notes or "").strip()
    if not notes:
        raise ConflictError("請輸入實際處理方式或確認結果")
    if resolution not in {"acknowledge", "retry_outbox"}:
        raise ValueError("resolution must be acknowledge or retry_outbox")
    with connect_from_config(config) as conn:
        conflict_rows = _mappings(conn.execute(
            """SELECT id, entity_type, entity_id FROM sync_conflicts
               WHERE id=? AND status='open'""",
            (int(conflict_id),),
        ))
        if not conflict_rows:
            raise ConflictError("找不到尚未結案的 conflict，請重新整理")
        conflict = conflict_rows[0]
        requeued = 0
        if resolution == "retry_outbox":
            sheet_name = OUTBOX_ENTITY_SHEETS.get(conflict["entity_type"])
            if sheet_name is None:
                raise ConflictError("此 conflict 類型不支援 outbound 重送")
            row_key = str(conflict["entity_id"])
            if sheet_name == "庫存記錄" and row_key.startswith("sheet:庫存記錄:"):
                row_key = row_key.removeprefix("sheet:庫存記錄:")
            requeued_rows = _mappings(conn.execute(
                """UPDATE sync_outbox
                   SET status='pending', processed_at=NULL, last_error=NULL
                   WHERE sheet_name=? AND row_key=? AND status='conflict'
                   RETURNING id""",
                (sheet_name, row_key),
            ))
            requeued = len(requeued_rows)
            if requeued == 0:
                raise ConflictError(
                    "找不到可重送的 outbound conflict event；請選擇只結案，或重新執行 inbound preflight"
                )
        updated = conn.execute(
            """UPDATE sync_conflicts
               SET status='resolved', resolved_at=?, resolution_notes=?
               WHERE id=? AND status='open' RETURNING id""",
            (utc_now_iso(), notes, int(conflict_id)),
        ).fetchone()
        if updated is None:
            raise ConflictError("找不到尚未結案的 conflict，請重新整理")
    return requeued


def reopen_sync_conflict(config: DatabaseConfig, conflict_id: int) -> None:
    with connect_from_config(config) as conn:
        updated = conn.execute(
            """UPDATE sync_conflicts
               SET status='open', resolved_at=NULL, resolution_notes=NULL
               WHERE id=? AND status='resolved' RETURNING id""",
            (int(conflict_id),),
        ).fetchone()
        if updated is None:
            raise ConflictError("找不到已結案的 conflict，請重新整理")
