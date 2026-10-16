from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.proto.WidgetStates_pb2 import WidgetStates
from streamlit.runtime.scriptrunner import RerunData, ScriptRunnerEvent
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.local_script_runner import LocalScriptRunner

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment


def queue_updates(monkeypatch, updates):
    original_init = LocalScriptRunner.__init__
    queued = []

    def initialize_runner(runner, *args, **kwargs):
        original_init(runner, *args, **kwargs)

        def rerun_workspace(sender, event, **kwargs):
            if event not in (ScriptRunnerEvent.SCRIPT_STOPPED_WITH_SUCCESS,
                             ScriptRunnerEvent.FRAGMENT_STOPPED_WITH_SUCCESS) or len(queued) >= len(updates):
                return
            key, value = updates[len(queued)]
            states = WidgetStates(widgets=runner._session_state.get_widget_states())
            if key:
                widget = next((widget for widget in states.widgets if widget.id.endswith("-" + key)), None)
                if widget is None:
                    widget = states.widgets.add(id=runner._session_state._state._key_id_mapping[key])
                if isinstance(value, bool):
                    widget.bool_value = value
                elif isinstance(value, int):
                    widget.int_value = value
                else:
                    widget.string_value = value
            fragment_id = next(iter(runner._fragment_storage._fragments))
            queued.append(fragment_id)
            assert runner.request_rerun(RerunData(fragment_id=fragment_id, widget_states=states))

        runner.on_event.connect(rerun_workspace, weak=False)

    monkeypatch.setattr(LocalScriptRunner, "__init__", initialize_runner)
    return queued


@pytest.mark.parametrize("editing", [False, True])
def test_shipment_fragment_changes_preserve_draft_and_reuse_reads_and_prints(tmp_path, monkeypatch, editing):
    import utils.customer_display as labels
    import utils.shipment_ui as ui

    config = DatabaseConfig(backend="sqlite", path=tmp_path / "shipment-speed.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Customer", short_name="Short name"))
    document = dict(blank_shipment(), customer_id="C01", customer_name="Customer")
    document["items"] = [dict(code="P1", name="Blue", quantity="2", unit="KG", price="100")]
    saved = save_shipment(config, document)
    reads = []
    for module, name in [(ui, "list_shipments"), (ui, "get_shipment"), (ui, "list_customers"),
                         (ui, "shipment_choices"), (ui, "shipment_price_history"), (labels, "connect_from_config")]:
        original = getattr(module, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            reads.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)
    prints = []
    original_print = ui.printable_shipment

    def count_print(*args, **kwargs):
        prints.append(kwargs["show_prices"])
        return original_print(*args, **kwargs)

    monkeypatch.setattr(ui, "printable_shipment", count_print)
    queued = queue_updates(monkeypatch, [("shipment_print_preview", True),
                                         ("shipment_hide_prices", True), ("shipment_print_preview", False)])
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
st.session_state["main_runs"] = st.session_state.get("main_runs", 0) + 1
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''')
    if editing:
        for key in ("shipment_draft", "shipment_original"):
            app.session_state[key] = deepcopy(saved)
        app.session_state["shipment_editor_base"] = deepcopy(saved["items"])
        app.session_state["shipment_epoch"] = 1
    app.run(timeout=30)
    assert not app.exception and len(queued) == 3, queued
    assert app.session_state["main_runs"] == 1
    assert prints == [True, False]
    assert len(reads) == len(set(reads))
    if editing:
        item = app.session_state["shipment_draft"]["items"][0]
        for key in ("code", "name", "unit", "order_number", "notes", "tax_exempt"):
            assert item[key] == saved["items"][0][key]
        for key in ("quantity", "price"):
            assert float(item[key]) == float(saved["items"][0][key])
        assert get_shipment(config, saved["id"]) == saved
        assert "list_shipments" not in reads and "get_shipment" not in reads
    else:
        assert app.session_state["shipment_selected"] == saved["id"]


def test_shipment_open_new_does_not_require_a_second_main_run(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "new-speed.db")
    initialize_database(config.path)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
st.session_state["main_runs"] = st.session_state.get("main_runs", 0) + 1
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})), start_new_on_entry=True)
''').run(timeout=30)
    assert not app.exception and app.session_state["main_runs"] == 1
    assert "shipment_draft" in app.session_state


def test_select_customer_in_new_shipment_fragment(tmp_path, monkeypatch):
    import utils.shipment_ui as ui

    config = DatabaseConfig(backend="sqlite", path=tmp_path / "customer-selection.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Customer", address="Delivery address"))
    reads = []
    for name in ("get_customer", "list_customers", "shipment_choices", "shipment_price_history"):
        original = getattr(ui, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            reads.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(ui, name, counted)
    queued = queue_updates(monkeypatch, [("shipment_1_customer_picker", 1),
                                         ("shipment_1_notes", "Keep editing")])
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
st.session_state["main_runs"] = st.session_state.get("main_runs", 0) + 1
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})), start_new_on_entry=True)
''').run(timeout=30)
    assert not app.exception and len(queued) == 2
    assert app.session_state["main_runs"] == 2
    draft = app.session_state["shipment_draft"]
    assert draft["customer_id"] == "C01"
    assert draft["address"] == "Delivery address"
    assert draft["notes"] == "Keep editing"
    assert app.text_input(key="shipment_1_recipient_id").value == "C01"
    assert app.text_input(key="shipment_1_address").value == "Delivery address"
    assert app.dataframe
    assert all(reads.count(name) == 1 for name in (
        "get_customer", "list_customers", "shipment_choices", "shipment_price_history"))


def test_customer_fragment_reuses_directory_and_refreshes_after_save(tmp_path, monkeypatch):
    import utils.customer_repository as repository
    from test_customer_contacts import customer_app

    config = DatabaseConfig(backend="sqlite", path=tmp_path / "customer-speed.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Customer", short_name="Short name"))
    reads = []
    original = repository.list_customers

    def counted(*args, **kwargs):
        reads.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "list_customers", counted)
    queued = queue_updates(monkeypatch, [("customer_action_id", 0), (None, None), (None, None)])
    app = customer_app(config)
    assert not app.exception and len(queued) == 3
    assert len(reads) == 1
    assert app.session_state["editing_customer_id"] == "C01"
    assert next(widget for widget in app.text_input if widget.label == "客戶完整名稱").value == "Customer"
    next(widget for widget in app.text_input if widget.label == "客戶簡稱").set_value("New name")
    app.session_state["shipment_page_cache"] = {"old": "label"}
    app.session_state["shipment_read_cache"] = {"old": "customer"}
    next(widget for widget in app.button if widget.label == "儲存變更").click().run()
    assert not app.exception
    assert repository.get_customer(config, "C01")["short_name"] == "New name"
    assert app.selectbox(key="customer_action_id").options == ["C01 · New name · Customer"]
    assert "shipment_page_cache" not in app.session_state and "shipment_read_cache" not in app.session_state
