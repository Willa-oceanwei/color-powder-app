from contextlib import contextmanager
import logging

import pytest

from utils.database import (
    DatabaseConfig,
    DatabaseStartupError,
    connect,
    connect_from_config,
    database_config_from_secrets,
    database_health_check,
    format_database_startup_diagnostics,
    initialize_database,
    log_database_startup_diagnostics,
)
from utils.sheet_import import (
    ImportAbortedError,
    SheetReadError,
    import_sheet_values,
    read_worksheet_values_with_retry,
)


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


def test_database_health_check_reports_schema_v2(tmp_path):
    db = tmp_path / "colorpowder.db"
    initialize_database(db)
    config = database_config_from_secrets({})
    config = config.__class__(backend="sqlite", path=db)
    health = database_health_check(config)
    assert health.backend == "sqlite"
    assert health.select_1_ok
    assert health.schema_version == 2
    assert health.main_tables_exist


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
    assert "Schema version: 2" in lines
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
