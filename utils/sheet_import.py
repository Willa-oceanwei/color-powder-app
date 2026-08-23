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
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

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
    "庫存記錄": "_sync_id",
    "配方管理": "配方編號",
    "客戶名單": "客戶名稱",
    "生產單": "生產單號",
    "代工管理": "代工單號",
    "代工送達記錄": "_sync_id",
    "代工載回記錄": "_sync_id",
}

SUPPLIER_ID_COLUMNS = ["supplier_id", "供應商ID", "供應商編號"]
SUPPLIER_NAME_COLUMNS = ["供應商名稱", "供應商簡稱", "名稱"]
UPDATED_AT_COLUMNS = ["updated_at", "更新時間", "修改時間", "last_modified_at"]
COLOR_COLUMNS = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
INVENTORY_COLUMNS = ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"]
RECIPE_COMPONENT_POSITIONS = range(1, 9)
TRANSIENT_GOOGLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class SheetReadError(RuntimeError):
    """A concise Google Sheets read error safe to show in the web UI."""


def _google_api_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    text = str(exc)
    for candidate in TRANSIENT_GOOGLE_STATUS_CODES:
        if str(candidate) in text[:200]:
            return candidate
    return None


def read_worksheet_values_with_retry(
    worksheet,
    *,
    attempts: int = 4,
    base_delay_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list[Any]]:
    """Read one worksheet, retrying only transient Google/API failures."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            return worksheet.get_all_values()
        except Exception as exc:
            status = _google_api_status_code(exc)
            is_transient = status in TRANSIENT_GOOGLE_STATUS_CODES
            if not is_transient or attempt == attempts:
                status_text = f"HTTP {status}" if status else type(exc).__name__
                retry_text = f" after {attempt} attempts" if is_transient else ""
                raise SheetReadError(
                    f"Google Sheets read failed ({status_text}){retry_text}. "
                    "Please wait 30 seconds and try again."
                ) from exc
            sleep(base_delay_seconds * (2 ** (attempt - 1)))


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


class ImportAbortedError(RuntimeError):
    """Raised after rolling back an atomic import that found unsafe issues."""

    def __init__(self, result: ImportResult):
        self.result = result
        super().__init__(
            f"Import aborted: errors={len(result.errors)}, "
            f"duplicates={len(result.duplicate_ids)}, conflicts={result.conflicts}"
        )


def missing_inventory_sync_id_updates(
    values: list[list[Any]],
    *,
    id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> list[tuple[int, int, str]]:
    """Return ``(row, column, id)`` updates for non-empty inventory rows missing IDs."""
    if not values:
        raise ValueError("庫存記錄沒有 header")
    headers = [str(value).strip() for value in values[0]]
    if "_sync_id" not in headers:
        raise ValueError("庫存記錄缺少 _sync_id 欄位")
    sync_column = headers.index("_sync_id")
    updates = []
    for row_number, raw_row in enumerate(values[1:], start=2):
        padded = list(raw_row) + [""] * max(0, len(headers) - len(raw_row))
        has_business_data = any(
            str(padded[index]).strip()
            for index in range(len(headers))
            if index != sync_column
        )
        if has_business_data and not str(padded[sync_column]).strip():
            updates.append((row_number, sync_column + 1, id_factory()))
    return updates


def missing_outsourcing_sync_id_updates(
    values: list[list[Any]],
    *,
    id_prefix: str,
    id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> list[tuple[int, int, str]]:
    """Return safe permanent-ID updates for non-empty outsourcing ledger rows."""
    if id_prefix not in {"delivery", "return"}:
        raise ValueError("id_prefix must be delivery or return")
    if not values:
        raise ValueError("代工歷程工作表沒有 header")
    headers = [str(value).strip() for value in values[0]]
    if "_sync_id" not in headers:
        raise ValueError("代工歷程工作表缺少 _sync_id 欄位")
    sync_column = headers.index("_sync_id")
    updates = []
    for row_number, raw_row in enumerate(values[1:], start=2):
        padded = list(raw_row) + [""] * max(0, len(headers) - len(raw_row))
        has_business_data = any(
            str(padded[index]).strip() for index in range(len(headers)) if index != sync_column
        )
        if has_business_data and not str(padded[sync_column]).strip():
            updates.append((row_number, sync_column + 1, f"{id_prefix}:{id_factory()}"))
    return updates


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


def _is_number(value: Any) -> bool:
    try:
        float(str(value).replace(",", "").strip())
        return True
    except (TypeError, ValueError):
        return False


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
    if sheet_name in {"庫存記錄", "代工送達記錄", "代工載回記錄"}:
        return ""
    return f"row-{index + 2}"


def _inventory_movement_key(sheet_name: str, row_key: str) -> str:
    return f"sheet:{sheet_name}:{row_key}"


def _fetchone_mapping(cursor) -> dict[str, Any] | None:
    """Normalize sqlite3.Row and libsql tuple rows to a column-name mapping."""
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = getattr(cursor, "description", None)
    if not description:
        raise TypeError("Database cursor returned a tuple row without column metadata")
    columns = [column[0] for column in description]
    return dict(zip(columns, row))


def _fetchall_mappings(cursor) -> list[dict[str, Any]]:
    """Normalize sqlite3 and libsql result sets without per-row database calls."""
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    description = getattr(cursor, "description", None)
    if not description:
        raise TypeError("Database cursor returned tuple rows without column metadata")
    columns = [column[0] for column in description]
    return [dict(zip(columns, row)) for row in rows]


def _row_changed_in_sqlite(conn, sheet_name: str, row_key: str, row_hash: str) -> tuple[bool, bool]:
    existing = _fetchone_mapping(conn.execute(
        "SELECT row_hash FROM sheet_rows WHERE sheet_name = ? AND row_key = ?",
        (sheet_name, row_key),
    ))
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
    initialize_schema: bool = True,
    abort_on_issues: bool = False,
) -> ImportResult:
    """Validate/copy worksheet values into local SQLite or configured Turso.

    dry_run=True performs all validations and insert/update counting without
    modifying the target database. ``db_path`` remains supported for local
    SQLite callers; production callers should pass ``db_config``. Callers that
    already completed startup health checks may set ``initialize_schema=False``
    to keep an interactive dry-run free of schema-maintenance statements. Set
    ``abort_on_issues=True`` for a formal import that must roll back completely
    when any validation error, duplicate, or conflict is found.
    """
    if db_config is not None and db_path is not None:
        raise ValueError("Pass either db_config or db_path, not both.")
    config = db_config or DatabaseConfig(backend="sqlite", path=db_path)
    if initialize_schema:
        initialize_database_from_config(config)
    result = ImportResult(sheet_name=sheet_name, dry_run=dry_run)
    rows = _records_from_values(values)
    result.sheet_rows = len(rows)
    seen: set[str] = set()
    started_at = utc_now_iso()

    with connect_from_config(config) as conn:
        baseline_hashes = {
            str(db_row["row_key"]): str(db_row["row_hash"])
            for db_row in _fetchall_mappings(conn.execute(
                "SELECT row_key, row_hash FROM sheet_rows WHERE sheet_name = ?",
                (sheet_name,),
            ))
        }
        known_inventory_powder_ids: set[str] | None = None
        known_inventory_supplier_ids: set[str] | None = None
        if sheet_name == "庫存記錄":
            known_inventory_powder_ids = {
                str(db_row[0]).strip()
                for db_row in conn.execute("SELECT colorpowder_id FROM color_powders").fetchall()
            }
            known_inventory_supplier_ids = {
                str(db_row[0]).strip()
                for db_row in conn.execute("SELECT supplier_id FROM suppliers").fetchall()
            }
        known_recipe_powder_ids: set[str] | None = None
        if sheet_name == "配方管理":
            known_recipe_powder_ids = {
                str(db_row[0]).strip()
                for db_row in conn.execute("SELECT colorpowder_id FROM color_powders").fetchall()
            }
        known_production_recipe_ids: set[str] | None = None
        if sheet_name == "生產單":
            known_production_recipe_ids = {
                str(db_row[0]).strip()
                for db_row in conn.execute("SELECT recipe_id FROM recipes").fetchall()
            }
        known_outsourcing_order_ids: set[str] | None = None
        if sheet_name in {"代工送達記錄", "代工載回記錄"}:
            known_outsourcing_order_ids = {
                str(db_row[0]).strip()
                for db_row in conn.execute(
                    "SELECT outsourcing_order_id FROM outsourcing_orders"
                ).fetchall()
            }
        for index, row in enumerate(rows):
            row_key = _row_key(sheet_name, row, index)
            if not row_key:
                missing_column = "_sync_id" if sheet_name == "庫存記錄" else "required ID"
                result.errors.append(f"row {index + 2}: missing {missing_column}")
                continue
            if row_key in seen:
                result.duplicate_ids.append(row_key)
                continue
            seen.add(row_key)

            row_hash = _row_hash(row)
            existed = row_key in baseline_hashes
            changed = not existed or baseline_hashes[row_key] != row_hash
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
                entity = _fetchone_mapping(
                    conn.execute("SELECT * FROM color_powders WHERE colorpowder_id = ?", (powder_id,))
                )
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="color_powder",
                            entity_id=powder_id,
                            sqlite_payload=dict(entity),
                            sheet_payload=row,
                            reason="Database entity exists but no Sheet sync baseline exists",
                        )
                    continue
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
                entity = _fetchone_mapping(
                    conn.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))
                )
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="supplier",
                            entity_id=supplier_id,
                            sqlite_payload=dict(entity),
                            sheet_payload=row,
                            reason="Database entity exists but no Sheet sync baseline exists",
                        )
                    continue
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

            elif sheet_name == "配方管理":
                recipe_id = row.get("配方編號", "").strip()
                if not recipe_id:
                    result.errors.append(f"row {index + 2}: missing 配方編號")
                    continue
                components = []
                component_error = False
                for position in RECIPE_COMPONENT_POSITIONS:
                    powder_id = row.get(f"色粉編號{position}", "").strip()
                    weight_text = row.get(f"色粉重量{position}", "").strip()
                    if not powder_id:
                        if weight_text and _safe_float(weight_text) != 0:
                            result.errors.append(
                                f"row {index + 2}: 色粉重量{position} has value but 色粉編號{position} is empty"
                            )
                            component_error = True
                        continue
                    if known_recipe_powder_ids is not None and powder_id not in known_recipe_powder_ids:
                        result.errors.append(
                            f"row {index + 2}: unknown 色粉編號{position} {powder_id}; import 色粉管理 first"
                        )
                        component_error = True
                        continue
                    components.append((position, powder_id, _safe_float(weight_text)))
                if component_error:
                    continue
                entity = _fetchone_mapping(
                    conn.execute("SELECT * FROM recipes WHERE recipe_id = ?", (recipe_id,))
                )
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="recipe",
                            entity_id=recipe_id,
                            sqlite_payload=dict(entity),
                            sheet_payload=row,
                            reason="Database recipe exists but no Sheet sync baseline exists",
                        )
                    continue
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="recipe",
                            entity_id=recipe_id,
                            sqlite_payload=dict(entity),
                            sheet_payload=row,
                            reason="Sheet recipe changed after database recipe was modified since last sync",
                        )
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    entity_updated_at = _sheet_updated_at(row) or synced_at
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        """INSERT INTO recipes(
                               recipe_id, color, customer_id, customer_name, recipe_category, status,
                               original_recipe, powder_category, measurement_unit, pantone_code,
                               ratio1, ratio2, ratio3, net_weight, net_weight_unit, total_category,
                               sheet_created_at, notes, important_notice, oem_multiplier, source, created_at, updated_at,
                               last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                   'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(recipe_id) DO UPDATE SET
                               color=excluded.color,
                               customer_id=excluded.customer_id,
                               customer_name=excluded.customer_name,
                               recipe_category=excluded.recipe_category,
                               status=excluded.status,
                               original_recipe=excluded.original_recipe,
                               powder_category=excluded.powder_category,
                               measurement_unit=excluded.measurement_unit,
                               pantone_code=excluded.pantone_code,
                               ratio1=excluded.ratio1,
                               ratio2=excluded.ratio2,
                               ratio3=excluded.ratio3,
                               net_weight=excluded.net_weight,
                               net_weight_unit=excluded.net_weight_unit,
                               total_category=excluded.total_category,
                               sheet_created_at=excluded.sheet_created_at,
                               notes=excluded.notes,
                               important_notice=excluded.important_notice,
                               oem_multiplier=excluded.oem_multiplier,
                               source=excluded.source,
                               version=recipes.version + 1,
                               updated_at=excluded.updated_at,
                               last_synced_at=excluded.last_synced_at""",
                        (
                            recipe_id,
                            row.get("顏色", ""),
                            row.get("客戶編號", ""),
                            row.get("客戶名稱", ""),
                            row.get("配方類別", ""),
                            row.get("狀態", ""),
                            row.get("原始配方", ""),
                            row.get("色粉類別", ""),
                            row.get("計量單位", ""),
                            row.get("Pantone色號", ""),
                            row.get("比例1", ""),
                            row.get("比例2", ""),
                            row.get("比例3", ""),
                            _safe_float(row.get("淨重", 0)),
                            row.get("淨重單位", ""),
                            row.get("合計類別", ""),
                            row.get("建檔時間", ""),
                            row.get("備註", ""),
                            row.get("重要提醒", ""),
                            _safe_float(row.get("代工倍率", 1)) or 1,
                            synced_at if entity is None else entity["created_at"],
                            entity_updated_at,
                            synced_at,
                        ),
                    )
                    conn.execute("DELETE FROM recipe_components WHERE recipe_id = ?", (recipe_id,))
                    for position, powder_id, weight in components:
                        conn.execute(
                            """INSERT INTO recipe_components(
                                   recipe_id, position, colorpowder_id, weight, created_at, updated_at
                               ) VALUES (?, ?, ?, ?, ?, ?)""",
                            (recipe_id, position, powder_id, weight, synced_at, synced_at),
                        )
                    result.inserted_or_updated += 1

            elif sheet_name == "生產單":
                order_id = row.get("生產單號", "").strip()
                recipe_id = row.get("配方編號", "").strip()
                if recipe_id and known_production_recipe_ids is not None and recipe_id not in known_production_recipe_ids:
                    result.errors.append(f"row {index + 2}: unknown 配方編號 {recipe_id}; import 配方管理 first")
                    continue
                entity = _fetchone_mapping(conn.execute(
                    "SELECT * FROM production_orders WHERE production_order_id=?", (order_id,)
                ))
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="production_order",
                            entity_id=order_id,
                            sqlite_payload=dict(entity),
                            sheet_payload=row,
                            reason="Database production order exists but no Sheet sync baseline exists",
                        )
                    continue
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        """INSERT INTO production_orders(
                               production_order_id, production_date, recipe_id, color, customer_name,
                               payload_json, source, created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(production_order_id) DO UPDATE SET
                               production_date=excluded.production_date, recipe_id=excluded.recipe_id,
                               color=excluded.color, customer_name=excluded.customer_name,
                               payload_json=excluded.payload_json, source=excluded.source,
                               version=production_orders.version+1, updated_at=excluded.updated_at,
                               last_synced_at=excluded.last_synced_at""",
                        (
                            order_id, row.get("生產日期", ""), recipe_id or None,
                            row.get("顏色", ""), row.get("客戶名稱", ""),
                            json.dumps(row, ensure_ascii=False), synced_at,
                            _sheet_updated_at(row) or synced_at, synced_at,
                        ),
                    )
                    conn.execute("DELETE FROM production_order_packages WHERE production_order_id=?", (order_id,))
                    for position in range(1, 5):
                        weight = _safe_float(row.get(f"包裝重量{position}", 0))
                        count = _safe_float(row.get(f"包裝份數{position}", 0))
                        if weight or count:
                            conn.execute(
                                """INSERT INTO production_order_packages(
                                       production_order_id, position, package_weight, package_count,
                                       created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)""",
                                (order_id, position, weight, count, synced_at, synced_at),
                            )
                    result.inserted_or_updated += 1

            elif sheet_name == "代工管理":
                order_id = row.get("代工單號", "").strip()
                quantity_text = row.get("代工數量", "").strip()
                target_text = row.get("目標載回數量", "").strip()
                multiplier_text = row.get("轉換倍率", "").strip()
                if not _is_number(quantity_text) or _safe_float(quantity_text) <= 0:
                    result.errors.append(f"row {index + 2}: 代工數量必須是大於 0 的數字")
                    continue
                if target_text and (not _is_number(target_text) or _safe_float(target_text) <= 0):
                    result.errors.append(f"row {index + 2}: 目標載回數量必須是大於 0 的數字")
                    continue
                if multiplier_text and (not _is_number(multiplier_text) or _safe_float(multiplier_text) <= 0):
                    result.errors.append(f"row {index + 2}: 轉換倍率必須是大於 0 的數字")
                    continue
                entity = _fetchone_mapping(conn.execute(
                    "SELECT * FROM outsourcing_orders WHERE outsourcing_order_id=?", (order_id,)
                ))
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type="outsourcing_order", entity_id=order_id,
                            sqlite_payload=dict(entity), sheet_payload=row,
                            reason="Database outsourcing order exists but no Sheet sync baseline exists",
                        )
                    continue
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    created_at = entity["created_at"] if entity else synced_at
                    updated_at = _sheet_updated_at(row) or synced_at
                    target = _safe_float(target_text) if target_text else _safe_float(quantity_text)
                    multiplier = _safe_float(multiplier_text) if multiplier_text else 1.0
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        """INSERT INTO outsourcing_orders(
                               outsourcing_order_id, production_order_id, recipe_id, customer_name,
                               quantity, target_return_quantity, conversion_multiplier, vendor_name,
                               notes, status, delivered, delivery_notes, payload_json, source,
                               created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(outsourcing_order_id) DO UPDATE SET
                               production_order_id=excluded.production_order_id,
                               recipe_id=excluded.recipe_id, customer_name=excluded.customer_name,
                               quantity=excluded.quantity,
                               target_return_quantity=excluded.target_return_quantity,
                               conversion_multiplier=excluded.conversion_multiplier,
                               vendor_name=excluded.vendor_name, notes=excluded.notes,
                               status=excluded.status, delivered=excluded.delivered,
                               delivery_notes=excluded.delivery_notes, payload_json=excluded.payload_json,
                               source=excluded.source, version=outsourcing_orders.version+1,
                               updated_at=excluded.updated_at, last_synced_at=excluded.last_synced_at""",
                        (
                            order_id, row.get("生產單號") or None, row.get("配方編號") or None,
                            row.get("客戶名稱", ""), _safe_float(quantity_text), target, multiplier,
                            row.get("代工廠商", ""), row.get("備註", ""),
                            row.get("狀態", "🏭 在廠內") or "🏭 在廠內",
                            1 if row.get("已交貨", "").strip() else 0,
                            row.get("交貨備註", ""), json.dumps(row, ensure_ascii=False),
                            created_at, updated_at, synced_at,
                        ),
                    )
                    result.inserted_or_updated += 1

            elif sheet_name in {"代工送達記錄", "代工載回記錄"}:
                order_id = row.get("代工單號", "").strip()
                if not order_id:
                    result.errors.append(f"row {index + 2}: missing 代工單號")
                    continue
                if known_outsourcing_order_ids is not None and order_id not in known_outsourcing_order_ids:
                    result.errors.append(
                        f"row {index + 2}: unknown 代工單號 {order_id}; import 代工管理 first"
                    )
                    continue
                is_delivery = sheet_name == "代工送達記錄"
                quantity_column = "送達數量" if is_delivery else "載回數量"
                date_column = "送達日期" if is_delivery else "載回日期"
                quantity_text = row.get(quantity_column, "").strip()
                if not _is_number(quantity_text) or _safe_float(quantity_text) < 0:
                    result.errors.append(f"row {index + 2}: {quantity_column} 必須是非負數字")
                    continue
                if is_delivery and _safe_float(quantity_text) <= 0:
                    result.errors.append(f"row {index + 2}: 送達數量必須大於 0")
                    continue
                table = "outsourcing_deliveries" if is_delivery else "outsourcing_returns"
                id_column = "delivery_id" if is_delivery else "return_id"
                sql_date_column = "delivery_date" if is_delivery else "return_date"
                entity = _fetchone_mapping(conn.execute(
                    f"SELECT * FROM {table} WHERE {id_column}=?", (row_key,)
                ))
                if not existed and entity is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn, entity_type="outsourcing_delivery" if is_delivery else "outsourcing_return",
                            entity_id=row_key, sqlite_payload=dict(entity), sheet_payload=row,
                            reason="Database outsourcing event exists but no Sheet sync baseline exists",
                        )
                    continue
                if existed and _entity_changed_since_sync(entity):
                    result.conflicts += 1
                    continue
                if not dry_run:
                    synced_at = utc_now_iso()
                    created_at = entity["created_at"] if entity else synced_at
                    updated_at = _sheet_updated_at(row) or synced_at
                    upsert_sheet_row(conn, sheet_name, row_key, row, row_hash, _sheet_updated_at(row))
                    conn.execute(
                        f"""INSERT INTO {table}(
                                {id_column}, outsourcing_order_id, {sql_date_column}, quantity,
                                payload_json, source, created_at, updated_at, last_synced_at)
                            VALUES (?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                            ON CONFLICT({id_column}) DO UPDATE SET
                                outsourcing_order_id=excluded.outsourcing_order_id,
                                {sql_date_column}=excluded.{sql_date_column}, quantity=excluded.quantity,
                                payload_json=excluded.payload_json, source=excluded.source,
                                version={table}.version+1, updated_at=excluded.updated_at,
                                last_synced_at=excluded.last_synced_at""",
                        (row_key, order_id, row.get(date_column, ""), _safe_float(quantity_text),
                         json.dumps(row, ensure_ascii=False), created_at, updated_at, synced_at),
                    )
                    result.inserted_or_updated += 1

            elif sheet_name == "庫存記錄":
                powder_id = row.get("色粉編號", "").strip()
                if not powder_id:
                    result.errors.append(f"row {index + 2}: missing 色粉編號")
                    continue
                if known_inventory_powder_ids is not None and powder_id not in known_inventory_powder_ids:
                    result.errors.append(
                        f"row {index + 2}: unknown 色粉編號 {powder_id}; import 色粉管理 first"
                    )
                    continue
                supplier_id = row.get("廠商編號", "").strip()
                if (
                    supplier_id
                    and known_inventory_supplier_ids is not None
                    and supplier_id not in known_inventory_supplier_ids
                ):
                    result.errors.append(
                        f"row {index + 2}: unknown 廠商編號 {supplier_id}; import 供應商管理 first"
                    )
                    continue
                movement_key = _inventory_movement_key(sheet_name, row_key)
                existing_movement = _fetchone_mapping(
                    conn.execute(
                        "SELECT * FROM inventory_movements WHERE movement_key = ?", (movement_key,)
                    )
                )
                if existing_movement and changed:
                    result.inventory_duplicate_risk += 1
                if not existed and existing_movement is not None:
                    result.conflicts += 1
                    if not dry_run:
                        record_sync_conflict(
                            conn,
                            entity_type="inventory_movement",
                            entity_id=movement_key,
                            sqlite_payload=dict(existing_movement),
                            sheet_payload=row,
                            reason="Database movement exists but no Sheet sync baseline exists",
                        )
                    continue
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
                        """INSERT INTO inventory_movements(movement_key, sheet_name, sheet_row_key, movement_type,
                               colorpowder_id, movement_date, quantity, unit, notes, supplier_id, supplier_name,
                               source, created_at, updated_at, last_synced_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'google_sheets_import', ?, ?, ?)
                           ON CONFLICT(movement_key) DO UPDATE SET
                               movement_type=excluded.movement_type,
                               colorpowder_id=excluded.colorpowder_id,
                               movement_date=excluded.movement_date,
                               quantity=excluded.quantity,
                               unit=excluded.unit,
                               notes=excluded.notes,
                               supplier_id=excluded.supplier_id,
                               supplier_name=excluded.supplier_name,
                               last_synced_at=excluded.last_synced_at""",
                        (movement_key, sheet_name, row_key, row.get("類型", ""), powder_id, row.get("日期", ""),
                         _safe_float(row.get("數量", 0)), row.get("單位", "g") or "g", row.get("備註", ""),
                         supplier_id, row.get("廠商名稱", ""),
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
        if not dry_run and abort_on_issues and not result.ok:
            raise ImportAbortedError(result)
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
        result.warnings.append(
            "Sheet has no explicit updated_at/更新時間 column; row_hash is used for change detection, "
            "and conflicts protect database edits, including Turso."
        )
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
                read_worksheet_values_with_retry(ws),
                db_path=db_path,
                db_config=db_config,
                dry_run=dry_run,
            )
        )
    return results
