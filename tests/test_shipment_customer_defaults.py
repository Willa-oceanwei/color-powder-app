from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerError, CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database


def test_new_shipment_fills_delivery_and_contacts_on_customer_selection(tmp_path, monkeypatch):
    from utils import shipment_ui

    config = DatabaseConfig(backend="sqlite", path=tmp_path / "customers.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput(
        "C01", "甲公司", address="第一路 1 號", phone="02-12345678",
        fax="02-87654321", contact="王先生", tax_id="12345678",
    ))
    create_customer(config, CustomerInput("C02", "乙公司", address="第二路 2 號"))

    def unavailable_detail(*args, **kwargs):
        raise CustomerError("個別客戶查詢暫時無法使用")

    monkeypatch.setattr(shipment_ui, "get_customer", unavailable_detail, raising=False)
    app = AppTest.from_string(f"""
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})),
                           start_new_on_entry=True)
""").run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.selectbox(key=prefix + "customer_picker").set_value("C01").run()
    assert not app.exception
    expected = {"recipient_id": "C01", "recipient_name": "甲公司", "address": "第一路 1 號",
                "phone": "02-12345678", "fax": "02-87654321", "contact": "王先生", "tax_id": "12345678"}
    for field, value in expected.items():
        assert app.text_input(key=prefix + field).value == value
    app.text_input(key=prefix + "address").set_value("臨時送貨地址").run()
    app.run()
    assert app.text_input(key=prefix + "address").value == "臨時送貨地址"
    app.selectbox(key=prefix + "customer_picker").set_value("C02").run()
    assert not app.exception
    assert app.text_input(key=prefix + "address").value == "第二路 2 號"
    assert app.text_input(key=prefix + "phone").value == ""
