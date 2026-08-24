"""Controlled Google Sheets to Turso synchronization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from uuid import uuid4

from .database import DatabaseConfig, initialize_database_from_config
from .sheet_import import ImportAbortedError, import_sheet_values, read_worksheet_values_with_retry
from .sync_worker import SYNC_WORKER_LOCK_NAME, acquire_worker_lock, release_worker_lock


INBOUND_SHEETS = (
    "色粉管理", "供應商管理", "客戶名單", "配方管理", "Pantone色號表", "樣品記錄", "庫存記錄", "生產單",
    "代工管理", "代工送達記錄", "代工載回記錄",
)


@dataclass
class InboundWorkerResult:
    dry_run: bool
    max_changes: int
    lock_acquired: bool = True
    preflight: list[dict[str, Any]] = field(default_factory=list)
    applied: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        results = self.applied if self.applied else self.preflight
        return self.lock_acquired and not self.errors and all(
            not item.get("errors")
            and not item.get("duplicate_ids")
            and not item.get("conflicts")
            for item in results
        )


def run_controlled_inbound_worker(
    spreadsheet,
    *,
    db_config: DatabaseConfig,
    dry_run: bool = True,
    sheet_names: Iterable[str] | None = None,
    max_changes: int = 25,
    lock_ttl_seconds: int = 900,
) -> InboundWorkerResult:
    """Preflight all selected Sheets, then atomically apply each safe snapshot.

    Missing Sheet rows are never interpreted as deletes. A write pass uses the
    exact values that passed preflight and stops before writing when any selected
    Sheet has validation errors, duplicate IDs, conflicts, or too many changes.
    """
    if max_changes < 1:
        raise ValueError("max_changes must be at least 1")
    names = list(sheet_names or INBOUND_SHEETS)
    unsupported = [name for name in names if name not in INBOUND_SHEETS]
    if unsupported:
        raise ValueError(f"Unsupported inbound sheets: {', '.join(unsupported)}")

    initialize_database_from_config(db_config)
    result = InboundWorkerResult(dry_run=dry_run, max_changes=max_changes)
    snapshots: list[tuple[str, list[list[Any]]]] = []

    for sheet_name in names:
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            values = read_worksheet_values_with_retry(worksheet)
            snapshots.append((sheet_name, values))
            preflight = import_sheet_values(
                sheet_name,
                values,
                db_config=db_config,
                dry_run=True,
                initialize_schema=False,
            )
            result.preflight.append(asdict(preflight))
        except Exception as exc:
            result.errors.append(f"{sheet_name}: {type(exc).__name__}: {exc}")
            return result

    change_count = sum(
        item["to_insert"] + item["to_update"] for item in result.preflight
    )
    if change_count > max_changes:
        result.errors.append(
            f"preflight found {change_count} changes; controlled limit is {max_changes}"
        )
    if not result.ok or dry_run:
        return result

    owner_id = f"inbound-worker-{uuid4().hex}"
    result.lock_acquired = acquire_worker_lock(
        db_config,
        lock_name=SYNC_WORKER_LOCK_NAME,
        owner_id=owner_id,
        ttl_seconds=lock_ttl_seconds,
    )
    if not result.lock_acquired:
        result.errors.append("another Turso/Sheets worker currently holds the synchronization lock")
        return result

    try:
        for sheet_name, values in snapshots:
            try:
                applied = import_sheet_values(
                    sheet_name,
                    values,
                    db_config=db_config,
                    dry_run=False,
                    initialize_schema=False,
                    abort_on_issues=True,
                )
                result.applied.append(asdict(applied))
            except ImportAbortedError as exc:
                result.applied.append(asdict(exc.result))
                result.errors.append(f"{sheet_name}: apply aborted after safety recheck")
                break
            except Exception as exc:
                result.errors.append(f"{sheet_name}: {type(exc).__name__}: {exc}")
                break
    finally:
        release_worker_lock(
            db_config, lock_name=SYNC_WORKER_LOCK_NAME, owner_id=owner_id
        )
    return result
