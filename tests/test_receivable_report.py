from copy import deepcopy
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect, initialize_database, database_health_check
from utils.receipt_repository import list_receipts, save_receipt, void_receipt
from utils.receivable_report import build_statements, render_statement_print, statement_pages
from utils.shipment_repository import ShipmentError, blank_shipment, get_shipment, list_shipments, save_shipment, void_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "receivable.db")
    initialize_database(config.path)
    for code in ("A01", "A02", "A03"):
        create_customer(config, CustomerInput(code, "客戶 " + code))
    return config


def shipment(config, customer="A01", account_date="2026-10-01", count=2):
    d = blank_shipment()
    d.update(customer_id=customer, customer_name="客戶 " + customer, shipment_date="2026-09-28", account_date=account_date)
    d["items"] = [dict(code="P1", name="藍", quantity="1", unit="包", price="100", notes="", order_number="")] * count
    return save_shipment(config, d)


def receipt(config, d, amount=50, receipt_date="2026-10-02", token=None):
    return save_receipt(config, receipt_id=token or str(uuid4()), shipment_id=d["id"], shipment_version=d["version"],
                        receipt_date=receipt_date, amount=amount, method="現金")


def test_filter_account_date_customer_range_void_and_mixed_units(config):
    first = shipment(config)
    second = shipment(config, "A02")
    other = shipment(config, "A03", account_date="2026-09-01")
    void_shipment(config, second["id"], second["version"], "取消")
    pages = build_statements(config, "2026-10-01", "2026-10-31", "A01", "A02")
    assert len(pages) == 1
    assert pages[0]["total"] == "210"  # Header counted once, not per line.
    assert pages[0]["net"] == "200" and pages[0]["tax"] == "10"
    assert len(build_statements(config, "2026-10-01", "2026-10-31", hide_empty=False)) == 3
    assert pages[0]["documents"][0]["date"] == "2026-09-28"
    first["items"].append(dict(code="P2", name="白", quantity="3", unit="KG", price="20", notes="", order_number=""))
    save_shipment(config, first)
    summary = build_statements(config, "2026-10-01", "2026-10-31")[0]
    assert summary["quantities"] == {"包": "2", "KG": "3"}


@pytest.mark.parametrize("start,end,lower,upper", [("2026-11-01", "2026-10-01", "", ""),
                                                 ("bad", "2026-10-01", "", ""),
                                                 ("2026-10-01", "2026-10-31", "A03", "A01")])
def test_invalid_filters(config, start, end, lower, upper):
    with pytest.raises(ShipmentError):
        build_statements(config, start, end, lower, upper)


def test_shipment_customer_date_ranges_and_intersection(config):
    first = shipment(config)
    second = shipment(config, "A02")
    third = shipment(config, "A03")
    third["shipment_date"] = "2026-10-02"
    save_shipment(config, third)
    assert [r["customer_id"] for r in list_shipments(config, customer_start="A01", customer_end="A02")] == ["A01", "A02"]
    assert len(list_shipments(config, start="2026-09-28", end="2026-09-28")) == 2
    assert not list_shipments(config, start="2026-10-01", customer_end="A02")
    assert len(list_shipments(config, customer_start="A02")) == 2
    with pytest.raises(ShipmentError):
        list_shipments(config, customer_start="A03", customer_end="A01")


def test_shipment_search_ui_and_hidden_order_fields(config):
    shipment(config)
    shipment(config, "A02")
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    assert not any(w.label == "訂單編號" for w in app.text_input)
    next(w for w in app.text_input if w.label == "起始客戶編號").set_value("A02")
    next(w for w in app.text_input if w.label == "結束客戶編號").set_value("A02")
    next(w for w in app.button if w.label == "查詢").click().run()
    assert not app.exception
    assert app.session_state["shipment_customer_start"] == "A02"
    assert len(app.dataframe[0].value) == 1
    assert "查詢結果 · 1 筆" in [w.label for w in app.expander]
    next(w for w in app.text_input if w.label == "起始客戶編號").set_value("A03")
    next(w for w in app.button if w.label == "查詢").click().run()
    assert app.error and app.session_state["shipment_customer_start"] == "A02"


def test_receipts_partial_idempotent_cutoff_and_void(config):
    d = shipment(config)
    token = str(uuid4())
    r = receipt(config, d, token=token)
    assert receipt(config, d, token=token)["id"] == r["id"]
    with pytest.raises(ShipmentError):
        receipt(config, d, amount=51, token=token)
    d = get_shipment(config, d["id"])
    receipt(config, d, amount=60, receipt_date="2026-11-01")
    summary = build_statements(config, "2026-10-01", "2026-10-31")[0]
    assert summary["received"] == "50" and summary["balance"] == "160"
    void_receipt(config, r["id"], "誤登")
    assert len(list_receipts(config, d["id"])) == 2
    summary = build_statements(config, "2026-10-01", "2026-10-31")[0]
    assert summary["received"] == "0" and summary["balance"] == "210"
    with pytest.raises(ShipmentError):
        void_receipt(config, r["id"], "重複作廢")


@pytest.mark.parametrize("amount", [0, -1, "NaN", "0.5", 211])
def test_invalid_or_overpayment_rolls_back(config, amount):
    d = shipment(config)
    with pytest.raises(ShipmentError):
        receipt(config, d, amount=amount)
    assert not list_receipts(config, d["id"])
    assert get_shipment(config, d["id"])["version"] == d["version"]


def test_receipt_conflicts_and_shipment_guards(config):
    d = shipment(config)
    r = receipt(config, d, amount=100)
    with pytest.raises(ShipmentError):
        receipt(config, d, amount=50)  # stale shipment version
    with pytest.raises(ShipmentError):
        save_shipment(config, d)
    d = get_shipment(config, d["id"])
    with pytest.raises(ShipmentError):
        void_shipment(config, d["id"], d["version"], "取消")
    smaller = deepcopy(d)
    smaller["items"] = [dict(smaller["items"][0], price="1")]
    with pytest.raises(ShipmentError):
        save_shipment(config, smaller)
    moved = dict(d, customer_id="A02")
    with pytest.raises(ShipmentError):
        save_shipment(config, moved)
    void_receipt(config, r["id"], "誤登")
    d = get_shipment(config, d["id"])
    void_shipment(config, d["id"], d["version"], "取消")
    with pytest.raises(ShipmentError):
        receipt(config, get_shipment(config, d["id"]))


def test_pagination_escape_totals_and_no_mutation(config):
    d = shipment(config, count=40)
    d["items"][0]["notes"] = "<script>bad</script>" + "測試" * 50
    d = save_shipment(config, d)
    receipt(config, d)
    statements = build_statements(config, "2026-10-01", "2026-10-31")
    original = deepcopy(statements)
    pages = statement_pages(statements)
    assert len(pages) >= 2 and all(len(p["rows"]) <= 32 for p in pages)
    assert all(page["paper_size"] == "A4" for page in pages)
    assert statements == original
    html = render_statement_print(pages)
    assert "<script>bad" not in html and "&lt;script&gt;" in html
    assert "size:A5 landscape" in html and "列印全部" in html
    assert "截至期末已登錄收款" not in html and "帳面未收餘額" not in html and "收款狀態" not in html
    assert html.count('class="sheet') == len(pages)
    assert "佳咊實業有限公司" in html
    visible = render_statement_print(pages, show_receipts=True)
    assert visible.count("截至期末已登錄收款") == 1 and "帳面未收餘額" in visible and "收款狀態" in visible
    assert "符合寬度" in html and "整頁" in html and "overflow:auto" in html
    assert all(page["rows"][0][0] == "出貨" for page in pages)
    embedded = render_statement_print(pages, embedded=True)
    assert '>上一頁</button>' not in embedded and '列印全部' in embedded


def test_schema_26_upgrade_preserves_data(config):
    d = shipment(config)
    with connect(config.path) as conn:
        conn.execute("DROP TABLE shipment_receipts")
        conn.execute("DELETE FROM schema_migrations WHERE version=26")
    initialize_database(config.path)
    assert database_health_check(config).schema_version == 27
    assert get_shipment(config, d["id"])["total_amount"] == "210"
    assert not list_receipts(config, d["id"])


def test_quantity_display_trims_zero_fraction_without_rounding(config):
    d = shipment(config)
    d["items"] = [dict(d["items"][0], quantity="6.000"), dict(d["items"][1], quantity="6.500")]
    save_shipment(config, d)
    statements = build_statements(config, "2026-10-01", "2026-10-31")
    pages = statement_pages(statements)
    assert [row[5] for row in pages[0]["rows"][1:]] == ["6", "6.5"]
    html = render_statement_print(pages)
    assert "數量合計：12.5 包" in html
    assert statements[0]["quantities"] == {"包": "12.500"}


def test_report_auto_and_manual_paper_sizes_match_pdf(config):
    from utils.accounting_export import statement_pdf
    shipment(config, count=1)
    shipment(config, 'A02', count=20)
    statements = build_statements(config, '2026-10-01', '2026-10-31')
    pages = statement_pages(statements)
    assert [page['paper_size'] for page in pages] == ['A5', 'A4']
    pdf = statement_pdf(pages)
    assert b'595.2756 419.5276' in pdf
    assert b'595.2756 841.8898' in pdf
    html = render_statement_print(pages)
    assert '@page a4{size:A4 portrait' in html and 'class="sheet a4' in html
    assert 'class="period"' in html and 'class="date-start"' in html
    assert all(page['paper_size'] == 'A5' and len(page['rows']) <= 10 for page in statement_pages(statements, paper_size='A5'))
    assert all(page['paper_size'] == 'A4' for page in statement_pages(statements, paper_size='A4'))


def test_invalid_report_page_configuration():
    with pytest.raises(ValueError):
        statement_pages([], capacity=1)
    with pytest.raises(ValueError):
        statement_pages([], paper_size='A3')


def test_report_ui_navigation_optional_receipt_and_validation(config):
    d = shipment(config)
    shipment(config, "A02")
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receivable_statement
render_receivable_statement(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    next(w for w in app.date_input if w.label == "起始帳款日期").set_value(date(2026, 10, 1))
    next(w for w in app.date_input if w.label == "結束帳款日期").set_value(date(2026, 10, 31))
    next(w for w in app.button if w.label == "預覽").click().run()
    assert len(app.session_state["receivable_pages"]) == 2
    app.button(key="receivable_下一頁").click().run()
    assert app.session_state["receivable_page"] == 1
    app.button(key="receivable_首頁").click().run()
    assert app.session_state["receivable_page"] == 0
    next(w for w in app.number_input if w.label == "本次收款金額").set_value(50)
    next(w for w in app.button if w.label == "登錄收款").click().run()
    assert not app.exception
    assert list_receipts(config, d["id"])[0]["amount"] == "50"
    assert next(w for w in app.number_input if w.label == "本次收款金額").value == 0
    next(w for w in app.button if w.label == "預覽").click().run()
    assert app.session_state["receivable_pages"][0]["statement"]["received"] == "50"
    next(w for w in app.text_input if w.label == "作廢收款原因").set_value("測試誤登")
    next(w for w in app.toggle if w.label == "確認作廢此收款").set_value(True)
    next(w for w in app.button if w.label == "作廢收款").click().run()
    assert not app.exception
    assert list_receipts(config, d["id"])[0]["status"] == "void"
