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
