from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import (
    ShipmentError, blank_shipment, get_shipment, printable_shipment,
    save_shipment, update_shipment_item_notes, void_shipment,
)


@pytest.fixture
def saved(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "notes.db")
    initialize_database(config.path)
    create_customer(config, CustomerInput("C01", "客戶"))
    doc = blank_shipment()
    doc.update(customer_id="C01", customer_name="客戶", notes="整單備註")
    doc["items"] = [
        dict(code="P1", name="藍", quantity="2", unit="KG", price="260", order_number="PO", notes="原附註"),
        dict(code="P2", name="白", quantity="3", unit="KG", price="100", order_number="", notes=""),
    ]
    return config, save_shipment(config, doc)


def test_note_only_write_preserves_all_other_fields_and_prints(saved):
    config, before = saved
    update_shipment_item_notes(config, before["id"], before["version"], {0: "新附註", 1: "第二列"})
    after = get_shipment(config, before["id"])
    expected = deepcopy(before)
    expected["items"][0]["notes"] = "新附註"
    expected["items"][1]["notes"] = "第二列"
    expected["version"] += 1
    expected["updated_at"] = after["updated_at"]
    assert after == expected
    assert "新附註" in printable_shipment(after)
    update_shipment_item_notes(config, after["id"], after["version"], {0: ""})
    assert get_shipment(config, before["id"])["items"][0]["notes"] == ""


def test_notes_reject_stale_versions_void_and_invalid_rows_atomically(saved):
    config, before = saved
    current = save_shipment(config, before)
    with pytest.raises(ShipmentError, match="其他人"):
        update_shipment_item_notes(config, before["id"], before["version"], {0: "過期"})
    with pytest.raises(ShipmentError, match="無效"):
        update_shipment_item_notes(config, current["id"], current["version"], {0: "不得寫入", 99: "無效"})
    assert get_shipment(config, before["id"]) == current
    void_shipment(config, current["id"], current["version"], "測試")
    voided = get_shipment(config, current["id"])
    with pytest.raises(ShipmentError, match="作廢"):
        update_shipment_item_notes(config, voided["id"], voided["version"], {0: "不得寫入"})
    assert get_shipment(config, current["id"]) == voided


def test_view_note_callback_commits_once_refreshes_snapshot_and_reports_failure(saved, monkeypatch):
    config, before = saved
    import utils.shipment_ui as ui
    root = str(Path(__file__).resolve().parents[1])
    # AppTest cannot edit data_editor cells; submit its edited_rows state through
    # the same callback used by the actual editor's on_change event.
    script = f'''import sys
sys.path.insert(0, {root!r})
import streamlit as st
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management, _save_item_notes
config = DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r}))
if st.session_state.pop("submit_notes", False):
    _save_item_notes(config, st.session_state["note_document"], st.session_state["note_key"])
render_shipment_management(config)
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    key = f"shipment_view_{before['id']}_{before['version']}_item_notes"
    editor = next(element for element in app.get("arrow_data_frame") if element.proto.id.endswith(key))
    import json
    columns = json.loads(editor.proto.columns)
    assert all(columns[name]["disabled"] for name in ("貨品編號", "數量", "單價", "免稅"))
    assert not columns.get("附註說明", {}).get("disabled", False)
    assert app.button(key="shipment_save").disabled
    app.session_state["note_key"] = key
    app.session_state["note_document"] = before
    app.session_state[key] = {"edited_rows": {0: {"附註說明": "直接輸入", "單價": 1}}, "added_rows": [], "deleted_rows": []}
    app.session_state["submit_notes"] = True
    app.run()
    assert not app.exception
    after = get_shipment(config, before["id"])
    assert after["version"] == before["version"] + 1
    assert after["items"][0]["notes"] == "直接輸入"
    assert after["items"][0]["price"] == before["items"][0]["price"]
    assert any("附註說明已儲存" in element.proto.body for element in app.get("toast"))
    app.run()
    assert get_shipment(config, before["id"]) == after
    app.button(key="shipment_edit").click().run()
    assert app.session_state["shipment_draft"]["items"][0]["notes"] == "直接輸入"
    app.button(key="shipment_cancel").click().run()
    key = f"shipment_view_{after['id']}_{after['version']}_item_notes"
    app.session_state["note_key"] = key
    app.session_state["note_document"] = after
    app.session_state[key] = {"edited_rows": {0: {"附註說明": "待重試"}}, "added_rows": [], "deleted_rows": []}
    original = ui.update_shipment_item_notes
    def fail(*args, **kwargs):
        raise RuntimeError("private database details")
    monkeypatch.setattr(ui, "update_shipment_item_notes", fail)
    app.session_state["submit_notes"] = True
    app.run()
    assert not app.exception
    assert any("附註未儲存" in element.value for element in app.error)
    assert not any("private database details" in element.value for element in app.error)
    assert get_shipment(config, before["id"]) == after
    monkeypatch.setattr(ui, "update_shipment_item_notes", original)
    app.button(key=key + "_retry").click().run()
    assert not app.exception
    assert get_shipment(config, before["id"])["items"][0]["notes"] == "待重試"


def test_order_note_only_write_preserves_other_data_and_rejects_conflicts(saved):
    from utils.shipment_repository import update_shipment_notes
    config, before = saved
    update_shipment_notes(config, before["id"], before["version"], "1. B01010:3g/kg\n2. B01010A:5g/kg")
    after = get_shipment(config, before["id"])
    expected = deepcopy(before)
    expected.update(notes="1. B01010:3g/kg\n2. B01010A:5g/kg",
                    version=before["version"] + 1, updated_at=after["updated_at"])
    assert after == expected
    assert "B01010A:5g/kg" in printable_shipment(after)
    with pytest.raises(ShipmentError, match="其他人"):
        update_shipment_notes(config, before["id"], before["version"], "過期版本")
    assert get_shipment(config, before["id"]) == after
    update_shipment_notes(config, after["id"], after["version"], "")
    cleared = get_shipment(config, before["id"])
    assert cleared["notes"] == ""
    void_shipment(config, cleared["id"], cleared["version"], "測試")
    voided = get_shipment(config, cleared["id"])
    with pytest.raises(ShipmentError, match="作廢"):
        update_shipment_notes(config, voided["id"], voided["version"], "不可寫入")
    assert get_shipment(config, before["id"]) == voided


def test_order_note_blur_saves_once_and_failure_preserves_input_for_retry(saved, monkeypatch):
    import utils.shipment_ui as ui
    config, before = saved
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    note = next(widget for widget in app.text_area if widget.label == "備註")
    assert not note.disabled
    assert app.button(key="shipment_save").disabled
    assert not any("附註說明可直接修改" in widget.value for widget in app.caption)
    note.set_value("第一行\n第二行").run()
    assert not app.exception
    saved_note = get_shipment(config, before["id"])
    assert saved_note["notes"] == "第一行\n第二行"
    assert saved_note["version"] == before["version"] + 1
    assert saved_note["items"] == before["items"]
    assert any("備註已儲存" in widget.proto.body for widget in app.get("toast"))
    app.run()
    assert get_shipment(config, before["id"]) == saved_note
    original = ui.update_shipment_notes
    def fail(*args):
        raise RuntimeError("private database details")
    monkeypatch.setattr(ui, "update_shipment_notes", fail)
    next(widget for widget in app.text_area if widget.label == "備註").set_value("保留輸入").run()
    assert not app.exception
    assert next(widget for widget in app.text_area if widget.label == "備註").value == "保留輸入"
    assert any("備註未儲存" in widget.value for widget in app.error)
    assert not any("private database details" in widget.value for widget in app.error)
    assert get_shipment(config, before["id"]) == saved_note
    monkeypatch.setattr(ui, "update_shipment_notes", original)
    app.button(key=f"shipment_view_{before['id']}_{saved_note['version']}_retry_notes").click().run()
    assert not app.exception
    assert get_shipment(config, before["id"])["notes"] == "保留輸入"
    next(widget for widget in app.text_area if widget.label == "備註").set_value("直接接著按修改")
    app.button(key="shipment_edit").click().run()
    assert "shipment_draft" in app.session_state
    assert app.session_state["shipment_draft"]["notes"] == "直接接著按修改"
    next(widget for widget in app.text_area if widget.label == "備註").set_value("完整修改尚未儲存").run()
    assert get_shipment(config, before["id"])["notes"] == "保留輸入"
