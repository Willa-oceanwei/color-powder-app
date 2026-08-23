import pytest

from utils.conflict_repository import (
    ConflictError,
    list_sync_conflicts,
    reopen_sync_conflict,
    resolve_sync_conflict,
)
from utils.database import (
    DatabaseConfig,
    connect,
    enqueue_sheet_sync,
    initialize_database,
    record_sync_conflict,
)


def _config(tmp_path):
    db = tmp_path / "conflicts.db"
    initialize_database(db)
    return db, DatabaseConfig(backend="sqlite", path=db)


def test_list_resolve_and_reopen_sync_conflict(tmp_path):
    db, config = _config(tmp_path)
    with connect(db) as conn:
        record_sync_conflict(
            conn,
            entity_type="color_powder",
            entity_id="P001",
            sqlite_payload={"name": "Turso"},
            sheet_payload={"name": "Sheet"},
            reason="both changed",
        )

    conflict = list_sync_conflicts(config)[0]
    assert conflict["status"] == "open"
    assert conflict["turso_payload"] == {"name": "Turso"}
    assert conflict["sheet_payload"] == {"name": "Sheet"}

    resolve_sync_conflict(config, conflict["id"], notes="保留 Turso 並重新檢查")
    assert list_sync_conflicts(config) == []
    resolved = list_sync_conflicts(config, status="resolved")[0]
    assert resolved["resolution_notes"] == "保留 Turso 並重新檢查"
    assert resolved["resolved_at"]

    reopen_sync_conflict(config, conflict["id"])
    reopened = list_sync_conflicts(config)[0]
    assert reopened["status"] == "open"
    assert reopened["resolved_at"] is None
    assert reopened["resolution_notes"] is None


def test_conflict_resolution_requires_notes_and_current_status(tmp_path):
    db, config = _config(tmp_path)
    with connect(db) as conn:
        record_sync_conflict(
            conn,
            entity_type="supplier",
            entity_id="S001",
            sqlite_payload=None,
            sheet_payload={"name": "Sheet"},
            reason="missing baseline",
        )
    conflict_id = list_sync_conflicts(config)[0]["id"]

    with pytest.raises(ConflictError, match="請輸入"):
        resolve_sync_conflict(config, conflict_id, notes="")
    resolve_sync_conflict(config, conflict_id, notes="已完成")
    with pytest.raises(ConflictError, match="尚未結案"):
        resolve_sync_conflict(config, conflict_id, notes="重複")
    reopen_sync_conflict(config, conflict_id)
    with pytest.raises(ConflictError, match="已結案"):
        reopen_sync_conflict(config, conflict_id)


def test_conflict_filters_and_limits_are_validated(tmp_path):
    _, config = _config(tmp_path)
    with pytest.raises(ValueError, match="status"):
        list_sync_conflicts(config, status="invalid")
    with pytest.raises(ValueError, match="limit"):
        list_sync_conflicts(config, limit=0)


def test_resolve_can_requeue_matching_outbound_conflict(tmp_path):
    db, config = _config(tmp_path)
    with connect(db) as conn:
        enqueue_sheet_sync(
            conn,
            sheet_name="色粉管理",
            row_key="P001",
            operation="update",
            payload={"色粉編號": "P001", "名稱": "Turso"},
            entity_version=2,
        )
        conn.execute(
            "UPDATE sync_outbox SET status='conflict', last_error='both changed'"
        )
        record_sync_conflict(
            conn,
            entity_type="color_powder",
            entity_id="P001",
            sqlite_payload={"name": "Turso"},
            sheet_payload={"name": "Sheet"},
            reason="both changed",
        )
    conflict_id = list_sync_conflicts(config)[0]["id"]

    requeued = resolve_sync_conflict(
        config,
        conflict_id,
        notes="Sheet 已修正，允許 Turso 重送",
        resolution="retry_outbox",
    )

    assert requeued == 1
    with connect(db) as conn:
        event = conn.execute(
            "SELECT status, processed_at, last_error FROM sync_outbox"
        ).fetchone()
    assert tuple(event) == ("pending", None, None)
    assert list_sync_conflicts(config) == []


def test_retry_resolution_requires_matching_outbox_event(tmp_path):
    db, config = _config(tmp_path)
    with connect(db) as conn:
        record_sync_conflict(
            conn,
            entity_type="color_powder",
            entity_id="P404",
            sqlite_payload={"name": "Turso"},
            sheet_payload={"name": "Sheet"},
            reason="both changed",
        )
    conflict_id = list_sync_conflicts(config)[0]["id"]

    with pytest.raises(ConflictError, match="找不到可重送"):
        resolve_sync_conflict(
            config,
            conflict_id,
            notes="重送",
            resolution="retry_outbox",
        )
    assert list_sync_conflicts(config)[0]["status"] == "open"
