"""Google Sheets -> SQLite-compatible database validation/import helpers.

The importer is read-only for Google Sheets. It supports dry-run validation and
idempotent writes so repeated syncs of the same Sheet rows do not duplicate
inventory movements. Google Sheets row timestamps are not assumed to exist: if a
Sheet lacks an explicit updated_at/更新時間 column, row_hash + sheet_rows metadata
are used for incremental change detection and conflicts are recorded instead of
silently overwriting local SQLite changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .database import (
    DatabaseConfig,
    connect_from_config,
    initialize_database_from_config,
    record_sync_conflict,
    record_sync_log,
    upsert_sheet_row,
    utc_now_iso,
)

SHEET_KEY_COLUMNS = {
    "色粉管理": "色粉編號",
    "供應商管理": "supplier_id",
    "庫存記錄": None,
    "配方管理": "配方編號",
    "客戶名單": "客戶名稱",
    "生產單": "生產單號",
}

SUPPLIER_ID_COLUMNS = ["supplier_id", "供應商ID", "供應商編號"]
SUPPLIER_NAME_COLUMNS = ["供應商名稱", "名稱"]
UPDATED_AT_COLUMNS = ["updated_at", "更新時間", "修改時間", "last_modified_at"]
COLOR_COLUMNS = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
INVENTORY_COLUMNS = ["類型", "色粉編號", "日期", "數量", "單位", "備註"]


@dataclass
class ImportResult:
    sheet_name: str
    dry_run: bool = False
    sheet_rows: int = 0
    sqlite_rows: int = 0
    unchanged: int = 0
    to_insert: int = 0
    to_update: int = 0
    inserted_or_updated: int = 0
    conflicts: int = 0
    inventory_duplicate_risk: int = 0
    errors: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.duplicate_ids and not self.conflicts


def _row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _records_from_values(values: list[list[Any]]) -> list[dict[str, str]]:
    if not values:
        return []
    headers = [str(h).strip() for h in values[0]]
    records = []
    for raw in values[1:]:
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        records.append({headers[i]: str(padded[i]).strip() for i in range(len(headers)) if headers[i]})
    return records


def _first_value(row: dict[str, Any], columns: list[str]) -> str:
    for col in columns:
        value = str(row.get(col, "")).strip()
        if value:
            return value
    return ""


def _sheet_updated_at(row: dict[str, Any]) -> str | None:
    return _first_value(row, UPDATED_AT_COLUMNS) or None


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _supplier_name(row: dict[str, Any]) -> str:
    return _first_value(row, SUPPLIER_NAME_COLUMNS)


def _supplier_id(row: dict[str, Any], row_key: str) -> str:
    explicit_id = _first_value(row, SUPPLIER_ID_COLUMNS)
    if explicit_id:
        return explicit_id
    # Minimal non-breaking fallback when the existing Sheet has no supplier_id:
    # bind identity to the Sheet row key, not mutable supplier name.
    return f"sheet:{row_key}"


def _row_key(sheet_name: str, row: dict[str, Any], index: int) -> str:
    key_col = SHEET_KEY_COLUMNS.get(sheet_name)
    if key_col and str(row.get(key_col, "")).strip():
        return str(row[key_col]).strip()
    if sheet_name == "供應商管理":
        explicit_id = _first_value(row, SUPPLIER_ID_COLUMNS)
        if explicit_id:
            return explicit_id
    return f"row-{index + 2}"


def _inventory_movement_key(sheet_name: str, row_key: str) -> str:
    return f"sheet:{sheet_name}:{row_key}"


def _row_changed_in_sqlite(conn, sheet_name: str, row_key: str, row_hash: str) -> tuple[bool, bool]:
    existing = conn.execute(
        "SELECT row_hash FROM sheet_rows WHERE sheet_name = ? AND row_key = ?",
        (sheet_name, row_key),
    ).fetchone()
    if existing is None:
        return True, False
    return existing["row_hash"] != row_hash, True


def _entity_changed_since_sync(entity_row) -> bool:
    if entity_row is None:
        return False
    last_synced_at = entity_row["last_synced_at"]
    updated_at = entity_row["updated_at"]
    return bool(last_synced_at and updated_at and updated_at > last_synced_at)


def import_sheet_values(
    sheet_name: str,
    values: list[list[Any]],
    db_path=None,
    *,
    db_config: DatabaseConfig | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """Validate/copy worksheet values into local SQLite or configured Turso.

    dry_run=True performs all validations and insert/update counting without
    modifying the target database. ``db_path`` remains supported for local
    SQLite callers; production callers should pass ``db_config``.
    """
    if db_config is not None and db_path is not None:
        raise ValueError("Pass either db_config or db_path, not both.")
    config = db_config or DatabaseConfig(backend="sqlite", path=db_path)
    initialize_database_from_config(config)
    result = ImportResult(sheet_name=sheet_name, dry_run=dry_run)
    rows = _records_from_values(values)
    result.sheet_rows = len(rows)
    seen: set[str] = set()
    started_at = utc_now_iso()

    with connect_from_config(config) as conn:
        for index, row in enumerate(rows):
            row_key = _row_key(sheet_name, row, index)
            if not row_key:
                result.errors.append(f"row {index + 2}: missing required ID")
                continue
            if row_key in seen:
                result.duplicate_ids.append(row_key)
                continue
            seen.add(row_key)

            row_hash = _row_hash(row)
            changed, existed = _row_changed_in_sqlite(conn, sheet_name, row_key, row_hash)
            if not changed:
                result.unchanged += 1
                continue
            if existed:
                result.to_update += 1
            else:
                result.to_insert += 1

            if sheet_name == "色粉管理":
                powder_id = row.get("色粉編號", "").strip()
                if not powder_id:
                    result.errors.append(f"row {index + 2}: missing 色粉編號")
                    continue
                entity = conn.execute("SELECT * FROM color_powders WHERE colorpowder_id = ?", (powder_id,)).fetchone()
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(conn, entity_type="color_powder", entity_id=powder_id,
                                             sqlite_payload=dict(entity), sheet_payload=row,
                                             reason="Sheet row changed after SQLite entity was modified since last sync")
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        """INSERT INTO color_powders(colorpowder_id, international_code, name, category, package, notes,
                               source, created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(colorpowder_id) DO UPDATE SET
                               international_code=excluded.international_code,
                               name=excluded.name,
                               category=excluded.category,
                               package=excluded.package,
                               notes=excluded.notes,
                               last_synced_at=excluded.last_synced_at""",
                        (powder_id, row.get("國際色號", ""), row.get("名稱", ""), row.get("色粉類別", ""),
                         row.get("包裝", ""), row.get("備註", ""), synced_at, _sheet_updated_at(row) or (entity["updated_at"] if entity else synced_at), synced_at),
                    )
                    result.inserted_or_updated += 1

            elif sheet_name == "供應商管理":
                name = _supplier_name(row)
                if not name:
                    result.errors.append(f"row {index + 2}: missing 供應商名稱")
                    continue
                supplier_id = _supplier_id(row, row_key)
                entity = conn.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,)).fetchone()
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(conn, entity_type="supplier", entity_id=supplier_id,
                                             sqlite_payload=dict(entity), sheet_payload=row,
                                             reason="Sheet supplier row changed after SQLite supplier was modified since last sync")
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        """INSERT INTO suppliers(supplier_id, name, phone, contact_person, notes, source,
                               created_at, updated_at, last_synced_at, sheet_row_key)
                           VALUES (?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?, ?)
                           ON CONFLICT(supplier_id) DO UPDATE SET
                               name=excluded.name, phone=excluded.phone, contact_person=excluded.contact_person,
                               notes=excluded.notes, last_synced_at=excluded.last_synced_at,
                               sheet_row_key=excluded.sheet_row_key""",
                        (supplier_id, name, row.get("電話", ""), row.get("聯絡人", ""), row.get("備註", ""),
                         synced_at, _sheet_updated_at(row) or (entity["updated_at"] if entity else synced_at), synced_at, row_key),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO supplier_aliases(alias, supplier_id, created_at) VALUES (?, ?, ?)",
                        (name, supplier_id, synced_at),
                    )
                    result.inserted_or_updated += 1

            elif sheet_name == "庫存記錄":
                powder_id = row.get("色粉編號", "").strip()
                if not powder_id:
                    result.errors.append(f"row {index + 2}: missing 色粉編號")
                    continue
                movement_key = _inventory_movement_key(sheet_name, row_key)
                existing_movement = conn.execute(
                    "SELECT * FROM inventory_movements WHERE movement_key = ?", (movement_key,)
                ).fetchone()
                if existing_movement and changed:
                    result.inventory_duplicate_risk += 1
                if existing_movement and _entity_changed_since_sync(existing_movement):
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(conn, entity_type="inventory_movement", entity_id=movement_key,
                                             sqlite_payload=dict(existing_movement), sheet_payload=row,
                                             reason="Sheet inventory row changed after SQLite movement was modified since last sync")
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        "INSERT OR IGNORE INTO color_powders(colorpowder_id, created_at, updated_at, last_synced_at) VALUES (?, ?, ?, ?)",
                        (powder_id, synced_at, synced_at, synced_at),
                    )
                    conn.execute(
                        """INSERT INTO inventory_movements(movement_key, sheet_name, sheet_row_key, movement_type,
                               colorpowder_id, movement_date, quantity, unit, notes, source, created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(movement_key) DO UPDATE SET
                               movement_type=excluded.movement_type,
                               colorpowder_id=excluded.colorpowder_id,
                               movement_date=excluded.movement_date,
                               quantity=excluded.quantity,
                               unit=excluded.unit,
                               notes=excluded.notes,
                               last_synced_at=excluded.last_synced_at""",
                        (movement_key, sheet_name, row_key, row.get("類型", ""), powder_id, row.get("日期", ""),
                         _safe_float(row.get("數量", 0)), row.get("單位", "g") or "g", row.get("備註", ""),
                         synced_at, _sheet_updated_at(row) or (existing_movement["updated_at"] if existing_movement else synced_at), synced_at),
                    )
                    result.inserted_or_updated += 1

            else:
                if not dry_run:
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    result.inserted_or_updated += 1

        result.sqlite_rows = conn.execute(
            "SELECT COUNT(*) FROM sheet_rows WHERE sheet_name = ?", (sheet_name,)
        ).fetchone()[0]
        if dry_run:
            conn.rollback()
        else:
            status = "success" if result.ok else "completed_with_errors"
            record_sync_log(conn, sync_name=f"initial_import:{sheet_name}", direction="google_sheets_to_sqlite",
                            status=status, started_at=started_at, finished_at=utc_now_iso(),
                            read_count=result.sheet_rows, written_count=result.inserted_or_updated,
                            error_count=len(result.errors) + len(result.duplicate_ids) + result.conflicts,
                            message="; ".join((result.errors + result.warnings)[:5]))
    if not any(_sheet_updated_at(row) for row in rows):
        result.warnings.append("Sheet has no explicit updated_at/更新時間 column; row_hash is used for change detection, and conflicts protect local SQLite edits.")
    return result


def import_worksheets(
    spreadsheet,
    sheet_names: Iterable[str] | None = None,
    db_path=None,
    *,
    db_config: DatabaseConfig | None = None,
    dry_run: bool = False,
) -> list[ImportResult]:
    """Read selected worksheets and validate/copy them into SQLite or Turso."""
    names = list(sheet_names or SHEET_KEY_COLUMNS.keys())
    results = []
    for name in names:
        ws = spreadsheet.worksheet(name)
        results.append(
            import_sheet_values(
                name,
                ws.get_all_values(),
                db_path=db_path,
                db_config=db_config,
                dry_run=dry_run,
            )
        )
    return results
