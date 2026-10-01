import csv
from datetime import datetime, timedelta

from utils.inventory_audit import (
    duplicate_initial_inventory_sync_ids,
    latest_initial_inventory_record,
    recent_confirmed_audit_keys,
)


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


def test_latest_initial_record_prefers_last_write_when_dates_are_equal():
    records = [
        {"類型": "初始", "色粉編號": "E25P", "日期": "2026/10/01", "數量": "107.61"},
        {"類型": "進貨", "色粉編號": "E25P", "日期": "2026/10/01", "數量": "5"},
        {"類型": "初始", "色粉編號": "E25P", "日期": "2026/10/01", "數量": "111.5"},
    ]

    assert latest_initial_inventory_record(records)["數量"] == "111.5"


def test_latest_initial_record_compares_mixed_historical_date_formats():
    records = [
        {"類型": "初始", "日期": "2026/09/30", "數量": "100"},
        {"類型": "初始", "日期": "2026-10-01", "數量": "120"},
    ]

    assert latest_initial_inventory_record(records)["數量"] == "120"


def test_duplicate_initial_cleanup_only_selects_older_exact_matches():
    records = [
        {"類型": "初始", "色粉編號": "E25P", "日期": "2026/10/01", "數量": "111.5",
         "單位": "kg", "備註": "盤點", "廠商編號": "legacy", "_sync_id": "old", "沖銷狀態": "有效"},
        {"類型": "初始", "色粉編號": "E25P", "日期": "2026-10-01", "數量": 111.5,
         "單位": "KG", "備註": "盤點", "_sync_id": "keep", "沖銷狀態": "有效"},
        {"類型": "初始", "色粉編號": "E25P", "日期": "2026-10-01", "數量": 112,
         "單位": "kg", "備註": "盤點", "_sync_id": "different", "沖銷狀態": "有效"},
    ]

    assert duplicate_initial_inventory_sync_ids(records, "E25P") == ["old"]


def test_latest_initial_record_ignores_cleaned_reversed_duplicate():
    records = [
        {"類型": "初始", "日期": "2026-10-01", "數量": "100", "沖銷狀態": "已沖銷"},
        {"類型": "初始", "日期": "2026-10-01", "數量": "120", "沖銷狀態": "有效"},
    ]

    assert latest_initial_inventory_record(records)["數量"] == "120"


def test_blank_powder_filter_scans_duplicates_across_all_powders():
    records = [
        {"類型": "初始", "色粉編號": "A", "日期": "2026-10-01", "數量": 10,
         "單位": "kg", "備註": "", "_sync_id": "a-old"},
        {"類型": "初始", "色粉編號": "A", "日期": "2026-10-01", "數量": 10,
         "單位": "kg", "備註": "", "_sync_id": "a-keep"},
        {"類型": "初始", "色粉編號": "B", "日期": "2026-10-01", "數量": 10,
         "單位": "kg", "備註": "", "_sync_id": "b-old"},
        {"類型": "初始", "色粉編號": "B", "日期": "2026-10-01", "數量": 10,
         "單位": "kg", "備註": "", "_sync_id": "b-keep"},
    ]

    assert duplicate_initial_inventory_sync_ids(records, "") == ["a-old", "b-old"]
