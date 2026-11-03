import ast
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from utils import navigation_data
from utils.database import DatabaseConfig, initialize_database
from utils.outsourcing_repository import (
    create_outsourcing_order, update_outsourcing_order, add_outsourcing_return,
)


SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def helpers():
    wanted = {"_safe_float", "_norm_oem_no", "_group_oem_events", "_build_oem_dropdown_label"}
    return "\n\n".join(ast.unparse(node) for node in ast.walk(ast.parse(SOURCE))
                       if isinstance(node, ast.FunctionDef) and node.name in wanted)


def test_reentering_workspace_refreshes_snapshot_but_normal_inputs_reuse_it(monkeypatch):
    config = DatabaseConfig("sqlite", Path("unused.db"))
    invalidated = []
    monkeypatch.setattr(navigation_data, "invalidate_read_cache", invalidated.append)
    state = {"oem_data_loaded": True}
    navigation_data.warm_navigation_reads(config, state, "代工管理", SimpleNamespace())
    assert not state["oem_data_loaded"] and invalidated == [config]
    state["oem_data_loaded"] = True
    navigation_data.warm_navigation_reads(config, state, "代工管理", SimpleNamespace())
    assert state["oem_data_loaded"] and invalidated == [config]
    navigation_data.warm_navigation_reads(config, state, "出貨單", SimpleNamespace())
    navigation_data.warm_navigation_reads(config, state, "代工管理", SimpleNamespace())
    assert not state["oem_data_loaded"] and invalidated == [config, config]


def test_pending_selector_excludes_same_recipe_history_and_refreshes_external_closure(tmp_path):
    config = DatabaseConfig("sqlite", tmp_path / "pending.db")
    initialize_database(config.path)
    orders = []
    for suffix, status in (("OLD", "✅ 已結案"), ("DONE", "🔄 進行中"), ("OPEN", "⏳ 未載回"), ("FACTORY", "🏭 在廠內")):
        order = {"代工單號": "OEM20261103-" + suffix, "配方編號": "68023CM", "客戶名稱": "Customer",
                 "代工數量": 100, "目標載回數量": 100, "狀態": status}
        orders.append(create_outsourcing_order(config, order))
    add_outsourcing_return(config, orders[1]["代工單號"], "2026/11/03", 100)
    add_outsourcing_return(config, orders[2]["代工單號"], "2026/11/03", 30)
    root = str(Path(__file__).resolve().parents[1])
    tree = ast.parse(SOURCE)
    pending = next(node for node in ast.walk(tree) if isinstance(node, ast.With)
                   and any(ast.unparse(item.context_expr) == "pending_return_tab" for item in node.items))
    workspace = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_render_return_workspace")
    app = AppTest.from_string(f'''import sys, re
sys.path.insert(0, {root!r})
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
from utils.database import DatabaseConfig
from utils.read_cache import invalidate_read_cache
from utils.outsourcing_repository import *
DATABASE_CONFIG = DatabaseConfig("sqlite", Path({str(config.path)!r}))
{helpers()}
def load_oem_data():
    st.session_state.read_count = st.session_state.get("read_count", 0) + 1
    st.session_state.df_oem = pd.DataFrame(list_outsourcing_orders(DATABASE_CONFIG))
    st.session_state.df_oem["日期排序"] = pd.Timestamp("2026-11-03")
    st.session_state.df_return = pd.DataFrame(list_outsourcing_events(DATABASE_CONFIG, "return"))
if "df_oem" not in st.session_state:
    load_oem_data()
df_oem = st.session_state.df_oem
returns_by_oem = _group_oem_events(st.session_state.df_return)
pending_return_tab = st.container()
class Display:
    def selectbox(self, target, label, options, **kwargs):
        return target.selectbox(label, options, **kwargs)
    def frame(self, frame):
        return frame
customer_display = Display()
render_metric_cards = lambda rows: None
{ast.unparse(workspace)}
{ast.unparse(pending)}
''').run(timeout=30)
    assert not app.exception
    picker = app.selectbox(key="select_oem_return_pending")
    assert len(picker.options) == 2 and picker.options[1].startswith(orders[2]["代工單號"])
    picker.set_value(picker.options[1]).run()
    assert not app.exception
    assert app.dataframe[0].value["載回數量"].tolist() == ["30.0"]
    update_outsourcing_order(config, dict(orders[2], 狀態="✅ 已結案"))
    app.run()
    assert app.session_state["read_count"] == 1
    app.button(key="reload_oem_pending_returns").click().run()
    assert not app.exception and app.session_state["read_count"] == 2
    assert not app.selectbox


def test_normalized_return_totals_match_selector_and_quantity_cards():
    namespace = {"re": __import__("re")}
    exec(helpers(), namespace)
    frame = pd.DataFrame([{"代工單號": " oem20261103-001\u200b ", "載回數量": "1,000"},
                          {"代工單號": "OEM20261103-001", "載回數量": "25"}])
    groups = namespace["_group_oem_events"](frame)
    assert sum(namespace["_safe_float"](row["載回數量"]) for row in groups["OEM20261103-001"]) == 1025
    tree = ast.parse(SOURCE)
    workspace = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_render_return_workspace")
    assignments = [node for node in ast.walk(workspace) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id in ("return_rows", "df_this_return", "total_returned") for target in node.targets)]
    namespace.update(returns_by_oem=groups, selected_oem="OEM20261103-001", pd=pd)
    exec(compile(ast.Module(body=assignments, type_ignores=[]), "return-total", "exec"), namespace)
    assert namespace["total_returned"] == 1025
    assert len(namespace["df_this_return"]) == 2
