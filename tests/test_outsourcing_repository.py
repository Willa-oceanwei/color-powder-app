import json

import pytest

from utils.database import DatabaseConfig, connect, initialize_database
from utils.outsourcing_repository import (
    OutsourcingError,
    add_outsourcing_delivery,
    add_outsourcing_return,
    archive_outsourcing_order,
    create_outsourcing_order,
    deactivate_outsourcing_order,
    list_outsourcing_events,
    list_outsourcing_orders,
    restore_outsourcing_order,
    update_outsourcing_order,
)
from utils.production_order_repository import (
    ProductionOrderError,
    create_production_order,
    merge_production_order_packages,
    set_production_order_cancelled,
)
from utils.sheet_import import import_sheet_values, missing_outsourcing_sync_id_updates


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "outsourcing.db"
    initialize_database(path)
    return DatabaseConfig(backend="sqlite", path=path)


def order(order_id="OEM001"):
    return {
        "代工單號": order_id,
        "生產單號": "P001",
        "配方編號": "R001",
        "客戶名稱": "客戶",
        "代工數量": 100,
        "目標載回數量": 105,
        "轉換倍率": 1.05,
        "代工廠商": "弘旭",
        "狀態": "🏭 在廠內",
    }


def test_merge_production_packages_updates_linked_order_total_and_note():
    existing = {
        "生產單號": "P001", "備註": "原備註",
        "包裝重量1": "500", "包裝份數1": "1",
    }
    delta = {
        "生產單號": "P002", "包裝重量1": "500", "包裝份數1": "1",
        "包裝重量2": "250", "包裝份數2": "2",
    }

    merged = merge_production_order_packages(
        existing, delta, note="20260827合併1000Kg共計1500kg"
    )

    assert merged["生產單號"] == "P001"
    assert (merged["包裝重量1"], merged["包裝份數1"]) == ("500", "2")
    assert (merged["包裝重量2"], merged["包裝份數2"]) == ("250", "2")
    assert merged["備註"] == "原備註\n20260827合併1000Kg共計1500kg"


def test_merge_production_packages_rejects_unrepresentable_fifth_weight():
    existing = {
        f"包裝重量{i}": str(i * 100) for i in range(1, 5)
    } | {f"包裝份數{i}": "1" for i in range(1, 5)}

    with pytest.raises(ProductionOrderError, match="超過 4 種"):
        merge_production_order_packages(
            existing, {"包裝重量1": "500", "包裝份數1": "1"}
        )


def test_order_write_and_update_are_atomic_with_outbox(config):
    create_outsourcing_order(config, order())
    changed = order()
    changed["備註"] = "已確認"
    update_outsourcing_order(config, changed)

    assert list_outsourcing_orders(config)[0]["備註"] == "已確認"
    with connect(config.path) as conn:
        versions = conn.execute(
            "SELECT entity_version, operation FROM sync_outbox WHERE sheet_name='代工管理' ORDER BY entity_version"
        ).fetchall()
    assert [tuple(row) for row in versions] == [(1, "insert"), (2, "update")]


def test_delivery_and_return_use_permanent_sync_ids(config):
    create_outsourcing_order(config, order())
    delivery = add_outsourcing_delivery(config, "OEM001", "2026/08/23", 105)
    returned = add_outsourcing_return(config, "OEM001", "2026/08/24", 104)

    assert delivery["_sync_id"].startswith("delivery:")
    assert returned["_sync_id"].startswith("return:")
    assert list_outsourcing_events(config, "delivery")[0]["送達數量"] == "105.0"
    with connect(config.path) as conn:
        events = conn.execute(
            "SELECT sheet_name, row_key, payload_json FROM sync_outbox WHERE sheet_name LIKE '代工%記錄' ORDER BY sheet_name"
        ).fetchall()
    assert len(events) == 2
    assert all(json.loads(row[2])["_sync_id"] == row[1] for row in events)


def test_deactivate_retains_history_and_queues_tombstone(config):
    create_outsourcing_order(config, order())
    add_outsourcing_delivery(config, "OEM001", "2026/08/23", 100)
    deactivate_outsourcing_order(config, "OEM001", reason="輸入錯誤")

    assert list_outsourcing_orders(config) == []
    inactive = list_outsourcing_orders(config, include_inactive=True)[0]
    assert inactive["生命週期"] == "inactive"
    assert list_outsourcing_events(config, "delivery")
    with connect(config.path) as conn:
        tombstone = conn.execute(
            "SELECT operation FROM sync_outbox WHERE sheet_name='代工管理' AND entity_version=2"
        ).fetchone()
    assert tombstone[0] == "delete"


def test_archive_and_restore_queue_all_sheet_copies_without_deleting_history(config):
    create_outsourcing_order(config, order())
    delivery = add_outsourcing_delivery(config, "OEM001", "2026/08/23", 100)
    returned = add_outsourcing_return(config, "OEM001", "2026/08/24", 100)

    archived = archive_outsourcing_order(config, "OEM001", reason="上線測試資料")
    restored = restore_outsourcing_order(config, "OEM001")

    assert archived == restored == {"deliveries": 1, "returns": 1}
    assert list_outsourcing_orders(config)[0]["代工單號"] == "OEM001"
    assert len(list_outsourcing_events(config, "delivery")) == 1
    assert len(list_outsourcing_events(config, "return")) == 1
    with connect(config.path) as conn:
        lifecycle = conn.execute(
            "SELECT lifecycle_status, deleted_at, delete_reason FROM outsourcing_orders WHERE outsourcing_order_id='OEM001'"
        ).fetchone()
        events = conn.execute(
            """SELECT sheet_name, row_key, operation, entity_version
               FROM sync_outbox WHERE row_key IN (?, ?) ORDER BY row_key, entity_version""",
            (delivery["_sync_id"], returned["_sync_id"]),
        ).fetchall()
    assert tuple(lifecycle) == ("active", None, None)
    assert [tuple(row)[2:] for row in events] == [
        ("insert", 1), ("delete", 2), ("insert", 3),
        ("insert", 1), ("delete", 2), ("insert", 3),
    ]


def test_cancelling_production_order_archives_linked_outsourcing_history(config):
    create_production_order(config, {"生產單號": "P001", "生產日期": "2026-09-01"})
    create_outsourcing_order(config, order("OEM001"))
    create_outsourcing_order(config, order("OEM002"))
    delivery = add_outsourcing_delivery(config, "OEM001", "2026/09/01", 100)

    set_production_order_cancelled(config, "P001", cancelled=True, reason="客戶取消")

    assert list_outsourcing_orders(config) == []
    archived = list_outsourcing_orders(config, include_inactive=True)
    assert {item["代工單號"] for item in archived} == {"OEM001", "OEM002"}
    assert {item["停用原因"] for item in archived} == {"生產單取消：客戶取消"}
    with connect(config.path) as conn:
        tombstones = conn.execute(
            """SELECT sheet_name, row_key, operation FROM sync_outbox
               WHERE operation='delete' ORDER BY sheet_name, row_key"""
        ).fetchall()
    assert [tuple(row) for row in tombstones] == [
        ("代工管理", "OEM001", "delete"),
        ("代工管理", "OEM002", "delete"),
        ("代工送達記錄", delivery["_sync_id"], "delete"),
        ("生產單", "P001", "delete"),
    ]


def test_rejects_events_for_unknown_order(config):
    with pytest.raises(OutsourcingError, match="找不到有效代工單"):
        add_outsourcing_delivery(config, "missing", "2026/08/23", 1)


def test_initial_sheet_import_preserves_order_and_event_baselines(config):
    orders = [["代工單號", "代工數量", "目標載回數量", "轉換倍率", "狀態"],
              ["OEM-OLD", "100", "105", "1.05", "🏭 在廠內"]]
    deliveries = [["代工單號", "送達日期", "送達數量", "_sync_id"],
                  ["OEM-OLD", "2026/08/20", "105", "delivery:old-1"]]
    returns = [["代工單號", "載回日期", "載回數量", "_sync_id"],
               ["OEM-OLD", "2026/08/21", "0", "return:old-1"]]

    for sheet_name, values in (("代工管理", orders), ("代工送達記錄", deliveries),
                               ("代工載回記錄", returns)):
        result = import_sheet_values(
            sheet_name, values, db_config=config, abort_on_issues=True,
            initialize_schema=False,
        )
        assert result.ok and result.inserted_or_updated == 1
        verification = import_sheet_values(
            sheet_name, values, db_config=config, dry_run=True, initialize_schema=False,
        )
        assert verification.unchanged == 1

    assert list_outsourcing_orders(config)[0]["代工單號"] == "OEM-OLD"
    assert list_outsourcing_events(config, "delivery")[0]["_sync_id"] == "delivery:old-1"
    assert list_outsourcing_events(config, "return")[0]["載回數量"] == "0"


def test_outsourcing_event_import_rejects_orphan(config):
    values = [["代工單號", "送達日期", "送達數量", "_sync_id"],
              ["MISSING", "2026/08/20", "5", "delivery:orphan"]]
    result = import_sheet_values(
        "代工送達記錄", values, db_config=config, dry_run=True,
        initialize_schema=False,
    )
    assert not result.ok
    assert "unknown 代工單號 MISSING" in result.errors[0]


def test_missing_outsourcing_sync_ids_are_prefixed_and_do_not_replace_existing():
    values = [["代工單號", "送達數量", "_sync_id"],
              ["OEM1", "5", ""], ["OEM2", "6", "delivery:existing"], ["", "", ""]]
    updates = missing_outsourcing_sync_id_updates(
        values, id_prefix="delivery", id_factory=lambda: "generated"
    )
    assert updates == [(2, 3, "delivery:generated")]
