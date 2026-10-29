from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment


def _editing_app(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "edit-save.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "Customer"))
    document = dict(blank_shipment(), customer_id="C01", customer_name="Customer",
                    shipment_number="001", number_mode="manual")
    document["items"] = [dict(code="P1", name="Blue", quantity="1", unit="KG", price="100")]
    saved = save_shipment(config, document)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f"""import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
""").run(timeout=30)
    return config, saved, app


def test_save_click_survives_interrupted_render_without_second_click(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    import streamlit as st
    config, saved, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    original = ui.render_shipment_quote_notices
    interrupted = []
    writes = []
    save = ui.save_shipment

    def interrupt_once(*args, **kwargs):
        if not interrupted and st.session_state.get("shipment_save"):
            interrupted.append(True)
            st.rerun()
        return original(*args, **kwargs)

    def count_save(*args, **kwargs):
        writes.append(True)
        return save(*args, **kwargs)

    monkeypatch.setattr(ui, "render_shipment_quote_notices", interrupt_once)
    monkeypatch.setattr(ui, "save_shipment", count_save)
    next(w for w in app.text_area if w.label == "備註").set_value("Single click")
    app.button(key="shipment_save").click().run()
    assert not app.exception and interrupted == [True]
    assert writes == [True]
    assert "shipment_draft" not in app.session_state
    assert get_shipment(config, saved["id"])["notes"] == "Single click"
    assert get_shipment(config, saved["id"])["version"] == 2
    app.run()
    assert writes == [True]


def test_editing_skips_query_results_even_after_cache_expiry(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    import utils.shipment_page_data as data
    config, saved, app = _editing_app(tmp_path)
    next(w for w in app.text_input if w.label == "出貨單號 / 客戶 / 貨品編號").set_value("001")
    next(w for w in app.button if w.label == "查詢").click().run()
    assert not app.exception
    app.button(key="shipment_edit").click().run()
    # Editing must not read results, navigation lists or their customer labels.
    def unexpected(*args, **kwargs):
        raise AssertionError("editing re-read the query results")
    monkeypatch.setattr(ui, "list_shipments", unexpected)
    monkeypatch.setattr(ui.CustomerDisplay, "name", unexpected)
    monkeypatch.setattr(data, "monotonic", lambda: 10**12)
    for notes in ("First edit", "Second edit", "Third edit"):
        next(w for w in app.text_area if w.label == "備註").set_value(notes).run()
        assert not app.exception
        assert app.session_state["shipment_draft"]["notes"] == notes
    app.button(key="shipment_save").click().run()
    assert not app.exception
    assert get_shipment(config, saved["id"])["notes"] == "Third edit"


def test_failed_save_consumes_request_and_retains_draft(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    config, saved, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    attempts = []
    def fail(*args, **kwargs):
        attempts.append(True)
        raise ui.ShipmentError("Try again")
    monkeypatch.setattr(ui, "save_shipment", fail)
    app.button(key="shipment_save").click().run()
    assert not app.exception and app.error
    assert "shipment_draft" in app.session_state
    assert "shipment_pending_save" not in app.session_state
    app.run()
    assert attempts == [True]
    assert get_shipment(config, saved["id"])["version"] == 1


def test_name_matching_indexes_history_codes_once():
    from utils.shipment_catalog import matching_products
    visits = []
    class Code(str):
        def upper(self):
            visits.append(self)
            return super().upper()
    choices = {Code(f"P{i}"): {"name": f"Product {i}"} for i in range(300)}
    history = [{"code": f"p{i}", "name": f"Previous name {i}"} for i in range(300)]
    assert matching_products(choices, "Previous name 299", by_name=True, history=history) == ["P299"]
    assert len(visits) == len(choices)
    # Preserve first-code behavior when legacy master keys differ only by case.
    assert matching_products({"p1": {"name": "A"}, "P1": {"name": "B"}},
                             "Legacy", by_name=True, history=[{"code": "P1", "name": "Legacy"}]) == ["p1"]

def test_save_after_auto_completion_reads_later_fields_in_same_render(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    from utils.recipe_repository import create_recipe
    config, saved, app = _editing_app(tmp_path)
    create_recipe(config, {"配方編號": "R1", "顏色": "White", "客戶編號": "C01", "計量單位": "KG"})
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.session_state[prefix + "items"] = {
        "edited_rows": {0: {"貨品編號": "R1", "品名": "", "單位": "", "單價": 0.0}},
        "added_rows": [], "deleted_rows": [],
    }
    next(w for w in app.text_area if w.label == "備註").set_value("Notes from same click")
    reruns = []
    original = ui._rerun_shipment
    def count_rerun():
        reruns.append(True)
        original()
    monkeypatch.setattr(ui, "_rerun_shipment", count_rerun)
    app.button(key="shipment_save").click().run()
    assert not app.exception and reruns == [True]
    document = get_shipment(config, saved["id"])
    assert document["items"][0]["code"] == "R1"
    assert document["items"][0]["name"] == "White"
    assert document["items"][0]["unit"] == "KG"
    assert document["notes"] == "Notes from same click"
    assert document["version"] == 2
