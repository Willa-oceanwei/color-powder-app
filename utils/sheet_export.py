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


def _sync_outbox(
    worksheet,
    values: list[list[Any]],
    *,
    db_config: DatabaseConfig,
    sheet_name: str,
    key_column: str,
    entity_type: str,
    entity_table: str,
    entity_id_column: str,
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
    result = ExportResult(sheet_name=sheet_name, dry_run=dry_run)
    if not values:
        result.errors.append(f"{sheet_name}沒有 header")
        return result
    headers = [str(value).strip() for value in values[0] if str(value).strip()]
    if key_column not in headers:
        result.errors.append(f"{sheet_name}缺少 {key_column} 欄位")
        return result
    rows = _records_from_values(values)
    sheet_rows: dict[str, tuple[int, dict[str, str]]] = {}
    for row_number, row in enumerate(rows, start=2):
        row_key = row.get(key_column, "").strip()
        if not row_key:
            continue
        if row_key in sheet_rows:
            result.errors.append(f"duplicate {key_column}: {row_key}")
        else:
            sheet_rows[row_key] = (row_number, row)
    if result.errors:
        return result

    started_at = utc_now_iso()
    with connect_from_config(db_config) as conn:
        pending = conn.execute(
            """SELECT event.id, event.row_key, event.operation, event.payload_json,
                      event.entity_version, event.status
               FROM sync_outbox AS event
               WHERE event.sheet_name = ?
                 AND event.status IN ('pending', 'failed', 'processing')
                 AND event.entity_version = (
                     SELECT MAX(latest.entity_version)
                     FROM sync_outbox AS latest
                     WHERE latest.sheet_name = event.sheet_name
                       AND latest.row_key = event.row_key
                       AND latest.status IN ('pending', 'failed', 'processing')
                 )
               ORDER BY event.id""",
            (sheet_name,),
        ).fetchall()
        result.queued = len(pending)
        claimed_ids: set[int] = set()
        if not dry_run:
            # Claim all currently claimable events in one short-lived session before
            # any Google Sheets I/O. This avoids both concurrent appends and a
            # mid-session libsql commit.
            with connect_from_config(db_config) as claim_conn:
                for raw_entry in pending:
                    candidate = dict(raw_entry) if hasattr(raw_entry, "keys") else dict(
                        zip(("id", "row_key", "operation", "payload_json", "entity_version", "status"), raw_entry)
                    )
                    if candidate["status"] == "processing":
                        continue
                    claimed_row = claim_conn.execute(
                        """UPDATE sync_outbox
                           SET status='processing', attempt_count=attempt_count+1,
                               processed_at=?, last_error=NULL
                           WHERE id=? AND status IN ('pending', 'failed')
                           RETURNING id""",
                        (utc_now_iso(), candidate["id"]),
                    ).fetchone()
                    if claimed_row is not None:
                        claimed_ids.add(int(candidate["id"]))
        for raw_entry in pending:
            entry = dict(raw_entry) if hasattr(raw_entry, "keys") else dict(
                zip(("id", "row_key", "operation", "payload_json", "entity_version", "status"), raw_entry)
            )
            row_key = str(entry["row_key"])
            recovering_uncertain_write = entry["status"] == "processing"
            if not dry_run and not recovering_uncertain_write:
                if int(entry["id"]) not in claimed_ids:
                    result.queued -= 1
                    continue
            if entry["operation"] == "delete":
                result.conflicts += 1
                result.warnings.append(f"{row_key}: delete is blocked until tombstones are implemented")
                if not dry_run:
                    conn.execute(
                        """UPDATE sync_outbox SET status='conflict', last_error=?
                           WHERE sheet_name=? AND row_key=?
                             AND entity_version <= ? AND status IN ('pending', 'failed', 'processing')""",
                        ("Delete requires tombstone workflow", sheet_name, row_key, entry["entity_version"]),
                    )
                continue
            payload = json.loads(entry["payload_json"] or "{}")
            desired = _normalized_payload(payload, headers)
            current_info = sheet_rows.get(row_key)
            baseline = _fetchone_mapping(conn.execute(
                "SELECT row_hash FROM sheet_rows WHERE sheet_name=? AND row_key=?",
                (sheet_name, row_key),
            ))
            if current_info is None:
                if recovering_uncertain_write:
                    reason = "Previous Sheet write outcome is uncertain and the row is absent; automatic retry is blocked"
                    result.conflicts += 1
                    result.warnings.append(f"{row_key}: {reason}")
                    continue
                if baseline is not None:
                    reason = "Sheet row disappeared after the last sync; automatic recreation is blocked"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type=entity_type, entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=None, reason=reason,
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name=? AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed', 'processing')""",
                            (reason, sheet_name, row_key, entry["entity_version"]),
                        )
                    continue
                result.to_insert += 1
                if not dry_run:
                    try:
                        worksheet.append_row([desired.get(header, "") for header in headers])
                    except Exception as exc:
                        conn.execute(
                            "UPDATE sync_outbox SET status='failed', last_error=? WHERE id=? AND status='processing'",
                            (f"{type(exc).__name__}: {exc}", entry["id"]),
                        )
                        raise
            else:
                row_number, current = current_info
                current = _normalized_payload(current, headers)
                if current == desired:
                    result.unchanged += 1
                    if not dry_run:
                        synced_at = utc_now_iso()
                        upsert_sheet_row(conn, sheet_name, row_key, desired, _row_hash(desired))
                        conn.execute(
                            f"UPDATE {entity_table} SET last_synced_at=? WHERE {entity_id_column}=?",
                            (synced_at, row_key),
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='completed', processed_at=?, last_error=NULL
                               WHERE sheet_name=? AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed', 'processing')""",
                            (synced_at, sheet_name, row_key, entry["entity_version"]),
                        )
                    continue
                sheet_changed = baseline is None or baseline["row_hash"] != _row_hash(current)
                if sheet_changed:
                    reason = "Both Turso and Google Sheet changed after the last sync"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type=entity_type, entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=current, reason=reason,
                        )
                        conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name=? AND row_key=?
                                 AND entity_version <= ? AND status IN ('pending', 'failed', 'processing')""",
                            (reason, sheet_name, row_key, entry["entity_version"]),
                        )
                    continue
                result.to_update += 1
                if not dry_run:
                    try:
                        worksheet.update(
                            f"A{row_number}",
                            [[desired.get(header, "") for header in headers]],
                        )
                    except Exception as exc:
                        conn.execute(
                            "UPDATE sync_outbox SET status='failed', last_error=? WHERE id=? AND status='processing'",
                            (f"{type(exc).__name__}: {exc}", entry["id"]),
                        )
                        raise
            if not dry_run:
                synced_at = utc_now_iso()
                upsert_sheet_row(conn, sheet_name, row_key, desired, _row_hash(desired))
                conn.execute(
                    f"UPDATE {entity_table} SET last_synced_at=? WHERE {entity_id_column}=?",
                    (synced_at, row_key),
                )
                conn.execute(
                    """UPDATE sync_outbox SET status='completed',
                           processed_at=?, last_error=NULL
                       WHERE sheet_name=? AND row_key=?
                         AND entity_version <= ? AND status IN ('pending', 'failed', 'processing')""",
                    (synced_at, sheet_name, row_key, entry["entity_version"]),
                )
                result.written += 1
        if not dry_run:
            record_sync_log(
                conn, sync_name=f"outbox:{sheet_name}", direction="turso_to_google_sheets",
                status="success" if result.ok else "completed_with_conflicts",
                started_at=started_at, finished_at=utc_now_iso(), read_count=result.queued,
                written_count=result.written, error_count=len(result.errors) + result.conflicts,
            )
    return result


def sync_color_powder_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="色粉管理", key_column="色粉編號",
        entity_type="color_powder", entity_table="color_powders", entity_id_column="colorpowder_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
    )


def sync_supplier_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="供應商管理", key_column="供應商編號",
        entity_type="supplier", entity_table="suppliers", entity_id_column="supplier_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
    )


def sync_recipe_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="配方管理", key_column="配方編號",
        entity_type="recipe", entity_table="recipes", entity_id_column="recipe_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
    )


def sync_inventory_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="庫存記錄", key_column="_sync_id",
        entity_type="inventory_movement", entity_table="inventory_movements",
        entity_id_column="sheet_row_key", dry_run=dry_run, initialize_schema=initialize_schema,
    )


def sync_production_order_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="生產單", key_column="生產單號",
        entity_type="production_order", entity_table="production_orders",
        entity_id_column="production_order_id", dry_run=dry_run,
        initialize_schema=initialize_schema,
    )
