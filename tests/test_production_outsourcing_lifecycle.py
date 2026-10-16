import pytest

from utils.database import DatabaseConfig, connect, initialize_database
from utils import outsourcing_repository as oem
from utils.production_order_repository import (
    create_production_order,
    list_production_orders,
    set_production_order_cancelled,
)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "lifecycle.db"
    initialize_database(path)
    config = DatabaseConfig(backend="sqlite", path=path)
    create_production_order(config, {"生產單號": "P1"})
    for order_id, production_id in (("A", "P1"), ("B", "P1"), ("C", "P2"), ("D", "P1")):
        oem.create_outsourcing_order(config, {
            "代工單號": order_id, "生產單號": production_id,
            "配方編號": "SAME", "代工數量": "10",
        })
    oem.archive_outsourcing_order(config, "D", reason="manual")
    return config


def active_ids(config):
    return {row["代工單號"] for row in oem.list_outsourcing_orders(config)}


def cancel(config):
    return set_production_order_cancelled(config, "P1", cancelled=True, reason="test")


def restore(config):
    return set_production_order_cancelled(config, "P1", cancelled=False)


def test_cascade_preserves_history_and_restores_only_linked_active_orders(config):
    delivery = oem.add_outsourcing_delivery(config, "A", "2026-10-16", 10)
    returned = oem.add_outsourcing_return(config, "A", "2026-10-16", 5)
    cancel(config)
    assert active_ids(config) == {"C"}
    assert list_production_orders(config) == []
    assert oem.list_outsourcing_events(config, "delivery") == [delivery]
    assert oem.list_outsourcing_events(config, "return") == [returned]
    with connect(config.path) as conn:
        for event in (delivery, returned):
            assert [tuple(row) for row in conn.execute(
                "SELECT operation, entity_version FROM sync_outbox WHERE row_key=? ORDER BY entity_version",
                (event["_sync_id"],),
            )] == [("insert", 1), ("delete", 2)]
    restored = restore(config)
    assert active_ids(config) == {"A", "B", "C"}
    assert "_cancelled_outsourcing_orders" not in restored
    with connect(config.path) as conn:
        for event in (delivery, returned):
            assert tuple(conn.execute(
                "SELECT operation, entity_version FROM sync_outbox WHERE row_key=? ORDER BY entity_version DESC LIMIT 1",
                (event["_sync_id"],),
            ).fetchone()) == ("insert", 3)
    cancel(config)
    restore(config)
    assert active_ids(config) == {"A", "B", "C"}


def test_restore_does_not_undo_later_manual_archival(config):
    cancel(config)
    oem.restore_outsourcing_order(config, "A")
    oem.archive_outsourcing_order(config, "A", reason="later manual decision")
    restore(config)
    assert active_ids(config) == {"B", "C"}


@pytest.mark.parametrize("restoring", [False, True])
def test_cascade_and_outbox_roll_back_together(config, monkeypatch, restoring):
    oem.add_outsourcing_delivery(config, "A", "2026-10-16", 10)
    if restoring:
        cancel(config)
    with connect(config.path) as conn:
        before = {
            table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
            for table in ("production_orders", "outsourcing_orders", "outsourcing_deliveries", "sync_outbox")
        }
    original = oem.enqueue_sheet_sync

    def fail_on_event(*args, **kwargs):
        if kwargs["sheet_name"] == "代工送達記錄":
            raise RuntimeError("sync failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(oem, "enqueue_sheet_sync", fail_on_event)
    with pytest.raises(RuntimeError, match="sync failure"):
        restore(config) if restoring else cancel(config)
    with connect(config.path) as conn:
        for table, rows in before.items():
            assert [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] == rows

