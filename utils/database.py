"""SQLite database layer for the color powder management system.

SQLite is the source of truth. Google Sheets is treated as a synchronized copy
and reporting/admin surface; web features should read/write through this module
or service/repository wrappers instead of calling Sheets directly.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("data/colorpowder.db")
SCHEMA_VERSION = 2


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path = DEFAULT_DB_PATH


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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def initialize_database(db_path: str | Path | None = None) -> Path:
    """Create/validate the SQLite database, schema, and indexes automatically."""
    path = get_db_path(db_path)
    with connect(path) as conn:
        conn.executescript(
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
        _add_column_if_missing(conn, "sheet_rows", "sheet_updated_at", "TEXT")
        _add_column_if_missing(conn, "sheet_rows", "last_seen_at", "TEXT")
        conn.execute("UPDATE sheet_rows SET last_seen_at = COALESCE(last_seen_at, updated_at, ?) WHERE last_seen_at IS NULL", (utc_now_iso(),))
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now_iso()),
        )
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_color_powders_updated_at ON color_powders(updated_at);
            CREATE INDEX IF NOT EXISTS idx_color_powders_category ON color_powders(category);
            CREATE INDEX IF NOT EXISTS idx_inventory_powder_date ON inventory_movements(colorpowder_id, movement_date);
            CREATE INDEX IF NOT EXISTS idx_inventory_updated_at ON inventory_movements(updated_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_sheet_row_key ON suppliers(sheet_row_key) WHERE sheet_row_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_movement_key ON inventory_movements(movement_key) WHERE movement_key IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_inventory_sheet_row ON inventory_movements(sheet_name, sheet_row_key);
            CREATE INDEX IF NOT EXISTS idx_sheet_rows_updated_at ON sheet_rows(sheet_name, updated_at);
            CREATE INDEX IF NOT EXISTS idx_sheet_rows_hash ON sheet_rows(sheet_name, row_hash);
            CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status ON sync_conflicts(status, detected_at);
            """
        )
    return path


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
