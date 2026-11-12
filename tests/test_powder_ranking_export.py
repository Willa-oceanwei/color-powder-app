import ast
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


def test_ranking_csv_uses_kg_and_tracks_suffix_filter_without_recalculation(monkeypatch):
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    rank_tab = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "inventory_view == 'rank'"
        and any(isinstance(child, ast.Constant) and child.value == "btn_powder_rank"
                for child in ast.walk(node))
    )
    rank_source = ast.unparse(ast.Module(body=rank_tab.body, type_ignores=[]))
    download = st.download_button

    def capture_download(label, data, *args, **kwargs):
        st.session_state["csv_bytes"] = data
        return download(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app = AppTest.from_string('''
import pandas as pd
import streamlit as st
from types import SimpleNamespace
customer_display = SimpleNamespace(frame=lambda frame: frame)
format_usage = lambda grams: f"{grams / 1000:g} kg"
calc_packs_total_kg = lambda order: 1
render_empty_state = st.info
df_order = pd.DataFrame([{"配方編號": "R1", "生產日期": "2026-01-02"}])
df_recipe = pd.DataFrame([{
    "配方編號": "R1", "色粉編號1": "B01", "色粉重量1": 3000,
    "色粉編號2": "A001", "色粉重量2": 2000,
    "色粉編號3": "4353", "色粉重量3": 1025,
    "色粉編號4": "0012", "色粉重量4": 0.5,
}])
''' + rank_source)
    app.session_state["rank_start_date"] = date(2026, 1, 1)
    app.session_state["rank_end_date"] = date(2026, 12, 31)
    app.run()
    app.button(key="btn_powder_rank").click().run()
    assert not app.exception

    def exported():
        return pd.read_csv(BytesIO(app.session_state["csv_bytes"]), dtype={"色粉編號": str})

    result = exported()
    assert result.columns.tolist() == ["色粉編號", "總用量(kg)"]
    assert result["色粉編號"].tolist() == ["B01", "A001", "4353", "0012"]
    assert result["總用量(kg)"].tolist() == [3, 2, 1.03, 0]
    app.toggle(key="rank_show_01_001").set_value(False).run()
    assert not app.exception
    assert exported()["色粉編號"].tolist() == ["4353", "0012"]
    assert app.dataframe[0].value["色粉編號"].tolist() == ["4353", "0012"]
    app.toggle(key="rank_show_01_001").set_value(True).run()
    assert not app.exception
    assert exported()["色粉編號"].tolist() == result["色粉編號"].tolist()
