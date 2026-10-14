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
    app.button(key="open_labels_tab2_P001").click().run()
    assert not app.exception and not app.dataframe
