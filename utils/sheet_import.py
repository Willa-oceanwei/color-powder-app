"""One-time and incremental Google Sheets -> SQLite import helpers.

The import is intentionally read-only for Google Sheets: it copies existing rows
into SQLite and reports validation problems without clearing, deleting, or
rewriting the original Sheet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .database import connect, initialize_database, record_sync_log, upsert_sheet_row, utc_now_iso

SHEET_KEY_COLUMNS = {
    "色粉管理": "色粉編號",
    "供應商管理": "供應商名稱",
    "庫存記錄": None,
    "配方管理": "配方編號",
    "客戶名單": "客戶名稱",
    "生產單": "生產單號",
}

COLOR_COLUMNS = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
INVENTORY_COLUMNS = ["類型", "色粉編號", "日期", "數量", "單位", "備註"]


@dataclass
class ImportResult:
    sheet_name: str
    sheet_rows: int = 0
    sqlite_rows: int = 0
    inserted_or_updated: int = 0
    errors: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.duplicate_ids


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


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_key(sheet_name: str, row: dict[str, Any], index: int) -> str:
    key_col = SHEET_KEY_COLUMNS.get(sheet_name)
    if key_col and str(row.get(key_col, "")).strip():
        return str(row[key_col]).strip()
    return f"row-{index + 2}"


def import_sheet_values(sheet_name: str, values: list[list[Any]], db_path=None) -> ImportResult:
    """Copy a worksheet's values into SQLite and validate row count/IDs."""
    initialize_database(db_path)
    result = ImportResult(sheet_name=sheet_name)
    rows = _records_from_values(values)
    result.sheet_rows = len(rows)
    seen: set[str] = set()
    started_at = utc_now_iso()

    with connect(db_path) as conn:
        for index, row in enumerate(rows):
            row_key = _row_key(sheet_name, row, index)
            if not row_key:
                result.errors.append(f"row {index + 2}: missing required ID")
                continue
            if row_key in seen:
                result.duplicate_ids.append(row_key)
                continue
            seen.add(row_key)

            upsert_sheet_row(conn, sheet_name, row_key, row, _row_hash(row))
            result.inserted_or_updated += 1

            if sheet_name == "色粉管理":
                powder_id = row.get("色粉編號", "").strip()
                if not powder_id:
                    result.errors.append(f"row {index + 2}: missing 色粉編號")
                    continue
                now = utc_now_iso()
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
                           updated_at=excluded.updated_at,
                           last_synced_at=excluded.last_synced_at""",
                    (powder_id, row.get("國際色號", ""), row.get("名稱", ""), row.get("色粉類別", ""),
                     row.get("包裝", ""), row.get("備註", ""), now, now, now),
                )

            elif sheet_name == "供應商管理":
                name = row.get("供應商名稱", row.get("名稱", "")).strip()
                if name:
                    now = utc_now_iso()
                    conn.execute(
                        """INSERT INTO suppliers(supplier_id, name, phone, contact_person, notes, source, created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(supplier_id) DO UPDATE SET
                               name=excluded.name, phone=excluded.phone, contact_person=excluded.contact_person,
                               notes=excluded.notes, updated_at=excluded.updated_at, last_synced_at=excluded.last_synced_at""",
                        (name, name, row.get("電話", ""), row.get("聯絡人", ""), row.get("備註", ""), now, now, now),
                    )

            elif sheet_name == "庫存記錄":
                powder_id = row.get("色粉編號", "").strip()
                if not powder_id:
                    result.errors.append(f"row {index + 2}: missing 色粉編號")
                    continue
                now = utc_now_iso()
                conn.execute(
                    "INSERT OR IGNORE INTO color_powders(colorpowder_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (powder_id, now, now),
                )
                conn.execute(
                    """INSERT INTO inventory_movements(movement_type, colorpowder_id, movement_date, quantity, unit, notes,
                           source, created_at, updated_at, last_synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)""",
                    (row.get("類型", ""), powder_id, row.get("日期", ""), _safe_float(row.get("數量", 0)),
                     row.get("單位", "g") or "g", row.get("備註", ""), now, now, now),
                )

        result.sqlite_rows = conn.execute(
            "SELECT COUNT(*) FROM sheet_rows WHERE sheet_name = ?", (sheet_name,)
        ).fetchone()[0]
        status = "success" if result.ok else "completed_with_errors"
        record_sync_log(conn, sync_name=f"initial_import:{sheet_name}", direction="google_sheets_to_sqlite",
                        status=status, started_at=started_at, finished_at=utc_now_iso(),
                        read_count=result.sheet_rows, written_count=result.inserted_or_updated,
                        error_count=len(result.errors) + len(result.duplicate_ids),
                        message="; ".join(result.errors[:5]))
    return result


def import_worksheets(spreadsheet, sheet_names: Iterable[str] | None = None, db_path=None) -> list[ImportResult]:
    """Read selected worksheets from Google Sheets and copy them into SQLite."""
    names = list(sheet_names or SHEET_KEY_COLUMNS.keys())
    results = []
    for name in names:
        ws = spreadsheet.worksheet(name)
        results.append(import_sheet_values(name, ws.get_all_values(), db_path=db_path))
    return results
