from utils.color_powder_repository import ColorPowderInput, create_color_powder
from utils.database import DatabaseConfig, connect, initialize_database
from utils.inbound_worker import run_controlled_inbound_worker
from utils.sheet_import import import_sheet_values


class Worksheet:
    def __init__(self, values):
        self.values = values

    def get_all_values(self):
        return self.values


class Spreadsheet:
    def __init__(self, sheets):
        self.sheets = {name: Worksheet(values) for name, values in sheets.items()}

    def worksheet(self, name):
        return self.sheets[name]


def test_controlled_inbound_preflights_then_applies_sheet_update(tmp_path):
    db = tmp_path / "inbound.db"
    baseline = [["色粉編號", "名稱", "備註"], ["P001", "Red", "old"]]
    changed = [["色粉編號", "名稱", "備註"], ["P001", "Red", "from Sheet"]]
    import_sheet_values("色粉管理", baseline, db_path=db, abort_on_issues=True)
    config = DatabaseConfig(backend="sqlite", path=db)
    spreadsheet = Spreadsheet({"色粉管理": changed})

    preflight = run_controlled_inbound_worker(
        spreadsheet, db_config=config, dry_run=True, sheet_names=["色粉管理"]
    )
    applied = run_controlled_inbound_worker(
        spreadsheet, db_config=config, dry_run=False, sheet_names=["色粉管理"]
    )

    assert preflight.ok
    assert preflight.preflight[0]["to_update"] == 1
    assert preflight.applied == []
    assert applied.ok
    assert applied.applied[0]["inserted_or_updated"] == 1
    with connect(db) as conn:
        powder = conn.execute(
            "SELECT notes, source FROM color_powders WHERE colorpowder_id='P001'"
        ).fetchone()
        outbox_count = conn.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0]
        lock_count = conn.execute("SELECT COUNT(*) FROM sync_worker_locks").fetchone()[0]
    assert tuple(powder) == ("from Sheet", "google_sheets_import")
    assert outbox_count == 0
    assert lock_count == 0


def test_controlled_inbound_blocks_entity_without_sheet_baseline(tmp_path):
    db = tmp_path / "inbound-conflict.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Turso"))
    spreadsheet = Spreadsheet({
        "色粉管理": [["色粉編號", "名稱"], ["P001", "Sheet"]]
    })

    result = run_controlled_inbound_worker(
        spreadsheet, db_config=config, dry_run=False, sheet_names=["色粉管理"]
    )

    assert not result.ok
    assert result.preflight[0]["conflicts"] == 1
    assert result.applied == []
    with connect(db) as conn:
        name = conn.execute(
            "SELECT name FROM color_powders WHERE colorpowder_id='P001'"
        ).fetchone()[0]
    assert name == "Turso"


def test_controlled_inbound_never_treats_missing_sheet_row_as_delete(tmp_path):
    db = tmp_path / "inbound-no-delete.db"
    baseline = [
        ["色粉編號", "名稱"],
        ["P001", "Red"],
        ["P002", "Blue"],
    ]
    import_sheet_values("色粉管理", baseline, db_path=db, abort_on_issues=True)
    config = DatabaseConfig(backend="sqlite", path=db)
    spreadsheet = Spreadsheet({
        "色粉管理": [["色粉編號", "名稱"], ["P001", "Red"]]
    })

    result = run_controlled_inbound_worker(
        spreadsheet, db_config=config, dry_run=False, sheet_names=["色粉管理"]
    )

    assert result.ok
    assert result.applied[0]["inserted_or_updated"] == 0
    with connect(db) as conn:
        ids = conn.execute(
            "SELECT colorpowder_id FROM color_powders ORDER BY colorpowder_id"
        ).fetchall()
    assert [row[0] for row in ids] == ["P001", "P002"]


def test_controlled_inbound_change_limit_blocks_all_writes(tmp_path):
    db = tmp_path / "inbound-limit.db"
    baseline = [
        ["色粉編號", "名稱"],
        ["P001", "Red"],
        ["P002", "Blue"],
    ]
    changed = [
        ["色粉編號", "名稱"],
        ["P001", "Changed Red"],
        ["P002", "Changed Blue"],
    ]
    import_sheet_values("色粉管理", baseline, db_path=db, abort_on_issues=True)
    config = DatabaseConfig(backend="sqlite", path=db)

    result = run_controlled_inbound_worker(
        Spreadsheet({"色粉管理": changed}),
        db_config=config,
        dry_run=False,
        sheet_names=["色粉管理"],
        max_changes=1,
    )

    assert not result.ok
    assert result.applied == []
    assert result.errors == ["preflight found 2 changes; controlled limit is 1"]
    with connect(db) as conn:
        names = conn.execute(
            "SELECT name FROM color_powders ORDER BY colorpowder_id"
        ).fetchall()
    assert [row[0] for row in names] == ["Red", "Blue"]
