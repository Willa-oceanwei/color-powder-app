import ast
from pathlib import Path
import re

import pandas as pd
import pytest

from utils.color_powder_repository import ColorPowderInput, create_color_powder
from utils.database import DatabaseConfig, initialize_database
from utils.production_order_repository import create_production_order, list_production_orders, set_production_order_cancelled
from utils.recipe_repository import create_recipe, normalize_color_powder_id
from utils.production_inventory import active_production_orders, prepare_inventory_orders, RESULT_KEYS


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
    order_load = inventory[inventory.index("    df_recipe ="):inventory.index("    # 庫存區可以從側邊欄")]
    entry = compile("if True:\n" + order_load, "inventory-entry", "exec")
    state = InventoryState(df_recipe=pd.DataFrame())
    calls = []
    rows = [{"生產單號": "A", "取消狀態": "有效"}]

    def read_orders(config, *, include_cancelled):
        assert include_cancelled
        calls.append(config)
        return rows

    config = object()
    namespace = {
        "st": SimpleNamespace(session_state=state),
        "pd": pd,
        "list_production_orders": read_orders,
        "DATABASE_CONFIG": config,
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
