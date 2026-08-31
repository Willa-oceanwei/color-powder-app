from contextlib import contextmanager
import json
import logging
import sqlite3

import pytest
import utils.database as database_module
import utils.sheet_export as sheet_export_module

from utils.database import (
    SCHEMA_VERSION,
    DatabaseConfig,
    DatabaseStartupError,
    connect,
    connect_from_config,
    database_config_from_secrets,
    database_health_check,
    enqueue_sheet_sync,
    format_database_startup_diagnostics,
    get_latest_sync_log,
    initialize_database,
    initialize_database_with_health,
    log_database_startup_diagnostics,
    record_sync_log,
)
from utils.sheet_export import (
    sync_color_powder_outbox,
    sync_inventory_outbox,
    sync_production_order_outbox,
    sync_recipe_outbox,
    sync_supplier_outbox,
)
from utils.color_powder_repository import (
    ColorPowderAlreadyExists,
    ColorPowderInput,
    create_color_powder,
    list_color_powders,
    update_color_powder,
    set_color_powder_active,
)
from utils.supplier_repository import (
    SupplierAlreadyExists,
    SupplierInput,
    create_supplier,
    list_suppliers,
    update_supplier,
    set_supplier_active,
)
from utils.recipe_repository import create_recipe, list_recipes, set_recipe_active, update_recipe
from utils.inventory_repository import (
    InventoryError,
    create_inventory_movement,
    list_inventory_movements,
    reverse_inventory_movement,
    update_inventory_movement,
)
from utils.production_order_repository import (
    ProductionOrderError,
    create_production_order,
    list_production_orders,
    set_production_order_cancelled,
    update_production_order,
)
from utils.sheet_import import (
    ImportAbortedError,
    SheetReadError,
    import_sheet_values,
    missing_inventory_sync_id_updates,
    read_worksheet_values_with_retry,
)
from utils.sync_worker import acquire_worker_lock, release_worker_lock, run_safe_worker


class FakeGoogleApiError(Exception):
    def __init__(self, status_code, body=""):
        super().__init__(body or f"HTTP {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


class SequencedWorksheet:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def get_all_values(self):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_get_latest_sync_log_returns_most_recent_completed_direction(tmp_path):
    db = tmp_path / "latest-sync.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    with connect(db) as conn:
        record_sync_log(
            conn, sync_name="outbox:色粉管理", direction="turso_to_google_sheets",
            status="success", started_at="2026-08-31T01:00:00+00:00",
            finished_at="2026-08-31T01:01:00+00:00", written_count=2,
        )
        record_sync_log(
            conn, sync_name="initial_import:色粉管理", direction="google_sheets_to_sqlite",
            status="success", started_at="2026-08-31T03:00:00+00:00",
            finished_at="2026-08-31T03:01:00+00:00", written_count=9,
        )
        record_sync_log(
            conn, sync_name="outbox:生產單", direction="turso_to_google_sheets",
            status="success", started_at="2026-08-31T02:00:00+00:00",
            finished_at="2026-08-31T02:01:00+00:00", written_count=6,
        )

    latest = get_latest_sync_log(config, direction="turso_to_google_sheets")

    assert latest is not None
    assert latest["sync_name"] == "outbox:生產單"
    assert latest["finished_at"] == "2026-08-31T02:01:00+00:00"
    assert latest["written_count"] == 6


class WritableWorksheet:
    def __init__(self):
        self.appended = []
        self.updated = []
        self.deleted = []

    def append_row(self, values):
        self.appended.append(values)

    def update(self, cell, values):
        self.updated.append((cell, values))

    def delete_rows(self, row_number):
        self.deleted.append(row_number)


def test_sheet_read_retries_transient_google_errors():
    worksheet = SequencedWorksheet([
        FakeGoogleApiError(502, "temporary HTML response"),
        FakeGoogleApiError(503, "temporarily unavailable"),
        [["色粉編號"], ["P001"]],
    ])
    delays = []

    values = read_worksheet_values_with_retry(worksheet, sleep=delays.append)

    assert values == [["色粉編號"], ["P001"]]
    assert worksheet.calls == 3
    assert delays == [1.0, 2.0]


def test_sheet_read_does_not_retry_permanent_google_errors():
    worksheet = SequencedWorksheet([FakeGoogleApiError(403, "permission denied")])
    delays = []

    with pytest.raises(SheetReadError, match="HTTP 403"):
        read_worksheet_values_with_retry(worksheet, sleep=delays.append)

    assert worksheet.calls == 1
    assert delays == []


def test_sheet_read_hides_google_html_after_retry_exhaustion():
    html = "<!DOCTYPE html><html>very long Google error page</html>"
    worksheet = SequencedWorksheet([FakeGoogleApiError(502, html) for _ in range(4)])

    with pytest.raises(SheetReadError) as error:
        read_worksheet_values_with_retry(
            worksheet,
            base_delay_seconds=0,
            sleep=lambda _delay: None,
        )

    assert worksheet.calls == 4
    assert "HTTP 502" in str(error.value)
    assert "after 4 attempts" in str(error.value)
    assert "<!DOCTYPE html>" not in str(error.value)


def test_initialize_database_creates_core_tables(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        inventory_cols = {row[1] for row in conn.execute("PRAGMA table_info(inventory_movements)")}
    assert "color_powders" in tables
    assert "inventory_movements" in tables
    assert "recipes" in tables
    assert "recipe_components" in tables
    assert "supplier_aliases" in tables
    assert "sync_log" in tables
    assert "sync_conflicts" in tables
    assert "sync_outbox" in tables
    assert "movement_key" in inventory_cols
    assert "supplier_id" in inventory_cols
    assert "supplier_name" in inventory_cols


def test_schema_v8_adds_lifecycle_and_reversal_foundations(tmp_path):
    db = tmp_path / "lifecycle-v8.db"
    initialize_database(db)
    with connect(db) as conn:
        columns = {
            table: {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for table in ("color_powders", "suppliers", "recipes", "inventory_movements", "production_orders")
        }
        now = "2026-08-17T00:00:00+00:00"
        conn.execute(
            "INSERT INTO color_powders(colorpowder_id, created_at, updated_at) VALUES ('P001', ?, ?)",
            (now, now),
        )
        lifecycle = conn.execute(
            "SELECT lifecycle_status, deleted_at, delete_reason FROM color_powders WHERE colorpowder_id='P001'"
        ).fetchone()
        conn.execute(
            """INSERT INTO inventory_movements(
                   movement_key, movement_type, colorpowder_id, quantity, created_at, updated_at)
               VALUES ('original', '進貨', 'P001', 10, ?, ?)""",
            (now, now),
        )
        conn.execute(
            """INSERT INTO inventory_movements(
                   movement_key, movement_type, colorpowder_id, quantity,
                   reversal_of_movement_key, created_at, updated_at)
               VALUES ('reversal-1', '沖銷', 'P001', -10, 'original', ?, ?)""",
            (now, now),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO inventory_movements(
                       movement_key, movement_type, colorpowder_id, quantity,
                       reversal_of_movement_key, created_at, updated_at)
                   VALUES ('reversal-2', '沖銷', 'P001', -10, 'original', ?, ?)""",
                (now, now),
            )

    assert {"lifecycle_status", "deleted_at", "delete_reason"} <= columns["color_powders"]
    assert {"lifecycle_status", "deleted_at", "delete_reason"} <= columns["suppliers"]
    assert {"lifecycle_status", "deleted_at", "delete_reason"} <= columns["recipes"]
    assert {"reversal_of_movement_key", "reversed_at"} <= columns["inventory_movements"]
    assert {"cancelled_at", "cancel_reason"} <= columns["production_orders"]
    assert tuple(lifecycle) == ("active", None, None)


def test_current_schema_migrates_inventory_supplier_columns(tmp_path):
    db = tmp_path / "legacy.db"
    with connect(db) as conn:
        conn.execute(
            """CREATE TABLE inventory_movements (
                movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_key TEXT UNIQUE,
                sheet_name TEXT,
                sheet_row_key TEXT,
                movement_type TEXT NOT NULL,
                colorpowder_id TEXT NOT NULL,
                movement_date TEXT,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT 'g',
                notes TEXT,
                source TEXT NOT NULL DEFAULT 'sqlite',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_synced_at TEXT
            )"""
        )

    initialize_database(db)

    with connect(db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(inventory_movements)")}
    assert {"supplier_id", "supplier_name"}.issubset(columns)


def test_schema_v6_backfills_recipe_oem_multiplier_from_sheet_baseline(tmp_path):
    db = tmp_path / "legacy-recipe.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version=6")
        conn.execute(
            """INSERT INTO recipes(recipe_id, source, created_at, updated_at, oem_multiplier)
               VALUES ('R001', 'google_sheets_import', '2026-01-01', '2026-01-01', 1)"""
        )
        conn.execute(
            """INSERT INTO sheet_rows(
                   sheet_name, row_key, payload_json, row_hash, created_at, updated_at,
                   last_seen_at, last_synced_at)
               VALUES ('配方管理', 'R001', ?, 'hash', '2026-01-01', '2026-01-01',
                       '2026-01-01', '2026-01-01')""",
            (json.dumps({"配方編號": "R001", "代工倍率": "2.5"}, ensure_ascii=False),),
        )

    initialize_database(db)

    with connect(db) as conn:
        multiplier = conn.execute(
            "SELECT oem_multiplier FROM recipes WHERE recipe_id='R001'"
        ).fetchone()[0]
    assert multiplier == 2.5


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


def test_incremental_color_apply_inserts_and_updates_then_converges(tmp_path):
    db = tmp_path / "colorpowder.db"
    initial_values = [
        ["色粉編號", "名稱", "備註"],
        ["P001", "Original", ""],
    ]
    import_sheet_values("色粉管理", initial_values, db_path=db, abort_on_issues=True)
    changed_values = [
        ["色粉編號", "名稱", "備註"],
        ["P001", "Updated", "changed"],
        ["P002", "New", "added"],
    ]

    preflight = import_sheet_values("色粉管理", changed_values, db_path=db, dry_run=True)
    applied = import_sheet_values(
        "色粉管理",
        changed_values,
        db_path=db,
        abort_on_issues=True,
    )
    verification = import_sheet_values("色粉管理", changed_values, db_path=db, dry_run=True)

    assert preflight.to_insert == 1
    assert preflight.to_update == 1
    assert applied.inserted_or_updated == 2
    assert verification.to_insert == 0
    assert verification.to_update == 0
    assert verification.unchanged == 2
    with connect(db) as conn:
        powders = {
            row["colorpowder_id"]: (row["name"], row["notes"])
            for row in conn.execute(
                "SELECT colorpowder_id, name, notes FROM color_powders ORDER BY colorpowder_id"
            ).fetchall()
        }
    assert powders == {
        "P001": ("Updated", "changed"),
        "P002": ("New", "added"),
    }


def test_color_outbox_dry_run_and_apply_updates_unchanged_sheet(tmp_path):
    db = tmp_path / "colorpowder.db"
    baseline = [
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        ["P001", "I1", "Old", "色粉", "袋", ""],
    ]
    import_sheet_values("色粉管理", baseline, db_path=db, abort_on_issues=True)
    with connect(db) as conn:
        conn.execute(
            "UPDATE color_powders SET name='New', version=version+1, updated_at=? WHERE colorpowder_id='P001'",
            ("2026-08-15T00:00:00+00:00",),
        )
        entity = dict(conn.execute("SELECT * FROM color_powders WHERE colorpowder_id='P001'").fetchone())
        enqueue_sheet_sync(
            conn, sheet_name="色粉管理", row_key="P001", operation="update",
            payload={
                "色粉編號": "P001", "國際色號": "I1", "名稱": "New",
                "色粉類別": "色粉", "包裝": "袋", "備註": "",
            }, entity_version=entity["version"],
        )
    worksheet = WritableWorksheet()
    config = DatabaseConfig(backend="sqlite", path=db)

    preflight = sync_color_powder_outbox(worksheet, baseline, db_config=config, dry_run=True)
    applied = sync_color_powder_outbox(worksheet, baseline, db_config=config, dry_run=False)

    assert preflight.to_update == 1
    assert preflight.written == 0
    assert applied.written == 1
    assert worksheet.updated == [("A2", [["P001", "I1", "New", "色粉", "袋", ""]])]
    with connect(db) as conn:
        outbox = conn.execute("SELECT status FROM sync_outbox").fetchone()
    assert outbox["status"] == "completed"


def test_color_outbox_blocks_concurrent_sheet_edit(tmp_path):
    db = tmp_path / "colorpowder.db"
    baseline = [["色粉編號", "名稱"], ["P001", "Old"]]
    import_sheet_values("色粉管理", baseline, db_path=db, abort_on_issues=True)
    with connect(db) as conn:
        enqueue_sheet_sync(
            conn, sheet_name="色粉管理", row_key="P001", operation="update",
            payload={"色粉編號": "P001", "名稱": "Database edit"}, entity_version=2,
        )
    worksheet = WritableWorksheet()
    changed_sheet = [["色粉編號", "名稱"], ["P001", "Sheet edit"]]

    result = sync_color_powder_outbox(
        worksheet, changed_sheet,
        db_config=DatabaseConfig(backend="sqlite", path=db), dry_run=False,
    )

    assert result.conflicts == 1
    assert result.written == 0
    assert worksheet.updated == []
    with connect(db) as conn:
        assert conn.execute("SELECT status FROM sync_outbox").fetchone()[0] == "conflict"
        assert conn.execute("SELECT COUNT(*) FROM sync_conflicts").fetchone()[0] == 1


def test_color_repository_create_is_atomic_with_outbox(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)

    created = create_color_powder(
        config,
        ColorPowderInput(" P001 ", " I1 ", " Red ", "色粉", "袋", " note "),
    )

    assert created["colorpowder_id"] == "P001"
    assert created["name"] == "Red"
    assert created["version"] == 1
    assert created["last_synced_at"] is None
    with connect(db) as conn:
        outbox = conn.execute("SELECT * FROM sync_outbox").fetchone()
    assert outbox["row_key"] == "P001"
    assert outbox["operation"] == "insert"
    assert outbox["entity_version"] == 1
    assert outbox["status"] == "pending"


def test_color_repository_update_increments_version_and_queues_payload(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Old"))

    updated = update_color_powder(
        config, ColorPowderInput("P001", international_code="I2", name="New", notes="changed")
    )

    assert updated["version"] == 2
    assert updated["name"] == "New"
    assert list_color_powders(config)[0]["international_code"] == "I2"
    with connect(db) as conn:
        events = conn.execute(
            "SELECT operation, entity_version, payload_json FROM sync_outbox ORDER BY id"
        ).fetchall()
    assert [(row["operation"], row["entity_version"]) for row in events] == [
        ("insert", 1), ("update", 2),
    ]
    assert '"名稱": "New"' in events[1]["payload_json"]


def test_color_repository_duplicate_does_not_queue_second_event(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="First"))

    with pytest.raises(ColorPowderAlreadyExists):
        create_color_powder(config, ColorPowderInput("P001", name="Duplicate"))

    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM color_powders").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0] == 1


def test_color_outbox_coalesces_unsynced_create_and_update(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="First"))
    update_color_powder(config, ColorPowderInput("P001", name="Latest"))
    worksheet = WritableWorksheet()
    values = [["色粉編號", "名稱"]]

    preflight = sync_color_powder_outbox(worksheet, values, db_config=config, dry_run=True)
    applied = sync_color_powder_outbox(worksheet, values, db_config=config, dry_run=False)

    assert preflight.queued == 1
    assert preflight.to_insert == 1
    assert applied.written == 1
    assert worksheet.appended == [["P001", "Latest"]]
    with connect(db) as conn:
        statuses = conn.execute("SELECT status FROM sync_outbox ORDER BY id").fetchall()
    assert [row["status"] for row in statuses] == ["completed", "completed"]


def test_color_outbox_matching_sheet_completes_metadata_without_write(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Already there"))
    worksheet = WritableWorksheet()
    values = [["色粉編號", "名稱"], ["P001", "Already there"]]

    applied = sync_color_powder_outbox(worksheet, values, db_config=config, dry_run=False)

    assert applied.unchanged == 1
    assert applied.written == 0
    assert worksheet.appended == []
    assert worksheet.updated == []
    with connect(db) as conn:
        powder = conn.execute(
            "SELECT last_synced_at FROM color_powders WHERE colorpowder_id='P001'"
        ).fetchone()
        event = conn.execute("SELECT status FROM sync_outbox").fetchone()
        baseline = conn.execute(
            "SELECT row_hash FROM sheet_rows WHERE sheet_name='色粉管理' AND row_key='P001'"
        ).fetchone()
    assert powder["last_synced_at"]
    assert event["status"] == "completed"
    assert baseline["row_hash"]


def test_supplier_repository_create_update_aliases_and_outbox(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)

    created = create_supplier(config, SupplierInput(" S001 ", " First Name ", " note "))
    updated = update_supplier(config, SupplierInput("S001", "New Name", "changed"))

    assert created["supplier_id"] == "S001"
    assert updated["version"] == 2
    assert list_suppliers(config)[0]["name"] == "New Name"
    with connect(db) as conn:
        aliases = conn.execute(
            "SELECT alias FROM supplier_aliases WHERE supplier_id='S001' ORDER BY alias"
        ).fetchall()
        events = conn.execute(
            "SELECT operation, entity_version FROM sync_outbox WHERE sheet_name='供應商管理' ORDER BY id"
        ).fetchall()
    assert [row["alias"] for row in aliases] == ["First Name", "New Name"]
    assert [(row["operation"], row["entity_version"]) for row in events] == [
        ("insert", 1), ("update", 2),
    ]


def test_master_data_lifecycle_filters_choices_but_keeps_history_readable(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Powder"))
    create_supplier(config, SupplierInput("S001", "Supplier"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "2"})

    powder = set_color_powder_active(config, "P001", active=False, reason="不再採購")
    supplier = set_supplier_active(config, "S001", active=False, reason="停止合作")
    recipe = set_recipe_active(config, "R001", active=False, reason="舊版")

    assert powder["lifecycle_status"] == supplier["lifecycle_status"] == recipe["lifecycle_status"] == "inactive"
    assert list_color_powders(config) == []
    assert list_suppliers(config) == []
    assert list_recipes(config) == []
    assert list_color_powders(config, include_inactive=True)[0]["delete_reason"] == "不再採購"
    assert list_suppliers(config, include_inactive=True)[0]["delete_reason"] == "停止合作"
    historical_recipe = list_recipes(config, include_inactive=True)[0]
    assert historical_recipe["停用原因"] == "舊版"
    assert historical_recipe["色粉編號1"] == "P001"
    with connect(db) as conn:
        lifecycle_events = conn.execute(
            """SELECT sheet_name, operation, entity_version, payload_json
               FROM sync_outbox WHERE entity_version=2 ORDER BY sheet_name"""
        ).fetchall()
    assert [(row["sheet_name"], row["operation"], row["entity_version"]) for row in lifecycle_events] == [
        ("供應商管理", "delete", 2), ("色粉管理", "delete", 2), ("配方管理", "delete", 2),
    ]
    assert all(row["payload_json"] is None for row in lifecycle_events)

    set_color_powder_active(config, "P001", active=True)
    set_supplier_active(config, "S001", active=True)
    set_recipe_active(config, "R001", active=True)
    assert list_color_powders(config)[0]["deleted_at"] is None
    assert list_suppliers(config)[0]["delete_reason"] is None
    assert list_recipes(config)[0]["生命週期"] == "active"
    with connect(db) as conn:
        restored_events = conn.execute(
            "SELECT sheet_name, entity_version FROM sync_outbox WHERE entity_version=3 ORDER BY sheet_name"
        ).fetchall()
    assert [tuple(row) for row in restored_events] == [
        ("供應商管理", 3), ("色粉管理", 3), ("配方管理", 3),
    ]


def test_sheet_tombstone_physically_deletes_synchronized_master_row(tmp_path):
    db = tmp_path / "tombstone.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Powder"))
    worksheet = WritableWorksheet()
    header = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    inserted = sync_color_powder_outbox(
        worksheet, [header], db_config=config, dry_run=False
    )
    assert inserted.written == 1

    set_color_powder_active(config, "P001", active=False, reason="停用")
    values = [header, worksheet.appended[0]]
    preflight = sync_color_powder_outbox(
        worksheet, values, db_config=config, dry_run=True
    )
    applied = sync_color_powder_outbox(
        worksheet, values, db_config=config, dry_run=False
    )

    assert preflight.to_delete == 1
    assert applied.written == 1
    assert worksheet.deleted == [2]
    with connect(db) as conn:
        assert conn.execute(
            "SELECT status FROM sync_outbox WHERE sheet_name='色粉管理' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0] == "completed"


def test_supplier_repository_duplicate_does_not_queue_second_event(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_supplier(config, SupplierInput("S001", "Supplier"))

    with pytest.raises(SupplierAlreadyExists):
        create_supplier(config, SupplierInput("S001", "Duplicate"))

    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM sync_outbox WHERE sheet_name='供應商管理'"
        ).fetchone()[0] == 1


def test_supplier_outbox_coalesces_and_pushes_latest_payload(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_supplier(config, SupplierInput("S001", "First"))
    update_supplier(config, SupplierInput("S001", "Latest", "note"))
    worksheet = WritableWorksheet()
    values = [["供應商編號", "供應商簡稱", "備註"]]

    preflight = sync_supplier_outbox(worksheet, values, db_config=config, dry_run=True)
    applied = sync_supplier_outbox(worksheet, values, db_config=config, dry_run=False)

    assert preflight.queued == 1
    assert preflight.to_insert == 1
    assert applied.written == 1
    assert worksheet.appended == [["S001", "Latest", "note"]]
    with connect(db) as conn:
        statuses = conn.execute(
            "SELECT status FROM sync_outbox WHERE sheet_name='供應商管理' ORDER BY id"
        ).fetchall()
    assert [row["status"] for row in statuses] == ["completed", "completed"]


def test_recipe_repository_atomically_replaces_components_and_queues(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_color_powder(config, ColorPowderInput("P002"))
    create_recipe(config, {
        "配方編號": "R001", "顏色": "Red", "代工倍率": "1.5",
        "色粉編號1": "P001", "色粉重量1": "2",
    })
    update_recipe(config, {
        "配方編號": "R001", "顏色": "Dark Red", "代工倍率": "2",
        "色粉編號1": "P002", "色粉重量1": "3",
    })

    recipes = list_recipes(config)
    assert recipes[0]["顏色"] == "Dark Red"
    assert recipes[0]["代工倍率"] == "2.0"
    assert recipes[0]["色粉編號1"] == "P002"
    with connect(db) as conn:
        components = conn.execute(
            "SELECT colorpowder_id, weight FROM recipe_components WHERE recipe_id='R001'"
        ).fetchall()
        events = conn.execute(
            "SELECT operation, entity_version FROM sync_outbox WHERE sheet_name='配方管理' ORDER BY id"
        ).fetchall()
    assert [(row["colorpowder_id"], row["weight"]) for row in components] == [("P002", 3)]
    assert [(row["operation"], row["entity_version"]) for row in events] == [
        ("insert", 1), ("update", 2),
    ]


def test_recipe_outbox_pushes_latest_full_row(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "顏色": "First", "色粉編號1": "P001", "色粉重量1": "1"})
    update_recipe(config, {"配方編號": "R001", "顏色": "Latest", "色粉編號1": "P001", "色粉重量1": "2"})
    worksheet = WritableWorksheet()
    values = [["配方編號", "顏色", "色粉編號1", "色粉重量1"]]

    preflight = sync_recipe_outbox(worksheet, values, db_config=config, dry_run=True)
    applied = sync_recipe_outbox(worksheet, values, db_config=config, dry_run=False)

    assert preflight.queued == 1
    assert preflight.to_insert == 1
    assert applied.written == 1
    assert worksheet.appended == [["R001", "Latest", "P001", "2"]]


def test_inventory_repository_create_update_and_push_is_idempotent(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_supplier(config, SupplierInput("S001", "Supplier"))
    create_inventory_movement(config, {
        "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
        "數量": 2, "單位": "kg", "廠商編號": "S001", "廠商名稱": "Supplier",
        "備註": "first", "_sync_id": "INV001",
    })
    update_inventory_movement(config, "INV001", {
        "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
        "數量": 3, "單位": "kg", "廠商編號": "S001", "廠商名稱": "Supplier",
        "備註": "latest",
    })
    assert list_inventory_movements(config)[0]["數量"] == "3.0"
    worksheet = WritableWorksheet()
    values = [["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"]]

    preflight = sync_inventory_outbox(worksheet, values, db_config=config, dry_run=True)
    applied = sync_inventory_outbox(worksheet, values, db_config=config, dry_run=False)
    verification = sync_inventory_outbox(
        worksheet,
        [values[0], worksheet.appended[0]],
        db_config=config,
        dry_run=True,
    )

    assert preflight.queued == 1
    assert preflight.to_insert == 1
    assert applied.written == 1
    assert worksheet.appended[0][-1] == "INV001"
    assert worksheet.appended[0][3] == "3.0"
    assert verification.queued == 0


def test_inventory_reversal_is_append_only_and_queued_for_sheet(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_supplier(config, SupplierInput("S001", "Supplier"))
    create_inventory_movement(config, {
        "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
        "數量": 3, "單位": "kg", "廠商編號": "S001", "廠商名稱": "Supplier",
        "備註": "original", "_sync_id": "INV001",
    })

    reversal = reverse_inventory_movement(
        config, "INV001", reason="數量輸入錯誤", reversal_sync_id="REV001"
    )
    movements = list_inventory_movements(config)

    assert reversal["類型"] == "沖銷"
    assert reversal["數量"] == "-3.0"
    assert [(row["_sync_id"], row["沖銷狀態"]) for row in movements] == [
        ("INV001", "已沖銷"), ("REV001", "沖銷記錄"),
    ]
    assert movements[0]["沖銷記錄ID"] == "REV001"
    assert movements[1]["沖銷原始ID"] == "sheet:庫存記錄:INV001"
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT quantity, reversed_at, reversal_of_movement_key FROM inventory_movements ORDER BY movement_id"
        ).fetchall()
        events = conn.execute(
            """SELECT operation, row_key, entity_version FROM sync_outbox
               WHERE row_key IN ('INV001','REV001') AND operation='delete' ORDER BY row_key"""
        ).fetchall()
    assert sum(row["quantity"] for row in rows) == 0
    assert rows[0]["reversed_at"]
    assert rows[1]["reversal_of_movement_key"] == "sheet:庫存記錄:INV001"
    assert [tuple(event) for event in events] == [
        ("delete", "INV001", 2), ("delete", "REV001", 1),
    ]

    with pytest.raises(InventoryError, match="已沖銷"):
        reverse_inventory_movement(config, "INV001", reason="再次沖銷")
    with pytest.raises(InventoryError, match="不可修改"):
        update_inventory_movement(config, "INV001", {
            "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
            "數量": 1, "單位": "kg",
        })


def test_inventory_reversal_requires_reason_without_changing_original(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_inventory_movement(config, {
        "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
        "數量": 2, "單位": "kg", "_sync_id": "INV001",
    })

    with pytest.raises(InventoryError, match="沖銷原因"):
        reverse_inventory_movement(config, "INV001", reason="")

    with connect(db) as conn:
        rows = conn.execute(
            "SELECT reversed_at FROM inventory_movements WHERE sheet_name='庫存記錄'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["reversed_at"] is None


def test_production_order_repository_snapshots_recipe_and_pushes_latest(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {
        "配方編號": "R001", "顏色": "Red", "色粉編號1": "P001", "色粉重量1": "2",
    })
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001",
        "顏色": "Red", "客戶名稱": "Customer", "包裝重量1": "1", "包裝份數1": "2",
    })
    update_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001",
        "顏色": "Dark Red", "客戶名稱": "Customer", "包裝重量1": "1", "包裝份數1": "3",
    })

    assert list_production_orders(config)[0]["顏色"] == "Dark Red"
    with connect(db) as conn:
        order = conn.execute("SELECT * FROM production_orders WHERE production_order_id='O001'").fetchone()
        package = conn.execute(
            "SELECT package_count FROM production_order_packages WHERE production_order_id='O001'"
        ).fetchone()
    assert order["recipe_version"] == 1
    assert '"colorpowder_id": "P001"' in order["recipe_snapshot_json"]
    assert package["package_count"] == 3

    worksheet = WritableWorksheet()
    values = [["生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "包裝重量1", "包裝份數1"]]
    preflight = sync_production_order_outbox(worksheet, values, db_config=config, dry_run=True)
    applied = sync_production_order_outbox(worksheet, values, db_config=config, dry_run=False)
    assert preflight.queued == 1
    assert preflight.to_insert == 1
    assert applied.written == 1
    assert worksheet.appended[0] == ["O001", "2026-08-17", "R001", "Dark Red", "Customer", "1", "3"]


def test_production_order_edit_keeps_original_order_id(tmp_path):
    db = tmp_path / "production-order-edit.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "顏色": "Red",
    })

    updated = update_production_order(
        config,
        {"生產單號": "O999", "生產日期": "2026-08-17", "顏色": "Blue"},
        original_order_id="O001",
    )

    assert updated["生產單號"] == "O001"
    assert [(row["生產單號"], row["顏色"]) for row in list_production_orders(config)] == [
        ("O001", "Blue")
    ]
    with connect(db) as conn:
        order_ids = conn.execute(
            "SELECT production_order_id FROM production_orders ORDER BY production_order_id"
        ).fetchall()
    assert [row["production_order_id"] for row in order_ids] == ["O001"]


def test_production_order_cancel_restore_preserves_history_and_queues_updates(tmp_path):
    db = tmp_path / "production-lifecycle.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "1"})
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001",
        "顏色": "Red", "客戶名稱": "Customer", "包裝重量1": "1", "包裝份數1": "2",
    })

    cancelled = set_production_order_cancelled(
        config, "O001", cancelled=True, reason="客戶取消"
    )

    assert cancelled["取消狀態"] == "已取消"
    assert list_production_orders(config) == []
    historical = list_production_orders(config, include_cancelled=True)[0]
    assert historical["生產單號"] == "O001"
    assert historical["取消原因"] == "客戶取消"
    with connect(db) as conn:
        entity = conn.execute(
            "SELECT cancelled_at, cancel_reason, recipe_snapshot_json FROM production_orders WHERE production_order_id='O001'"
        ).fetchone()
        events = conn.execute(
            "SELECT operation, entity_version FROM sync_outbox WHERE sheet_name='生產單' ORDER BY id"
        ).fetchall()
    assert entity["cancelled_at"]
    assert entity["cancel_reason"] == "客戶取消"
    assert '"colorpowder_id": "P001"' in entity["recipe_snapshot_json"]
    assert [tuple(row) for row in events] == [("insert", 1), ("delete", 2)]

    with pytest.raises(ProductionOrderError, match="已取消"):
        update_production_order(config, historical)
    with pytest.raises(ProductionOrderError, match="已取消"):
        set_production_order_cancelled(config, "O001", cancelled=True, reason="再次取消")

    restored = set_production_order_cancelled(config, "O001", cancelled=False)
    assert restored["取消狀態"] == "有效"
    assert list_production_orders(config)[0]["生產單號"] == "O001"
    with connect(db) as conn:
        entity = conn.execute(
            "SELECT status, cancelled_at, cancel_reason FROM production_orders WHERE production_order_id='O001'"
        ).fetchone()
    assert tuple(entity) == ("draft", None, None)


def test_production_order_cancel_requires_reason(tmp_path):
    db = tmp_path / "production-cancel-reason.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_production_order(config, {"生產單號": "O001", "生產日期": "2026-08-17"})

    with pytest.raises(ProductionOrderError, match="取消原因"):
        set_production_order_cancelled(config, "O001", cancelled=True, reason="")

    assert list_production_orders(config)[0]["取消狀態"] == "有效"


def test_cancelled_order_and_reversed_inventory_are_removed_from_sheet(tmp_path):
    db = tmp_path / "operational-tombstones.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_inventory_movement(config, {
        "類型": "進貨", "色粉編號": "P001", "日期": "2026/08/17",
        "數量": 5, "單位": "kg", "_sync_id": "INV001",
    })
    create_production_order(config, {"生產單號": "O001", "生產日期": "2026-08-17"})
    inventory_ws = WritableWorksheet()
    inventory_header = ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"]
    order_ws = WritableWorksheet()
    order_header = ["生產單號", "生產日期"]
    sync_inventory_outbox(inventory_ws, [inventory_header], db_config=config, dry_run=False)
    sync_production_order_outbox(order_ws, [order_header], db_config=config, dry_run=False)

    reverse_inventory_movement(config, "INV001", reason="登錄錯誤", reversal_sync_id="REV001")
    set_production_order_cancelled(config, "O001", cancelled=True, reason="取消")
    inventory_values = [inventory_header, inventory_ws.appended[0]]
    order_values = [order_header, order_ws.appended[0]]
    inventory_preflight = sync_inventory_outbox(
        inventory_ws, inventory_values, db_config=config, dry_run=True
    )
    order_preflight = sync_production_order_outbox(
        order_ws, order_values, db_config=config, dry_run=True
    )
    sync_inventory_outbox(inventory_ws, inventory_values, db_config=config, dry_run=False)
    sync_production_order_outbox(order_ws, order_values, db_config=config, dry_run=False)

    assert inventory_preflight.to_delete == 1
    assert order_preflight.to_delete == 1
    assert inventory_ws.deleted == [2]
    assert order_ws.deleted == [2]
    assert len(list_inventory_movements(config)) == 2
    assert list_production_orders(config, include_cancelled=True)[0]["取消狀態"] == "已取消"


def test_outbox_claim_prevents_concurrent_duplicate_production_append(tmp_path):
    db = tmp_path / "production-concurrent-push.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "1"})
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001", "顏色": "Red",
    })
    values = [["生產單號", "生產日期", "配方編號", "顏色"]]

    class ConcurrentWorksheet(WritableWorksheet):
        def __init__(self):
            super().__init__()
            self.concurrent_result = None

        def append_row(self, row):
            self.concurrent_result = sync_production_order_outbox(
                self, values, db_config=config, dry_run=False,
            )
            super().append_row(row)

    worksheet = ConcurrentWorksheet()
    applied = sync_production_order_outbox(worksheet, values, db_config=config, dry_run=False)

    assert applied.written == 1
    assert len(worksheet.appended) == 1
    assert worksheet.concurrent_result.written == 0
    assert worksheet.concurrent_result.conflicts == 1


def test_processing_outbox_is_reconciled_without_second_append(tmp_path):
    db = tmp_path / "production-processing-recovery.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "1"})
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001", "顏色": "Red",
    })
    with connect(db) as conn:
        conn.execute("UPDATE sync_outbox SET status='completed' WHERE sheet_name != '生產單'")
        conn.execute("UPDATE sync_outbox SET status='processing' WHERE sheet_name = '生產單'")
    values = [
        ["生產單號", "生產日期", "配方編號", "顏色"],
        ["O001", "2026-08-17", "R001", "Red"],
    ]
    worksheet = WritableWorksheet()

    recovered = sync_production_order_outbox(worksheet, values, db_config=config, dry_run=False)
    verification = sync_production_order_outbox(worksheet, values, db_config=config, dry_run=True)

    assert recovered.unchanged == 1
    assert recovered.written == 0
    assert worksheet.appended == []
    assert verification.queued == 0


def test_outbox_push_never_overlaps_database_sessions(tmp_path, monkeypatch):
    db = tmp_path / "isolated-outbox-sessions.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "1"})
    create_production_order(config, {
        "生產單號": "O001", "生產日期": "2026-08-17", "配方編號": "R001", "顏色": "Red",
    })
    original_connect = sheet_export_module.connect_from_config
    active_sessions = 0

    @contextmanager
    def tracked_connect(tracked_config):
        nonlocal active_sessions
        assert active_sessions == 0, "outbox opened overlapping database sessions"
        active_sessions += 1
        try:
            with original_connect(tracked_config) as conn:
                yield conn
        finally:
            active_sessions -= 1

    monkeypatch.setattr(sheet_export_module, "connect_from_config", tracked_connect)
    worksheet = WritableWorksheet()
    applied = sync_production_order_outbox(
        worksheet,
        [["生產單號", "生產日期", "配方編號", "顏色"]],
        db_config=config,
        dry_run=False,
    )

    assert applied.written == 1
    assert active_sessions == 0


def test_schema_v7_backfills_production_orders_and_packages_from_baseline(tmp_path):
    db = tmp_path / "legacy-production.db"
    initialize_database(db)
    payload = {
        "生產單號": "O001", "生產日期": "2026-08-17", "顏色": "Red",
        "客戶名稱": "Customer", "包裝重量1": "2", "包裝份數1": "3",
    }
    with connect(db) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version=7")
        conn.execute("DROP TABLE production_order_packages")
        conn.execute("DROP TABLE production_orders")
        conn.execute(
            """INSERT INTO sheet_rows(
                   sheet_name, row_key, payload_json, row_hash, created_at, updated_at,
                   last_seen_at, last_synced_at)
               VALUES ('生產單', 'O001', ?, 'hash', '2026-01-01', '2026-01-01',
                       '2026-01-01', '2026-01-01')""",
            (json.dumps(payload, ensure_ascii=False),),
        )

    initialize_database(db)

    with connect(db) as conn:
        order = conn.execute("SELECT * FROM production_orders WHERE production_order_id='O001'").fetchone()
        package = conn.execute(
            "SELECT package_weight, package_count FROM production_order_packages WHERE production_order_id='O001'"
        ).fetchone()
    assert order["customer_name"] == "Customer"
    assert json.loads(order["payload_json"])["顏色"] == "Red"
    assert (package["package_weight"], package["package_count"]) == (2, 3)


def test_production_order_sheet_increment_imports_new_order_after_baseline(tmp_path):
    db = tmp_path / "production-increment.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001"))
    create_recipe(config, {"配方編號": "R001", "色粉編號1": "P001", "色粉重量1": "1"})
    headers = [
        "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "包裝重量1", "包裝份數1",
    ]
    baseline = [headers, ["O001", "2026-08-16", "R001", "Red", "Customer", "1", "2"]]
    import_sheet_values("生產單", baseline, db_path=db, abort_on_issues=True)

    latest = baseline + [["O002", "2026-08-17", "R001", "Blue", "Customer", "2", "3"]]
    preflight = import_sheet_values("生產單", latest, db_path=db, dry_run=True)
    assert preflight.to_insert == 1
    assert preflight.unchanged == 1

    applied = import_sheet_values("生產單", latest, db_path=db, abort_on_issues=True)
    verification = import_sheet_values("生產單", latest, db_path=db, dry_run=True)
    assert applied.inserted_or_updated == 1
    assert verification.unchanged == 2
    assert {row["生產單號"] for row in list_production_orders(config)} == {"O001", "O002"}


def test_recipe_import_persists_components_and_is_idempotent(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        for powder_id in ("P001", "P002"):
            conn.execute(
                """INSERT INTO color_powders(
                       colorpowder_id, created_at, updated_at, last_synced_at
                   ) VALUES (?, ?, ?, ?)""",
                (powder_id, "2026-08-14T00:00:00+00:00", "2026-08-14T00:00:00+00:00", None),
            )
    values = [
        [
            "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
            "色粉編號1", "色粉編號2", "色粉重量1", "色粉重量2", "淨重", "淨重單位", "備註",
        ],
        ["R001", "紅", "C001", "客戶甲", "正式", "啟用", "P001", "P002", "2.5", "1.5", "4", "kg", "test"],
    ]

    first = import_sheet_values("配方管理", values, db_path=db, abort_on_issues=True)
    second = import_sheet_values("配方管理", values, db_path=db, dry_run=True)

    assert first.inserted_or_updated == 1
    assert second.unchanged == 1
    with connect(db) as conn:
        recipe = conn.execute("SELECT * FROM recipes WHERE recipe_id = 'R001'").fetchone()
        components = conn.execute(
            "SELECT position, colorpowder_id, weight FROM recipe_components WHERE recipe_id = 'R001' ORDER BY position"
        ).fetchall()
    assert recipe["color"] == "紅"
    assert recipe["customer_id"] == "C001"
    assert recipe["net_weight"] == 4
    assert [(row["position"], row["colorpowder_id"], row["weight"]) for row in components] == [
        (1, "P001", 2.5),
        (2, "P002", 1.5),
    ]


def test_recipe_dry_run_rejects_unknown_component_powder(tmp_path):
    values = [
        ["配方編號", "色粉編號1", "色粉重量1"],
        ["R001", "UNKNOWN", "1"],
    ]

    result = import_sheet_values("配方管理", values, db_path=tmp_path / "colorpowder.db", dry_run=True)

    assert result.errors == ["row 2: unknown 色粉編號1 UNKNOWN; import 色粉管理 first"]
    assert result.inserted_or_updated == 0


def test_atomic_import_rolls_back_every_row_when_duplicate_is_found(tmp_path):
    db = tmp_path / "colorpowder.db"
    values = [
        ["色粉編號", "名稱"],
        ["P001", "First"],
        ["P002", "Second"],
        ["P001", "Duplicate"],
    ]

    with pytest.raises(ImportAbortedError) as error:
        import_sheet_values(
            "色粉管理",
            values,
            db_path=db,
            abort_on_issues=True,
        )

    assert error.value.result.duplicate_ids == ["P001"]
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM color_powders").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sheet_rows").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sync_log").fetchone()[0] == 0


def test_dry_run_flags_database_entity_without_sheet_baseline_as_conflict(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT INTO color_powders(
                   colorpowder_id, name, created_at, updated_at, last_synced_at
               ) VALUES (?, ?, ?, ?, ?)""",
            ("P001", "Turso value", "2026-08-14T00:00:00+00:00", "2026-08-14T00:00:00+00:00", None),
        )

    result = import_sheet_values(
        "色粉管理",
        [["色粉編號", "名稱"], ["P001", "Sheet value"]],
        db_path=db,
        dry_run=True,
    )

    assert result.conflicts == 1
    assert result.inserted_or_updated == 0
    with connect(db) as conn:
        assert conn.execute(
            "SELECT name FROM color_powders WHERE colorpowder_id = ?", ("P001",)
        ).fetchone()[0] == "Turso value"


def test_import_inventory_is_idempotent_for_same_sheet_row(tmp_path):
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"],
        ["進貨", "P001", "2026-08-12", "15", "kg", "direct sheet import", "SUP-1", "甲廠商", "sync-001"],
    ]
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT INTO color_powders(
                   colorpowder_id, created_at, updated_at, last_synced_at
               ) VALUES (?, ?, ?, ?)""",
            ("P001", "2026-08-14T00:00:00+00:00", "2026-08-14T00:00:00+00:00", None),
        )
        conn.execute(
            """INSERT INTO suppliers(
                   supplier_id, name, created_at, updated_at, last_synced_at
               ) VALUES (?, ?, ?, ?, ?)""",
            ("SUP-1", "甲廠商", "2026-08-14T00:00:00+00:00", "2026-08-14T00:00:00+00:00", None),
        )
    first = import_sheet_values("庫存記錄", values, db_path=db)
    second = import_sheet_values("庫存記錄", values, db_path=db)
    assert first.ok
    assert second.unchanged == 1
    with connect(db) as conn:
        powder_count = conn.execute("SELECT COUNT(*) FROM color_powders WHERE colorpowder_id='P001'").fetchone()[0]
        movement_count = conn.execute("SELECT COUNT(*) FROM inventory_movements WHERE colorpowder_id='P001'").fetchone()[0]
        movement = conn.execute(
            "SELECT movement_key, supplier_id, supplier_name FROM inventory_movements WHERE colorpowder_id='P001'"
        ).fetchone()
    assert powder_count == 1
    assert movement_count == 1
    assert movement["movement_key"] == "sheet:庫存記錄:sync-001"
    assert movement["supplier_id"] == "SUP-1"
    assert movement["supplier_name"] == "甲廠商"


def test_inventory_dry_run_requires_sync_id(tmp_path):
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"],
        ["初始", "P001", "2026-08-12", "15", "kg", "", "", "", ""],
    ]

    result = import_sheet_values("庫存記錄", values, db_path=tmp_path / "colorpowder.db", dry_run=True)

    assert result.errors == ["row 2: missing _sync_id"]
    assert result.to_insert == 0


def test_inventory_dry_run_rejects_unknown_color_powder(tmp_path):
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"],
        ["進貨", "UNKNOWN", "2026-08-12", "15", "kg", "", "", "", "sync-001"],
    ]

    result = import_sheet_values("庫存記錄", values, db_path=tmp_path / "colorpowder.db", dry_run=True)

    assert result.errors == ["row 2: unknown 色粉編號 UNKNOWN; import 色粉管理 first"]
    assert result.inserted_or_updated == 0


def test_inventory_dry_run_rejects_unknown_supplier(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT INTO color_powders(
                   colorpowder_id, created_at, updated_at, last_synced_at
               ) VALUES (?, ?, ?, ?)""",
            ("P001", "2026-08-14T00:00:00+00:00", "2026-08-14T00:00:00+00:00", None),
        )
    values = [
        ["類型", "色粉編號", "日期", "數量", "單位", "備註", "廠商編號", "廠商名稱", "_sync_id"],
        ["進貨", "P001", "2026-08-12", "15", "kg", "", "UNKNOWN", "未知", "sync-001"],
    ]

    result = import_sheet_values("庫存記錄", values, db_path=db, dry_run=True)

    assert result.errors == ["row 2: unknown 廠商編號 UNKNOWN; import 供應商管理 first"]
    assert result.inserted_or_updated == 0


def test_missing_inventory_sync_id_updates_only_nonempty_rows():
    counter = iter(["generated-1", "generated-2"])
    values = [
        ["類型", "色粉編號", "_sync_id"],
        ["初始", "P001", ""],
        ["進貨", "P002", "existing-id"],
        ["", "", ""],
        ["進貨", "P003", ""],
    ]

    updates = missing_inventory_sync_id_updates(values, id_factory=lambda: next(counter))

    assert updates == [(2, 3, "generated-1"), (5, 3, "generated-2")]


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
    assert result.warnings == [
        "Sheet has no explicit updated_at/更新時間 column; row_hash is used for change detection, "
        "and conflicts protect database edits, including Turso."
    ]
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


def test_supplier_import_accepts_supplier_code_and_short_name_headers(tmp_path):
    db = tmp_path / "colorpowder.db"
    values = [
        ["供應商編號", "供應商簡稱", "備註"],
        ["SUP-001", "甲供應商", "常用"],
    ]

    dry_run = import_sheet_values("供應商管理", values, db_path=db, dry_run=True)

    assert dry_run.ok
    assert dry_run.to_insert == 1
    assert dry_run.errors == []

    result = import_sheet_values("供應商管理", values, db_path=db)

    assert result.ok
    assert result.inserted_or_updated == 1
    with connect(db) as conn:
        supplier = conn.execute(
            "SELECT supplier_id, name, notes FROM suppliers WHERE supplier_id = ?",
            ("SUP-001",),
        ).fetchone()
    assert supplier["supplier_id"] == "SUP-001"
    assert supplier["name"] == "甲供應商"
    assert supplier["notes"] == "常用"


def test_database_health_check_reports_current_schema(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = database_config_from_secrets({})
    config = config.__class__(backend="sqlite", path=db)
    health = database_health_check(config)
    assert health.backend == "sqlite"
    assert health.select_1_ok
    assert health.schema_version == SCHEMA_VERSION
    assert health.main_tables_exist
    assert health.schema_compatible
    assert health.missing_required_columns == {}


def test_initialize_database_with_health_initializes_and_validates_once(tmp_path):
    db = tmp_path / "combined-startup.db"
    config = DatabaseConfig(backend="sqlite", path=db)

    initialized, health = initialize_database_with_health(config)

    assert initialized == db
    assert db.exists()
    assert health.backend == "sqlite"
    assert health.select_1_ok
    assert health.schema_version == SCHEMA_VERSION
    assert health.schema_compatible


def test_initialize_database_with_health_skips_schema_ddl_when_current(tmp_path, monkeypatch):
    db = tmp_path / "current-schema.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    schema_initializations = 0
    original_initialize_schema = database_module._initialize_schema

    def counted_initialize_schema(conn):
        nonlocal schema_initializations
        schema_initializations += 1
        return original_initialize_schema(conn)

    monkeypatch.setattr(database_module, "_initialize_schema", counted_initialize_schema)

    initialized, health = initialize_database_with_health(config)

    assert initialized == db
    assert health.schema_version == SCHEMA_VERSION
    assert health.schema_compatible
    assert schema_initializations == 0


def test_initialize_database_with_health_retries_transient_turso_session_error(monkeypatch):
    config = DatabaseConfig(
        backend="turso",
        path=None,
        turso_database_url="libsql://example.turso.io",
        turso_auth_token="token",
    )
    attempts = 0
    expected_health = database_module.DatabaseHealth(
        backend="turso",
        select_1_ok=True,
        schema_version=SCHEMA_VERSION,
        existing_tables=set(database_module.MAIN_TABLES),
        missing_required_columns={},
    )

    def initialize_connection(_config):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Tried to use SessionInfo before it was initialized")
        return expected_health

    monkeypatch.setattr(database_module, "_initialize_database_connection", initialize_connection)
    monkeypatch.setattr(database_module.time, "sleep", lambda _delay: None)

    initialized, health = initialize_database_with_health(config)

    assert initialized == "turso"
    assert health is expected_health
    assert attempts == 2


def test_initialize_database_connection_does_not_treat_session_error_as_missing_schema(monkeypatch):
    config = DatabaseConfig(backend="sqlite")
    schema_initializations = 0

    @contextmanager
    def fake_connection(_config):
        yield object()

    def failed_health_check(_config, _conn):
        raise RuntimeError("Tried to use SessionInfo before it was initialized")

    def counted_initialize_schema(_conn):
        nonlocal schema_initializations
        schema_initializations += 1

    monkeypatch.setattr(database_module, "connect_from_config", fake_connection)
    monkeypatch.setattr(database_module, "_database_health_from_connection", failed_health_check)
    monkeypatch.setattr(database_module, "_initialize_schema", counted_initialize_schema)

    with pytest.raises(RuntimeError, match="SessionInfo"):
        database_module._initialize_database_connection(config)

    assert schema_initializations == 0


def test_partial_turso_credentials_fail_fast(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    with pytest.raises(DatabaseStartupError, match="missing TURSO_AUTH_TOKEN"):
        database_config_from_secrets({"TURSO_DATABASE_URL": "libsql://example.turso.io"})
    with pytest.raises(DatabaseStartupError, match="missing TURSO_DATABASE_URL"):
        database_config_from_secrets({"TURSO_AUTH_TOKEN": "secret-token"})


def test_complete_turso_credentials_select_turso_backend(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    config = database_config_from_secrets({
        "TURSO_DATABASE_URL": "libsql://example.turso.io",
        "TURSO_AUTH_TOKEN": "secret-token",
    })
    assert config.backend == "turso"
    assert config.path is None
    assert config.turso_database_url == "libsql://example.turso.io"
    assert config.turso_auth_token == "secret-token"


@pytest.mark.parametrize(
    "secrets",
    [
        {
            "turso": {
                "database_url": "libsql://nested.turso.io",
                "auth_token": "nested-token",
            }
        },
        {
            "connections": {
                "turso": {
                    "url": "libsql://nested.turso.io",
                    "token": "nested-token",
                }
            }
        },
    ],
)
def test_nested_streamlit_secrets_select_turso_backend(monkeypatch, secrets):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    config = database_config_from_secrets(secrets)

    assert config.backend == "turso"
    assert config.path is None
    assert config.turso_database_url == "libsql://nested.turso.io"
    assert config.turso_auth_token == "nested-token"


def test_partial_nested_turso_credentials_fail_fast(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(DatabaseStartupError, match="missing TURSO_AUTH_TOKEN"):
        database_config_from_secrets(
            {"connections": {"turso": {"url": "libsql://nested.turso.io"}}}
        )


def test_connect_from_config_uses_turso_transaction_lifecycle(monkeypatch):
    events = []

    class FakeTursoConnection:
        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    fake = FakeTursoConnection()
    monkeypatch.setattr("utils.database._connect_turso", lambda config: fake)
    config = DatabaseConfig(
        backend="turso",
        path=None,
        turso_database_url="libsql://example.turso.io",
        turso_auth_token="secret-token",
    )

    with connect_from_config(config) as conn:
        assert conn is fake

    assert events == ["commit", "close"]


def test_connect_from_config_rolls_back_failed_turso_transaction(monkeypatch):
    events = []

    class FakeTursoConnection:
        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    monkeypatch.setattr("utils.database._connect_turso", lambda config: FakeTursoConnection())
    config = DatabaseConfig(
        backend="turso",
        path=None,
        turso_database_url="libsql://example.turso.io",
        turso_auth_token="secret-token",
    )

    with pytest.raises(RuntimeError, match="write failed"):
        with connect_from_config(config):
            raise RuntimeError("write failed")

    assert events == ["rollback", "close"]


def test_import_sheet_values_accepts_database_config(tmp_path):
    db = tmp_path / "configured.db"
    config = DatabaseConfig(backend="sqlite", path=db)
    values = [
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        ["P-CONFIG", "I-CONFIG", "Configured", "色粉", "袋", ""],
    ]

    result = import_sheet_values("色粉管理", values, db_config=config)

    assert result.to_insert == 1
    with connect(db) as conn:
        assert conn.execute(
            "SELECT name FROM color_powders WHERE colorpowder_id = ?", ("P-CONFIG",)
        ).fetchone()[0] == "Configured"


def test_import_sheet_values_routes_turso_config_through_shared_connection(monkeypatch, tmp_path):
    db = tmp_path / "turso-test-double.db"
    initialize_database(db)
    seen_configs = []

    @contextmanager
    def fake_connect_from_config(config):
        seen_configs.append(config)
        with connect(db) as conn:
            yield conn

    monkeypatch.setattr("utils.sheet_import.initialize_database_from_config", lambda config: None)
    monkeypatch.setattr("utils.sheet_import.connect_from_config", fake_connect_from_config)
    config = DatabaseConfig(
        backend="turso",
        path=None,
        turso_database_url="libsql://example.turso.io",
        turso_auth_token="secret-token",
    )
    values = [
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        ["P-TURSO", "I-TURSO", "Remote", "色粉", "袋", ""],
    ]

    result = import_sheet_values("色粉管理", values, db_config=config)

    assert result.inserted_or_updated == 1
    assert seen_configs == [config]
    with connect(db) as conn:
        assert conn.execute(
            "SELECT name FROM color_powders WHERE colorpowder_id = ?", ("P-TURSO",)
        ).fetchone()[0] == "Remote"


def test_importer_normalizes_libsql_tuple_rows(monkeypatch, tmp_path):
    db = tmp_path / "tuple-row-test-double.db"
    initialize_database(db)

    class TupleCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        @property
        def description(self):
            return self._cursor.description

        def fetchone(self):
            row = self._cursor.fetchone()
            return tuple(row) if row is not None else None

        def fetchall(self):
            return [tuple(row) for row in self._cursor.fetchall()]

    class TupleRowConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, parameters=()):
            return TupleCursor(self._conn.execute(sql, parameters))

        def rollback(self):
            return self._conn.rollback()

    @contextmanager
    def fake_connect_from_config(_config):
        with connect(db) as conn:
            yield TupleRowConnection(conn)

    monkeypatch.setattr("utils.sheet_import.initialize_database_from_config", lambda config: None)
    monkeypatch.setattr("utils.sheet_import.connect_from_config", fake_connect_from_config)
    config = DatabaseConfig(
        backend="turso",
        path=None,
        turso_database_url="libsql://example.turso.io",
        turso_auth_token="secret-token",
    )

    first = import_sheet_values(
        "色粉管理",
        [["色粉編號", "名稱"], ["P001", "Original"]],
        db_config=config,
    )
    changed = import_sheet_values(
        "色粉管理",
        [["色粉編號", "名稱"], ["P001", "Changed"]],
        db_config=config,
        dry_run=True,
    )

    assert first.inserted_or_updated == 1
    assert changed.to_update == 1
    assert changed.conflicts == 0


def test_import_sheet_values_rejects_path_and_config_together(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "configured.db")

    with pytest.raises(ValueError, match="either db_config or db_path"):
        import_sheet_values("色粉管理", [], db_path=tmp_path / "other.db", db_config=config)


def test_import_sheet_values_can_skip_schema_initialization(monkeypatch, tmp_path):
    db = tmp_path / "already-initialized.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)

    def unexpected_initialization(_config):
        raise AssertionError("schema initialization should have been skipped")

    monkeypatch.setattr(
        "utils.sheet_import.initialize_database_from_config",
        unexpected_initialization,
    )
    result = import_sheet_values(
        "色粉管理",
        [["色粉編號", "名稱"], ["P001", "Blue"]],
        db_config=config,
        dry_run=True,
        initialize_schema=False,
    )

    assert result.to_insert == 1
    assert result.inserted_or_updated == 0


def test_database_startup_diagnostics_do_not_include_token_value(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = database_config_from_secrets({})
    config = config.__class__(backend="sqlite", path=db)
    health = database_health_check(config)
    lines = format_database_startup_diagnostics(
        config,
        health,
        {"TURSO_DATABASE_URL": True, "TURSO_AUTH_TOKEN": True},
    )
    assert "Database backend: sqlite" in lines
    assert "Database health: OK" in lines
    assert f"Schema version: {SCHEMA_VERSION}" in lines
    assert "Required columns present: True" in lines
    assert "TURSO_AUTH_TOKEN configured: True" in lines
    assert "secret-token" not in "\n".join(lines)


def test_database_startup_diagnostics_are_logged_once(caplog, tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    health = database_health_check(config)

    with caplog.at_level(logging.WARNING, logger="utils.database"):
        log_database_startup_diagnostics(
            config,
            health,
            {"TURSO_DATABASE_URL": False, "TURSO_AUTH_TOKEN": False},
        )

    messages = [record.getMessage() for record in caplog.records]
    assert messages.count("Database backend: sqlite") == 1
    assert messages.count("Database health: OK") == 1


class NonIterableCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        raise TypeError("'builtins.Cursor' object is not iterable")


class NonIterableCursorConnection:
    """SQLite-backed test double matching libsql 0.1.11 non-iterable cursors."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, parameters=()):
        return NonIterableCursor(self._conn.execute(sql, parameters))


def test_initialize_schema_does_not_iterate_cursor_directly(tmp_path):
    from utils.database import _initialize_schema

    db = tmp_path / "colorpowder.db"
    with connect(db) as conn:
        non_iterable_conn = NonIterableCursorConnection(conn)
        _initialize_schema(non_iterable_conn)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        inventory_cols = conn.execute("PRAGMA table_info(inventory_movements)").fetchall()

    assert "color_powders" in {row[0] for row in tables}
    assert "movement_key" in {row[1] for row in inventory_cols}


def test_safe_worker_lock_is_exclusive_and_releasable(tmp_path):
    db = tmp_path / "worker-lock.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)

    assert acquire_worker_lock(config, lock_name="worker", owner_id="first")
    assert not acquire_worker_lock(config, lock_name="worker", owner_id="second")
    release_worker_lock(config, lock_name="worker", owner_id="first")
    assert acquire_worker_lock(config, lock_name="worker", owner_id="second")


def test_safe_mode_retains_delete_events_for_manual_push(tmp_path):
    db = tmp_path / "safe-delete.db"
    values = [["色粉編號", "名稱"], ["P001", "Red"]]
    import_sheet_values("色粉管理", values, db_path=db, abort_on_issues=True)
    config = DatabaseConfig(backend="sqlite", path=db)
    set_color_powder_active(config, "P001", active=False, reason="停止使用")

    result = sync_color_powder_outbox(
        WritableWorksheet(), values, db_config=config, dry_run=False,
        allow_deletes=False, max_entries=25,
    )

    assert result.queued == 0
    assert result.written == 0
    assert result.skipped_deletes == 1
    with connect(db) as conn:
        latest = conn.execute(
            "SELECT operation, status FROM sync_outbox ORDER BY entity_version DESC LIMIT 1"
        ).fetchone()
    assert tuple(latest) == ("delete", "pending")


def test_controlled_worker_applies_baseline_protected_delete(tmp_path):
    db = tmp_path / "controlled-delete.db"
    values = [["色粉編號", "名稱"], ["P001", "Red"]]
    import_sheet_values("色粉管理", values, db_path=db, abort_on_issues=True)
    config = DatabaseConfig(backend="sqlite", path=db)
    set_color_powder_active(config, "P001", active=False, reason="停止使用")

    class DeleteWorksheet(WritableWorksheet):
        def get_all_values(self):
            return values

    class DeleteSpreadsheet:
        def __init__(self):
            self.sheet = DeleteWorksheet()

        def worksheet(self, name):
            assert name == "色粉管理"
            return self.sheet

    spreadsheet = DeleteSpreadsheet()
    result = run_safe_worker(
        spreadsheet,
        db_config=config,
        dry_run=False,
        batch_size=1,
        allow_deletes=True,
    )

    assert result.ok
    assert result.allow_deletes
    assert result.sheets[0]["to_delete"] == 1
    assert result.sheets[0]["written"] == 1
    assert spreadsheet.sheet.deleted == [2]
    with connect(db) as conn:
        lifecycle = conn.execute(
            "SELECT lifecycle_status FROM color_powders WHERE colorpowder_id='P001'"
        ).fetchone()[0]
        status = conn.execute(
            "SELECT status FROM sync_outbox ORDER BY entity_version DESC LIMIT 1"
        ).fetchone()[0]
    assert lifecycle == "inactive"
    assert status == "completed"


def test_safe_worker_applies_only_one_bounded_insert(tmp_path):
    db = tmp_path / "safe-batch.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    create_color_powder(config, ColorPowderInput("P001", name="Red"))
    create_color_powder(config, ColorPowderInput("P002", name="Blue"))

    class WorkerWorksheet(WritableWorksheet):
        def get_all_values(self):
            return [["色粉編號", "名稱"]]

    class WorkerSpreadsheet:
        def __init__(self):
            self.sheet = WorkerWorksheet()

        def worksheet(self, name):
            assert name == "色粉管理"
            return self.sheet

    spreadsheet = WorkerSpreadsheet()
    result = run_safe_worker(
        spreadsheet, db_config=config, dry_run=False, batch_size=1,
    )

    assert result.ok
    assert result.sheets[0]["queued"] == 1
    assert result.sheets[0]["written"] == 1
    assert len(spreadsheet.sheet.appended) == 1
    with connect(db) as conn:
        statuses = conn.execute(
            "SELECT status FROM sync_outbox WHERE sheet_name='色粉管理' ORDER BY id"
        ).fetchall()
        locks = conn.execute("SELECT COUNT(*) FROM sync_worker_locks").fetchone()[0]
    assert [row[0] for row in statuses] == ["completed", "pending"]
    assert locks == 0
