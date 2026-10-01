import csv
from datetime import datetime, timedelta

from utils.inventory_audit import recent_confirmed_audit_keys


def _write_records(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["盤點日期", "儲存時間", "已確認", "儲位", "色粉編號"]
        )
        writer.writeheader()
        writer.writerows(rows)


def test_recent_confirmations_are_hidden_only_for_same_audit_date(tmp_path):
    record = tmp_path / "inventory_audit.csv"
    _write_records(record, [
        {"盤點日期": "2026-10-01", "儲存時間": "2026-10-01 09:00:00", "已確認": True,
         "儲位": "A", "色粉編號": "P001"},
        {"盤點日期": "2026-09-30", "儲存時間": "2026-10-01 09:00:00", "已確認": True,
         "儲位": "B", "色粉編號": "P002"},
        {"盤點日期": "2026-10-01", "儲存時間": "2026-10-01 09:00:00", "已確認": False,
         "儲位": "C", "色粉編號": "P003"},
    ])

    assert recent_confirmed_audit_keys(
        record, "2026-10-01", now=datetime(2026, 10, 1, 12, 0),
    ) == {("A", "P001")}


def test_confirmation_expires_after_24_hours(tmp_path):
    record = tmp_path / "inventory_audit.csv"
    _write_records(record, [
        {"盤點日期": "2026-10-01", "儲存時間": "2026-10-01 08:00:00", "已確認": True,
         "儲位": "A", "色粉編號": "P001"},
    ])

    assert recent_confirmed_audit_keys(
        record, "2026-10-01", now=datetime(2026, 10, 2, 8, 0),
    ) == {("A", "P001")}
    assert recent_confirmed_audit_keys(
        record, "2026-10-01", now=datetime(2026, 10, 2, 8, 0) + timedelta(seconds=1),
    ) == set()
