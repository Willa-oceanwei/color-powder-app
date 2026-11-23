from streamlit.proto.WidgetStates_pb2 import WidgetStates

from test_shipment_edit_save_flow import _editing_app
from utils.customer_repository import CustomerInput, create_customer, update_customer
from utils.shipment_repository import get_shipment, list_shipments


def test_new_shipment_resolves_retained_customer_to_updated_contact_master(tmp_path):
    config, saved, app = _editing_app(tmp_path)
    # Original customer/order was created with a name only; contacts added later.
    update_customer(config, CustomerInput("C01", "Customer", address="New address", phone="0123456"))
    app.button(key="shipment_new").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    # Simulate a retained picker value without an on_change callback.
    app.session_state[prefix + "customer_picker"] = "C01"
    app.run()
    assert not app.exception
    draft = app.session_state["shipment_draft"]
    assert draft["customer_id"] == draft["recipient_id"] == "C01"
    assert draft["recipient_name"] == "Customer"
    assert draft["address"] == "New address" and draft["phone"] == "0123456"
    address = next(widget for widget in app.text_input if widget.label == "送貨地址")
    assert address.value == "New address"
    address.set_value("One-off address").run()
    assert not app.exception
    assert app.session_state["shipment_draft"]["address"] == "One-off address"


def test_customer_selection_keeps_address_when_previous_widget_state_arrives(tmp_path):
    config, _, app = _editing_app(tmp_path)
    create_customer(config, CustomerInput("RD04", "Delivery customer", address="Master address"))
    app.button(key="shipment_new").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.text_input(key=prefix + "customer_search_query").set_value("RD04").run()
    previous_address = next(widget for widget in app.text_input if widget.label == "送貨地址")
    assert previous_address.value == ""

    app.selectbox(key=prefix + "customer_picker").set_value("RD04").run()
    address = next(widget for widget in app.text_input if widget.label == "送貨地址")
    assert address.value == "Master address"

    # A second rerun requested before the browser received the address update
    # still carries the empty input from before the customer was selected.
    states = WidgetStates(widgets=[widget for widget in app._tree.get_widget_states().widgets
                                   if widget.id != address.id])
    states.widgets.add(id=previous_address.id, string_value="")
    app._run(states)

    assert not app.exception
    assert next(widget for widget in app.text_input if widget.label == "送貨地址").value == "Master address"
    assert app.session_state["shipment_draft"]["address"] == "Master address"

    app.text_input(key=prefix + "shipment_number").set_value("RD04-TEST").run()
    app.session_state[prefix + "items"] = {"edited_rows": {}, "deleted_rows": [], "added_rows": [
        {"貨品編號": "P1", "品名": "Blue", "數量": 1.0, "單位": "KG", "單價": 100.0},
    ]}
    app.run()
    app.button(key="shipment_save").click().run()
    assert not app.exception and not app.error
    shipment = next(row for row in list_shipments(config) if row["shipment_number"] == "RD04-TEST")
    saved = get_shipment(config, shipment["id"])
    assert saved["address"] == "Master address"
