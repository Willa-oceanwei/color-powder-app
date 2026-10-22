from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from test_advance_prices import config, quote, document
from utils.advance_price_repository import list_advance_prices
from utils.shipment_repository import save_shipment


def workspace(path, page):
    import streamlit as st
    from pathlib import Path
    from utils.database import DatabaseConfig
    from utils.advance_price_ui import render_advance_price_management
    from utils.shipment_ui import render_shipment_management
    config = DatabaseConfig(backend='sqlite', path=Path(path))
    if page == 'quotes':
        render_advance_price_management(config)
    else:
        render_shipment_management(config, start_new_on_entry=True)


def test_create_quote_in_workspace(config):
    app = AppTest.from_function(workspace, args=(str(config.path), 'quotes')).run()
    app.selectbox(key='advance_0_customer').set_value('C1').run()
    app.selectbox(key='advance_0_code_C1').set_value('P1').run()
    next(i for i in app.text_input if i.label == '預告單價').set_value('110')
    app.date_input[0].set_value(date(2026,11,1))
    next(b for b in app.button if b.label == '確認儲存預告報價').click().run()
    assert not app.exception
    assert list_advance_prices(config)[0]['price'] == '110'
    assert any('已儲存' in message.value for message in app.success)


def test_shipment_date_switch_and_override_guard(config):
    quote(config)
    app = AppTest.from_function(workspace, args=(str(config.path), 'shipment')).run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.selectbox(key=prefix+'customer_picker').set_value('C1').run()
    app.date_input(key=prefix+'shipment_date').set_value(date(2026,10,31)).run()
    app.session_state[prefix+'items'] = {'edited_rows':{},'deleted_rows':[], 'added_rows':[
        {'貨品編號':'P1','品名':'Red','數量':20.0,'單位':'KG','單價':100.0}]}
    app.run()
    assert app.session_state['shipment_draft']['items'][0]['price'] in (100.0, '100')
    app.date_input(key=prefix+'shipment_date').set_value(date(2026,11,1)).run()
    assert not app.exception
    assert str(app.session_state['shipment_draft']['items'][0]['price']) in ('110','110.0')
    # Move back across the boundary: restored original default, no future price leakage.
    app.date_input(key=prefix+'shipment_date').set_value(date(2026,10,31)).run()
    assert str(app.session_state['shipment_draft']['items'][0]['price']) in ('100','100.0')


def test_copy_applies_current_quote_and_manual_reason_persists(config):
    from utils.shipment_ui import _begin
    from utils.shipment_repository import copy_shipment
    saved = save_shipment(config, document(price='100'))
    quote(config)
    app = AppTest.from_function(workspace, args=(str(config.path), 'shipment')).run()
    app.session_state['shipment_draft'] = copy_shipment(saved)
    app.session_state['shipment_original'] = copy_shipment(saved)
    app.session_state['shipment_editor_base'] = copy_shipment(saved)['items']
    app.session_state['shipment_epoch'] += 1
    app.session_state['shipment_grid_epoch'] = 0
    app.run()
    assert not app.exception
    assert str(app.session_state['shipment_draft']['items'][0]['price']) in ('110','110.0')
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    suffix = app.session_state['shipment_grid_epoch']
    key = prefix+'items'+(f'_{suffix}' if suffix else '')
    app.session_state[key] = {'edited_rows':{0:{'單價':100.0}},'deleted_rows':[], 'added_rows':[]}
    app.run()
    assert any('目前為' in message.value for message in app.warning)
    app.button(key='shipment_save').click().run()
    assert any('特殊議價原因' in message.value for message in app.error)
    reason = next(t for t in app.text_input if '特殊議價原因' in t.label)
    reason.set_value('本次優惠').run()
    app.text_input(key=prefix+'shipment_number').set_value('SPECIAL')
    app.button(key='shipment_save').click().run()
    assert not app.exception and not app.error
    assert app.session_state['shipment_saved_view']['document']['items'][0]['advance_price_override_reason'] == '本次優惠'
