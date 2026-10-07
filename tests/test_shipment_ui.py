from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, list_shipments, save_shipment


def test_shipment_editor_save_cancel_and_navigation(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'ui.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', '範例客戶'))
    d = blank_shipment()
    d.update(customer_id='C01', customer_name='範例客戶')
    d['items'] = [dict(code='P1', name='藍', quantity='1', unit='包', price='260', order_number='', notes='')]
    first = save_shipment(config, d)
    second = save_shipment(config, d)
    root = str(Path(__file__).resolve().parents[1])
    script = f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    app.button(key='shipment_nav_下一筆').click().run()
    assert not app.exception
    app.button(key='shipment_edit').click().run()
    assert app.button(key='shipment_nav_上一筆').disabled
    invoice_input = next(widget for widget in app.text_input if widget.label == '發票編號')
    invoice_input.set_value('AB12345678').run()
    invoice_date = next(widget for widget in app.date_input if widget.label == '發票日期')
    from datetime import date
    invoice_date.set_value(date(2026, 10, 7)).run()
    app.button(key='shipment_save').click().run()
    assert not app.exception
    assert len(list_shipments(config)) == 2
    assert get_shipment(config, app.session_state['shipment_selected'])['invoice']['number'] == 'AB12345678'
    app.button(key='shipment_edit').click().run()
    next(widget for widget in app.text_area if widget.label == '備註').set_value('不要儲存').run()
    app.button(key='shipment_cancel').click().run()
    assert not app.exception
    assert next(widget for widget in app.text_area if widget.label == '備註').value == ''
    app.button(key='shipment_new').click().run()
    assert not app.exception
    picker = next(widget for widget in app.selectbox if widget.label == '客戶')
    picker.set_value('C01').run()
    epoch = app.session_state['shipment_epoch']
    app.session_state[f'shipment_{epoch}_items'] = {
        'edited_rows': {}, 'added_rows': [{'貨品編號': 'P2', '品名': '白', '數量': 2.0,
                                        '單位': '包', '單價': 280.0, '訂單編號': '', '附註說明': ''}],
        'deleted_rows': [],
    }
    app.run()
    assert not app.exception
    next(widget for widget in app.text_area if widget.label == '備註').set_value('新單').run()
    assert len(app.session_state['shipment_draft']['items']) == 1
    app.button(key='shipment_save').click().run()
    assert not app.exception
    assert len(list_shipments(config)) == 3
    created = get_shipment(config, app.session_state['shipment_selected'])
    assert created['items'][0]['amount'] == '560'
    assert created['notes'] == '新單'
    app.toggle(key='shipment_print_preview').set_value(True).run()
    assert not app.exception
    app.toggle(key='shipment_hide_prices').set_value(True).run()
    app.button(key='shipment_nav_首筆').click().run()
    assert not app.exception
    assert app.toggle(key='shipment_print_preview').value
    assert app.toggle(key='shipment_hide_prices').value
    assert app.session_state['shipment_selected'] == first['id']
    app.toggle(key='shipment_print_preview').set_value(False).run()
    app.button(key='shipment_edit').click().run()
    next(widget for widget in app.selectbox if widget.label == '單號方式').set_value('自行輸入').run()
    next(widget for widget in app.text_input if widget.label == '出貨單號').set_value('000123').run()
    app.button(key='shipment_save').click().run()
    assert not app.exception
    assert get_shipment(config, first['id'])['shipment_number'] == '000123'
