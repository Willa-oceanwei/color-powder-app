import ast
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


APP_SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def inventory_app():
    page = next(node for node in ast.walk(ast.parse(APP_SOURCE))
                if isinstance(node, ast.If) and ast.unparse(node.test) == "menu == '庫存區'")
    body = ast.unparse(ast.Module(body=page.body, type_ignores=[]))
    root = str(Path(__file__).parents[1])
    return AppTest.from_string(f"""
import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from utils.inventory_audit import recent_confirmed_audit_keys
from utils.inventory_navigation import (
    CUSTOMER_STOCK_INPUTS, INVENTORY_VIEW_KEY, INVENTORY_VIEWS, MOVEMENT_VIEWS,
    ORDER_VIEWS, RECIPE_VIEWS, remember_audit_upload, retain_inventory_widgets, selected_inventory_view,
)
DATABASE_CONFIG = None
reads = st.session_state['reads'] = []
def list_inventory_movements(config):
    reads.append('movements')
    return []
def list_recipes(config):
    reads.append('recipes')
    return []
def list_production_orders(config, *, include_cancelled):
    assert include_cancelled
    reads.append('orders')
    if st.session_state.get('orders_unavailable'):
        raise RuntimeError('temporary read failure')
    return st.session_state.get('orders', [])
def list_color_powders(config):
    reads.append('powders')
    return []
def list_customer_inventory_records(config):
    reads.append('customer inventory')
    return []
def render_empty_state(message):
    st.info(message)
customer_display = SimpleNamespace(
    selectbox=lambda target, *args, **kwargs: target.selectbox(*args, **kwargs),
    frame=lambda frame: frame,
)
retain_inventory_widgets(st.session_state, selected_inventory_view(st.session_state))
""" + body)


def test_inventory_only_renders_and_loads_the_selected_view():
    app = inventory_app().run()
    assert not app.exception
    assert app.session_state["reads"] == ["movements"]
    assert {w.label for w in app.button} >= {"💾 儲存初始庫存"}
    assert app.radio(key="inventory_view").value == "initial"

    app.radio(key="inventory_view").set_value("query").run()
    assert not app.exception
    assert app.session_state["reads"] == ["recipes", "orders", "movements"]
    assert {w.label for w in app.button} == {"計算庫存"}

    app.radio(key="inventory_view").set_value("customer").run()
    assert not app.exception
    assert app.session_state["reads"] == ["customer inventory"]
    assert "✅ 新增" in {w.label for w in app.button}


def test_switching_inventory_views_retains_unsubmitted_inputs_and_refreshes_orders():
    app = inventory_app().run()
    app.text_input(key="ini_color").set_value("P123")
    app.number_input(key="ini_qty").set_value(25.0).run()
    app.radio(key="inventory_view").set_value("query").run()
    app.text_input(key="stock_powder").set_value("P123")
    app.selectbox(key="match_mode").set_value("精準匹配").run()

    app.radio(key="inventory_view").set_value("initial").run()
    assert not app.exception
    assert app.text_input(key="ini_color").value == "P123"
    assert app.number_input(key="ini_qty").value == 25.0
    app.session_state["stock_query_result"] = [{"舊結果": True}]
    app.session_state["orders"] = [{"生產單號": "A", "取消狀態": "已取消"}]
    app.radio(key="inventory_view").set_value("query").run()
    assert not app.exception
    assert app.session_state["reads"] == ["orders", "movements"]
    assert app.text_input(key="stock_powder").value == "P123"
    assert app.selectbox(key="match_mode").value == "精準匹配"
    assert "stock_query_result" not in app.session_state


def test_inventory_can_leave_a_view_when_order_refresh_fails():
    app = inventory_app().run()
    app.session_state["orders_unavailable"] = True
    app.radio(key="inventory_view").set_value("query").run()
    assert not app.exception and app.error
    assert app.session_state["reads"] == ["recipes", "orders"]
    assert not app.button
    app.radio(key="inventory_view").set_value("customer").run()
    assert not app.exception and not app.error
    assert app.session_state["reads"] == ["customer inventory"]


def test_inventory_audit_preserves_upload_and_unsaved_edits_across_views(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = inventory_app().run()
    app.radio(key="inventory_view").set_value("audit").run()
    upload = BytesIO(b"test upload")
    upload.name = "audit.csv"
    app.session_state["stock_audit_uploaded_file"] = upload
    app.session_state["stock_audit_result"] = pd.DataFrame([{
        "儲位": "A", "色粉編號": "P1", "狀態": "🔴 重盤", "備註": "", "已確認": False,
    }])

    def edit_once(frame, *args, **kwargs):
        return frame.assign(備註="待確認") if st.session_state.get("enter_note") else frame

    monkeypatch.setattr(st, "data_editor", edit_once)
    app.session_state["enter_note"] = True
    app.run()
    app.session_state["enter_note"] = False
    app.radio(key="inventory_view").set_value("initial").run()
    app.radio(key="inventory_view").set_value("audit").run()
    assert not app.exception
    assert app.session_state["stock_audit_editor_draft"][1]["備註"].tolist() == ["待確認"]
    assert any("audit.csv" in caption.value for caption in app.caption)

    app.button(key="stock_audit_clear_upload").click().run()
    assert "stock_audit_uploaded_file" not in app.session_state


def test_recalculated_inventory_audit_uses_a_fresh_editor_state():
    audit_source = APP_SOURCE[
        APP_SOURCE.index("# Tab 3：庫存盤點分析"):
        APP_SOURCE.index("# Tab 7：個別客戶庫存")
    ]

    assert 'st.session_state["stock_audit_editor_revision"] = (' in audit_source
    assert 'editor_revision = st.session_state.get("stock_audit_editor_revision", 0)' in audit_source
    assert 'key=f"stock_audit_editor_{editor_revision}"' in audit_source


def test_saving_initial_stock_invalidates_previous_audit_snapshot():
    initial_stock_source = APP_SOURCE[
        APP_SOURCE.index("# Tab 1：初始庫存設定"):
        APP_SOURCE.index("# Tab 2：庫存查詢")
    ]

    assert "invalidate_inventory_caches()" in initial_stock_source


def test_inventory_cache_invalidator_clears_every_derived_stock_view():
    import ast
    from types import SimpleNamespace
    from utils.production_inventory import RESULT_KEYS
    state = {key: ["stale"] for key in RESULT_KEYS}
    node = next(node for node in ast.parse(APP_SOURCE).body
                if isinstance(node, ast.FunctionDef) and node.name == "invalidate_inventory_caches")
    namespace = {"st": SimpleNamespace(session_state=state)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "inventory-invalidator", "exec"), namespace)
    namespace["invalidate_inventory_caches"]()
    assert all(key not in state for key in RESULT_KEYS)
    assert state["stock_need_reload"] is True
    assert state["stock_audit_editor_revision"] == 1


def test_all_app_inventory_writes_invalidate_derived_stock_views():
    assert APP_SOURCE.count("invalidate_inventory_caches()") >= 7


def test_saved_audit_confirmation_message_belongs_to_inventory_audit_tab():
    audit_source = APP_SOURCE[
        APP_SOURCE.index("# Tab 3：庫存盤點分析"):
        APP_SOURCE.index("# Tab 7：個別客戶庫存")
    ]

    assert 'st.session_state.pop("stock_audit_saved_message", None)' in audit_source


def test_carwash_movement_editor_only_shows_five_most_recent_records():
    editor_source = APP_SOURCE[
        APP_SOURCE.index('with edit_tab2:') : APP_SOURCE.index('\ndef parse_formula_root')
    ]

    assert '["紀錄日期排序", "sheet_idx"]' in editor_source
    assert "ascending=[False, False]" in editor_source
    assert ".head(5)" in editor_source
    assert "最近五筆" in editor_source


def test_carwash_movement_editor_can_archive_duplicate_records():
    editor_source = APP_SOURCE[
        APP_SOURCE.index('with edit_tab2:') : APP_SOURCE.index('\ndef parse_formula_root')
    ]

    assert "我確認這筆是重覆新增的資料" in editor_source
    assert "archive_carwash_inventory_movement(" in editor_source
    assert 'reason="使用者刪除重覆新增的出入庫資料"' in editor_source


def test_all_selection_controls_use_toggle_switches_instead_of_checkboxes():
    project_root = Path(__file__).parents[1]
    python_sources = [project_root / "app.py", *(project_root / "utils").glob("*.py")]

    checkbox_calls = [
        path.relative_to(project_root)
        for path in python_sources
        if "st.checkbox(" in path.read_text(encoding="utf-8")
    ]

    assert checkbox_calls == []


def test_purchase_search_hides_carwash_transfers_until_toggle_is_enabled():
    purchase_source = APP_SOURCE[
        APP_SOURCE.index('elif menu == "採購管理":'):
        APP_SOURCE.index('# ======== 庫存區分頁 =========')
    ]

    assert '"包含洗車廠轉入明細"' in purchase_source
    assert 'key="purchase_search_include_carwash_transfers"' in purchase_source
    assert "value=False" in purchase_source
    assert "if not include_carwash_transfers:" in purchase_source
    assert '.str.startswith("洗車廠出庫轉入")' in purchase_source
    assert "is_carwash_transfer_inventory_movement" not in APP_SOURCE


def test_purchase_edit_selector_excludes_reversed_records():
    purchase_source = APP_SOURCE[
        APP_SOURCE.index('elif menu == "採購管理":'):
        APP_SOURCE.index('# ======== 庫存區分頁 =========')
    ]
    edit_source = purchase_source.split("# ========== Tab 3：進貨編輯 / 沖銷 ==========", 1)[1]

    status_filter = edit_source.index('df_in_edit["沖銷狀態"]')
    selector = edit_source.index('key="purchase_edit_record"')
    assert status_filter < selector
    assert '!= "已沖銷"' in edit_source[status_filter:selector]
