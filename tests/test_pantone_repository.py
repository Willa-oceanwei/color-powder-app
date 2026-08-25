from utils.database import DatabaseConfig, connect, initialize_database
from utils.pantone_repository import create_pantone_record, list_pantone_records
from utils.sheet_import import import_sheet_values


def test_pantone_create_and_outbox(tmp_path):
    path = tmp_path / "pantone.db"; initialize_database(path)
    config = DatabaseConfig(backend="sqlite", path=path)
    create_pantone_record(config, formula_id="R001", pantone_code="P 186 C",
                          customer_name="甲客戶", material_no="M1")
    assert list_pantone_records(config)[0]["pantone_code"] == "P 186 C"
    with connect(path) as conn:
        event = conn.execute("SELECT sheet_name,row_key,operation FROM sync_outbox").fetchone()
    assert tuple(event) == ("Pantone色號表", "R001", "insert")


def test_pantone_initial_import_baseline(tmp_path):
    path = tmp_path / "pantone.db"; initialize_database(path)
    values = [["Pantone色號", "配方編號", "客戶名稱", "料號"],
              ["P 186 C", "R001", "甲客戶", "M1"]]
    result = import_sheet_values("Pantone色號表", values, db_path=path, abort_on_issues=True)
    check = import_sheet_values("Pantone色號表", values, db_path=path, dry_run=True)
    assert result.inserted_or_updated == 1
    assert check.unchanged == 1
