import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.big_label_repository import build_big_label_editor_defaults
from utils.database import DatabaseConfig, initialize_database


def test_saved_order_can_open_edit_save_and_generate_labels_without_new_order(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "history.db")
    initialize_database(config.path)
    root = str(Path(__file__).resolve().parents[1])
    source = (Path(root) / "app.py").read_text(encoding="utf-8")
    wanted = {"render_order_download_actions", "render_big_label_editor", "build_big_label_rows", "generate_big_label_html", "chunk_label_pages"}
    helpers = "\n\n".join(ast.get_source_segment(source, node) for node in ast.parse(source).body
                          if isinstance(node, ast.FunctionDef) and node.name in wanted)
    app = AppTest.from_string(f'''import sys, ast, logging, re
sys.path.insert(0, {root!r})
from pathlib import Path
import html as html_escape
import pandas as pd
import streamlit as st
from utils.database import DatabaseConfig
from utils.big_label_repository import *
from utils.small_label_print import generate_small_label_html
DATABASE_CONFIG = DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r}))
{helpers}
format_label_ratio = lambda order: "4g/kg"
to_roc_date = lambda value: "115/10/14"
order = {{"生產單號": "P001", "配方編號": "R001", "顏色": "Red", "包裝重量1": "25", "包裝份數1": "2"}}
render_order_download_actions(order, b"A5", "P001.html")
''').run(timeout=30)
    assert not app.exception
    assert not app.dataframe
    app.button(key="open_labels_tab2_P001").click().run()
    assert not app.exception and len(app.dataframe) == 1
    assert app.selectbox(key="tab2_label_paper_P001").value == "A4／100%"
    assert app.dataframe[0].value.iloc[0]["列印張數"] == 2
    app.session_state["tab2_big_label_editor_P001"] = {
        "edited_rows": {0: {"品名": "Edited red", "列印張數": 3}},
        "added_rows": [], "deleted_rows": [],
    }
    next(button for button in app.button if button.label == "儲存並更新標籤").click().run()
    assert not app.exception
    labels = app.session_state["tab2_big_label_confirmed_P001"]
    assert len(labels) == 3 and labels[0]["名稱"] == "Edited red"
    saved = build_big_label_editor_defaults(config, {"配方編號": "R001"}, [])
    assert saved[0]["品名"] == "Edited red" and saved[0]["列印張數"] == 3
    app.radio(key="tab2_label_kind_P001").set_value("小標籤").run()
    assert not app.exception
    assert app.selectbox(key="tab2_small_label_paper_P001").value == "自訂 14×23 公分／100%"
    assert app.dataframe[0].value.iloc[0]["品名"] == "Red"
    assert app.toggle(key="tab2_small_choose_positions_P001").value is False
    assert len(app.checkbox) == 0
    app.session_state["tab2_small_big_label_editor_P001"] = {
        "edited_rows": {0: {"品名": "Small red", "比例": "5g/kg", "列印張數": 11}},
        "added_rows": [], "deleted_rows": [],
    }
    next(button for button in app.button if button.label == "儲存並更新標籤").click().run()
    assert not app.exception
    assert len(app.session_state["tab2_small_big_label_confirmed_P001"]) == 11
    small_saved = build_big_label_editor_defaults(config, {"配方編號": "R001"}, [], label_kind="small")
    assert small_saved[0]["品名"] == "Small red"
    assert build_big_label_editor_defaults(config, {"配方編號": "R001"}, []) == saved
    app.toggle(key="tab2_small_choose_positions_P001").set_value(True).run()
    assert not app.exception and len(app.checkbox) == 10
    assert any("請勾選至少一個" in warning.value for warning in app.warning)
    download = next(item for item in app.get("download_button") if item.proto.label == "下載列印檔")
    assert download.proto.disabled
    for position in (4, 6, 8):
        app.checkbox(key=f"tab2_small_position_P001_{position}").check().run()
    assert not app.exception
    assert any("小標籤紙 4 張" in caption.value for caption in app.caption)
    download = next(item for item in app.get("download_button") if item.proto.label == "下載列印檔")
    assert not download.proto.disabled
    app.toggle(key="tab2_small_choose_positions_P001").set_value(False).run()
    assert not app.exception and not app.checkbox
    assert any("小標籤紙 2 張" in caption.value for caption in app.caption)
    app.radio(key="tab2_label_kind_P001").set_value("大標籤").run()
    assert not app.exception
    assert app.dataframe[0].value.iloc[0]["品名"] == "Edited red"
    app.button(key="open_labels_tab2_P001").click().run()
    assert not app.exception and not app.dataframe
