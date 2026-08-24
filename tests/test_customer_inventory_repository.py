from utils.customer_inventory_repository import (
    archive_customer_inventory_record,
    list_customer_inventory_records,
    save_customer_inventory_record,
)
from utils.database import DatabaseConfig, connect, initialize_database
from utils.sheet_import import import_sheet_values, missing_inventory_sync_id_updates


def config(tmp_path):
    path = tmp_path / "customer_inventory.db"
    initialize_database(path)
    return path, DatabaseConfig(backend="sqlite", path=path)


def test_create_update_archive_are_atomic_with_outbox(tmp_path):
    path, db_config = config(tmp_path)
    row = {"客戶名稱": "甲公司", "配方編號": "R001", "顏色": "紅", "數量": 10, "單位": "kg"}
    created = save_customer_inventory_record(db_config, row, create=True)
    assert created["record_id"].startswith("customer-stock-")
    row.update({"_sync_id": created["record_id"], "數量": 12})
    save_customer_inventory_record(db_config, row, create=False)
    archive_customer_inventory_record(db_config, created["record_id"], reason="測試")
    assert list_customer_inventory_records(db_config) == []
    with connect(path) as conn:
        operations = conn.execute(
            "SELECT operation FROM sync_outbox ORDER BY entity_version"
        ).fetchall()
    assert [item[0] for item in operations] == ["insert", "update", "delete"]


def test_initial_import_and_permanent_id_prepare(tmp_path):
    path, _ = config(tmp_path)
    values = [
        ["客戶名稱", "配方編號", "顏色", "數量", "單位", "備註", "建立時間", "更新時間", "_sync_id"],
        ["甲公司", "R001", "紅", "10", "kg", "", "2026-08-24", "2026-08-24", "stock-1"],
    ]
    result = import_sheet_values("個別客戶庫存", values, db_path=path, abort_on_issues=True)
    assert result.inserted_or_updated == 1
    assert import_sheet_values("個別客戶庫存", values, db_path=path, dry_run=True).unchanged == 1
    missing = [values[0], values[1][:-1] + [""]]
    assert missing_inventory_sync_id_updates(missing, id_factory=lambda: "stock-2") == [(2, 9, "stock-2")]
