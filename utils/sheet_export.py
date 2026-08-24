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
    to_delete: int = 0
    written: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_deletes: int = 0

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
        "生命週期": str(entity.get("lifecycle_status") or "active"),
        "停用時間": str(entity.get("deleted_at") or ""),
        "停用原因": str(entity.get("delete_reason") or ""),
    }


def _normalized_payload(payload: dict[str, Any], headers: list[str]) -> dict[str, str]:
    return {header: str(payload.get(header, "") or "").strip() for header in headers if header}


def _ensure_tombstone_outbox(conn, sheet_name: str) -> None:
    """Backfill one pending delete event for lifecycle rows created before tombstones."""
    queries = {
        "色粉管理": ("color_powders", "colorpowder_id", "lifecycle_status='inactive'"),
        "供應商管理": ("suppliers", "supplier_id", "lifecycle_status='inactive'"),
        "客戶名單": ("customers", "customer_id", "lifecycle_status='inactive'"),
        "樣品記錄": ("sample_records", "sample_id", "lifecycle_status='inactive'"),
        "個別客戶庫存": (
            "customer_inventory_records", "record_id", "lifecycle_status='inactive'",
        ),
        "洗車廠庫存": (
            "carwash_inventory_movements", "movement_id", "lifecycle_status='inactive'",
        ),
        "試色登錄": ("trial_records", "trial_id", "lifecycle_status='inactive'"),
        "配方管理": ("recipes", "recipe_id", "lifecycle_status='inactive'"),
        "生產單": ("production_orders", "production_order_id", "cancelled_at IS NOT NULL"),
        "庫存記錄": (
            "inventory_movements", "sheet_row_key",
            "sheet_name='庫存記錄' AND (reversed_at IS NOT NULL OR reversal_of_movement_key IS NOT NULL)",
        ),
    }
    if sheet_name not in queries:
        return
    table, id_column, condition = queries[sheet_name]
    rows = conn.execute(
        f"SELECT {id_column}, version FROM {table} WHERE {condition} AND {id_column} IS NOT NULL"
    ).fetchall()
    for row in rows:
        row_key, entity_version = str(row[0]), int(row[1])
        existing_delete = conn.execute(
            """SELECT 1 FROM sync_outbox
               WHERE sheet_name=? AND row_key=? AND operation='delete'
                 AND status IN ('pending','failed','processing','completed') LIMIT 1""",
            (sheet_name, row_key),
        ).fetchone()
        if existing_delete:
            continue
        max_version = conn.execute(
            "SELECT COALESCE(MAX(entity_version), 0) FROM sync_outbox WHERE sheet_name=? AND row_key=?",
            (sheet_name, row_key),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO sync_outbox(
                   sheet_name, row_key, operation, payload_json, entity_version, created_at)
               VALUES (?, ?, 'delete', NULL, ?, ?)""",
            (sheet_name, row_key, max(entity_version, int(max_version) + 1), utc_now_iso()),
        )


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
    max_entries: int | None = None,
    allow_deletes: bool = True,
) -> ExportResult:
    """Preflight or deliver pending color-powder outbox entries.

    A queued database edit is written only when the current Sheet row still
    matches its last synchronized baseline. Tombstones physically remove the
    Sheet row while retaining the canonical Turso history.
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
    with connect_from_config(db_config) as read_conn:
        _ensure_tombstone_outbox(read_conn, sheet_name)
        pending = read_conn.execute(
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
    entries = [
        dict(row) if hasattr(row, "keys") else dict(
            zip(("id", "row_key", "operation", "payload_json", "entity_version", "status"), row)
        )
        for row in pending
    ]
    entries.sort(key=lambda entry: (
        entry["operation"] == "delete",
        -(sheet_rows.get(str(entry["row_key"]), (0, {}))[0]) if entry["operation"] == "delete" else 0,
    ))
    if not allow_deletes:
        result.skipped_deletes = sum(entry["operation"] == "delete" for entry in entries)
        entries = [entry for entry in entries if entry["operation"] != "delete"]
        if result.skipped_deletes:
            result.warnings.append(
                f"safe mode retained {result.skipped_deletes} delete event(s) for manual PUSH"
            )
    if max_entries is not None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        entries = entries[:max_entries]
    result.queued = len(entries)

    claimed_ids: set[int] = set()
    if not dry_run:
        # Claim in a fully isolated session. No read/processing connection remains
        # open while this transaction commits, which is required by remote libsql.
        with connect_from_config(db_config) as claim_conn:
            for entry in entries:
                if entry["status"] == "processing":
                    continue
                claimed = claim_conn.execute(
                    """UPDATE sync_outbox
                       SET status='processing', attempt_count=attempt_count+1,
                           processed_at=?, last_error=NULL
                       WHERE id=? AND status IN ('pending', 'failed')
                       RETURNING id""",
                    (utc_now_iso(), entry["id"]),
                ).fetchone()
                if claimed is not None:
                    claimed_ids.add(int(entry["id"]))

    for entry in entries:
        row_key = str(entry["row_key"])
        recovering = entry["status"] == "processing"
        if not dry_run and not recovering and int(entry["id"]) not in claimed_ids:
            result.queued -= 1
            continue
        payload = json.loads(entry["payload_json"] or "{}")
        desired = _normalized_payload(payload, headers)
        current_info = sheet_rows.get(row_key)
        action: str | None = None

        with connect_from_config(db_config) as decision_conn:
            baseline = _fetchone_mapping(decision_conn.execute(
                "SELECT row_hash FROM sheet_rows WHERE sheet_name=? AND row_key=?",
                (sheet_name, row_key),
            ))
            if entry["operation"] == "delete":
                if current_info is None:
                    result.unchanged += 1
                    action = "acknowledge_delete"
                elif baseline is None or baseline["row_hash"] != _row_hash(
                    _normalized_payload(current_info[1], headers)
                ):
                    reason = "Sheet row changed or has no synchronized baseline; tombstone delete is blocked"
                    result.conflicts += 1
                    result.warnings.append(f"{row_key}: {reason}")
                    if not dry_run:
                        record_sync_conflict(
                            decision_conn, entity_type=entity_type, entity_id=row_key,
                            sqlite_payload=None, sheet_payload=current_info[1], reason=reason,
                        )
                    continue
                else:
                    result.to_delete += 1
                    action = "delete"
            elif current_info is None:
                if recovering:
                    reason = "Previous Sheet write outcome is uncertain and the row is absent; automatic retry is blocked"
                    result.conflicts += 1
                    result.warnings.append(f"{row_key}: {reason}")
                    continue
                if baseline is not None:
                    reason = "Sheet row disappeared after the last sync; automatic recreation is blocked"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            decision_conn, entity_type=entity_type, entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=None, reason=reason,
                        )
                        decision_conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name=? AND row_key=? AND entity_version <= ?
                                 AND status IN ('pending', 'failed', 'processing')""",
                            (reason, sheet_name, row_key, entry["entity_version"]),
                        )
                    continue
                result.to_insert += 1
                action = "insert"
            else:
                row_number, raw_current = current_info
                current = _normalized_payload(raw_current, headers)
                if current == desired:
                    result.unchanged += 1
                    action = "acknowledge"
                elif baseline is None or baseline["row_hash"] != _row_hash(current):
                    reason = "Both Turso and Google Sheet changed after the last sync"
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            decision_conn, entity_type=entity_type, entity_id=row_key,
                            sqlite_payload=desired, sheet_payload=current, reason=reason,
                        )
                        decision_conn.execute(
                            """UPDATE sync_outbox SET status='conflict', last_error=?
                               WHERE sheet_name=? AND row_key=? AND entity_version <= ?
                                 AND status IN ('pending', 'failed', 'processing')""",
                            (reason, sheet_name, row_key, entry["entity_version"]),
                        )
                    continue
                else:
                    result.to_update += 1
                    action = "update"

        if dry_run:
            continue
        try:
            # Never keep a Turso/libsql session open during Google API I/O.
            if action == "insert":
                worksheet.append_row([desired.get(header, "") for header in headers])
            elif action == "update":
                worksheet.update(
                    f"A{current_info[0]}",
                    [[desired.get(header, "") for header in headers]],
                )
            elif action == "delete":
                worksheet.delete_rows(current_info[0])
        except Exception as exc:
            with connect_from_config(db_config) as failure_conn:
                failure_conn.execute(
                    "UPDATE sync_outbox SET status='failed', last_error=? WHERE id=? AND status='processing'",
                    (f"{type(exc).__name__}: {exc}", entry["id"]),
                )
            raise

        synced_at = utc_now_iso()
        with connect_from_config(db_config) as finalize_conn:
            if action in {"delete", "acknowledge_delete"}:
                finalize_conn.execute(
                    "DELETE FROM sheet_rows WHERE sheet_name=? AND row_key=?", (sheet_name, row_key)
                )
            else:
                upsert_sheet_row(finalize_conn, sheet_name, row_key, desired, _row_hash(desired))
            finalize_conn.execute(
                f"UPDATE {entity_table} SET last_synced_at=? WHERE {entity_id_column}=?",
                (synced_at, row_key),
            )
            finalize_conn.execute(
                """UPDATE sync_outbox SET status='completed', processed_at=?, last_error=NULL
                   WHERE sheet_name=? AND row_key=? AND entity_version <= ?
                     AND status IN ('pending', 'failed', 'processing')""",
                (synced_at, sheet_name, row_key, entry["entity_version"]),
            )
        if action in {"insert", "update", "delete"}:
            result.written += 1

    if not dry_run:
        with connect_from_config(db_config) as log_conn:
            record_sync_log(
                log_conn, sync_name=f"outbox:{sheet_name}", direction="turso_to_google_sheets",
                status="success" if result.ok else "completed_with_conflicts",
                started_at=started_at, finished_at=utc_now_iso(), read_count=result.queued,
                written_count=result.written, error_count=len(result.errors) + result.conflicts,
            )
    return result


def sync_color_powder_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="色粉管理", key_column="色粉編號",
        entity_type="color_powder", entity_table="color_powders", entity_id_column="colorpowder_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_supplier_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="供應商管理", key_column="供應商編號",
        entity_type="supplier", entity_table="suppliers", entity_id_column="supplier_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_customer_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="客戶名單", key_column="客戶編號",
        entity_type="customer", entity_table="customers", entity_id_column="customer_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_pantone_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="Pantone色號表", key_column="配方編號",
        entity_type="pantone_record", entity_table="pantone_records", entity_id_column="formula_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )

def sync_sample_outbox(worksheet, values, *, db_config, dry_run=True, initialize_schema=True,
                       max_entries=None, allow_deletes=True):
    return _sync_outbox(worksheet,values,db_config=db_config,sheet_name="樣品記錄",key_column="樣品編號",
        entity_type="sample_record",entity_table="sample_records",entity_id_column="sample_id",dry_run=dry_run,
        initialize_schema=initialize_schema,max_entries=max_entries,allow_deletes=allow_deletes)


def sync_customer_inventory_outbox(
    worksheet, values, *, db_config, dry_run=True, initialize_schema=True,
    max_entries=None, allow_deletes=True,
):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="個別客戶庫存",
        key_column="_sync_id", entity_type="customer_inventory_record",
        entity_table="customer_inventory_records", entity_id_column="record_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_carwash_inventory_outbox(
    worksheet, values, *, db_config, dry_run=True, initialize_schema=True,
    max_entries=None, allow_deletes=True,
):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="洗車廠庫存",
        key_column="_sync_id", entity_type="carwash_inventory_movement",
        entity_table="carwash_inventory_movements", entity_id_column="movement_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_trial_outbox(
    worksheet, values, *, db_config, dry_run=True, initialize_schema=True,
    max_entries=None, allow_deletes=True,
):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="試色登錄",
        key_column="_sync_id", entity_type="trial_record",
        entity_table="trial_records", entity_id_column="trial_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_recipe_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="配方管理", key_column="配方編號",
        entity_type="recipe", entity_table="recipes", entity_id_column="recipe_id",
        dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_inventory_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="庫存記錄", key_column="_sync_id",
        entity_type="inventory_movement", entity_table="inventory_movements",
        entity_id_column="sheet_row_key", dry_run=dry_run, initialize_schema=initialize_schema,
        max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_production_order_outbox(
    worksheet, values: list[list[Any]], *, db_config: DatabaseConfig,
    dry_run: bool = True, initialize_schema: bool = True,
    max_entries: int | None = None, allow_deletes: bool = True,
) -> ExportResult:
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="生產單", key_column="生產單號",
        entity_type="production_order", entity_table="production_orders",
        entity_id_column="production_order_id", dry_run=dry_run,
        initialize_schema=initialize_schema, max_entries=max_entries,
        allow_deletes=allow_deletes,
    )


def sync_outsourcing_order_outbox(worksheet, values, *, db_config, dry_run=True,
                                   initialize_schema=True, max_entries=None, allow_deletes=True):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="代工管理", key_column="代工單號",
        entity_type="outsourcing_order", entity_table="outsourcing_orders",
        entity_id_column="outsourcing_order_id", dry_run=dry_run,
        initialize_schema=initialize_schema, max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_outsourcing_delivery_outbox(worksheet, values, *, db_config, dry_run=True,
                                      initialize_schema=True, max_entries=None, allow_deletes=True):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="代工送達記錄", key_column="_sync_id",
        entity_type="outsourcing_delivery", entity_table="outsourcing_deliveries",
        entity_id_column="delivery_id", dry_run=dry_run,
        initialize_schema=initialize_schema, max_entries=max_entries, allow_deletes=allow_deletes,
    )


def sync_outsourcing_return_outbox(worksheet, values, *, db_config, dry_run=True,
                                    initialize_schema=True, max_entries=None, allow_deletes=True):
    return _sync_outbox(
        worksheet, values, db_config=db_config, sheet_name="代工載回記錄", key_column="_sync_id",
        entity_type="outsourcing_return", entity_table="outsourcing_returns",
        entity_id_column="return_id", dry_run=dry_run,
        initialize_schema=initialize_schema, max_entries=max_entries, allow_deletes=allow_deletes,
    )
