from test_shipment_edit_save_flow import _editing_app
from utils.customer_repository import CustomerInput, update_customer


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
    assert app.text_input(key=prefix + "address").value == "New address"
    app.text_input(key=prefix + "address").set_value("One-off address").run()
    assert not app.exception
    assert app.session_state["shipment_draft"]["address"] == "One-off address"
