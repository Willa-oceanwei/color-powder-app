from pathlib import Path

import pytest
from streamlit.runtime.scriptrunner import RerunData, ScriptRunnerEvent
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.local_script_runner import LocalScriptRunner

from test_historical_label_ui import label_ui_helpers_source
from utils.database import DatabaseConfig, initialize_database


def performance_app(tmp_path, section):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "performance.db")
    initialize_database(config.path)
    root = str(Path(__file__).resolve().parents[1])
    return AppTest.from_string(f'''import sys, logging, re
sys.path.insert(0, {root!r})
from pathlib import Path
import html as html_escape
import pandas as pd
import streamlit as st
from utils.database import DatabaseConfig
from utils.big_label_repository import *
from utils.small_label_print import generate_small_label_html
DATABASE_CONFIG = DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r}))
{label_ui_helpers_source()}
format_label_ratio = lambda order: "4g/kg"
to_roc_date = lambda value: "115/10/16"
original_defaults = build_big_label_editor_defaults
original_big = generate_big_label_html
original_small = generate_small_label_html
original_editor = render_big_label_editor
def counted_defaults(*args, **kwargs):
    st.session_state["template_reads"] = st.session_state.get("template_reads", 0) + 1
    return original_defaults(*args, **kwargs)
def counted_big(*args, **kwargs):
    st.session_state["html_generations"] = st.session_state.get("html_generations", 0) + 1
    return original_big(*args, **kwargs)
def counted_small(*args, **kwargs):
    st.session_state["html_generations"] = st.session_state.get("html_generations", 0) + 1
    return original_small(*args, **kwargs)
def counted_editor(*args, **kwargs):
    st.session_state["editor_runs"] = st.session_state.get("editor_runs", 0) + 1
    return original_editor(*args, **kwargs)
build_big_label_editor_defaults = counted_defaults
generate_big_label_html = counted_big
generate_small_label_html = counted_small
render_big_label_editor = counted_editor
st.session_state["full_runs"] = st.session_state.get("full_runs", 0) + 1
order = {{"生產單號": "P001", "配方編號": "R001", "顏色": "Red", "包裝重量1": "25", "包裝份數1": "14"}}
prefix = "tab2" if {section!r} == "history" else "tab1"
st.session_state.setdefault(f"{{prefix}}_big_label_confirmed_P001", [{{"編號": "R001", "名稱": "Red"}}] * 14)
if {section!r} == "history":
    st.session_state.setdefault("history_labels_open_P001", True)
    render_order_download_actions(order, b"A5", "P001.html")
else:
    st.session_state.setdefault("show_big_label_P001", True)
    render_saved_label_section(order, a5_downloaded=False)
''')


@pytest.mark.parametrize("section", ["saved", "history"])
def test_fragment_reruns_skip_main_page_database_reads_and_html_generation(tmp_path, monkeypatch, section):
    original_init = LocalScriptRunner.__init__
    fragment_runs = []

    def initialize_runner(runner, *args, **kwargs):
        original_init(runner, *args, **kwargs)

        def rerun_fragment(sender, event, **kwargs):
            if event in (ScriptRunnerEvent.SCRIPT_STOPPED_WITH_SUCCESS,
                         ScriptRunnerEvent.FRAGMENT_STOPPED_WITH_SUCCESS) and len(fragment_runs) < 3:
                fragment_id, = runner._fragment_storage._fragments
                fragment_runs.append(fragment_id)
                assert runner.request_rerun(RerunData(fragment_id=fragment_id))

        runner.on_event.connect(rerun_fragment, weak=False)

    monkeypatch.setattr(LocalScriptRunner, "__init__", initialize_runner)
    app = performance_app(tmp_path, section).run(timeout=30)
    assert not app.exception
    assert len(fragment_runs) == 3
    assert app.session_state["full_runs"] == 1
    assert app.session_state["editor_runs"] == 4
    assert app.session_state["template_reads"] == 1
    assert app.session_state["html_generations"] == 1


def test_download_cache_updates_for_paper_positions_and_saved_content(tmp_path):
    app = performance_app(tmp_path, "history").run(timeout=30)
    assert not app.exception and app.session_state["html_generations"] == 1
    app.run()
    assert not app.exception and app.session_state["html_generations"] == 1
    app.selectbox(key="tab2_label_paper_P001").set_value("自訂 12×32 公分／100%").run()
    assert not app.exception and app.session_state["html_generations"] == 2
    assert b"12.0cm 32.0cm" in app.session_state["tab2_label_render_P001"][1]
    app.session_state["tab2_big_label_editor_P001"] = {
        "edited_rows": {0: {"品名": "Changed"}}, "added_rows": [], "deleted_rows": [],
    }
    app.button(key="tab2_save_labels_P001").click().run()
    assert not app.exception and app.session_state["html_generations"] == 3
    assert b"Changed" in app.session_state["tab2_label_render_P001"][1]
    app.radio(key="tab2_label_kind_P001").set_value("小標籤").run()
    app.button(key="tab2_small_save_labels_P001").click().run()
    assert not app.exception and app.session_state["html_generations"] == 4
    app.toggle(key="tab2_small_choose_positions_P001").set_value(True).run()
    assert not app.exception and app.session_state["html_generations"] == 5
    assert app.session_state["tab2_small_label_render_P001"][1] == b""
    app.checkbox(key="tab2_small_position_P001_8").check().run()
    assert not app.exception and app.session_state["html_generations"] == 6
    html = app.session_state["tab2_small_label_render_P001"][1].decode("utf-8")
    assert html.count('class="sheet"') == 14
    assert 'left:0.6cm;top:18.25cm;' in html
    app.run()
    assert not app.exception and app.session_state["html_generations"] == 6
