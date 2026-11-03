from pathlib import Path
from decimal import Decimal

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer, update_customer
from utils.database import DatabaseConfig, initialize_database
from utils.receipt_repository import list_receipts, save_receipt
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment


def editing_app(tmp_path, *, separate_recipient=False):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "customer-refresh.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Old customer", address="Old billing address", phone="111"))
    create_customer(config, CustomerInput("C02", "Old recipient", address="Old delivery address", phone="222"))
    document = dict(blank_shipment(), customer_id="C01", customer_name="Old customer",
                    recipient_id="C02" if separate_recipient else "C01",
                    recipient_name="Old recipient" if separate_recipient else "Old customer",
                    address="Custom delivery address", phone="Custom phone", contact="Custom contact",
                    shipment_number="001", number_mode="manual", notes="Keep notes")
    document["items"] = [dict(code="P1", name="Blue", quantity="2", unit="KG", price="100")]
    document["invoice"].update(number="AB12345678", amount="10", date=document["shipment_date"])
    saved = save_shipment(config, document)
    save_receipt(config, receipt_id="receipt1", shipment_id=saved["id"], shipment_version=saved["version"],
                 receipt_date=saved["shipment_date"], amount="50")
    saved = get_shipment(config, saved["id"])
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.button(key="shipment_edit").click().run()
    assert not app.exception
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    return config, saved, app, prefix


def test_refresh_names_preserves_original_id_prices_invoice_receipts_and_unsaved_grid(tmp_path):
    config, saved, app, prefix = editing_app(tmp_path)
    receipts = list_receipts(config, saved["id"])
    update_customer(config, CustomerInput("C01", "Correct customer", address="New billing address", phone="999"))
    app.session_state[prefix + "items"] = {"edited_rows": {0: {"數量": 3.0}}, "added_rows": [], "deleted_rows": []}
    app.text_area(key=prefix + "notes").set_value("Pending notes").run()
    # Reading and applying only changes the draft, including after the master
    # was updated while this editing snapshot remained open.
    app.button(key="shipment_read_customer_refresh").click().run()
    assert not app.exception
    selector = app.multiselect[0]
    assert set(selector.value) == {"customer_name", "recipient_name"}
    app.button(key="shipment_apply_customer_refresh").click().run()
    assert not app.exception
    draft = app.session_state["shipment_draft"]
    assert draft["customer_name"] == draft["recipient_name"] == "Correct customer"
    assert app.text_input(key=prefix + "recipient_name").value == "Correct customer"
    assert draft["address"] == "Custom delivery address" and draft["phone"] == "Custom phone"
    assert draft["items"][0]["quantity"] == 3.0 and draft["notes"] == "Pending notes"
    assert get_shipment(config, saved["id"]) == saved
    app.button(key="shipment_save").click().run()
    assert not app.exception
    actual = get_shipment(config, saved["id"])
    assert actual["id"] == saved["id"] and actual["shipment_number"] == "001"
    assert actual["customer_name"] == actual["recipient_name"] == "Correct customer"
    assert Decimal(actual["items"][0]["price"]) == Decimal(saved["items"][0]["price"])
    assert actual["invoice"] == saved["invoice"] and actual["notes"] == "Pending notes"
    assert list_receipts(config, saved["id"]) == receipts


def test_separate_recipient_and_explicit_blank_values_cancel_without_writing(tmp_path):
    config, saved, app, prefix = editing_app(tmp_path, separate_recipient=True)
    update_customer(config, CustomerInput("C01", "Correct customer", address="Wrong billing source", phone="999"))
    update_customer(config, CustomerInput("C02", "Correct recipient", address="Correct delivery address", phone=""))
    app.button(key="shipment_read_customer_refresh").click().run()
    assert not app.exception
    preview = app.session_state["shipment_customer_refresh_preview"]["values"]
    assert preview["address"] == "Correct delivery address" and preview["phone"] == ""
    app.multiselect[0].set_value(["customer_name", "address", "phone"]).run()
    app.button(key="shipment_apply_customer_refresh").click().run()
    assert not app.exception
    draft = app.session_state["shipment_draft"]
    assert draft["customer_name"] == "Correct customer"
    assert draft["recipient_id"] == "C02" and draft["recipient_name"] == "Old recipient"
    assert draft["address"] == "Correct delivery address" and draft["phone"] == ""
    assert draft["contact"] == "Custom contact"
    app.button(key="shipment_cancel").click().run()
    assert not app.exception and get_shipment(config, saved["id"]) == saved


def test_failed_read_discards_previous_preview_and_keeps_draft(tmp_path, monkeypatch):
    import utils.shipment_customer_refresh as refresh
    config, saved, app, prefix = editing_app(tmp_path)
    update_customer(config, CustomerInput("C01", "Correct customer"))
    app.button(key="shipment_read_customer_refresh").click().run()
    assert "shipment_customer_refresh_preview" in app.session_state
    def fail(*args):
        raise RuntimeError("Unavailable")
    monkeypatch.setattr(refresh, "get_customer", fail)
    app.button(key="shipment_read_customer_refresh").click().run()
    assert not app.exception and app.error
    assert "shipment_customer_refresh_preview" not in app.session_state
    assert app.session_state["shipment_draft"]["customer_name"] == "Old customer"
    assert get_shipment(config, saved["id"]) == saved


def test_changing_recipient_invalidates_preview(tmp_path):
    config, saved, app, prefix = editing_app(tmp_path)
    update_customer(config, CustomerInput("C01", "Correct customer"))
    app.button(key="shipment_read_customer_refresh").click().run()
    app.text_input(key=prefix + "recipient_id").set_value("C02").run()
    assert not app.exception
    assert "shipment_customer_refresh_preview" not in app.session_state
    app.button(key="shipment_read_customer_refresh").click().run()
    assert app.session_state["shipment_customer_refresh_preview"]["values"]["recipient_name"] == "Old recipient"
    assert get_shipment(config, saved["id"]) == saved
