from utils.database import DatabaseConfig, connect, initialize_database
from utils.sheet_import import import_sheet_values, missing_inventory_sync_id_updates
from utils.trial_repository import (
    create_trial_record,
    get_trial_settings,
    list_trial_records,
    mark_trial_purchased,
    save_trial_settings,
)


def config(tmp_path):
    path = tmp_path / "trial.db"
    initialize_database(path)
    return path, DatabaseConfig(backend="sqlite", path=path)


def test_create_and_purchase_update_enqueue_outbox(tmp_path):
    path, db_config = config(tmp_path)
    created = create_trial_record(db_config, {
        "配方編號": "ABS001", "主配方編號": "ABS001", "客戶編號": "C01",
        "客戶名稱": "甲公司", "試色日期": "2026-08-24", "原料": "ABS",
        "已採購": "否",
    })
    assert created["trial_id"].startswith("trial-")
    mark_trial_purchased(db_config, "ABS001", "2026-08-25")
    assert list_trial_records(db_config)[0]["purchased"] == "是"
    with connect(path) as conn:
        operations = conn.execute("SELECT operation FROM sync_outbox ORDER BY entity_version").fetchall()
    assert [item[0] for item in operations] == ["insert", "update"]


def test_settings_are_turso_backed(tmp_path):
    _, db_config = config(tmp_path)
    assert get_trial_settings(db_config)["最小樣本數"] == "10"
    save_trial_settings(db_config, {"最小樣本數": "25"})
    assert get_trial_settings(db_config)["最小樣本數"] == "25"


def test_initial_import_and_prepare(tmp_path):
    path, _ = config(tmp_path)
    values = [
        ["配方編號", "主配方編號", "客戶編號", "客戶名稱", "試色日期", "日期精度", "歷史補登", "原料", "已採購", "採購日期", "建立時間", "更新時間", "_sync_id"],
        ["ABS001", "ABS001", "C01", "甲公司", "2026-08-24", "精確", "否", "ABS", "否", "", "", "", "trial-1"],
    ]
    assert import_sheet_values("試色登錄", values, db_path=path, abort_on_issues=True).inserted_or_updated == 1
    assert import_sheet_values("試色登錄", values, db_path=path, dry_run=True).unchanged == 1
    missing = [values[0], values[1][:-1] + [""]]
    assert missing_inventory_sync_id_updates(missing, id_factory=lambda: "trial-2") == [(2, 13, "trial-2")]
