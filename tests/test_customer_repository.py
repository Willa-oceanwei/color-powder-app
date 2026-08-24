from utils.customer_repository import (
    CustomerInput,
    create_customer,
    list_customers,
    set_customer_active,
    update_customer,
)
from utils.database import DatabaseConfig, connect, initialize_database
from utils.sheet_import import import_sheet_values


def config_for(tmp_path):
    path = tmp_path / "customers.db"
    initialize_database(path)
    return DatabaseConfig(backend="sqlite", path=path)


def test_customer_crud_lifecycle_and_outbox(tmp_path):
    config = config_for(tmp_path)
    create_customer(config, CustomerInput("C001", "甲客戶", "初始"))
    update_customer(config, CustomerInput("C001", "甲公司", "更新"))
    set_customer_active(config, "C001", active=False, reason="停止往來")
    assert list_customers(config) == []
    assert list_customers(config, include_inactive=True)[0]["delete_reason"] == "停止往來"
    set_customer_active(config, "C001", active=True)
    assert list_customers(config)[0]["name"] == "甲公司"
    with connect(config.path) as conn:
        operations = conn.execute(
            "SELECT operation FROM sync_outbox WHERE sheet_name='客戶名單' ORDER BY entity_version"
        ).fetchall()
    assert [row[0] for row in operations] == ["insert", "update", "delete", "update"]


def test_customer_sheet_initial_import_and_baseline(tmp_path):
    config = config_for(tmp_path)
    values = [["客戶編號", "客戶簡稱", "備註"], ["C001", "甲客戶", "舊資料"]]
    result = import_sheet_values("客戶名單", values, db_config=config, abort_on_issues=True,
                                 initialize_schema=False)
    verification = import_sheet_values("客戶名單", values, db_config=config, dry_run=True,
                                       initialize_schema=False)
    assert result.inserted_or_updated == 1
    assert verification.unchanged == 1
    assert list_customers(config)[0]["customer_id"] == "C001"
