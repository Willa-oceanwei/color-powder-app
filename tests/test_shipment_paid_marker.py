from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.receipt_repository import list_receipts, save_receipt
from utils.receivable_report import build_statements
from utils.shipment_repository import blank_shipment, copy_shipment, get_shipment, list_shipments, save_shipment


@pytest.fixture
def paid_data(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "paid.db")
    initialize_database(config.path)
    for code in ("A01", "A02", "A03"):
        create_customer(config, CustomerInput(code, "客戶" + code))
    documents = []
    for number, customer, paid in (("001", "A01", False), ("002", "A01", True), ("003", "A02", True)):
        document = dict(blank_shipment(), number_mode="manual", shipment_number=number,
                        shipment_date="2026-10-01", account_date="2026-10-01",
                        customer_id=customer, customer_name="客戶" + customer, paid_in_full=paid)
        document["items"] = [dict(code="P1", name="藍", unit="KG", quantity="2", price="100")]
        documents.append(save_shipment(config, document))
    return config, documents


def test_paid_marker_round_trip_copy_and_legacy_defaults_without_receipt_changes(paid_data):
    config, documents = paid_data
    document = get_shipment(config, documents[1]["id"])
    before = deepcopy(document)
    assert document["paid_in_full"] is True
    assert list_receipts(config, document["id"]) == []
    assert copy_shipment(document)["paid_in_full"] is False
    for summary in (False, True):
        rows = list_shipments(config, summary=summary)
        assert [bool(row["paid_in_full"]) for row in rows] == [False, True, True]
    document["paid_in_full"] = False
    saved = save_shipment(config, document)
    assert not get_shipment(config, saved["id"])["paid_in_full"]
    for key in ("items", "net_amount", "tax_amount", "total_amount", "invoice", "notes"):
        assert saved[key] == before[key]
    assert list_receipts(config, document["id"]) == []
    with connect_from_config(config) as conn:
        conn.execute("UPDATE shipment_orders SET payload_json=json_remove(payload_json,'$.paid_in_full') WHERE id=?", (saved["id"],))
    assert get_shipment(config, saved["id"])["paid_in_full"] is False


def test_paid_filter_omits_only_marked_documents_and_keeps_ledger_unchanged(paid_data):
    config, documents = paid_data
    save_receipt(config, receipt_id="payment", shipment_id=documents[1]["id"],
                           shipment_version=documents[1]["version"], receipt_date="2026-10-02", amount=50, method="現金")
    all_rows = build_statements(config, "2026-10-01", "2026-10-31")
    filtered = build_statements(config, "2026-10-01", "2026-10-31", hide_paid=True)
    assert [row["customer_id"] for row in filtered] == ["A01"]
    assert [doc["number"] for doc in filtered[0]["documents"]] == ["001"]
    assert filtered[0]["total"] == "210" and all_rows[0]["total"] == "420"
    assert list_receipts(config, documents[1]["id"])[0]["amount"] == "50"
    assert get_shipment(config, documents[1]["id"])["total_amount"] == "210"
    assert [row["customer_id"] for row in build_statements(config, "2026-10-01", "2026-10-31", hide_empty=False, hide_paid=True)] == ["A01", "A03"]
    assert len(build_statements(config, "2026-10-01", "2026-10-31", hide_empty=False)) == 3


def receipt_app(config, function):
    root = str(Path(__file__).resolve().parents[1])
    return AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import {function}
{function}(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)


def test_single_receipt_can_hide_or_reveal_marked_shipments_and_handle_all_marked(paid_data):
    config, documents = paid_data
    app = receipt_app(config, "render_receipt_entry")
    assert not app.exception
    assert app.toggle(key="receipt_hide_paid").value
    assert app.selectbox(key="receipt_customer").options == ["A01 · 客戶A01"]
    assert app.selectbox(key="receipt_shipment").options == ["001 · 2026-10-01"]
    app.toggle(key="receipt_hide_paid").set_value(False).run()
    app.selectbox(key="receipt_customer").set_value("A02").run()
    assert not app.exception
    assert app.selectbox(key="receipt_shipment").value == documents[2]["id"]
    assert any("已付清註記" in caption.value for caption in app.caption)
    app.toggle(key="receipt_hide_paid").set_value(True).run()
    assert not app.exception
    remaining = get_shipment(config, documents[0]["id"])
    remaining["paid_in_full"] = True
    save_shipment(config, remaining)
    app.run()
    assert not app.exception
    assert any("沒有可登錄" in info.value for info in app.info)
    app.toggle(key="receipt_hide_paid").set_value(False).run()
    assert not app.exception and len(app.selectbox(key="receipt_customer").options) == 2


def test_report_preview_defaults_to_hide_marked_and_can_include_them(paid_data):
    config, _ = paid_data
    app = receipt_app(config, "render_report")
    assert app.toggle(key="receivable_hide_paid").value
    next(w for w in app.date_input if w.label == "起始帳款日期").set_value(date(2026, 10, 1))
    next(w for w in app.date_input if w.label == "結束帳款日期").set_value(date(2026, 10, 31))
    app.button(key="receivable_preview").click().run()
    assert not app.exception and len(app.session_state["receivable_pages"]) == 1
    assert app.session_state["receivable_pages"][0]["statement"]["total"] == "210"
    app.toggle(key="receivable_hide_paid").set_value(False).run()
    app.button(key="receivable_preview").click().run()
    assert not app.exception and len(app.session_state["receivable_pages"]) == 2
    assert app.session_state["receivable_pages"][0]["statement"]["total"] == "420"
