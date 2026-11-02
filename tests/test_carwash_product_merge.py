from copy import deepcopy
from datetime import date
from pathlib import Path
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, connect_from_config, initialize_database, initialize_database_with_health
from utils.carwash_inventory_repository import (
    CarwashInventoryError, save_carwash_inventory_movement, list_carwash_inventory_movements,
    calculate_carwash_inventory_balances,
)
from utils.carwash_product_repository import (
    list_carwash_aliases, preview_carwash_merge, merge_carwash_names, canonical_name, carwash_merge_history,
)
from utils.carwash_merge_ui import movement_frame
from utils.carwash_query import carwash_query_rows, group_carwash_rows


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "merge.db")
    initialize_database(config.path)
    for code, qty, day in [("K1035", 10, "2026-10-01"), ("PPK1035", 20, "2026-10-10")]:
        save_carwash_inventory_movement(config, {"類型": "初始庫存", "貨品編號": code,
            "初始庫存日期": day, "初始數量": qty, "單位": "KG"}, create=True)
    save_carwash_inventory_movement(config, {"類型": "出庫", "貨品編號": "K1035",
        "出庫日期": "2026-10-05", "數量": 2, "單位": "KG"}, create=True)
    return config


def snapshot(config, table):
    with connect_from_config(config) as conn:
        return [tuple(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def commit(config, source="K1035", target="PPK1035"):
    preview = preview_carwash_merge(config, source, target)
    return merge_carwash_names(config, source, target, preview["token"], actor="Q", confirm_initials=True)


def test_merge_changes_metadata_only_and_keeps_per_code_results(config):
    records = list_carwash_inventory_movements(config)
    rows = carwash_query_rows(movement_frame(records), today=date(2026, 11, 2))
    assert rows.set_index("產品編號")["目前庫存"].to_dict() == {"K1035": "8", "PPK1035": "20"}
    before = {table: snapshot(config, table) for table in ("carwash_inventory_movements", "inventory_movements", "sync_outbox")}
    balances = calculate_carwash_inventory_balances(records, as_of=date(2026, 11, 2))
    preview = preview_carwash_merge(config, "K1035", "PPK1035")
    assert preview["needs_initial_confirmation"]
    with pytest.raises(CarwashInventoryError, match="初始"):
        merge_carwash_names(config, "K1035", "PPK1035", preview["token"], actor="Q")
    assert not list_carwash_aliases(config)
    commit(config)
    assert all(snapshot(config, table) == values for table, values in before.items())
    assert calculate_carwash_inventory_balances(list_carwash_inventory_movements(config), as_of=date(2026, 11, 2)) == balances
    pd.testing.assert_frame_equal(carwash_query_rows(movement_frame(list_carwash_inventory_movements(config)), today=date(2026, 11, 2)), rows)
    aliases = list_carwash_aliases(config)
    merged = group_carwash_rows(rows, aliases)
    assert merged.iloc[0]["產品編號"] == "PPK1035" and merged.iloc[0]["目前庫存"] == "28"
    assert "K1035" in merged.iloc[0]["出入庫歷程"]
    assert canonical_name(" k1035 ", aliases) == "PPK1035"
    assert len(carwash_merge_history(config)) == 1


def test_stale_preview_units_and_already_merged_are_rejected(config):
    preview = preview_carwash_merge(config, "K1035", "PPK1035")
    save_carwash_inventory_movement(config, {"類型": "入庫", "貨品編號": "K1035",
        "入庫日期": "2026-10-20", "數量": 1, "單位": "KG"}, create=True)
    with pytest.raises(CarwashInventoryError, match="變更"):
        merge_carwash_names(config, "K1035", "PPK1035", preview["token"], actor="Q", confirm_initials=True)
    save_carwash_inventory_movement(config, {"類型": "入庫", "貨品編號": "OTHER",
        "入庫日期": "2026-10-20", "數量": 1, "單位": "包"}, create=True)
    with pytest.raises(CarwashInventoryError, match="單位"):
        preview_carwash_merge(config, "K1035", "OTHER")
    commit(config)
    with pytest.raises(CarwashInventoryError, match="不同"):
        preview_carwash_merge(config, "K1035", "PPK1035")


def test_group_chain_is_flat_and_later_old_name_records_keep_original_ledger(config):
    commit(config)
    save_carwash_inventory_movement(config, {"類型": "入庫", "貨品編號": "FINAL",
        "入庫日期": "2026-10-20", "數量": 5, "單位": "KG"}, create=True)
    commit(config, "PPK1035", "FINAL")
    aliases = list_carwash_aliases(config)
    assert canonical_name("K1035", aliases) == canonical_name("PPK1035", aliases) == "FINAL"
    saved = save_carwash_inventory_movement(config, {"類型": "出庫", "貨品編號": "K1035",
        "出庫日期": "2026-10-06", "數量": 1, "單位": "KG"}, create=True)
    assert saved["product_id"] == "K1035"
    rows = carwash_query_rows(movement_frame(list_carwash_inventory_movements(config)), today=date(2026, 11, 2))
    assert rows.set_index("產品編號").loc["K1035", "目前庫存"] == "7"
    assert group_carwash_rows(rows, aliases).iloc[0]["目前庫存"] == "32"


def test_upgrade_from_v32_does_not_rewrite_any_business_rows(config):
    from utils.database import MAIN_TABLES, CARWASH_MERGE_TABLES
    with connect_from_config(config) as conn:
        conn.execute("INSERT INTO recipes(recipe_id,source,created_at,updated_at,oem_multiplier) VALUES ('UNCHANGED','google_sheets_import','2026-01-01','2026-01-01',7)")
        conn.execute("INSERT INTO sheet_rows(sheet_name,row_key,payload_json,row_hash,created_at,updated_at,last_seen_at) VALUES ('配方管理','UNCHANGED',?,'hash','2026-01-01','2026-01-01','2026-01-01')",
                     (json.dumps({"配方編號": "UNCHANGED", "代工倍率": 2}),))
    before = {table: snapshot(config, table) for table in MAIN_TABLES - CARWASH_MERGE_TABLES}
    with connect_from_config(config) as conn:
        for table in ("carwash_product_aliases", "carwash_product_merge_log", "carwash_product_catalog"):
            conn.execute(f"DROP TABLE {table}")
        conn.execute("DELETE FROM schema_migrations WHERE version=33")
        conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (32,'2026-10-30')")
    _, health = initialize_database_with_health(config)
    assert health.schema_version == 33 and health.schema_compatible
    assert all(snapshot(config, table) == values for table, values in before.items())
    assert list_carwash_aliases(config) == []


def test_merge_ui_requires_preview_and_initial_confirmation(config):
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.carwash_inventory_repository import list_carwash_inventory_movements
from utils.carwash_product_repository import list_carwash_aliases
from utils.carwash_merge_ui import render_carwash_merge
config=DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r}))
render_carwash_merge(config,list_carwash_inventory_movements(config),list_carwash_aliases(config))
''').run(timeout=30)
    assert not app.exception
    assert not any(button.label == "確認合併編號" for button in app.button)
    app.button(key="cw_merge_preview_button").click().run()
    assert not app.exception
    assert app.button(key="cw_merge_commit").disabled
    assert app.metric[0].value == "28 KG"
    for toggle in app.toggle:
        toggle.set_value(True)
    app.button(key="cw_merge_commit").click().run()
    assert not app.exception and canonical_name("K1035", list_carwash_aliases(config)) == "PPK1035"


def test_merge_failure_rolls_back_aliases_log_and_revision(config, monkeypatch):
    from contextlib import contextmanager
    from utils import carwash_product_repository as repo
    preview = preview_carwash_merge(config, "K1035", "PPK1035")
    original = repo.connect_from_config
    @contextmanager
    def failing(config):
        with original(config) as conn:
            class Fault:
                def execute(self, sql, args=()):
                    if "INSERT INTO carwash_product_aliases" in sql:
                        raise RuntimeError("simulated write failure")
                    return conn.execute(sql, args)
            yield Fault()
    monkeypatch.setattr(repo, "connect_from_config", failing)
    with pytest.raises(RuntimeError):
        merge_carwash_names(config, "K1035", "PPK1035", preview["token"], actor="Q", confirm_initials=True)
    monkeypatch.setattr(repo, "connect_from_config", original)
    assert list_carwash_aliases(config) == [] and carwash_merge_history(config) == []
    assert preview_carwash_merge(config, "K1035", "PPK1035")["revision"] == preview["revision"]


def test_later_unit_conflict_does_not_add_incompatible_balances(config):
    commit(config)
    save_carwash_inventory_movement(config, {"類型": "入庫", "貨品編號": "K1035",
        "入庫日期": "2026-10-20", "數量": 1, "單位": "包"}, create=True)
    raw = carwash_query_rows(movement_frame(list_carwash_inventory_movements(config)), today=date(2026, 11, 2))
    grouped = group_carwash_rows(raw, list_carwash_aliases(config))
    assert len(grouped) == 2
    assert grouped.set_index("產品編號")["目前庫存"].to_dict() == raw.set_index("產品編號")["目前庫存"].to_dict()


def carwash_page(config):
    import ast
    root = str(Path(__file__).resolve().parents[1])
    source = (Path(root) / "app.py").read_text(encoding="utf-8")
    node = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "menu"
                and any(isinstance(value, ast.Constant) and value.value == "洗車廠庫存" for value in node.test.comparators))
    page = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
    return AppTest.from_string(f'''import sys, re, uuid
sys.path.insert(0,{root!r})
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.database import DatabaseConfig
from utils.carwash_inventory_repository import *
from utils.carwash_inventory_ui import show_carwash_save_notice
from utils.inventory_repository import create_inventory_movement
from utils.customer_display import CustomerDisplay
DATABASE_CONFIG=DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r}))
customer_display=CustomerDisplay(DATABASE_CONFIG)
def render_empty_state(message, **kwargs): st.info(message)
def invalidate_inventory_caches(): pass
{page}
''').run(timeout=30)


def test_page_preserves_original_query_and_offers_group_query_and_existing_picker(config):
    app = carwash_page(config)
    assert not app.exception
    assert "編號合併" in [tab.label for tab in app.tabs]
    next(button for button in app.button if button.label == "搜尋").click().run()
    assert not app.exception
    before = app.session_state["cw_inventory_result_df"]
    assert before.set_index("產品編號")["目前庫存"].to_dict() == {"K1035": "8", "PPK1035": "20"}
    commit(config)
    app.run()
    assert not app.exception
    assert "cw_inventory_result_df" not in app.session_state
    app.text_input(key="cw_query_pid").set_value("PPK1035")
    next(button for button in app.button if button.label == "搜尋").click().run()
    merged = app.session_state["cw_inventory_result_df"]
    assert merged["產品編號"].tolist() == ["PPK1035"]
    assert merged["目前庫存"].tolist() == ["28"]
    app.selectbox(key="cw_query_view").set_value("原編號明細")
    next(button for button in app.button if button.label == "搜尋").click().run()
    assert app.session_state["cw_inventory_result_df"]["目前庫存"].tolist() == ["20"]
    app.selectbox(key="cw_io_existing_name").set_value("PPK1035").run()
    assert not app.exception and app.text_input(key="cw_io_product_id").value == "PPK1035"

def test_merge_locks_movements_before_rechecking_preview(config, monkeypatch):
    import sqlite3
    from utils import carwash_product_repository as repo
    preview = preview_carwash_merge(config, "K1035", "PPK1035")
    original = repo._preview
    attempted = []
    def checked(conn, source, target):
        # A second writer must be blocked before any validation SELECT runs.
        other = sqlite3.connect(config.path, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("UPDATE carwash_inventory_movements SET unit='包' WHERE product_id='K1035'")
            attempted.append(True)
        finally:
            other.close()
        return original(conn, source, target)
    monkeypatch.setattr(repo, "_preview", checked)
    merge_carwash_names(config, "K1035", "PPK1035", preview["token"], actor="Q", confirm_initials=True)
    assert attempted == [True]
    assert {row["unit"] for row in list_carwash_inventory_movements(config)} == {"KG"}
