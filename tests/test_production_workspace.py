import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.runtime.scriptrunner import ScriptRunnerEvent
from streamlit.testing.v1.local_script_runner import LocalScriptRunner

from utils.database import DatabaseConfig, initialize_database
from utils.production_order_repository import create_production_order, list_production_orders
from utils.recipe_repository import create_recipe
from test_workspace_performance import queue_updates


def workspace_source():
    source = Path('app.py').read_text(encoding='utf-8')
    lines = source.splitlines()
    wanted = {
        'render_production_order_workspace', 'rerun_production_order_workspace',
        'clean_powder_id', 'fix_leading_zero', 'split_search_keywords', 'filter_df_by_keywords',
        'calculate_shipment_display', 'colorant_shipment_display_multiplier', 'fmt_num',
        'parse_pack_value', 'safe_float_convert', 'safe_int_convert', 'safe_str_convert',
        'safe_str', 'safe_float', 'calc_packs_total_kg', 'calculate_production_package_total_kg',
        'reset_production_order_draft_state', 'initialize_production_order_recipe_widgets',
        'clear_production_order_edit_state', 'begin_production_order_edit',
        'sync_selected_production_order_state', 'build_a5_production_order_download',
        'generate_production_order_print', 'generate_print_page_content',
        'generate_order_preview_text', 'generate_recipe_preview_text',
        'render_order_download_actions', 'render_big_label_editor', 'render_saved_label_section',
        'get_saved_label_order', 'build_big_label_rows', 'generate_big_label_html',
        'chunk_label_pages', 'format_label_ratio', 'to_roc_date',
        'render_empty_state', 'render_pagination_bar',
    }
    nodes = [n for n in ast.parse(source).body if
             isinstance(n, ast.FunctionDef) and n.name in wanted or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
             t.id == 'PRODUCTION_ORDER_EDIT_WIDGET_KEYS' for t in n.targets)]
    return '\n\n'.join('\n'.join(lines[min([n.lineno] + [d.lineno for d in getattr(n, 'decorator_list', [])])-1:n.end_lineno])
                        for n in nodes)


@pytest.fixture
def production_config(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'production.db')
    initialize_database(config.path)
    for code in ('R001', 'R002'):
        create_recipe(config, {'配方編號': code, '顏色': 'Blue', '客戶名稱': 'Customer',
                               '色粉類別': '配方', '配方類別': '原始配方', '計量單位': '包'})
    create_production_order(config, {'生產單號': 'P001', '配方編號': 'R001',
                                    '生產日期': '2026-10-19', '建立時間': '2026-10-19 09:00:00', '客戶名稱': 'Customer',
                                    '顏色': 'Blue', '包裝重量1': '1', '包裝份數1': '2'})
    return config


def workspace_app(config):
    root = str(Path.cwd())
    return AppTest.from_string(f'''import sys, time, json, re, logging, ast, concurrent.futures
sys.path.insert(0, {root!r})
from pathlib import Path
from datetime import datetime, timedelta
import html as html_escape
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from utils.database import DatabaseConfig
from utils.production_order_repository import *
from utils.recipe_repository import *
from utils.inventory_repository import list_inventory_movements
from utils.outsourcing_repository import *
from utils.big_label_repository import *
from utils.small_label_print import generate_small_label_html
from utils.customer_display import CustomerDisplay
from utils.paper_preview import build_paper_preview, paper_preview_height
from utils.list_ui import render_selection_table as original_selection, render_compact_pagination
from utils.read_cache import invalidate_read_cache
DATABASE_CONFIG = DatabaseConfig(backend='sqlite', path=Path({str(config.path)!r}))
customer_display = CustomerDisplay(DATABASE_CONFIG)
log_performance = lambda *a, **kw: None
{workspace_source()}
original_outsourcing = list_outsourcing_orders
def list_outsourcing_orders(*a, **kw):
    st.session_state.qa_outsourcing_reads = st.session_state.get('qa_outsourcing_reads', 0) + 1
    return original_outsourcing(*a, **kw)
def render_selection_table(frame, records, **kwargs):
    st.dataframe(frame)
    if kwargs['key'] == 'production_manage':
        return records[0] if records and not st.session_state.get('qa_drop_manage_selection') else None
    if kwargs['key'] == 'production_history' and not st.session_state.get('qa_drop_selection'):
        return records[0] if records else None
    return None
st.session_state.qa_main_runs = st.session_state.get('qa_main_runs', 0) + 1
st.caption(f"Main runs: {{st.session_state.qa_main_runs}}")
st.session_state.setdefault('last_search_tab3_done', True)
render_production_order_workspace()
''')


def test_saving_edit_refreshes_records_without_restarting_main_app(production_config, monkeypatch):
    queued = queue_updates(monkeypatch, [('edit_order_btn_tab3', True),
                                         ('edit_color_tab3', 'Changed'),
                                         ('save_edit_button_tab3', True)])
    app = workspace_app(production_config).run(timeout=30)
    assert not app.exception
    assert len(queued) == 3 and app.session_state['qa_main_runs'] == 1
    assert list_production_orders(production_config)[0]['顏色'] == 'Changed'
    assert app.session_state['df_order'].iloc[0]['顏色'] == 'Changed'
    assert not app.session_state['show_edit_panel']
    assert 'qa_outsourcing_reads' not in app.session_state
    assert any('Changed' in str(table.value) for table in app.dataframe)
    # Model a dataframe reset after the saved row's display data changes.
    restored = workspace_app(production_config)
    restored.session_state['qa_drop_manage_selection'] = True
    restored.session_state['production_manage_saved_order_id'] = 'P001'
    restored.run(timeout=30)
    assert not restored.exception
    assert restored.button(key='edit_order_btn_tab3')
    assert restored.session_state['production_manage_saved_order_id'] == 'P001'


@pytest.mark.parametrize('label_kind', ['大標籤', '小標籤'])
def test_saved_label_panel_survives_lost_table_selection(production_config, label_kind):
    app = workspace_app(production_config).run(timeout=30)
    assert not app.exception
    app.button(key='open_labels_tab2_P001').click().run()
    assert not app.exception
    if label_kind == '小標籤':
        app.radio(key='tab2_label_kind_P001').set_value(label_kind).run()
    prefix = 'tab2_small' if label_kind == '小標籤' else 'tab2'
    app.button(key=f'{prefix}_save_labels_P001').click().run()
    assert not app.exception
    assert app.session_state['history_labels_pinned_order_id'] == 'P001'
    app.session_state['qa_drop_selection'] = True
    app.run()
    assert not app.exception
    download = next(item for item in app.get('download_button') if item.proto.label == '下載列印檔')
    assert not download.proto.disabled
    assert app.session_state['history_labels_open_P001']
    app.button(key='open_labels_tab2_P001').click().run()
    assert not app.exception
    assert 'history_labels_pinned_order_id' not in app.session_state


@pytest.mark.parametrize('saved', [False, True])
def test_clear_creation_draft_preserves_saved_orders(production_config, saved):
    app = workspace_app(production_config).run(timeout=30)
    app.text_input(key='search_text_tab1').set_value('R002').run()
    assert not app.exception and app.session_state['show_confirm_panel']
    app.session_state['form_weight1_tab1'] = '25'
    app.session_state['form_count1_tab1'] = '8'
    app.session_state['form_remark_tab1'] = 'Previous draft'
    app.session_state['new_order_saved'] = saved
    app.session_state['downloaded_html_tab1'] = saved
    app.session_state['saved_label_snapshot'] = {'old': True}
    app.session_state['merge_decision_R002_sameday'] = 'merge'
    before = list_production_orders(production_config)
    app.button(key='clear_production_draft_tab1').click().run()
    assert not app.exception
    assert app.text_input(key='search_text_tab1').value == ''
    assert app.selectbox(key='search_add_form_selected_recipe_tab1').value == '請選擇'
    assert not app.session_state['show_confirm_panel']
    assert not app.session_state['new_order_saved']
    assert not app.session_state['downloaded_html_tab1']
    assert 'saved_label_snapshot' not in app.session_state
    assert 'merge_decision_R002_sameday' not in app.session_state
    assert not any(b.label == '💾 僅儲存生產單' for b in app.button)
    assert list_production_orders(production_config) == before
    app.text_input(key='search_text_tab1').set_value('R002').run()
    assert not app.exception and app.session_state['show_confirm_panel']
    assert app.text_input(key='form_weight1_tab1').value == ''
    assert app.text_input(key='form_count1_tab1').value == ''
    assert app.text_area(key='form_remark_tab1').value == ''


def test_short_exact_recipe_search_prefers_full_id_and_keeps_draft_inputs(production_config):
    for code in ('917', '0917', '1917', '917A'):
        create_recipe(production_config, {'配方編號': code, '顏色': '螢光黃', '客戶名稱': 'Customer',
                                         '色粉類別': '配方', '配方類別': '原始配方', '計量單位': 'kg'})
    before = list_production_orders(production_config)
    app = workspace_app(production_config).run(timeout=30)
    app.text_input(key='search_text_tab1').set_value('917').run()
    assert not app.exception and app.session_state['show_confirm_panel']
    assert app.session_state['new_order']['配方編號'] == '917'
    app.text_input(key='form_weight1_tab1').set_value('25').run()
    assert not app.exception
    assert app.text_input(key='form_weight1_tab1').value == '25'
    assert app.session_state['new_order']['配方編號'] == '917'
    assert app.session_state['recipe_row_cache']['配方編號'] == '917'
    app.text_input(key='search_text_tab1').set_value('0917').run()
    assert not app.exception and app.session_state['show_confirm_panel']
    assert app.session_state['new_order']['配方編號'] == '0917'
    assert app.session_state['recipe_row_cache']['配方編號'] == '0917'
    assert list_production_orders(production_config) == before


def test_manual_recipe_selection_opens_creation_without_another_add_click(production_config):
    for code in ('917', '917A'):
        create_recipe(production_config, {'配方編號': code, '顏色': '螢光黃', '客戶名稱': 'Customer',
                                         '色粉類別': '配方', '配方類別': '原始配方', '計量單位': 'kg'})
    before = list_production_orders(production_config)
    app = workspace_app(production_config).run(timeout=30)
    app.text_input(key='search_text_tab1').set_value('螢光黃').run()
    picker = app.selectbox(key='search_add_form_selected_recipe_tab1')
    label = next(option for option in picker.options if option.startswith('917 |'))
    picker.set_value(label).run()
    assert not app.exception and app.session_state['show_confirm_panel']
    assert app.session_state['new_order']['配方編號'] == '917'
    app.text_input(key='form_weight1_tab1').set_value('25').run()
    picker = app.selectbox(key='search_add_form_selected_recipe_tab1')
    label = next(option for option in picker.options if option.startswith('917A |'))
    picker.set_value(label).run()
    assert not app.exception and app.session_state['show_confirm_panel']
    assert app.session_state['new_order']['配方編號'] == '917A'
    assert app.text_input(key='form_weight1_tab1').value == ''
    assert list_production_orders(production_config) == before


def test_history_label_editor_and_workspace_have_one_render_owner(production_config, monkeypatch):
    original_init = LocalScriptRunner.__init__
    fragment_counts = []

    def initialize_runner(runner, *args, **kwargs):
        original_init(runner, *args, **kwargs)

        def collect_fragments(sender, event, **kwargs):
            if event == ScriptRunnerEvent.SCRIPT_STOPPED_WITH_SUCCESS:
                fragment_counts.append(len(runner._fragment_storage._fragments))

        runner.on_event.connect(collect_fragments, weak=False)

    monkeypatch.setattr(LocalScriptRunner, '__init__', initialize_runner)
    app = workspace_app(production_config)
    app.session_state['history_labels_open_P001'] = True
    app.run(timeout=30)
    assert not app.exception
    assert fragment_counts == [1]
    assert any(button.label == '儲存並更新標籤' for button in app.button)
    assert any(item.proto.label == '下載列印檔' for item in app.get('download_button'))


@pytest.mark.parametrize("label_kind", ["大標籤", "小標籤"])
def test_first_label_save_survives_selection_reset(production_config, label_kind):
    app = workspace_app(production_config).run(timeout=30)
    app.button(key="open_labels_tab2_P001").click().run()
    if label_kind == "小標籤":
        app.radio(key="tab2_label_kind_P001").set_value(label_kind).run()
    prefix = "tab2_small" if label_kind == "小標籤" else "tab2"
    app.session_state[f"{prefix}_big_label_editor_P001"] = {
        "edited_rows": {0: {"品名": "First click", "列印張數": 3}},
        "added_rows": [], "deleted_rows": [],
    }
    # The selection table can reset in the same rerun as a label save.
    app.session_state["qa_drop_selection"] = True
    app.button(key=f"{prefix}_save_labels_P001").click().run()
    assert not app.exception
    assert app.session_state["history_labels_pinned_order_id"] == "P001"
    assert len(app.session_state[f"{prefix}_big_label_confirmed_P001"]) == 3
    assert b"First click" in app.session_state[f"{prefix}_label_render_P001"][1]
    download = next(item for item in app.get("download_button") if item.proto.label == "下載列印檔")
    assert not download.proto.disabled
