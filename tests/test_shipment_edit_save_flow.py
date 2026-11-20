from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer, update_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, printable_shipment, save_shipment


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


def test_resaving_shipment_prints_the_current_full_customer_name(tmp_path):
    config, saved, app = _editing_app(tmp_path)
    update_customer(config, CustomerInput("C01", "範例模具有限公司", short_name="範例"))
    assert get_shipment(config, saved["id"])["customer_name"] == "Customer"

    app.button(key="shipment_edit").click().run()
    app.button(key="shipment_save").click().run()
    assert not app.exception and not app.error

    updated = get_shipment(config, saved["id"])
    assert updated["customer_name"] == "範例模具有限公司"
    assert "客戶名稱：C01　範例模具有限公司</div>" in printable_shipment(updated)


def test_product_search_only_sends_a_bounded_result_set(tmp_path, monkeypatch):
    from utils import shipment_ui as ui
    from utils.product_repository import blank_product

    catalog = {f"P{i:03d}": dict(blank_product(), name=f"Product {i}") for i in range(70)}
    monkeypatch.setattr(ui, "shipment_choices", lambda *args, **kwargs: catalog)
    _, _, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    assert not any(widget.label == "貨品／配方" for widget in app.selectbox)

    app.toggle(key=prefix + "show_product_search").set_value(True).run()
    assert len(app.selectbox(key=prefix + "recipe_picker_C01").options) == 51
    app.text_input(key=prefix + "product_search_query").set_value("product 69").run()
    assert app.selectbox(key=prefix + "recipe_picker_C01").options == ["請選擇貨品或配方", "P069 · Product 69"]
    assert not app.exception


def test_saved_export_is_prepared_only_when_requested(tmp_path, monkeypatch):
    from utils import shipment_ui as ui

    _, _, app = _editing_app(tmp_path)
    original = ui.printable_shipment
    calls = []

    def capture(document, **options):
        calls.append(options)
        return original(document, **options)

    monkeypatch.setattr(ui, "printable_shipment", capture)
    assert not app.get("download_button")
    app.button(key="shipment_prepare_saved_export").click().run()
    assert len(calls) == 1 and app.get("download_button")
    app.run()
    assert len(calls) == 1 and app.get("download_button")
    app.toggle(key="shipment_hide_prices").set_value(True).run()
    assert len(calls) == 1 and not app.get("download_button")
    app.button(key="shipment_prepare_saved_export").click().run()
    assert len(calls) == 2 and calls[-1]["show_prices"] is False


def test_ambiguous_match_button_survives_rerun_apply_and_save(tmp_path):
    from utils.recipe_repository import create_recipe
    config, saved, app = _editing_app(tmp_path)
    for code in ("P1A", "P1B"):
        create_recipe(config, {"配方編號": code, "顏色": "Blue", "客戶編號": "C01", "計量單位": "KG"})
    app.button(key="shipment_edit").click().run()
    assert not app.exception
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.text_area(key=prefix + "notes").set_value("Preserve pending match").run()
    assert not app.exception
    app.button(key=prefix + "apply_0").click().run()
    assert not app.exception
    app.button(key="shipment_save").click().run()
    assert not app.exception and "shipment_draft" not in app.session_state
    result = get_shipment(config, saved["id"])
    assert result["items"][0]["code"] == "P1A"
    assert result["notes"] == "Preserve pending match"


def test_sidebar_retains_fields_without_assigning_adopt_button_state():
    from utils.accounting_navigation import preserve_accounting_widgets
    class State(dict):
        def __setitem__(self, key, value):
            assert key != "shipment_1_apply_0"
            super().__setitem__(key, value)
    state = State(shipment_draft={"id": "S1"}, shipment_epoch=1,
                  shipment_1_apply_0=False, shipment_1_notes="Keep notes")
    preserve_accounting_widgets(state)
    assert state["shipment_1_notes"] == "Keep notes"


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
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.session_state[prefix + "items"] = {
        "edited_rows": {0: {"數量": 2.0}}, "deleted_rows": [], "added_rows": [],
    }
    next(w for w in app.text_area if w.label == "備註").set_value("Single click")
    app.button(key="shipment_save").click().run()
    assert not app.exception and interrupted == [True]
    assert writes == [True]
    assert "shipment_draft" not in app.session_state
    assert get_shipment(config, saved["id"])["notes"] == "Single click"
    assert get_shipment(config, saved["id"])["items"][0]["quantity"] == "2.0"
    assert get_shipment(config, saved["id"])["version"] == 2
    app.run()
    assert writes == [True]


def test_explicit_save_does_not_depend_only_on_callback_flag(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    config, saved, app = _editing_app(tmp_path)
    monkeypatch.setattr(ui, "_request_shipment_save", lambda: None)
    app.button(key="shipment_edit").click().run()
    app.session_state["shipment_search_epoch"] = 1
    next(w for w in app.text_area if w.label == "備註").set_value("Save from paused query").run()
    app.button(key="shipment_save").click().run()
    assert not app.exception
    assert "shipment_draft" not in app.session_state
    assert get_shipment(config, saved["id"])["notes"] == "Save from paused query"


def test_save_with_latest_note_goes_directly_to_saved_view(tmp_path, monkeypatch):
    from utils import shipment_ui as ui

    config, saved, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    editor_runs = []
    monkeypatch.setattr(ui, "render_shipment_quote_notices", lambda *args: editor_runs.append(True))
    app.text_area(key=prefix + "notes").set_value("Last input")
    app.button(key="shipment_save").click().run()

    assert not app.exception and not editor_runs
    assert "shipment_draft" not in app.session_state
    current = get_shipment(config, saved["id"])
    assert current["notes"] == "Last input" and current["version"] == 2

    # The immediate Edit must reuse its product index and only look up the
    # selected customer. A full customer or catalog read blocks this screen.
    from unittest.mock import Mock
    catalog = app.session_state["shipment_product_matcher"]
    list_customers = Mock(wraps=ui.list_customers)
    shipment_choices = Mock(wraps=ui.shipment_choices)
    get_customer = Mock(wraps=ui.get_customer)
    monkeypatch.setattr(ui, "list_customers", list_customers)
    monkeypatch.setattr(ui, "shipment_choices", shipment_choices)
    monkeypatch.setattr(ui, "get_customer", get_customer)
    app.button(key="shipment_edit").click().run()
    assert not app.exception
    assert app.session_state["shipment_draft"]["notes"] == "Last input"
    assert app.session_state["shipment_product_matcher"] is catalog
    list_customers.assert_not_called()
    shipment_choices.assert_not_called()
    get_customer.assert_called_once_with(config, "C01")


def test_save_conflict_preserves_current_draft(tmp_path):
    config, saved, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    external = save_shipment(config, dict(saved, notes="External edit"))
    app.text_area(key=prefix + "notes").set_value("Unsaved note")
    app.button(key="shipment_save").click().run()

    assert not app.exception and any("其他人修改" in error.value for error in app.error)
    assert app.text_area(key=prefix + "notes").value == "Unsaved note"
    assert get_shipment(config, saved["id"]) == external


def test_only_active_edit_details_and_matching_customers_are_loaded(tmp_path):
    config, saved, app = _editing_app(tmp_path)
    create_customer(config, CustomerInput("C02", "另一間有限公司", short_name="另一間"))
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    assert not any(w.label in ("客戶", "發票編號") for w in app.text_input)
    assert not any(w.label == "客戶" for w in app.selectbox)
    section = prefix + "detail_section"
    app.radio(key=section).set_value("帳款資料").run()
    app.text_input(key=prefix + "payment_terms").set_value("月結")
    app.radio(key=section).set_value("相關資料").run()
    assert not any(w.label == "付款條件" for w in app.text_input)
    app.radio(key=section).set_value("帳款資料").run()
    assert app.text_input(key=prefix + "payment_terms").value == "月結"
    app.toggle(key=prefix + "show_customer_search").set_value(True).run()
    app.text_input(key=prefix + "customer_search_query").set_value("另一間").run()
    picker = app.selectbox(key=prefix + "customer_picker")
    assert picker.options == ["請選擇客戶", "C02 · 另一間", "C01 · Customer"]
    picker.set_value("C02").run()
    app.button(key="shipment_save").click().run()
    assert not app.exception
    current = get_shipment(config, saved["id"])
    assert current["customer_id"] == "C02" and current["payment_terms"] == "月結"


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


def test_missing_number_and_save_success_are_shown_above_toolbar(tmp_path):
    config, saved, app = _editing_app(tmp_path)
    app.button(key="shipment_edit").click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.text_input(key=prefix + "shipment_number").set_value("")
    app.button(key="shipment_save").click().run()
    assert not app.exception
    error = next(e for e in app.error if e.value == "請輸入出貨單號")
    elements = list(app.main)
    assert elements.index(error) < elements.index(app.button(key="shipment_save"))
    assert get_shipment(config, saved["id"])["version"] == 1
    assert "shipment_draft" in app.session_state
    app.text_input(key=prefix + "shipment_number").set_value("002")
    app.button(key="shipment_save").click().run()
    assert not app.exception and not app.error
    assert any("已儲存出貨單 002" in e.proto.body for e in app.get("toast"))
    assert get_shipment(config, saved["id"])["shipment_number"] == "002"


def test_rebased_grid_is_mounted_after_failed_save_or_export(tmp_path):
    from utils.recipe_repository import create_recipe
    for action in ("shipment_save", "shipment_prepare_draft_export"):
        directory = tmp_path / action
        directory.mkdir()
        config, saved, app = _editing_app(directory)
        create_recipe(config, {"配方編號": "R1", "顏色": "White", "客戶編號": "C01", "計量單位": "KG"})
        app.button(key="shipment_edit").click().run()
        prefix = f"shipment_{app.session_state['shipment_epoch']}_"
        app.session_state[prefix + "items"] = {
            "edited_rows": {0: {"貨品編號": "R1", "品名": "", "單位": "", "單價": 0.0}},
            "added_rows": [], "deleted_rows": [],
        }
        if action == "shipment_save":
            app.text_input(key=prefix + "shipment_number").set_value("")
        next(w for w in app.text_area if w.label == "備註").set_value("Keep notes")
        app.button(key=action).click().run()
        assert not app.exception
        grid_key = prefix + f"items_{app.session_state['shipment_grid_epoch']}"
        assert grid_key in app.session_state
        if action == "shipment_save":
            error = next(e for e in app.error if e.value == "請輸入出貨單號")
            elements = list(app.main)
            assert elements.index(error) < elements.index(app.button(key="shipment_save"))
        else:
            assert "White" in app.session_state["shipment_draft_export"]["html"]
        app.session_state[grid_key] = {
            "edited_rows": {0: {"數量": 7.0}}, "added_rows": [], "deleted_rows": [],
        }
        app.run()
        assert not app.exception
        assert app.session_state["shipment_draft"]["items"][0]["quantity"] == 7.0
        assert app.session_state["shipment_draft"]["notes"] == "Keep notes"
        app.text_input(key=prefix + "shipment_number").set_value("002")
        app.button(key="shipment_save").click().run()
        assert not app.exception
        document = get_shipment(config, saved["id"])
        assert document["items"][0]["quantity"] == "7.0"
        assert document["notes"] == "Keep notes"
