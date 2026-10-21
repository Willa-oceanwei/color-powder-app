from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.recipe_repository import create_recipe
from utils.shipment_repository import get_shipment, list_shipments


def test_equivalent_numeric_defaults_do_not_recreate_grid():
    from utils.shipment_ui import _editor_rebase_needed
    raw = [dict(code="R1", name="Blue", quantity=2.0, price=100.0, unit="KG", tax_exempt=False)]
    completed = deepcopy(raw)
    completed[0].update(price="100.000", quantity="2", amount="200")
    assert not _editor_rebase_needed(raw, completed)
    for field, value in (("price", "101"), ("name", "White"), ("unit", "包"), ("tax_exempt", True), ("code", "R2")):
        changed = deepcopy(completed)
        changed[0][field] = value
        assert _editor_rebase_needed(raw, changed)


def test_continuous_grid_edits_skip_hidden_print_and_keep_values_on_save(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "stable.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Customer"))
    create_recipe(config, {"配方編號": "R1", "顏色": "Blue", "客戶編號": "C01", "計量單位": "KG"})
    calls = []
    original = ui.printable_shipment

    def capture(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(ui, "printable_shipment", capture)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})),start_new_on_entry=True)
''').run(timeout=30)
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.selectbox(key=prefix + "customer_picker").set_value("C01").run()
    app.text_input(key=prefix + "shipment_number").set_value("001").run()
    app.selectbox(key=prefix + "recipe_picker_C01").set_value("R1").run()
    app.button(key="shipment_add_recipe").click().run()
    grid_epoch = app.session_state["shipment_grid_epoch"]
    grid_key = prefix + f"items_{grid_epoch}"
    edits = {}
    for field, value in (("單價", 100.0), ("數量", 2.5), ("品名", "Custom Blue"), ("採購單號", "PO-1")):
        edits[field] = value
        app.session_state[grid_key] = {"edited_rows": {0: dict(edits)}, "added_rows": [], "deleted_rows": []}
        app.run()
        assert not app.exception
        assert app.session_state["shipment_grid_epoch"] == grid_epoch
    assert calls == []
    assert app.session_state["shipment_draft"]["items"][0]["quantity"] == 2.5
    app.button(key="shipment_prepare_draft_export").click().run()
    assert len(calls) == 1
    assert "Custom Blue" in app.session_state["shipment_draft_export"]["html"]
    app.run()
    assert len(calls) == 1
    edits["數量"] = 3.0
    app.session_state[grid_key] = {"edited_rows": {0: dict(edits)}, "added_rows": [], "deleted_rows": []}
    app.run()
    assert len(calls) == 1 and "shipment_draft_export" not in app.session_state
    assert list_shipments(config) == []
    app.button(key="shipment_save").click().run()
    assert not app.exception
    saved = get_shipment(config, app.session_state["shipment_selected"])
    assert saved["items"][0]["name"] == "Custom Blue"
    assert saved["items"][0]["quantity"] == "3.0"
    assert saved["items"][0]["order_number"] == "PO-1"
    assert saved["total_amount"] == "315"
    # Saving or preparing a file while a code needs automatic completion must
    # survive the one necessary grid refresh, rather than drop the action.
    for number, action in (("002", "shipment_save"), ("003", "shipment_prepare_draft_export")):
        app.button(key="shipment_new").click().run()
        prefix = f"shipment_{app.session_state['shipment_epoch']}_"
        app.selectbox(key=prefix + "customer_picker").set_value("C01").run()
        app.text_input(key=prefix + "shipment_number").set_value(number).run()
        app.session_state[prefix + "items"] = {"edited_rows": {}, "deleted_rows": [], "added_rows": [
            {"貨品編號": "R1", "品名": "", "數量": 1.0, "單位": "", "單價": 0.0}]}
        app.button(key=action).click().run()
        assert not app.exception
        if action == "shipment_prepare_draft_export":
            assert "Blue" in app.session_state["shipment_draft_export"]["html"]
            app.button(key="shipment_save").click().run()
        saved = get_shipment(config, app.session_state["shipment_selected"])
        assert saved["shipment_number"] == number
        assert saved["items"][0]["name"] == "Custom Blue" and saved["items"][0]["unit"] == "KG"
