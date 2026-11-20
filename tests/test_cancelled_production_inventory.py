import ast
import json
from pathlib import Path
import re

import pandas as pd
import pytest

from utils.color_powder_repository import ColorPowderInput, create_color_powder
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.production_order_repository import (
    create_production_order, list_production_orders, set_production_order_cancelled,
    update_production_order,
)
from utils.recipe_repository import create_recipe, normalize_color_powder_id
from utils.production_inventory import (
    active_production_orders, prepare_inventory_orders, recorded_inventory_consumption, RESULT_KEYS,
)


def usage_function():
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"calc_usage_for_stock", "calc_packs_total_kg", "parse_pack_value",
              "safe_float", "safe_float_convert", "safe_int_convert", "clean_powder_id", "fix_leading_zero"}
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"pd": pd, "re": re, "normalize_color_powder_id": normalize_color_powder_id}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "inventory-functions", "exec"), namespace)
    return namespace["calc_usage_for_stock"]


def test_cancelled_order_releases_usage_and_restore_counts_exactly_once(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "inventory.db")
    initialize_database(config.path)
    recipe = {"配方編號": "R1", "色粉編號1": "P1", "色粉重量1": "5", "淨重": "10", "合計類別": "料"}
    create_color_powder(config, ColorPowderInput("P1", name="測試色粉"))
    create_recipe(config, recipe)
    create_production_order(config, {"生產單號": "P1", "配方編號": "R1",
        "生產日期": "2026-10-30", "建立時間": "2026-10-30 09:00:00", "包裝重量1": "10", "包裝份數1": "2"})
    calculate = usage_function()
    state = {}
    def consumption():
        frame = pd.DataFrame(list_production_orders(config, include_cancelled=True))
        frame["生產時間"] = "2026-10-30 09:00:00"
        active = prepare_inventory_orders(state, frame)
        # The real calculator is also defensive when passed the full history.
        usage = calculate("P1", frame, pd.DataFrame([recipe]), "2026-10-01", "2026-11-01")
        assert len(active) == (1 if usage else 0)
        return usage
    assert consumption() == 100
    state["stock_query_result"] = ["old result"]
    state["tab4_usage_result"] = ["old usage"]
    set_production_order_cancelled(config, "P1", cancelled=True, reason="不生產")
    assert consumption() == 0
    assert "stock_query_result" not in state and "tab4_usage_result" not in state
    assert len(list_production_orders(config, include_cancelled=True)) == 1
    set_production_order_cancelled(config, "P1", cancelled=False)
    assert consumption() == 100
    assert consumption() == 100


def test_existing_cached_results_expire_once_without_mutating_history():
    history = pd.DataFrame([{"生產單號": "A", "取消狀態": "有效"}, {"生產單號": "B", "取消狀態": "已取消"}])
    before = history.copy(deep=True)
    state = {key: ["stale"] for key in RESULT_KEYS}
    assert prepare_inventory_orders(state, history)["生產單號"].tolist() == ["A"]
    assert all(key not in state for key in RESULT_KEYS)
    state["stock_query_result"] = ["new result"]
    prepare_inventory_orders(state, history)
    assert state["stock_query_result"] == ["new result"]
    history.loc[1, "取消狀態"] = "有效"
    assert prepare_inventory_orders(state, history)["生產單號"].tolist() == ["A", "B"]
    assert "stock_query_result" not in state
    assert before.loc[1, "取消狀態"] == "已取消"


def test_unavailable_recipe_uses_complete_original_snapshot():
    snapshot = {
        "recipe_id": "R1",
        "components": [{"position": 1, "colorpowder_id": "P1", "weight": 5}],
        "net_weight": 10,
        "total_category": "料",
        "additional_recipes": [],
    }
    orders = pd.DataFrame([{
        "生產單號": "A", "配方編號": "R1", "生產時間": "2026-10-30 09:00:00",
        "包裝重量1": "10", "包裝份數1": "2", "_recipe_snapshot_json": json.dumps(snapshot),
    }])
    recipes = pd.DataFrame()
    orders["_inventory_consumption"] = recorded_inventory_consumption(orders, recipes)
    calculate = usage_function()
    assert calculate("P1", orders, recipes, "2026-10-01", "2026-11-01") == 100
    assert calculate("料", orders, recipes, "2026-10-01", "2026-11-01") == 100
    del snapshot["additional_recipes"]
    orders["_recipe_snapshot_json"] = json.dumps(snapshot)
    assert recorded_inventory_consumption(orders, recipes) == [None]
    orders["附加配方"] = "[]"
    assert recorded_inventory_consumption(orders, recipes)[0]["pigments"] == {"P1": 100}


def test_preview_archive_is_independent_of_approved_inventory_recovery(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "inventory.db")
    initialize_database(config.path)
    create_color_powder(config, ColorPowderInput("P1"))
    recipe = {"配方編號": "R1", "色粉編號1": "P1", "色粉重量1": "5"}
    create_recipe(config, recipe)
    order = {"生產單號": "A", "配方編號": "R1", "包裝重量1": "10", "包裝份數1": "2"}
    create_production_order(config, order)
    evidence = {
        "order": order, "recipe": recipe, "additional_recipes": [],
        "source": "原始試算表版本 2026-07-28 15:22",
    }
    with connect_from_config(config) as conn:
        conn.execute("UPDATE production_orders SET recipe_snapshot_json=NULL WHERE production_order_id='A'")
        conn.execute("UPDATE production_order_history_previews SET evidence_json=? WHERE production_order_id='A'",
                     (json.dumps(evidence),))

    def read_orders():
        return pd.DataFrame(list_production_orders(
            config, include_recipe_snapshot=True, include_inventory_evidence=True,
        ))

    assert recorded_inventory_consumption(read_orders(), pd.DataFrame()) == [None]
    with connect_from_config(config) as conn:
        conn.execute("INSERT INTO production_order_inventory_recoveries VALUES (?, ?, ?)",
                     ("A", json.dumps(evidence), "2026-11-20"))
        conn.execute("DELETE FROM production_order_history_previews WHERE production_order_id='A'")
    orders = read_orders()
    assert recorded_inventory_consumption(orders, pd.DataFrame())[0]["pigments"] == {"P1": 100}
    orders["包裝份數1"] = "3"
    assert recorded_inventory_consumption(orders, pd.DataFrame()) == [None]


def test_new_order_uses_frozen_consumption_after_master_recipe_changes(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "inventory.db")
    initialize_database(config.path)
    create_color_powder(config, ColorPowderInput("P1"))
    recipe = {"配方編號": "R1", "色粉編號1": "P1", "色粉重量1": "5"}
    create_recipe(config, recipe)
    order = {
        "生產單號": "A", "配方編號": "R1", "生產時間": "2026-10-30 09:00:00",
        "包裝重量1": "10", "包裝份數1": "2",
    }
    create_production_order(config, order)
    with connect_from_config(config) as conn:
        archived = conn.execute(
            "SELECT evidence_json FROM production_order_history_previews WHERE production_order_id='A'"
        ).fetchone()[0]
    assert json.loads(archived)["order"]["包裝份數1"] == "2"
    assert json.loads(archived)["recipe"]["色粉重量1"] == "5.0"
    master_after_edit = pd.DataFrame([{**recipe, "色粉重量1": "99"}])

    def current_usage():
        orders = pd.DataFrame(list_production_orders(config, include_recipe_snapshot=True))
        orders["_inventory_consumption"] = recorded_inventory_consumption(orders, master_after_edit)
        return usage_function()("P1", orders, master_after_edit, "2026-10-01", "2026-11-01")

    snapshot = json.loads(list_production_orders(config, include_recipe_snapshot=True)[0]["_recipe_snapshot_json"])
    assert snapshot["inventory_consumption_v1"]["grams"]["pigments"] == {"P1": 100}
    assert current_usage() == 100
    update_production_order(config, {**order, "包裝份數1": "3"})
    assert current_usage() == 150
    set_production_order_cancelled(config, "A", cancelled=True, reason="測試")
    assert current_usage() == 0
    set_production_order_cancelled(config, "A", cancelled=False)
    assert current_usage() == 150


@pytest.mark.parametrize("row, expected", [
    ({"生產單號": "legacy"}, True),
    ({"取消狀態": " 有效 ", "取消時間": ""}, True),
    ({"取消狀態": " 已取消 "}, False),
    ({"取消狀態": "有效", "取消時間": "2026-10-30"}, False),
])
def test_legacy_and_lifecycle_flags(row, expected):
    assert len(active_production_orders(pd.DataFrame([row]))) == int(expected)


def test_inventory_entry_refreshes_orders_once_and_uses_the_latest_lifecycle():
    from types import SimpleNamespace

    class InventoryState(dict):
        __setattr__ = dict.__setitem__

    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    inventory = source.split('elif menu == "庫存區":', 1)[1]
    order_load = inventory[inventory.index("    df_recipe ="):inventory.index('    if inventory_view == "master":')]
    entry = compile("if True:\n" + order_load, "inventory-entry", "exec")
    state = InventoryState(df_recipe=pd.DataFrame())
    calls = []
    rows = [{"生產單號": "A", "取消狀態": "有效"}]

    def read_orders(config, *, include_cancelled, include_recipe_snapshot, include_inventory_evidence):
        assert include_cancelled and include_recipe_snapshot and include_inventory_evidence
        calls.append(config)
        return rows

    config = object()
    namespace = {
        "st": SimpleNamespace(session_state=state),
        "pd": pd,
        "list_production_orders": read_orders,
        "DATABASE_CONFIG": config,
        "inventory_view": "query",
        "ORDER_VIEWS": {"query"},
        "RECIPE_VIEWS": {"query"},
    }
    exec(entry, namespace)
    assert calls == [config]
    assert namespace["df_order"]["生產單號"].tolist() == ["A"]

    state["stock_query_result"] = ["stale result"]
    rows = [{"生產單號": "A", "取消狀態": "已取消"}]
    exec(entry, namespace)
    assert calls == [config, config]
    assert state["df_order"]["取消狀態"].tolist() == ["已取消"]
    assert namespace["df_order"].empty
    assert "stock_query_result" not in state
