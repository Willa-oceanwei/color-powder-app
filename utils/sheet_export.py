"""Safe Turso/SQLite -> Google Sheets delivery for queued color-powder edits."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .database import (
    DatabaseConfig,
    connect_from_config,
    initialize_database_from_config,
    record_sync_conflict,
    record_sync_log,
    upsert_sheet_row,
    utc_now_iso,
)
from .sheet_import import COLOR_COLUMNS, _fetchone_mapping, _records_from_values, _row_hash


@dataclass
class ExportResult:
    sheet_name: str = "色粉管理"
    dry_run: bool = True
    queued: int = 0
    unchanged: int = 0
    to_insert: int = 0
    to_update: int = 0
    written: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.conflicts


def color_powder_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    """Map the canonical color-powder entity to existing Sheet column names."""
    return {
        "色粉編號": str(entity.get("colorpowder_id") or ""),
        "國際色號": str(entity.get("international_code") or ""),
        "名稱": str(entity.get("name") or ""),
        "色粉類別": str(entity.get("category") or ""),
        "包裝": str(entity.get("package") or ""),
        "備註": str(entity.get("notes") or ""),
    }


def _normalized_payload(payload: dict[str, Any], headers: list[str]) -> dict[str, str]:
    return {header: str(payload.get(header, "") or "").strip() for header in headers if header}


def sync_color_powder_outbox(
    worksheet,
    values: list[list[Any]],
    *,
    db_config: DatabaseConfig,
    dry_run: bool = True,
    initialize_schema: bool = True,
) -> ExportResult:
    """Preflight or deliver pending color-powder outbox entries.

    A queued database edit is written only when the current Sheet row still
    matches its last synchronized baseline. Deletes intentionally remain
    blocked until the tombstone phase.
    """
    if initialize_schema:
        initialize_database_from_config(db_config)
    result = ExportResult(dry_run=dry_run)
    if not values:
        result.errors.append("色粉管理沒有 header")
        return result
    headers = [str(value).strip() for value in values[0] if str(value).strip()]
    if "色粉編號" not in headers:
        result.errors.append("色粉管理缺少 色粉編號 欄位")
        return result
    rows = _records_from_values(values)
    sheet_rows: dict[str, tuple[int, dict[str, str]]] = {}
    for row_number, row in enumerate(rows, start=2):
        row_key = row.get("色粉編號", "").strip()
        if not row_key:
            continue
        if row_key in sheet_rows:
            result.errors.append(f"duplicate 色粉編號: {row_key}")
        else:
            sheet_rows[row_key] = (row_number, row)
    if result.errors:
        return result

    started_at = utc_now_iso()
    with connect_from_config(db_config) as conn:
        pending = conn.execute(
            """SELECT event.id, event.row_key, event.operation, event.payload_json,
                      event.entity_version
               FROM sync_outbox AS event
               WHERE event.sheet_name = '色粉管理'
                 AND event.status IN ('pending', 'failed')
                 AND event.entity_version = (
                     SELECT MAX(latest.entity_version)
                     FROM sync_outbox AS latest
                     WHERE latest.sheet_name = event.sheet_name
                       AND latest.row_key = event.row_key
                       AND latest.status IN ('pending', 'failed')
                 )
               ORDER BY event.id"""
        ).fetchall()
        result.queued = len(pending)
        for raw_entry in pending:
            entry = dict(raw_entry) if hasattr(raw_entry, "keys") else dict(
                zip(("id", "row_key", "operation", "payload_json", "entity_version"), raw_entry)
            )
            row_key = str(entry["row_key"])
            if entry["operation"] == "delete":
                result.conflicts += 1
                result.warnings.append(f"{row_key}: delete is blocked until tombstones are implemented")
                if not dry_run:
                    conn.execute(
                        """UPDATE sync_outbox SET status='conflict', last_error=?
                           WHERE sheet_name='色粉管理' AND row_key=?
                             AND entity_version <= ? AND status IN ('pending', 'failed')""",
                        ("Delete requires tombstone workflow", row_key, entry["entity_version"]),
                    )
                continue
            payload = json.loads(entry["payload_json"] or "{}")
            desired = _normalized_payload(payload, headers)
            current_info = sheet_rows.get(row_key)
            baseline = _fetchone_mapping(conn.execute(
                "SELECT row_hash FROM sheet_rows WHERE sheet_name='色粉管理' AND row_key=?",
                (row_key,),
            ))
            if current_info is None:
                if baseline is not None:
                    reason = "Sheet row disappeared after the last sync; automatic recreation is blocked"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type="color_powder", entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=None, reason=reason,
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name='色粉管理' AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed')""",
                            (reason, row_key, entry["entity_version"]),
                        )
                    continue
                result.to_insert += 1
                if not dry_run:
                    worksheet.append_row([desired.get(header, "") for header in headers])
            else:
                row_number, current = current_info
                current = _normalized_payload(current, headers)
                if current == desired:
                    result.unchanged += 1
                    if not dry_run:
                        synced_at = utc_now_iso()
                        upsert_sheet_row(conn, "色粉管理", row_key, desired, _row_hash(desired))
                        conn.execute(
                            "UPDATE color_powders SET last_synced_at=? WHERE colorpowder_id=?",
                            (synced_at, row_key),
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='completed', processed_at=?, last_error=NULL
                               WHERE sheet_name='色粉管理' AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed')""",
                            (synced_at, row_key, entry["entity_version"]),
                        )
                    continue
                sheet_changed = baseline is None or baseline["row_hash"] != _row_hash(current)
                if sheet_changed:
                    reason = "Both Turso and Google Sheet changed after the last sync"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type="color_powder", entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=current, reason=reason,
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name='色粉管理' AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed')""",
                            (reason, row_key, entry["entity_version"]),
                        )
                    continue
                result.to_update += 1
                if not dry_run:
                    worksheet.update(
                        f"A{row_number}",
                        [[desired.get(header, "") for header in headers]],
                    )
            if not dry_run:
                synced_at = utc_now_iso()
                upsert_sheet_row(conn, "色粉管理", row_key, desired, _row_hash(desired))
                conn.execute(
                    "UPDATE color_powders SET last_synced_at=? WHERE colorpowder_id=?",
                    (synced_at, row_key),
                )
                conn.execute(
                    """UPDATE sync_outbox SET status='completed', attempt_count=attempt_count+1,
                           processed_at=?, last_error=NULL
                       WHERE sheet_name='色粉管理' AND row_key=?
                         AND entity_version <= ? AND status IN ('pending', 'failed')""",
                    (synced_at, row_key, entry["entity_version"]),
                )
                result.written += 1
        if not dry_run:
            record_sync_log(
                conn, sync_name="outbox:色粉管理", direction="turso_to_google_sheets",
                status="success" if result.ok else "completed_with_conflicts",
                started_at=started_at, finished_at=utc_now_iso(), read_count=result.queued,
                written_count=result.written, error_count=len(result.errors) + result.conflicts,
            )
    return result
