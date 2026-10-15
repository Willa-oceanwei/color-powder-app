from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils import list_ui


def test_selection_returns_original_record_and_resets_with_visible_ids(monkeypatch):
    records = [{'id': 'P02', 'customer': 'Full name', 'amount': 123}, {'id': 'P01', 'amount': 456}]
    frame = pd.DataFrame([{'客戶簡稱': '簡稱'}, {'客戶簡稱': '另一家'}], index=[20, 8])
    calls = []

    def select(data, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(selection=SimpleNamespace(rows=[1]))

    monkeypatch.setattr(list_ui.st, 'dataframe', select)
    assert list_ui.render_selection_table(frame, records, key='orders', id_field='id') is records[1]
    original_key = calls[-1]['key']
    assert list_ui.render_selection_table(frame, records[::-1], key='orders', id_field='id') is records[0]
    assert original_key != calls[-1]['key']
    list_ui.render_selection_table(frame.iloc[:1], records[:1], key='orders', id_field='id')
    assert original_key != calls[-1]['key']
    assert records[0]['customer'] == 'Full name' and records[0]['amount'] == 123


def test_no_selection_empty_and_disabled_cannot_trigger_actions(monkeypatch):
    def empty(data, **kwargs):
        return SimpleNamespace(selection=SimpleNamespace(rows=[]))
    monkeypatch.setattr(list_ui.st, 'dataframe', empty)
    frame = pd.DataFrame([{'id': 'A'}, {'id': 'B'}])
    assert list_ui.render_selection_table(frame, frame.to_dict('records'), key='orders', id_field='id') is None
    one = frame.iloc[:1].to_dict('records')
    assert list_ui.render_selection_table(frame.iloc[:1], one, key='orders', id_field='id') is one[0]
    assert list_ui.render_selection_table(frame.iloc[:1], one, key='orders', id_field='id', disabled=True) is None
    assert list_ui.render_selection_table(frame.iloc[:0], [], key='orders', id_field='id') is None
    with pytest.raises(ValueError):
        list_ui.render_selection_table(frame, one, key='orders', id_field='id')


def test_compact_pagination_next_jump_limit_and_boundaries():
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
import streamlit as st
from utils.list_ui import render_compact_pagination
st.session_state.setdefault('limit', 5)
total = 12
pages = (total - 1) // st.session_state.limit + 1
render_compact_pagination('page', pages, total, 'limit', [5, 10, 20], 'test')
st.write(st.session_state.page)
''').run()
    assert not app.exception and app.button(key='test_prev_page').disabled
    app.button(key='test_next_page').click().run()
    assert not app.exception and app.session_state['page'] == 2
    app.number_input(key='test_jump_page').set_value(3).run()
    assert not app.exception and app.session_state['page'] == 3
    assert app.button(key='test_next_page').disabled
    app.selectbox(key='limit').set_value(20).run()
    assert not app.exception and app.session_state['page'] == 1
    assert app.button(key='test_next_page').disabled and app.number_input(key='test_jump_page').value == 1
    assert any('第 1–12 筆' in caption.value for caption in app.caption)
