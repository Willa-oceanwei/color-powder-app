from utils.database import initialize_database, connect
from utils.sheet_import import import_sheet_values


def test_initialize_database_creates_core_tables(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "color_powders" in tables
    assert "inventory_movements" in tables
    assert "sync_log" in tables
    assert "sync_conflicts" in tables


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


def test_import_inventory_creates_powder_stub_and_movement(tmp_path):
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註"],
        ["入庫", "P001", "2026-08-12", "15", "kg", "direct sheet import"],
    ]
    result = import_sheet_values("庫存記錄", values, db_path=tmp_path / "colorpowder.db")
    assert result.ok
    with connect(tmp_path / "colorpowder.db") as conn:
        powder_count = conn.execute("SELECT COUNT(*) FROM color_powders WHERE colorpowder_id='P001'").fetchone()[0]
        movement_count = conn.execute("SELECT COUNT(*) FROM inventory_movements WHERE colorpowder_id='P001'").fetchone()[0]
    assert powder_count == 1
    assert movement_count == 1
