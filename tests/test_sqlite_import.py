from utils.database import initialize_database, connect
from utils.sheet_import import import_sheet_values


def test_initialize_database_creates_core_tables(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        inventory_cols = {row[1] for row in conn.execute("PRAGMA table_info(inventory_movements)")}
    assert "color_powders" in tables
    assert "inventory_movements" in tables
    assert "supplier_aliases" in tables
    assert "sync_log" in tables
    assert "sync_conflicts" in tables
    assert "movement_key" in inventory_cols


def test_import_color_powders_validates_duplicates(tmp_path):
    values = [
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        ["TPR_52824", "P001", "Red", "色粉", "袋", ""],
        ["TPR_52824", "P002", "Dup", "色粉", "袋", ""],
    ]
    result = import_sheet_values("色粉管理", values, db_path=tmp_path / "colorpowder.db")
    assert result.sheet_rows == 2
    assert result.duplicate_ids == ["TPR_52824"]
    with connect(tmp_path / "colorpowder.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM color_powders").fetchone()[0]
    assert count == 1


def test_import_inventory_is_idempotent_for_same_sheet_row(tmp_path):
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註"],
        ["入庫", "P001", "2026-08-12", "15", "kg", "direct sheet import"],
    ]
    db = tmp_path / "colorpowder.db"
    first = import_sheet_values("庫存記錄", values, db_path=db)
    second = import_sheet_values("庫存記錄", values, db_path=db)
    assert first.ok
    assert second.unchanged == 1
    with connect(db) as conn:
        powder_count = conn.execute("SELECT COUNT(*) FROM color_powders WHERE colorpowder_id='P001'").fetchone()[0]
        movement_count = conn.execute("SELECT COUNT(*) FROM inventory_movements WHERE colorpowder_id='P001'").fetchone()[0]
    assert powder_count == 1
    assert movement_count == 1


def test_dry_run_reports_changes_without_writing_rows(tmp_path):
    db = tmp_path / "colorpowder.db"
    values = [
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        ["P001", "I001", "Blue", "色粉", "袋", ""],
    ]
    result = import_sheet_values("色粉管理", values, db_path=db, dry_run=True)
    assert result.dry_run
    assert result.to_insert == 1
    assert result.inserted_or_updated == 0
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM color_powders").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sheet_rows").fetchone()[0] == 0


def test_supplier_without_id_uses_stable_sheet_row_identity(tmp_path):
    db = tmp_path / "colorpowder.db"
    values = [
        ["供應商名稱", "電話", "聯絡人", "備註"],
        ["原名稱", "123", "Amy", ""],
    ]
    import_sheet_values("供應商管理", values, db_path=db)
    renamed = [
        ["供應商名稱", "電話", "聯絡人", "備註"],
        ["新名稱", "123", "Amy", ""],
    ]
    import_sheet_values("供應商管理", renamed, db_path=db)
    with connect(db) as conn:
        suppliers = conn.execute("SELECT supplier_id, name FROM suppliers").fetchall()
    assert len(suppliers) == 1
    assert suppliers[0]["supplier_id"] == "sheet:row-2"
    assert suppliers[0]["name"] == "新名稱"
