"""SQLite-compatible database layer for the color powder management system.

Turso is the production source of truth when configured, while local SQLite is
kept for development and tests. Google Sheets remains a synchronized human
interface; web features should read/write through this module or repository
wrappers instead of calling Sheets directly.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

DEFAULT_DB_PATH = Path("data/colorpowder.db")
SCHEMA_VERSION = 19
LOGGER = logging.getLogger(__name__)
MAIN_TABLES = {
    "color_powders",
    "suppliers",
    "supplier_aliases",
    "inventory_movements",
    "recipes",
    "recipe_components",
    "production_orders",
    "production_order_packages",
    "outsourcing_orders",
    "outsourcing_deliveries",
    "outsourcing_returns",
    "customers",
    "customer_aliases",
    "pantone_records",
    "sample_records",
    "customer_inventory_records",
    "carwash_inventory_movements",
    "trial_records",
    "trial_settings",
    "sheet_rows",
    "sync_state",
    "sync_log",
    "sync_conflicts",
    "sync_outbox",
    "sync_worker_locks",
    "employee_master",
    "salary_monthly",
    "salary_adjustments",
    "annual_leave_history",
    "salary_rules",
    "employee_annual_leave_settings",
    "salary_deletion_audit",
}
REQUIRED_TABLE_COLUMNS = {
    "color_powders": {"lifecycle_status", "deleted_at", "delete_reason"},
    "suppliers": {"lifecycle_status", "deleted_at", "delete_reason"},
    "inventory_movements": {
        "supplier_id", "supplier_name", "reversal_of_movement_key", "reversed_at",
    },
    "recipes": {"oem_multiplier", "lifecycle_status", "deleted_at", "delete_reason"},
    "production_orders": {"cancelled_at", "cancel_reason"},
    "outsourcing_orders": {"lifecycle_status", "deleted_at", "delete_reason"},
    "customers": {"lifecycle_status", "deleted_at", "delete_reason"},
    "pantone_records": {"lifecycle_status", "deleted_at", "delete_reason"},
    "sample_records": {"lifecycle_status", "deleted_at", "delete_reason"},
    "customer_inventory_records": {"lifecycle_status", "deleted_at", "delete_reason"},
    "carwash_inventory_movements": {"lifecycle_status", "deleted_at", "delete_reason"},
    "trial_records": {"lifecycle_status", "deleted_at", "delete_reason"},
    "salary_monthly": {"annual_leave_entitlement_snapshot", "annual_leave_note_snapshot", "is_deleted", "deleted_at"},
    "employee_annual_leave_settings": {"annual_entitlement", "opening_balance", "opening_month"},
}


class DatabaseStartupError(RuntimeError):
    """Raised when production database startup cannot safely continue."""


class SqlExecutor(Protocol):
    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any: ...


def _execute_script(conn: SqlExecutor, sql_script: str) -> None:
    if hasattr(conn, "executescript"):
        conn.executescript(sql_script)
        return
    for statement in sql_script.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


@dataclass(frozen=True)
class DatabaseHealth:
    backend: str
    select_1_ok: bool
    schema_version: int | None
    existing_tables: set[str]
    missing_required_columns: dict[str, set[str]]

    @property
    def main_tables_exist(self) -> bool:
        return MAIN_TABLES.issubset(self.existing_tables)

    @property
    def schema_compatible(self) -> bool:
        return self.main_tables_exist and not self.missing_required_columns


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str
    path: Path | None = DEFAULT_DB_PATH
    turso_database_url: str | None = None
    turso_auth_token: str | None = None


def _clean_secret(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _secret_value(container: Any, *names: str) -> str | None:
    """Read the first non-empty value from mapping- or attribute-style secrets."""
    if container is None:
        return None
    for name in names:
        try:
            value = container.get(name)
        except (AttributeError, KeyError, TypeError):
            value = getattr(container, name, None)
        cleaned = _clean_secret(value)
        if cleaned:
            return cleaned
    return None


def _secret_section(container: Any, name: str) -> Any | None:
    if container is None:
        return None
    try:
        return container.get(name)
    except (AttributeError, KeyError, TypeError):
        return getattr(container, name, None)


def _turso_credentials_from_secrets(secrets: Any | None) -> tuple[str | None, str | None]:
    """Support top-level, ``[turso]``, and ``[connections.turso]`` secrets."""
    if secrets is None:
        return None, None
    turso = _secret_section(secrets, "turso")
    connections = _secret_section(secrets, "connections")
    connection_turso = _secret_section(connections, "turso")
    url = _secret_value(secrets, "TURSO_DATABASE_URL")
    token = _secret_value(secrets, "TURSO_AUTH_TOKEN")
    sections = (turso, connection_turso)
    url = url or next(
        (
            value
            for section in sections
            if (value := _secret_value(section, "TURSO_DATABASE_URL", "database_url", "url"))
        ),
        None,
    )
    token = token or next(
        (
            value
            for section in sections
            if (value := _secret_value(section, "TURSO_AUTH_TOKEN", "auth_token", "token"))
        ),
        None,
    )
    return url, token


def database_config_from_secrets(secrets: Any | None = None) -> DatabaseConfig:
    """Build database config from Streamlit secrets/env without exposing tokens."""
    url = _clean_secret(os.environ.get("TURSO_DATABASE_URL"))
    token = _clean_secret(os.environ.get("TURSO_AUTH_TOKEN"))
    secret_url, secret_token = _turso_credentials_from_secrets(secrets)
    url = secret_url or url
    token = secret_token or token
    if bool(url) != bool(token):
        missing = "TURSO_AUTH_TOKEN" if url else "TURSO_DATABASE_URL"
        raise DatabaseStartupError(f"Turso credentials are incomplete: missing {missing}.")
    if url and token:
        return DatabaseConfig(backend="turso", path=None, turso_database_url=url, turso_auth_token=token)
    return DatabaseConfig(backend="sqlite", path=DEFAULT_DB_PATH)


def secret_presence_from_secrets(secrets: Any | None = None) -> dict[str, bool]:
    """Return safe Turso secret presence flags without exposing secret values."""
    url_present = bool(_clean_secret(os.environ.get("TURSO_DATABASE_URL")))
    token_present = bool(_clean_secret(os.environ.get("TURSO_AUTH_TOKEN")))
    secret_url, secret_token = _turso_credentials_from_secrets(secrets)
    url_present = bool(secret_url) or url_present
    token_present = bool(secret_token) or token_present
    return {
        "TURSO_DATABASE_URL": url_present,
        "TURSO_AUTH_TOKEN": token_present,
    }


def format_database_startup_diagnostics(
    config: DatabaseConfig,
    health: DatabaseHealth,
    secret_presence: dict[str, bool] | None = None,
) -> list[str]:
    """Format safe startup diagnostics for Streamlit logs/UI without token values."""
    lines = [
        f"Database backend: {config.backend}",
        f"Database health: {'OK' if health.select_1_ok and health.schema_compatible else 'FAILED'}",
        f"Schema version: {health.schema_version}",
        f"Main tables present: {health.main_tables_exist}",
        f"Required columns present: {not health.missing_required_columns}",
    ]
    if secret_presence is not None:
        lines.extend([
            f"TURSO_DATABASE_URL configured: {secret_presence.get('TURSO_DATABASE_URL', False)}",
            f"TURSO_AUTH_TOKEN configured: {secret_presence.get('TURSO_AUTH_TOKEN', False)}",
        ])
    return lines


def log_database_startup_diagnostics(
    config: DatabaseConfig,
    health: DatabaseHealth,
    secret_presence: dict[str, bool] | None = None,
) -> None:
    """Emit safe startup diagnostics once through the configured logger."""
    for line in format_database_startup_diagnostics(config, health, secret_presence):
        LOGGER.warning(line)


def get_db_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else DEFAULT_DB_PATH


@contextmanager
def connect(db_path: str | Path | None = None):
    """Open a SQLite connection with production-safe defaults."""
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def connect_from_config(config: DatabaseConfig):
    """Open the configured SQLite-compatible backend with one transaction policy."""
    if config.backend == "sqlite":
        with connect(config.path) as conn:
            yield conn
        return
    if config.backend != "turso":
        raise DatabaseStartupError(f"Unsupported database backend: {config.backend}")

    client = _connect_turso(config)
    try:
        yield client
        if hasattr(client, "commit"):
            client.commit()
    except Exception:
        if hasattr(client, "rollback"):
            client.rollback()
        raise
    finally:
        client.close()


def _fetchall(cursor: Any) -> list[Any]:
    """Return all rows from DB-API cursors that are not directly iterable.

    Python's sqlite3 cursor supports direct iteration, but libsql 0.1.11's
    builtins.Cursor does not. Always using fetchall() keeps SQLite behavior while
    avoiding Turso startup failures.
    """
    return cursor.fetchall()


def _table_columns(conn: SqlExecutor, table_name: str) -> set[str]:
    rows = _fetchall(conn.execute(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in rows}


def _add_column_if_missing(conn: SqlExecutor, table_name: str, column_name: str, column_sql: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _initialize_schema(conn: SqlExecutor) -> None:
    """Create/validate the current schema on an open SQLite-compatible connection."""
    _execute_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS color_powders (
            colorpowder_id TEXT PRIMARY KEY,
            international_code TEXT,
            name TEXT,
            category TEXT,
            package TEXT,
            notes TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            contact_person TEXT,
            notes TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            sheet_row_key TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS supplier_aliases (
            alias TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_key TEXT UNIQUE,
            sheet_name TEXT,
            sheet_row_key TEXT,
            movement_type TEXT NOT NULL,
            colorpowder_id TEXT NOT NULL,
            movement_date TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'g',
            notes TEXT,
            supplier_id TEXT,
            supplier_name TEXT,
            reversal_of_movement_key TEXT,
            reversed_at TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            FOREIGN KEY (colorpowder_id) REFERENCES color_powders(colorpowder_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            UNIQUE(sheet_name, sheet_row_key)
        );

        CREATE TABLE IF NOT EXISTS recipes (
            recipe_id TEXT PRIMARY KEY,
            color TEXT,
            customer_id TEXT,
            customer_name TEXT,
            recipe_category TEXT,
            status TEXT,
            original_recipe TEXT,
            powder_category TEXT,
            measurement_unit TEXT,
            pantone_code TEXT,
            ratio1 TEXT,
            ratio2 TEXT,
            ratio3 TEXT,
            net_weight REAL,
            net_weight_unit TEXT,
            total_category TEXT,
            sheet_created_at TEXT,
            notes TEXT,
            important_notice TEXT,
            oem_multiplier REAL NOT NULL DEFAULT 1,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS recipe_components (
            recipe_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            colorpowder_id TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (recipe_id, position),
            FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id)
                ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (colorpowder_id) REFERENCES color_powders(colorpowder_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS production_orders (
            production_order_id TEXT PRIMARY KEY,
            production_date TEXT,
            recipe_id TEXT,
            color TEXT,
            customer_name TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            cancelled_at TEXT,
            cancel_reason TEXT,
            payload_json TEXT NOT NULL,
            recipe_version INTEGER,
            recipe_snapshot_json TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS production_order_packages (
            production_order_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            package_weight REAL NOT NULL DEFAULT 0,
            package_count REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (production_order_id, position),
            FOREIGN KEY (production_order_id) REFERENCES production_orders(production_order_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS outsourcing_orders (
            outsourcing_order_id TEXT PRIMARY KEY,
            production_order_id TEXT,
            recipe_id TEXT,
            customer_name TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            target_return_quantity REAL NOT NULL DEFAULT 0,
            conversion_multiplier REAL NOT NULL DEFAULT 1,
            vendor_name TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT '🏭 在廠內',
            delivered INTEGER NOT NULL DEFAULT 0,
            delivery_notes TEXT,
            payload_json TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS outsourcing_deliveries (
            delivery_id TEXT PRIMARY KEY,
            outsourcing_order_id TEXT NOT NULL,
            delivery_date TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            FOREIGN KEY (outsourcing_order_id) REFERENCES outsourcing_orders(outsourcing_order_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS outsourcing_returns (
            return_id TEXT PRIMARY KEY,
            outsourcing_order_id TEXT NOT NULL,
            return_date TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            FOREIGN KEY (outsourcing_order_id) REFERENCES outsourcing_orders(outsourcing_order_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            notes TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customer_aliases (
            alias TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pantone_records (
            formula_id TEXT PRIMARY KEY,
            pantone_code TEXT NOT NULL,
            customer_name TEXT,
            material_no TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sample_records (
            sample_id TEXT PRIMARY KEY,
            sample_date TEXT,
            customer_name TEXT,
            sample_name TEXT,
            quantity TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customer_inventory_records (
            record_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            recipe_id TEXT NOT NULL,
            color TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL,
            notes TEXT,
            sheet_created_at TEXT,
            sheet_updated_at TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS carwash_inventory_movements (
            movement_id TEXT PRIMARY KEY,
            movement_type TEXT NOT NULL,
            initial_date TEXT,
            initial_quantity REAL,
            product_id TEXT NOT NULL,
            inbound_date TEXT,
            outbound_date TEXT,
            quantity REAL,
            unit TEXT NOT NULL,
            registrar TEXT,
            notes TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS trial_records (
            trial_id TEXT PRIMARY KEY,
            formula_code TEXT NOT NULL UNIQUE,
            root_formula_code TEXT,
            customer_id TEXT,
            customer_name TEXT,
            trial_date TEXT NOT NULL,
            date_precision TEXT,
            historical_backfill TEXT,
            material TEXT NOT NULL,
            purchased TEXT NOT NULL DEFAULT '否',
            purchase_date TEXT,
            sheet_created_at TEXT,
            sheet_updated_at TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            delete_reason TEXT,
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS trial_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sheet_rows (
            sheet_name TEXT NOT NULL,
            row_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            row_hash TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'google_sheets',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sheet_updated_at TEXT,
            last_seen_at TEXT NOT NULL,
            last_synced_at TEXT,
            PRIMARY KEY (sheet_name, row_key)
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            sync_name TEXT PRIMARY KEY,
            last_success_at TEXT,
            last_attempt_at TEXT,
            status TEXT NOT NULL DEFAULT 'never_run',
            message TEXT,
            high_watermark TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_name TEXT NOT NULL,
            direction TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            read_count INTEGER NOT NULL DEFAULT 0,
            written_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            message TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            sqlite_payload_json TEXT,
            sheet_payload_json TEXT,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            detected_at TEXT NOT NULL,
            resolved_at TEXT,
            resolution_notes TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_name TEXT NOT NULL,
            row_key TEXT NOT NULL,
            operation TEXT NOT NULL CHECK(operation IN ('insert', 'update', 'delete')),
            payload_json TEXT,
            entity_version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'processing', 'completed', 'failed', 'conflict')),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            processed_at TEXT,
            UNIQUE(sheet_name, row_key, entity_version)
        );

        CREATE TABLE IF NOT EXISTS sync_worker_locks (
            lock_name TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS employee_master (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            join_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            base_salary INTEGER NOT NULL DEFAULT 0,
            attendance_bonus INTEGER NOT NULL DEFAULT 0,
            cooling_allowance INTEGER NOT NULL DEFAULT 0,
            allowance INTEGER NOT NULL DEFAULT 0,
            position_allowance INTEGER NOT NULL DEFAULT 0,
            insurance INTEGER NOT NULL DEFAULT 0,
            standard_hours REAL NOT NULL DEFAULT 8,
            annual_leave_base REAL NOT NULL DEFAULT 0,
            special_addition_enabled INTEGER NOT NULL DEFAULT 0,
            special_addition_amount INTEGER NOT NULL DEFAULT 0,
            special_addition_note TEXT,
            default_deduction_enabled INTEGER NOT NULL DEFAULT 0,
            default_deduction_amount INTEGER NOT NULL DEFAULT 0,
            default_deduction_note TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS salary_monthly (
            salary_id TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            employee_id TEXT NOT NULL,
            employee_name_snapshot TEXT NOT NULL,
            base_salary_snapshot INTEGER NOT NULL DEFAULT 0,
            attendance_bonus_snapshot INTEGER NOT NULL DEFAULT 0,
            cooling_allowance_snapshot INTEGER NOT NULL DEFAULT 0,
            allowance_snapshot INTEGER NOT NULL DEFAULT 0,
            position_allowance_snapshot INTEGER NOT NULL DEFAULT 0,
            insurance_snapshot INTEGER NOT NULL DEFAULT 0,
            standard_hours_snapshot REAL NOT NULL DEFAULT 8,
            leave_days REAL NOT NULL DEFAULT 0,
            leave_hours REAL NOT NULL DEFAULT 0,
            leave_deduction INTEGER NOT NULL DEFAULT 0,
            annual_leave_days REAL NOT NULL DEFAULT 0,
            annual_leave_hours REAL NOT NULL DEFAULT 0,
            annual_leave_balance_before REAL NOT NULL DEFAULT 0,
            annual_leave_balance_after REAL NOT NULL DEFAULT 0,
            annual_leave_entitlement_snapshot REAL NOT NULL DEFAULT 0,
            annual_leave_note_snapshot TEXT,
            late_deduction INTEGER NOT NULL DEFAULT 0,
            total_additions INTEGER NOT NULL DEFAULT 0,
            total_deductions INTEGER NOT NULL DEFAULT 0,
            final_salary INTEGER NOT NULL DEFAULT 0,
            system_note TEXT,
            manual_note TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','settled')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            settled_at TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            FOREIGN KEY(employee_id) REFERENCES employee_master(employee_id) ON DELETE RESTRICT,
            UNIQUE(year, month, employee_id)
        );

        CREATE TABLE IF NOT EXISTS salary_adjustments (
            adjustment_id TEXT PRIMARY KEY,
            salary_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('addition','deduction')),
            item_name TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            FOREIGN KEY(salary_id) REFERENCES salary_monthly(salary_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS annual_leave_history (
            id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, date TEXT NOT NULL,
            type TEXT NOT NULL, days REAL NOT NULL DEFAULT 0, hours REAL NOT NULL DEFAULT 0,
            note TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(employee_id) REFERENCES employee_master(employee_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS salary_rules (
            rule_key TEXT PRIMARY KEY, rule_value TEXT NOT NULL, updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS employee_annual_leave_settings (
            employee_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            annual_entitlement REAL NOT NULL DEFAULT 0,
            opening_balance REAL NOT NULL DEFAULT 0,
            opening_month INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(employee_id, year),
            FOREIGN KEY(employee_id) REFERENCES employee_master(employee_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS salary_deletion_audit (
            audit_id TEXT PRIMARY KEY,
            salary_id TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            adjustments_json TEXT NOT NULL,
            deleted_at TEXT NOT NULL
        );
        """
    )
    # Lightweight migrations for databases created by schema version 1.
    _add_column_if_missing(conn, "suppliers", "sheet_row_key", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "movement_key", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "sheet_name", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "sheet_row_key", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "supplier_id", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "supplier_name", "TEXT")
    _add_column_if_missing(conn, "sheet_rows", "sheet_updated_at", "TEXT")
    _add_column_if_missing(conn, "sheet_rows", "last_seen_at", "TEXT")
    _add_column_if_missing(conn, "recipes", "oem_multiplier", "REAL NOT NULL DEFAULT 1")
    for table_name in ("color_powders", "suppliers", "recipes"):
        _add_column_if_missing(conn, table_name, "lifecycle_status", "TEXT NOT NULL DEFAULT 'active'")
        _add_column_if_missing(conn, table_name, "deleted_at", "TEXT")
        _add_column_if_missing(conn, table_name, "delete_reason", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "reversal_of_movement_key", "TEXT")
    _add_column_if_missing(conn, "inventory_movements", "reversed_at", "TEXT")
    _add_column_if_missing(conn, "production_orders", "cancelled_at", "TEXT")
    _add_column_if_missing(conn, "production_orders", "cancel_reason", "TEXT")
    _add_column_if_missing(conn, "employee_master", "special_addition_enabled", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "employee_master", "special_addition_amount", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "employee_master", "special_addition_note", "TEXT")
    _add_column_if_missing(conn, "employee_master", "default_deduction_enabled", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "employee_master", "default_deduction_amount", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "employee_master", "default_deduction_note", "TEXT")
    _add_column_if_missing(conn, "salary_monthly", "annual_leave_entitlement_snapshot", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "salary_monthly", "annual_leave_note_snapshot", "TEXT")
    _add_column_if_missing(conn, "salary_monthly", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "salary_monthly", "deleted_at", "TEXT")
    conn.execute(
        """UPDATE recipes
           SET oem_multiplier = COALESCE(
               (SELECT CAST(json_extract(sheet_rows.payload_json, '$."代工倍率"') AS REAL)
                FROM sheet_rows
                WHERE sheet_rows.sheet_name='配方管理'
                  AND sheet_rows.row_key=recipes.recipe_id
                  AND TRIM(COALESCE(json_extract(sheet_rows.payload_json, '$."代工倍率"'), '')) != ''),
               oem_multiplier
           )
           WHERE recipes.source != 'app'"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO production_orders(
               production_order_id, production_date, recipe_id, color, customer_name,
               payload_json, source, version, created_at, updated_at, last_synced_at)
           SELECT row_key,
                  json_extract(payload_json, '$."生產日期"'),
                  CASE WHEN EXISTS(
                      SELECT 1 FROM recipes
                      WHERE recipes.recipe_id=json_extract(sheet_rows.payload_json, '$."配方編號"')
                  ) THEN NULLIF(json_extract(payload_json, '$."配方編號"'), '') ELSE NULL END,
                  json_extract(payload_json, '$."顏色"'),
                  json_extract(payload_json, '$."客戶名稱"'),
                  payload_json, 'google_sheets_import', 1,
                  COALESCE(last_synced_at, created_at), updated_at, last_synced_at
           FROM sheet_rows WHERE sheet_name='生產單'"""
    )
    for position in range(1, 5):
        conn.execute(
            f"""INSERT OR IGNORE INTO production_order_packages(
                    production_order_id, position, package_weight, package_count, created_at, updated_at)
                SELECT row_key, ?,
                       CAST(COALESCE(NULLIF(json_extract(payload_json, '$."包裝重量{position}"'), ''), 0) AS REAL),
                       CAST(COALESCE(NULLIF(json_extract(payload_json, '$."包裝份數{position}"'), ''), 0) AS REAL),
                       COALESCE(last_synced_at, created_at), updated_at
                FROM sheet_rows
                WHERE sheet_name='生產單'
                  AND (TRIM(COALESCE(json_extract(payload_json, '$."包裝重量{position}"'), '')) != ''
                       OR TRIM(COALESCE(json_extract(payload_json, '$."包裝份數{position}"'), '')) != '')""",
            (position,),
        )
    conn.execute("UPDATE sheet_rows SET last_seen_at = COALESCE(last_seen_at, updated_at, ?) WHERE last_seen_at IS NULL", (utc_now_iso(),))
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now_iso()),
    )
    _execute_script(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_color_powders_updated_at ON color_powders(updated_at);
        CREATE INDEX IF NOT EXISTS idx_color_powders_category ON color_powders(category);
        CREATE INDEX IF NOT EXISTS idx_inventory_powder_date ON inventory_movements(colorpowder_id, movement_date);
        CREATE INDEX IF NOT EXISTS idx_inventory_updated_at ON inventory_movements(updated_at);
        CREATE INDEX IF NOT EXISTS idx_inventory_supplier_id ON inventory_movements(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_recipes_updated_at ON recipes(updated_at);
        CREATE INDEX IF NOT EXISTS idx_recipes_customer_id ON recipes(customer_id);
        CREATE INDEX IF NOT EXISTS idx_recipe_components_powder ON recipe_components(colorpowder_id);
        CREATE INDEX IF NOT EXISTS idx_production_orders_recipe ON production_orders(recipe_id);
        CREATE INDEX IF NOT EXISTS idx_production_orders_date ON production_orders(production_date);
        CREATE INDEX IF NOT EXISTS idx_outsourcing_orders_production ON outsourcing_orders(production_order_id);
        CREATE INDEX IF NOT EXISTS idx_outsourcing_deliveries_order ON outsourcing_deliveries(outsourcing_order_id);
        CREATE INDEX IF NOT EXISTS idx_outsourcing_returns_order ON outsourcing_returns(outsourcing_order_id);
        CREATE INDEX IF NOT EXISTS idx_customers_lifecycle ON customers(lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_pantone_records_code ON pantone_records(pantone_code);
        CREATE INDEX IF NOT EXISTS idx_sample_records_date ON sample_records(sample_date);
        CREATE INDEX IF NOT EXISTS idx_customer_inventory_customer ON customer_inventory_records(customer_name);
        CREATE INDEX IF NOT EXISTS idx_customer_inventory_recipe ON customer_inventory_records(recipe_id);
        CREATE INDEX IF NOT EXISTS idx_carwash_inventory_product ON carwash_inventory_movements(product_id);
        CREATE INDEX IF NOT EXISTS idx_trial_records_date ON trial_records(trial_date);
        CREATE INDEX IF NOT EXISTS idx_trial_records_customer ON trial_records(customer_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_sheet_row_key ON suppliers(sheet_row_key) WHERE sheet_row_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_movement_key ON inventory_movements(movement_key) WHERE movement_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_inventory_sheet_row ON inventory_movements(sheet_name, sheet_row_key);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_single_reversal
            ON inventory_movements(reversal_of_movement_key)
            WHERE reversal_of_movement_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_color_powders_lifecycle ON color_powders(lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_suppliers_lifecycle ON suppliers(lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_recipes_lifecycle ON recipes(lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_production_orders_status ON production_orders(status);
        CREATE INDEX IF NOT EXISTS idx_sheet_rows_updated_at ON sheet_rows(sheet_name, updated_at);
        CREATE INDEX IF NOT EXISTS idx_sheet_rows_hash ON sheet_rows(sheet_name, row_hash);
        CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status ON sync_conflicts(status, detected_at);
        CREATE INDEX IF NOT EXISTS idx_sync_outbox_pending ON sync_outbox(status, sheet_name, created_at);
        CREATE INDEX IF NOT EXISTS idx_salary_month ON salary_monthly(year, month);
        CREATE INDEX IF NOT EXISTS idx_salary_employee ON salary_monthly(employee_id);
        CREATE INDEX IF NOT EXISTS idx_adjustments_salary ON salary_adjustments(salary_id);
        CREATE INDEX IF NOT EXISTS idx_annual_leave_employee_date ON annual_leave_history(employee_id, date);
        CREATE INDEX IF NOT EXISTS idx_salary_active_month ON salary_monthly(year, month, is_deleted, status);
        """
    )
    now = utc_now_iso()
    for key, value in (("monthly_days", "30"), ("standard_hours", "8"),
                       ("leave_affects_attendance", "false"),
                       ("leave_affects_cooling", "false"),
                       ("leave_affects_allowance", "false")):
        conn.execute("INSERT OR IGNORE INTO salary_rules(rule_key, rule_value, updated_at) VALUES (?, ?, ?)",
                     (key, value, now))

def initialize_database(db_path: str | Path | None = None) -> Path:
    """Create/validate the local SQLite database, schema, and indexes automatically."""
    path = get_db_path(db_path)
    with connect(path) as conn:
        _initialize_schema(conn)
    return path


def _connect_turso(config: DatabaseConfig):
    try:
        import libsql
    except ImportError as exc:
        raise DatabaseStartupError("Turso backend requires the libsql package to be installed.") from exc
    return libsql.connect(database=config.turso_database_url, auth_token=config.turso_auth_token)


def initialize_database_from_config(config: DatabaseConfig) -> str | Path:
    """Initialize configured backend; full Turso credentials never fall back to SQLite."""
    if config.backend == "sqlite":
        return initialize_database(config.path)
    if config.backend != "turso":
        raise DatabaseStartupError(f"Unsupported database backend: {config.backend}")
    client = _connect_turso(config)
    try:
        _initialize_schema(client)
        if hasattr(client, "commit"):
            client.commit()
    except Exception as exc:
        raise DatabaseStartupError(f"Could not initialize Turso database schema v{SCHEMA_VERSION}: {exc}") from exc
    finally:
        client.close()
    return "turso"


def _database_health_from_connection(config: DatabaseConfig, conn: SqlExecutor) -> DatabaseHealth:
    """Collect startup health information using an already-open connection."""
    select_1_ok = bool(conn.execute("SELECT 1").fetchone()[0] == 1)
    schema_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    schema_version = schema_row[0] if schema_row else None
    table_rows = conn.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall()
    existing_tables = {row[0] for row in table_rows}
    missing_required_columns = {}
    for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        missing = required_columns - existing_columns
        if missing:
            missing_required_columns[table_name] = missing
    return DatabaseHealth(
        config.backend,
        select_1_ok,
        schema_version,
        existing_tables,
        missing_required_columns,
    )


def initialize_database_with_health(config: DatabaseConfig) -> tuple[str | Path, DatabaseHealth]:
    """Initialize and validate the backend over a single database connection.

    Turso connection setup is a network operation. Combining schema initialization
    and health validation avoids opening a second connection during process startup.
    """
    initialized: str | Path = get_db_path(config.path) if config.backend == "sqlite" else "turso"
    try:
        with connect_from_config(config) as conn:
            _initialize_schema(conn)
            health = _database_health_from_connection(config, conn)
    except Exception as exc:
        raise DatabaseStartupError(
            f"Could not initialize or validate {config.backend} database schema "
            f"v{SCHEMA_VERSION}: {exc}"
        ) from exc
    return initialized, health


def database_health_check(config: DatabaseConfig) -> DatabaseHealth:
    """Run non-destructive startup checks: SELECT 1, schema_migrations, and table presence."""
    conn_manager = None
    client = None
    conn = None
    try:
        if config.backend == "sqlite":
            conn_manager = connect(config.path)
            conn = conn_manager.__enter__()
        elif config.backend == "turso":
            client = _connect_turso(config)
            conn = client
        else:
            raise DatabaseStartupError(f"Unsupported database backend: {config.backend}")
        return _database_health_from_connection(config, conn)
    except DatabaseStartupError:
        raise
    except Exception as exc:
        raise DatabaseStartupError(f"Database health check failed for backend {config.backend}: {exc}") from exc
    finally:
        if conn_manager is not None and conn is not None:
            conn_manager.__exit__(None, None, None)
        if client is not None:
            client.close()


def backup_database(db_path: str | Path | None = None, backup_dir: str | Path = "data/backups") -> Path:
    """Create a timestamped SQLite file backup without modifying Google Sheets."""
    source = initialize_database(db_path)
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"colorpowder-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
    shutil.copy2(source, target)
    return target


def record_sync_log(conn: sqlite3.Connection, *, sync_name: str, direction: str, status: str,
                    started_at: str, finished_at: str | None = None, read_count: int = 0,
                    written_count: int = 0, error_count: int = 0, message: str | None = None) -> None:
    conn.execute(
        """INSERT INTO sync_log(sync_name, direction, status, started_at, finished_at,
               read_count, written_count, error_count, message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sync_name, direction, status, started_at, finished_at, read_count, written_count, error_count, message),
    )


def record_sync_conflict(conn: sqlite3.Connection, *, entity_type: str, entity_id: str,
                         sqlite_payload: dict[str, Any] | None, sheet_payload: dict[str, Any] | None,
                         reason: str) -> None:
    conn.execute(
        """INSERT INTO sync_conflicts(entity_type, entity_id, sqlite_payload_json, sheet_payload_json, reason, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entity_type, entity_id,
         json.dumps(sqlite_payload, ensure_ascii=False, default=str) if sqlite_payload is not None else None,
         json.dumps(sheet_payload, ensure_ascii=False, default=str) if sheet_payload is not None else None,
         reason, utc_now_iso()),
    )


def enqueue_sheet_sync(
    conn: sqlite3.Connection,
    *,
    sheet_name: str,
    row_key: str,
    operation: str,
    payload: dict[str, Any] | None,
    entity_version: int,
) -> None:
    """Durably queue one entity version for delivery to Google Sheets."""
    if operation not in {"insert", "update", "delete"}:
        raise ValueError(f"Unsupported sync operation: {operation}")
    conn.execute(
        """INSERT INTO sync_outbox(
               sheet_name, row_key, operation, payload_json, entity_version, created_at
           ) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(sheet_name, row_key, entity_version) DO NOTHING""",
        (
            sheet_name,
            row_key,
            operation,
            json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None,
            entity_version,
            utc_now_iso(),
        ),
    )


def upsert_sheet_row(conn: sqlite3.Connection, sheet_name: str, row_key: str, payload: dict[str, Any],
                     row_hash: str, sheet_updated_at: str | None = None) -> None:
    observed_at = utc_now_iso()
    conn.execute(
        """INSERT INTO sheet_rows(sheet_name, row_key, payload_json, row_hash, created_at, updated_at,
               sheet_updated_at, last_seen_at, last_synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(sheet_name, row_key) DO UPDATE SET
               payload_json=excluded.payload_json,
               row_hash=excluded.row_hash,
               updated_at=CASE
                   WHEN sheet_rows.row_hash != excluded.row_hash THEN excluded.updated_at
                   ELSE sheet_rows.updated_at
               END,
               sheet_updated_at=excluded.sheet_updated_at,
               last_seen_at=excluded.last_seen_at,
               last_synced_at=excluded.last_synced_at""",
        (sheet_name, row_key, json.dumps(payload, ensure_ascii=False), row_hash,
         observed_at, sheet_updated_at or observed_at, sheet_updated_at, observed_at, observed_at),
    )
