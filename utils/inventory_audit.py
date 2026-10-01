"""Persistence helpers for inventory-audit confirmations."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


def _is_checked(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _inventory_date(value: object) -> datetime:
    """Parse the date formats historically used by inventory movements."""
    text = str(value or "").strip().replace("/", "-")
    if not text:
        return datetime.min
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def latest_initial_inventory_record(
    records: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pick the newest initial record, preferring the last write on date ties.

    Old Sheet data can contain several ``初始`` rows for one powder on the same
    date.  Repository results are in movement creation order, so the later row
    must win when dates tie; choosing only by date would keep the stale first row.
    """
    candidates = [
        (index, record)
        for index, record in enumerate(records)
        if str(record.get("類型") or record.get("movement_type") or "").strip() == "初始"
        and str(record.get("沖銷狀態") or "有效").strip() == "有效"
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _inventory_date(item[1].get("日期") or item[1].get("movement_date")),
            item[0],
        ),
    )[1]


def duplicate_initial_inventory_sync_ids(
    records: Iterable[dict[str, Any]], powder_id: str,
) -> list[str]:
    """Return older exact duplicates, scanning every powder when ID is blank."""
    groups: dict[tuple[object, ...], list[str]] = {}
    target = str(powder_id or "").strip()
    for record in records:
        if str(record.get("類型") or "").strip() != "初始":
            continue
        record_powder_id = str(record.get("色粉編號") or "").strip()
        if target and record_powder_id != target:
            continue
        if str(record.get("沖銷狀態") or "有效").strip() != "有效":
            continue
        sync_id = str(record.get("_sync_id") or "").strip()
        if not sync_id:
            continue
        try:
            quantity = float(record.get("數量") or 0)
        except (TypeError, ValueError):
            continue
        key = (
            record_powder_id, _inventory_date(record.get("日期")), quantity,
            str(record.get("單位") or "g").strip().casefold(),
            str(record.get("備註") or "").strip(),
        )
        groups.setdefault(key, []).append(sync_id)
    return [sync_id for ids in groups.values() for sync_id in ids[:-1]]


def recent_confirmed_audit_keys(
    record_path: str | Path,
    audit_date: str,
    *,
    now: datetime | None = None,
    retention: timedelta = timedelta(hours=24),
) -> set[tuple[str, str]]:
    """Return ``(location, powder_id)`` confirmed on this audit date recently.

    Confirmations intentionally require both the same audit date and a save time
    inside the retention window.  This keeps confirmed rows hidden throughout the
    day's repeated analyses without carrying them into another day's count.
    """
    path = Path(record_path)
    audit_date = str(audit_date or "").strip()
    if not path.exists() or not audit_date:
        return set()

    current_time = now or datetime.now()
    cutoff = current_time - retention
    confirmed: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("盤點日期") or "").strip() != audit_date:
                continue
            if not _is_checked(row.get("已確認")):
                continue
            try:
                saved_at = datetime.fromisoformat(str(row.get("儲存時間") or "").strip())
            except ValueError:
                continue
            if not cutoff <= saved_at <= current_time:
                continue
            powder_id = str(row.get("色粉編號") or "").strip()
            if powder_id:
                confirmed.add((str(row.get("儲位") or "").strip(), powder_id))
    return confirmed
