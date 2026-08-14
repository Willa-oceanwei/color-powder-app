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
SCHEMA_VERSION = 3
LOGGER = logging.getLogger(__name__)
MAIN_TABLES = {
    "color_powders",
    "suppliers",
    "supplier_aliases",
    "inventory_movements",
    "sheet_rows",
    "sync_state",
    "sync_log",
    "sync_conflicts",
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

    @property
    def main_tables_exist(self) -> bool:
        return MAIN_TABLES.issubset(self.existing_tables)


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
        f"Database health: {'OK' if health.select_1_ok and health.main_tables_exist else 'FAILED'}",
        f"Schema version: {health.schema_version}",
        f"Main tables present: {health.main_tables_exist}",
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
            source TEXT NOT NULL DEFAULT 'sqlite',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT,
            FOREIGN KEY (colorpowder_id) REFERENCES color_powders(colorpowder_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            UNIQUE(sheet_name, sheet_row_key)
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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_sheet_row_key ON suppliers(sheet_row_key) WHERE sheet_row_key IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_movement_key ON inventory_movements(movement_key) WHERE movement_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_inventory_sheet_row ON inventory_movements(sheet_name, sheet_row_key);
        CREATE INDEX IF NOT EXISTS idx_sheet_rows_updated_at ON sheet_rows(sheet_name, updated_at);
        CREATE INDEX IF NOT EXISTS idx_sheet_rows_hash ON sheet_rows(sheet_name, row_hash);
        CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status ON sync_conflicts(status, detected_at);
        """
    )

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
        select_1_ok = bool(conn.execute("SELECT 1").fetchone()[0] == 1)
        schema_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = schema_row[0] if schema_row else None
        table_rows = conn.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall()
        existing_tables = {row[0] for row in table_rows}
        return DatabaseHealth(config.backend, select_1_ok, schema_version, existing_tables)
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
