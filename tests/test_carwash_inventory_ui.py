from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

from utils.carwash_inventory_repository import (
    list_carwash_inventory_movements, save_carwash_inventory_movement,
)
from utils.database import DatabaseConfig, initialize_database


@pytest.mark.parametrize('movement_type,unit,amount,expected', [
    ('入庫', 'KG', 250.5, '1,250.50 KG'),
    ('出庫', 'KG', 250.5, '749.50 KG'),
    ('出庫', '包', 1000, '0.00 包'),
    ('出庫', 'KG', 1200, '-200.00 KG'),
])
def test_saved_balance_dialog_and_close_do_not_repeat_write(tmp_path, movement_type, unit, amount, expected):
    config = DatabaseConfig('sqlite', tmp_path / 'carwash.db')
    initialize_database(config.path)
    today = datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()
    save_carwash_inventory_movement(config, {
        '類型': '初始庫存', '貨品編號': '68146DM', '初始庫存日期': today,
        '初始數量': 1000, '單位': unit,
    }, create=True)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''
import sys
sys.path.insert(0, {root!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.carwash_inventory_repository import save_carwash_inventory_movement, list_carwash_inventory_movements
from utils.carwash_inventory_ui import show_carwash_save_notice
config = DatabaseConfig('sqlite', Path({str(config.path)!r}))
movements = list_carwash_inventory_movements(config)
notice = st.session_state.pop('cw_save_notice', None)
if notice:
    show_carwash_save_notice(notice, movements)
if st.button('儲存'):
    save_carwash_inventory_movement(config, {{'類型': {movement_type!r}, '貨品編號': '68146DM',
        '入庫日期': {today!r}, '出庫日期': {today!r}, '數量': {amount!r}, '單位': {unit!r}}}, create=True)
    st.session_state['cw_save_notice'] = {{'product_id': '68146DM', 'movement_type': {movement_type!r},
        'quantity': {amount!r}, 'unit': {unit!r}, 'movement_date': {today!r}}}
    st.rerun()
''').run()
    assert not app.exception and not app.metric
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].label == '目前洗車廠庫存'
    assert app.metric[0].value == expected
    assert '68146DM' in app.success[0].value
    assert len(list_carwash_inventory_movements(config)) == 2
    app.button(key='cw_save_notice_close').click().run()
    assert not app.exception and not app.metric
    app.run()
    assert not app.metric
    assert len(list_carwash_inventory_movements(config)) == 2


def test_future_movement_notice_does_not_inflate_current_stock():
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    future = (today + timedelta(days=1)).isoformat()
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''
import sys
sys.path.insert(0, {root!r})
from utils.carwash_inventory_ui import show_carwash_save_notice
show_carwash_save_notice({{'product_id': 'A1', 'movement_type': '入庫', 'quantity': 20,
    'unit': 'KG', 'movement_date': {future!r}}}, [
    {{'product_id': 'A1', 'movement_type': '初始庫存', 'initial_date': {today.isoformat()!r},
      'initial_quantity': 100, 'unit': 'KG'}},
    {{'product_id': 'A1', 'movement_type': '入庫', 'inbound_date': {future!r}, 'quantity': 20, 'unit': 'KG'}}])
''').run()
    assert not app.exception
    assert app.metric[0].value == '100.00 KG'
    assert '未來日期' in app.info[0].value
