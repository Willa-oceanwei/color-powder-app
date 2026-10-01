"""Persistence helpers for inventory-audit confirmations."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path


def _is_checked(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


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
