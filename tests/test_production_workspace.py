import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

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
