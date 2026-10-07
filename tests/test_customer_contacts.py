import ast
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer, list_customers, update_customer
from utils.database import DatabaseConfig, connect, initialize_database, initialize_database_with_health
from utils.sheet_import import import_sheet_values
from utils.shipment_repository import blank_shipment, get_shipment, printable_shipment, save_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "contacts.db")
    initialize_database(config.path)
    return config


def test_optional_contacts_crud_outbox_and_legacy_update(config):
    created = create_customer(config, CustomerInput("C01", "範例", address=" 台南市測試路1號 ",
                              phone="06-0123456", fax="06-0012345", contact="王先生", tax_id="01234567"))
    assert created["address"] == "台南市測試路1號" and created["phone"].startswith("0")
    updated = update_customer(config, CustomerInput("C01", "範例公司", "只修改備註"))
    assert updated["contact"] == "王先生" and updated["fax"] == "06-0012345"
    cleared = update_customer(config, CustomerInput("C01", "範例公司", fax=""))
    assert cleared["fax"] == "" and cleared["phone"] == "06-0123456"
    with connect(config.path) as conn:
        payload = json.loads(conn.execute("SELECT payload_json FROM sync_outbox WHERE row_key='C01' ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert payload["地址"] == created["address"] and payload["統一編號"] == "01234567"
    assert payload["傳真"] == ""
    assert create_customer(config, CustomerInput("C02", "另一家"))["address"] == ""


def test_sheet_contacts_import_and_missing_columns_preserve(config):
    original = [["客戶編號", "客戶簡稱", "地址", "電話", "傳真", "聯絡人", "統一編號"],
                ["C01", "範例", "台南市測試路", "06-0012345", "06-0098765", "李小姐", "01234567"]]
    result = import_sheet_values("客戶名單", original, db_config=config, initialize_schema=False)
    assert not result.errors and result.inserted_or_updated == 1
    old_sheet = [["客戶編號", "客戶簡稱", "備註"], ["C01", "範例", "舊格式新備註"]]
    result = import_sheet_values("客戶名單", old_sheet, db_config=config, initialize_schema=False)
    assert not result.errors and result.inserted_or_updated == 1
    customer = list_customers(config)[0]
    assert customer["phone"] == "06-0012345" and customer["contact"] == "李小姐"
    result = import_sheet_values("客戶名單", [["客戶編號", "客戶簡稱", "電話"], ["C01", "範例", ""]],
                                db_config=config, initialize_schema=False)
    assert not result.errors
    assert list_customers(config)[0]["phone"] == "" and list_customers(config)[0]["contact"] == "李小姐"


def test_schema_27_adds_columns_to_existing_customer_table(config):
    create_customer(config, CustomerInput("C01", "原客戶"))
    with connect(config.path) as conn:
        for column in ("address", "phone", "fax", "contact", "tax_id"):
            conn.execute(f"ALTER TABLE customers DROP COLUMN {column}")
        conn.execute("DELETE FROM schema_migrations WHERE version=27")
    _, health = initialize_database_with_health(config)
    assert health.schema_version == 27 and health.schema_compatible
    assert list_customers(config)[0]["name"] == "原客戶"
    assert list_customers(config)[0]["address"] == ""


def test_customer_form_add_edit_cancel_and_clear(config):
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "app.py").read_text(encoding="utf-8"))
    branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                  and isinstance(n.test.left, ast.Name) and n.test.left.id == "menu"
                  and isinstance(n.test.comparators[0], ast.Constant) and n.test.comparators[0].value == "客戶名單")
    body = ast.unparse(ast.Module(body=branch.body, type_ignores=[]))
    script = f'''import sys
sys.path.insert(0,{str(root)!r})
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.customer_repository import *
from utils.database import DatabaseConfig
DATABASE_CONFIG=DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r}))
''' + body
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    for label, value in (("客戶編號", "C01"), ("客戶簡稱", "範例"), ("地址", "台南市測試路1號"),
                         ("電話", "06-0012345"), ("傳真", "06-0023456"), ("聯絡人", "林小姐"), ("統一編號", "01234567")):
        next(w for w in app.text_input if w.label == label).set_value(value)
    next(w for w in app.button if "儲存至 Turso" in w.label).click().run()
    assert not app.exception
    assert list_customers(config)[0]["phone"] == "06-0012345"
    assert next(w for w in app.text_input if w.label == "地址").value == ""
    next(w for w in app.button if "編輯選取客戶" in w.label).click().run()
    assert next(w for w in app.text_input if w.label == "地址").value == "台南市測試路1號"
    next(w for w in app.text_input if w.label == "地址").set_value("未儲存地址")
    app.button(key="cancel_customer_edit").click().run()
    assert list_customers(config)[0]["address"] == "台南市測試路1號"
    next(w for w in app.button if "編輯選取客戶" in w.label).click().run()
    next(w for w in app.text_input if w.label == "地址").set_value("高雄市新地址")
    next(w for w in app.button if "儲存至 Turso" in w.label).click().run()
    assert not app.exception and list_customers(config)[0]["address"] == "高雄市新地址"


def test_shipment_customer_autofill_overrides_snapshot_and_switch(config):
    create_customer(config, CustomerInput("C01", "範例", address="台南市測試路1號", phone="06-0012345", fax="06-0023456", contact="林小姐", tax_id="01234567"))
    create_customer(config, CustomerInput("C02", "空資料客戶"))
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.button(key="shipment_new").click().run()
    next(w for w in app.selectbox if w.label == "客戶").set_value("C01").run()
    assert not app.exception
    assert next(w for w in app.text_input if w.label == "送貨地址").value == "台南市測試路1號"
    assert next(w for w in app.text_input if w.label == "聯絡人").value == "林小姐"
    next(w for w in app.text_input if w.label == "送貨地址").set_value("本次指定地址").run()
    epoch = app.session_state["shipment_epoch"]
    app.session_state[f"shipment_{epoch}_items"] = {"edited_rows": {}, "deleted_rows": [], "added_rows": [
        {"貨品編號": "P1", "品名": "藍", "數量": 1.0, "單位": "包", "單價": 100.0, "附註說明": ""}]}
    app.run()
    app.button(key="shipment_save").click().run()
    assert not app.exception
    saved = get_shipment(config, app.session_state["shipment_selected"])
    assert saved["address"] == "本次指定地址" and saved["phone"] == "06-0012345"
    update_customer(config, CustomerInput("C01", "範例", address="新版地址", phone="09-99999999"))
    assert get_shipment(config, saved["id"])["phone"] == "06-0012345"
    html = printable_shipment(saved)
    assert "本次指定地址" in html and "06-0012345" in html and "林小姐" in html
    app.run()
    app.button(key="shipment_edit").click().run()
    assert not app.exception, [error.message for error in app.exception]
    assert next(w for w in app.text_input if w.label == "送貨地址").value == "本次指定地址"
    next(w for w in app.selectbox if w.label == "客戶").set_value("C02").run()
    assert next(w for w in app.text_input if w.label == "送貨地址").value == ""
    assert next(w for w in app.text_input if w.label == "聯絡電話").value == ""
    next(w for w in app.selectbox if w.label == "客戶").set_value("C01").run()
    assert next(w for w in app.text_input if w.label == "送貨地址").value == "新版地址"
    app.button(key="shipment_cancel").click().run()
    assert get_shipment(config, saved["id"])["address"] == "本次指定地址"
