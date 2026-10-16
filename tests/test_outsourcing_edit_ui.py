import ast
import json
from pathlib import Path
from textwrap import dedent

import pytest
from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, connect, initialize_database
from utils.outsourcing_repository import (
    add_outsourcing_delivery, create_outsourcing_order, list_outsourcing_events,
    list_outsourcing_orders,
)


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "edit-oem.db")
    initialize_database(config.path)
    for order_id, recipe_id, customer in (("1151016-001", "00123", "First"),
                                           ("1151016-002", "R002", "Second")):
        create_outsourcing_order(config, {
            "代工單號": order_id, "生產單號": "P001", "配方編號": recipe_id,
            "客戶名稱": customer, "代工數量": 100, "目標載回數量": 100,
            "轉換倍率": 1, "狀態": "🏭 在廠內", "代工廠商": "弘旭", "備註": "Original",
        })
    return config


def outsourcing_editor(config):
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    wanted = {"tw_to_ad", "_safe_float", "_norm_oem_no", "_build_oem_dropdown_label"}
    helpers = "\n\n".join(ast.unparse(node) for node in ast.walk(ast.parse(source))
                          if isinstance(node, ast.FunctionDef) and node.name in wanted)
    section = dedent(source.split("# Tab 2：編輯代工", 1)[1].split("# Tab 3：載回登入", 1)[0])
    script = f'''import sys, re
sys.path.insert(0, {str(root)!r})
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.database import DatabaseConfig
from utils.outsourcing_repository import *
DATABASE_CONFIG = DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r}))
{helpers}
if "df_oem" not in st.session_state:
    st.session_state.df_oem = pd.DataFrame(list_outsourcing_orders(DATABASE_CONFIG))
    st.session_state.df_delivery = pd.DataFrame(list_outsourcing_events(DATABASE_CONFIG, "delivery"))
df_oem = st.session_state.df_oem
df_delivery = st.session_state.df_delivery
returns_by_oem = {{}}
render_metric_cards = lambda rows: None
class Display:
    def selectbox(self, target, label, options, **kwargs):
        return target.selectbox(label, options, **kwargs)
customer_display = Display()
tab2 = st.container()
{section}
'''
    return AppTest.from_string(script).run(timeout=30)


def choose(app, order_id):
    picker = app.selectbox(key="select_oem_edit")
    picker.set_value(next(option for option in picker.options if option.startswith(order_id))).run()
    assert not app.exception


def test_editable_identity_saves_database_session_and_outbox(config):
    app = outsourcing_editor(config)
    choose(app, "1151016-001")
    assert not app.text_input(key="oem_recipe_id").disabled
    assert not app.text_input(key="oem_customer_name").disabled
    assert app.text_input(key="oem_recipe_id").value == "00123"
    app.text_input(key="oem_recipe_id").set_value(" 000456 ").run()
    app.text_input(key="oem_customer_name").set_value(" New customer ").run()
    app.button(key="update_oem_info").click().run()
    assert not app.exception
    saved = next(row for row in list_outsourcing_orders(config) if row["代工單號"] == "1151016-001")
    assert saved["配方編號"] == "000456" and saved["客戶名稱"] == "New customer"
    assert saved["生產單號"] == "P001" and saved["代工數量"] == "100"
    assert saved["備註"] == "Original"
    assert app.session_state["df_oem"].set_index("代工單號").loc["1151016-001", "配方編號"] == "000456"
    with connect(config.path) as conn:
        record = conn.execute("SELECT recipe_id,customer_name,production_order_id FROM outsourcing_orders WHERE outsourcing_order_id=?", ("1151016-001",)).fetchone()
        payload = json.loads(conn.execute("SELECT payload_json FROM sync_outbox WHERE sheet_name='代工管理' AND row_key=? ORDER BY entity_version DESC LIMIT 1", ("1151016-001",)).fetchone()[0])
    assert tuple(record) == ("000456", "New customer", "P001")
    assert payload["配方編號"] == "000456" and payload["客戶名稱"] == "New customer"


def test_switching_orders_resets_identity_and_blank_fields_disable_save(config):
    app = outsourcing_editor(config)
    choose(app, "1151016-001")
    app.text_input(key="oem_recipe_id").set_value("Unsaved").run()
    choose(app, "1151016-002")
    assert app.text_input(key="oem_recipe_id").value == "R002"
    assert app.text_input(key="oem_customer_name").value == "Second"
    for key in ("oem_recipe_id", "oem_customer_name"):
        previous = app.text_input(key=key).value
        app.text_input(key=key).set_value(" ").run()
        assert app.button(key="update_oem_info").disabled and app.button(key="add_delivery").disabled
        app.text_input(key=key).set_value(previous).run()
    assert not app.exception
    assert next(row for row in list_outsourcing_orders(config) if row["代工單號"] == "1151016-001")["配方編號"] == "00123"


def test_delivery_confirmation_includes_changed_identity(config):
    add_outsourcing_delivery(config, "1151016-001", "2026/10/16", 10)
    app = outsourcing_editor(config)
    choose(app, "1151016-001")
    app.text_input(key="oem_recipe_id").set_value("R003").run()
    app.text_input(key="oem_customer_name").set_value("Third").run()
    app.number_input(key="delivery_qty").set_value(5).run()
    app.button(key="add_delivery").click().run()
    assert not app.exception and app.session_state["pending_delivery_edit"]
    assert len(list_outsourcing_events(config, "delivery")) == 1
    app.button(key="confirm_delivery_edit").click().run()
    app.button(key="add_delivery").click().run()
    assert not app.exception
    saved = next(row for row in list_outsourcing_orders(config) if row["代工單號"] == "1151016-001")
    assert saved["配方編號"] == "R003" and saved["客戶名稱"] == "Third"
    events = list_outsourcing_events(config, "delivery")
    assert len(events) == 2 and {row["代工單號"] for row in events} == {"1151016-001"}
