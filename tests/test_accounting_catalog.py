import ast
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from utils.accounting_export import statement_excel, statement_pdf, ranking_excel, ranking_pdf
from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.product_repository import blank_product, get_product, list_products, product_references, product_from_recipe, save_product, set_product_active
from utils.recipe_repository import create_recipe
from utils.receivable_report import build_statements, statement_pages
from utils.shipment_catalog import complete_items, shipment_choices
from utils.shipment_repository import ShipmentError, blank_shipment, list_shipments, save_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "catalog.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "範例"))
    create_customer(config, CustomerInput("C02", "其他客戶"))
    create_recipe(config, {"配方編號": "R1", "顏色": "藍", "客戶編號": "C01", "計量單位": "包"})
    create_recipe(config, {"配方編號": "R2", "顏色": "白", "客戶編號": "C01", "計量單位": "1000g"})
    return config


def shipment(price="125", **updates):
    data = blank_shipment()
    data.update(customer_id="C01", customer_name="範例", shipment_date="2026-10-01", account_date="2026-10-01")
    data["items"] = [dict(code="R1", name="藍", unit="包", quantity="2", price=price, notes="")]
    data.update(updates)
    return data


def test_recipe_defaults_direct_code_and_price_precedence(config):
    refs, _ = product_references(config)
    assert product_from_recipe(refs[1])["specification"] == "1000g"
    choices = shipment_choices(config, "C01")
    assert choices["R1"]["sales_unit"] == "包"
    assert "R1" not in shipment_choices(config, "C02")
    raw = [dict(code="R1", name="", unit="", quantity=2, price="", notes="")]
    item = complete_items(config, shipment(), raw, [])[0]
    assert item["name"] == "藍" and item["unit"] == "包" and item["price"] == "0"
    product = product_from_recipe(refs[0])
    product["standard_price"] = "200"
    saved = save_product(config, product)
    assert complete_items(config, shipment(), raw, [])[0]["price"] == "200"
    history = save_shipment(config, shipment())
    assert complete_items(config, shipment(shipment_date="2026-10-02"), raw, [])[0]["price"] == "125"
    override = dict(raw[0], price="0", name="手動名稱", unit="桶")
    assert complete_items(config, shipment(), [override], [])[0]["price"] == "0"
    assert complete_items(config, shipment(), [override], [])[0]["name"] == "手動名稱"
    assert complete_items(config, shipment(), [item], [item]) == [item]
    changed = dict(item, code="R2")
    assert complete_items(config, shipment(), [changed], [item])[0]["name"] == "白"


def test_optional_bidirectional_sync_and_atomic_rollback(config):
    save_shipment(config, shipment())
    assert not list_products(config)
    save_shipment(config, shipment("160"), sync_products=True)
    product = get_product(config, "R1")
    assert product["standard_price"] == "0" and product["recipe_id"] == "R1"
    product["standard_price"] = "200"
    product = save_product(config, product)
    assert "R1" in shipment_choices(config, "C02")
    save_shipment(config, shipment("180"), sync_products=True)
    assert get_product(config, "R1")["standard_price"] == "200"
    save_shipment(config, shipment("260", customer_id="C02", customer_name="其他客戶"), sync_products=True)
    from utils.shipment_catalog import item_price
    assert item_price(config, shipment(shipment_date="2026-10-02"), "R1", "包", product) == "180"
    assert item_price(config, shipment(customer_id="C02", shipment_date="2026-10-02"), "R1", "包", product) == "260"
    set_product_active(config, "R1", product["version"], active=False, reason="test")
    before = len(list_shipments(config))
    bad = shipment()
    bad["items"] += [dict(code="NEW", name="新貨品", unit="KG", quantity="1", price="1"),
                      dict(code="R1", name="藍", unit="桶", quantity="1", price="2")]
    with pytest.raises(ShipmentError, match="已刪除貨品"):
        save_shipment(config, bad, sync_products=True)
    assert len(list_shipments(config)) == before and len(list_products(config, include_inactive=True)) == 1
    bad = shipment()
    bad["items"][0]["unit"] = "桶"
    with pytest.raises(ShipmentError, match="已刪除貨品"):
        save_shipment(config, bad, sync_products=True)
    assert len(list_shipments(config)) == before


@pytest.mark.parametrize("value,expected", [("260.000", "260"), ("260.500", "260.5"), ("0.000", "0"), ("1000000.125", "1000000.125")])
def test_display_price(value, expected):
    from utils.shipment_print import display_price
    assert display_price(value) == expected


def test_tax_choices_sync_with_invoice_mode(config):
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.button(key="shipment_new").click().run()
    epoch = app.session_state["shipment_epoch"]
    key = f"shipment_{epoch}_"
    app.selectbox(key=key + "tax_rate").set_value(0).run()
    assert not app.exception
    assert app.session_state["shipment_draft"]["tax_mode"] == "免稅"
    assert app.session_state["shipment_draft"]["tax_rate"] == "0"
    app.selectbox(key=key + "tax_rate").set_value(5).run()
    assert not app.exception and app.session_state["shipment_draft"]["tax_mode"] == "外加"
    app.selectbox(key=key + "tax_mode").set_value("內含").run()
    assert not app.exception and app.session_state["shipment_draft"]["tax_rate"] == "5"
    app.selectbox(key=key + "tax_mode").set_value("免稅").run()
    assert not app.exception and app.session_state["shipment_draft"]["tax_rate"] == "0"


def test_report_exports_keep_totals_and_text_safe(config):
    doc = shipment()
    doc["items"][0]["name"] = "=HYPERLINK(\"danger\")"
    save_shipment(config, doc)
    statements = build_statements(config, "2026-10-01", "2026-10-31")
    workbook = load_workbook(BytesIO(statement_excel(statements)))
    assert workbook["交易明細"]["F2"].value.startswith("=HYPERLINK")
    assert workbook["交易明細"]["F2"].data_type == "s"
    assert workbook["客戶合計"]["G2"].value == 263
    pdf = statement_pdf(statement_pages(statements))
    assert pdf.startswith(b"%PDF") and b"/UniCNS-UCS2-H" in pdf
    assert ranking_pdf(statements).startswith(b"%PDF")
    assert load_workbook(BytesIO(ranking_excel(statements))).active["E2"].value == 250


def test_product_recipe_ui_and_hidden_old_fields(config):
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_ui import render_product_management
render_product_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.selectbox(key="product_recipe_search").set_value("R1").run()
    app.button(key="product_recipe_open").click().run()
    assert not app.exception
    assert next(w for w in app.text_input if w.label == "規格").value == "包"
    assert next(w for w in app.text_input if w.label == "貨品編號").value == "R1"
    assert not any(w.label.startswith("外包裝") for w in app.text_input)
    assert not any(w.label in ("售價 C", "售價 D", "售價 E") for w in app.number_input)
    next(w for w in app.number_input if w.label == "標準售價").set_value(260.0).run()
    app.button(key="product_save").click().run()
    assert not app.exception and get_product(config, "R1")["standard_price"] == "260.0"


def test_navigation_retains_shipment_grid_and_inputs(config, monkeypatch):
    from streamlit.elements.lib import policies
    check = policies.check_session_state_rules

    def check_every_widget(*args, **kwargs):
        # Streamlit normally shows this warning only once per process.
        policies._shown_default_value_warning = False
        return check(*args, **kwargs)

    monkeypatch.setattr(policies, "check_session_state_rules", check_every_widget)
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "app.py").read_text(encoding="utf-8"))
    sidebar = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_sidebar")
    script = f'''import sys
sys.path.insert(0,{str(root)!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
def request_logout(): pass
''' + ast.unparse(sidebar) + f'''
render_sidebar()
if st.session_state.menu == "出貨單":
    render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
'''
    app = AppTest.from_string(script).run(timeout=30)
    app.button(key="出貨單").click().run()
    app.button(key="shipment_new").click().run()
    next(w for w in app.selectbox if w.label == "客戶").set_value("C01").run()
    date_widget_id = next(w for w in app.date_input if w.label == "出貨日期").proto.id
    address_widget_id = next(w for w in app.text_input if w.label == "送貨地址").proto.id
    next(w for w in app.text_input if w.label == "送貨地址").set_value("草稿地址").run()
    from datetime import date
    next(w for w in app.date_input if w.label == "出貨日期").set_value(date(2026, 10, 3)).run()
    assert next(w for w in app.date_input if w.label == "出貨日期").proto.id == date_widget_id
    assert next(w for w in app.text_input if w.label == "送貨地址").proto.id == address_widget_id
    assert not any("Session State API" in w.value for w in app.warning)
    epoch = app.session_state["shipment_epoch"]
    app.session_state[f"shipment_{epoch}_items"] = {"edited_rows": {}, "deleted_rows": [], "added_rows": [
        {"貨品編號": "R1", "數量": 1.0}]}
    app.run()
    assert not app.exception
    assert app.session_state["shipment_draft"]["items"][0]["name"] == "藍"
    assert not any("Session State API" in w.value for w in app.warning)
    app.button(key="客戶名單").click().run()
    assert not app.exception and app.session_state["menu"] == "客戶名單"
    app.run()
    app.button(key="出貨單").click().run()
    assert not app.exception
    assert next(w for w in app.text_input if w.label == "送貨地址").value == "草稿地址"
    assert next(w for w in app.date_input if w.label == "出貨日期").value == date(2026, 10, 3)
    assert not any("Session State API" in w.value for w in app.warning)
    assert app.session_state["shipment_draft"]["items"][0]["unit"] == "包"
    assert not list_shipments(config)
