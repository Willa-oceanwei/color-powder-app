"""Bounded safe-mode delivery of Turso outbox events to Google Sheets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from .database import DatabaseConfig, connect_from_config, initialize_database_from_config
from .sheet_export import (
    ExportResult,
    sync_color_powder_outbox,
    sync_customer_outbox,
    sync_inventory_outbox,
    sync_outsourcing_delivery_outbox,
    sync_outsourcing_order_outbox,
    sync_outsourcing_return_outbox,
    sync_pantone_outbox,
    sync_production_order_outbox,
    sync_recipe_outbox,
    sync_supplier_outbox,
)
from .sheet_import import read_worksheet_values_with_retry


SAFE_SHEETS: tuple[tuple[str, Callable[..., ExportResult]], ...] = (
    ("色粉管理", sync_color_powder_outbox),
    ("供應商管理", sync_supplier_outbox),
    ("客戶名單", sync_customer_outbox),
    ("Pantone色號表", sync_pantone_outbox),
    ("配方管理", sync_recipe_outbox),
    ("庫存記錄", sync_inventory_outbox),
    ("生產單", sync_production_order_outbox),
    ("代工管理", sync_outsourcing_order_outbox),
    ("代工送達記錄", sync_outsourcing_delivery_outbox),
    ("代工載回記錄", sync_outsourcing_return_outbox),
)
SYNC_WORKER_LOCK_NAME = "turso-sheets-worker"


@dataclass
class SafeWorkerResult:
    dry_run: bool
    batch_size: int
    allow_deletes: bool = False
    lock_acquired: bool = True
    sheets: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.lock_acquired and not self.errors and all(
            not item.get("errors") and not item.get("conflicts") for item in self.sheets
        )


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def acquire_worker_lock(
    config: DatabaseConfig, *, lock_name: str, owner_id: str, ttl_seconds: int = 900
) -> bool:
    """Atomically acquire an expiring database lock for one delivery worker."""
    if ttl_seconds < 1:
        raise ValueError("ttl_seconds must be at least 1")
    now = datetime.now(timezone.utc)
    with connect_from_config(config) as conn:
        claimed = conn.execute(
            """INSERT INTO sync_worker_locks(lock_name, owner_id, acquired_at, expires_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(lock_name) DO UPDATE SET
                   owner_id=excluded.owner_id,
                   acquired_at=excluded.acquired_at,
                   expires_at=excluded.expires_at
               WHERE sync_worker_locks.expires_at <= ?
                  OR sync_worker_locks.owner_id = excluded.owner_id
               RETURNING owner_id""",
            (
                lock_name,
                owner_id,
                _utc_iso(now),
                _utc_iso(now + timedelta(seconds=ttl_seconds)),
                _utc_iso(now),
            ),
        ).fetchone()
    return claimed is not None


def release_worker_lock(config: DatabaseConfig, *, lock_name: str, owner_id: str) -> None:
    with connect_from_config(config) as conn:
        conn.execute(
            "DELETE FROM sync_worker_locks WHERE lock_name=? AND owner_id=?",
            (lock_name, owner_id),
        )


def run_safe_worker(
    spreadsheet,
    *,
    db_config: DatabaseConfig,
    dry_run: bool = True,
    batch_size: int = 25,
    lock_ttl_seconds: int = 900,
    allow_deletes: bool = False,
) -> SafeWorkerResult:
    """Deliver a bounded batch; deletes require an explicit controlled opt-in."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    initialize_database_from_config(db_config)
    result = SafeWorkerResult(
        dry_run=dry_run, batch_size=batch_size, allow_deletes=allow_deletes
    )
    owner_id = f"safe-worker-{uuid4().hex}"
    lock_name = SYNC_WORKER_LOCK_NAME
    if not dry_run:
        result.lock_acquired = acquire_worker_lock(
            db_config, lock_name=lock_name, owner_id=owner_id, ttl_seconds=lock_ttl_seconds
        )
        if not result.lock_acquired:
            result.errors.append("another safe worker currently holds the delivery lock")
            return result

    remaining = batch_size
    try:
        for sheet_name, sync_function in SAFE_SHEETS:
            if remaining <= 0:
                break
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                values = read_worksheet_values_with_retry(worksheet)
                sheet_result = sync_function(
                    worksheet,
                    values,
                    db_config=db_config,
                    dry_run=dry_run,
                    initialize_schema=False,
                    max_entries=remaining,
                    allow_deletes=allow_deletes,
                )
                result.sheets.append(asdict(sheet_result))
                remaining -= sheet_result.queued
                if not sheet_result.ok:
                    break
            except Exception as exc:
                result.errors.append(f"{sheet_name}: {type(exc).__name__}: {exc}")
                break
    finally:
        if not dry_run and result.lock_acquired:
            release_worker_lock(db_config, lock_name=lock_name, owner_id=owner_id)
    return result
