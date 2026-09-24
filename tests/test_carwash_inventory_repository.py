from datetime import date

from utils.carwash_inventory_repository import (
    archive_carwash_inventory_movement,
    calculate_carwash_inventory_balances,
    list_carwash_inventory_movements,
    save_carwash_inventory_movement,
)
from utils.database import DatabaseConfig, connect, initialize_database
from utils.inventory_repository import is_carwash_transfer_inventory_movement
from utils.sheet_import import import_sheet_values, missing_inventory_sync_id_updates


def config(tmp_path):
    path = tmp_path / "carwash.db"
    initialize_database(path)
    return path, DatabaseConfig(backend="sqlite", path=path)


def test_carwash_transfer_inventory_movement_is_identified_by_system_note():
    assert is_carwash_transfer_inventory_movement({"備註": "洗車廠出庫轉入"})
    assert is_carwash_transfer_inventory_movement(
        {"備註": "  洗車廠出庫轉入（例行補貨）  "}
    )
    assert not is_carwash_transfer_inventory_movement({"備註": "一般採購"})
    assert not is_carwash_transfer_inventory_movement({"備註": None})


def test_movement_create_update_archive_outbox(tmp_path):
    path, db_config = config(tmp_path)
    row = {
        "類型": "入庫", "貨品編號": "CW-01", "入庫日期": "2026-08-24",
        "數量": 10, "單位": "KG", "登記人": "德",
    }
    created = save_carwash_inventory_movement(db_config, row, create=True)
    assert created["movement_id"].startswith("carwash-")
    row.update({"_sync_id": created["movement_id"], "數量": 12})
    save_carwash_inventory_movement(db_config, row, create=False)
    archive_carwash_inventory_movement(db_config, created["movement_id"], reason="測試")
    assert list_carwash_inventory_movements(db_config) == []
    with connect(path) as conn:
        operations = conn.execute(
            "SELECT operation FROM sync_outbox ORDER BY entity_version"
        ).fetchall()
    assert [item[0] for item in operations] == ["insert", "update", "delete"]


def test_initial_import_and_prepare(tmp_path):
    path, _ = config(tmp_path)
    values = [
        ["類型", "初始庫存日期", "初始數量", "貨品編號", "入庫日期", "出庫日期", "數量", "單位", "登記人", "備註", "_sync_id"],
        ["初始庫存", "2026-08-24", "20", "CW-01", "", "", "", "KG", "德", "", "cw-1"],
    ]
    assert import_sheet_values("洗車廠庫存", values, db_path=path, abort_on_issues=True).inserted_or_updated == 1
    assert import_sheet_values("洗車廠庫存", values, db_path=path, dry_run=True).unchanged == 1
    missing = [values[0], values[1][:-1] + [""]]
    assert missing_inventory_sync_id_updates(missing, id_factory=lambda: "cw-2") == [(2, 11, "cw-2")]


def test_import_normalizes_legacy_outbound_date_in_inbound_column(tmp_path):
    path, _ = config(tmp_path)
    values = [
        ["類型", "初始庫存日期", "初始數量", "貨品編號", "入庫日期", "出庫日期", "數量", "單位", "登記人", "備註", "_sync_id"],
        ["出庫", "", "", "ABS709", "2026-07-08", "", "375", "KG", "德", "", "legacy-out-1"],
    ]
    result = import_sheet_values("洗車廠庫存", values, db_path=path, abort_on_issues=True)
    assert result.inserted_or_updated == 1
    assert result.errors == []
    assert "已正規化" in result.warnings[0]
    with connect(path) as conn:
        movement = conn.execute(
            "SELECT inbound_date,outbound_date FROM carwash_inventory_movements WHERE movement_id='legacy-out-1'"
        ).fetchone()
    assert tuple(movement) == (None, "2026-07-08")


def test_calculate_balances_uses_latest_initial_and_following_movements():
    records = [
        {"movement_type": "初始庫存", "initial_date": "2026-01-01", "initial_quantity": 20,
         "product_id": " MB-01 ", "unit": "KG"},
        {"movement_type": "入庫", "inbound_date": "2026-01-03", "quantity": 7,
         "product_id": "mb-01", "unit": "KG"},
        {"movement_type": "初始庫存", "initial_date": "2026-02-01", "initial_quantity": 10,
         "product_id": "MB-01", "unit": "KG"},
        {"movement_type": "出庫", "outbound_date": "2026-02-02", "quantity": 2.5,
         "product_id": "MB-01", "unit": "KG"},
        {"movement_type": "入庫", "inbound_date": "2026-04-01", "quantity": 99,
         "product_id": "MB-01", "unit": "KG"},
        {"movement_type": "初始庫存", "initial_date": "2026-05-01", "initial_quantity": 500,
         "product_id": "MB-01", "unit": "KG"},
    ]

    assert calculate_carwash_inventory_balances(
        records, as_of=date(2026, 3, 1)
    ) == {"mb-01": (7.5, "KG")}
