from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, list_shipments, save_shipment


def test_entry_defaults_new_without_reloading_saved_documents(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'entry.db')
    initialize_database(config.path)
    def no_list(*args, **kwargs):
        raise AssertionError('Draft editing must not read all shipment records')
    monkeypatch.setattr(ui, 'list_shipments', no_list)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})), start_new_on_entry=True)
''').run(timeout=30)
    assert not app.exception
    assert app.button(key='shipment_new').disabled and not app.button(key='shipment_save').disabled
    assert not any(widget.label in ('首筆', '尾筆') for widget in app.button)
    layout = app.selectbox(key='shipment_print_orientation')
    assert layout.proto.label_visibility.value == 2
    assert layout.options == ['列印：橫式', '列印：直式']
    layout.set_value('直式').run()
    assert not app.exception and app.selectbox(key='shipment_print_orientation').value == '直式'
    epoch = app.session_state['shipment_epoch']
    next(w for w in app.text_area if w.label == '備註').set_value('保留草稿').run()
    assert not app.exception and app.session_state['shipment_epoch'] == epoch
    assert app.session_state['shipment_draft']['notes'] == '保留草稿'


def test_view_reads_are_cached_and_purchase_history_is_on_demand(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    import utils.shipment_history_ui as history_ui
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'history-ui.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Customer'))
    doc = blank_shipment()
    doc.update(customer_id='C01', customer_name='Customer')
    doc['items'] = [dict(code='P1', name='Blue', quantity='2', unit='KG', price='100', order_number='', notes='')]
    save_shipment(config, doc)
    calls = {'records': 0, 'document': 0, 'history': 0}
    for name, key in [('list_shipments', 'records'), ('get_shipment', 'document')]:
        original = getattr(ui, name)
        def count(*args, _key=key, _original=original, **kwargs):
            calls[_key] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(ui, name, count)
    original_history = history_ui.customer_purchase_history
    def read_history(*args, **kwargs):
        calls['history'] += 1
        return original_history(*args, **kwargs)
    monkeypatch.setattr(history_ui, 'customer_purchase_history', read_history)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception and calls == {'records': 1, 'document': 1, 'history': 0}
    app.toggle(key='shipment_print_preview').set_value(True).run()
    assert not app.exception and calls == {'records': 1, 'document': 1, 'history': 0}
    app.text_input(key='shipment_purchase_history_code').set_value('P1')
    next(b for b in app.button if b.label == '搜尋歷程').click().run()
    assert not app.exception and calls['history'] == 1
    assert app.session_state['shipment_purchase_history_result'][3][0]['amount'] == '200'
    app.button(key='shipment_edit').click().run()
    assert not app.exception and calls['records'] == 1 and calls['document'] == 1
    app.button(key='shipment_cancel').click().run()
    assert not app.exception and calls['records'] == 2 and calls['document'] == 2
    assert 'shipment_purchase_history_result' not in app.session_state


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
                                        '單位': '包', '單價': 280.0, '採購單號': 'PO-002', '附註說明': ''}],
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
    assert created['items'][0]['order_number'] == 'PO-002'
    from utils.shipment_repository import printable_shipment
    assert 'PO-002' in printable_shipment(created)
    assert created['notes'] == '新單'
    app.toggle(key='shipment_print_preview').set_value(True).run()
    assert not app.exception
    app.toggle(key='shipment_hide_prices').set_value(True).run()
    app.button(key='shipment_nav_上一筆').click().run()
    app.button(key='shipment_nav_上一筆').click().run()
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
    from utils.recipe_repository import create_recipe
    create_recipe(config, {'配方編號': 'P1', '顏色': '藍', '客戶編號': 'C01'})
    app.button(key='shipment_new').click().run()
    next(widget for widget in app.selectbox if widget.label == '客戶').set_value('C01').run()
    next(widget for widget in app.selectbox if widget.label == '貨品／配方').set_value('P1').run()
    next(widget for widget in app.text_input if widget.label == '銷售單位').set_value('包').run()
    app.button(key='shipment_add_recipe').click().run()
    assert not app.exception
    assert app.session_state['shipment_draft']['items'][0]['code'] == 'P1'
    assert str(app.session_state['shipment_draft']['items'][0]['price']) in ('260', '260.0')
    epoch = app.session_state['shipment_epoch']
    grid = app.session_state['shipment_grid_epoch']
    app.session_state[f'shipment_{epoch}_items_{grid}'] = {
        'edited_rows': {0: {'單價': 299.0, '品名': '手動調整品名'}}, 'added_rows': [], 'deleted_rows': []}
    app.button(key='shipment_add_recipe').click().run()
    assert not app.exception
    assert app.session_state['shipment_draft']['items'][0]['price'] == 299.0
    assert app.session_state['shipment_draft']['items'][0]['name'] == '手動調整品名'
    assert len(app.session_state['shipment_draft']['items']) == 2
    app.button(key='shipment_save').click().run()
    saved = get_shipment(config, app.session_state['shipment_selected'])
    assert saved['items'][0]['name'] == '手動調整品名'
    from utils.shipment_repository import printable_shipment
    assert '手動調整品名' in printable_shipment(saved)
    assert not app.exception
    assert get_shipment(config, app.session_state['shipment_selected'])['items'][0]['price'] == '299.0'
    from utils.product_repository import blank_product, save_product
    master = blank_product()
    master.update(product_id='NEW', name='貨品白', sales_unit='包', standard_price='99', specification='25KG')
    saved_product = save_product(config, master)
    app.button(key='shipment_new').click().run()
    next(w for w in app.selectbox if w.label == '客戶').set_value('C01').run()
    next(w for w in app.selectbox if w.label == '貨品／配方').set_value('NEW').run()
    assert next(w for w in app.text_input if w.label == '銷售單位').value == '包'
    app.button(key='shipment_add_recipe').click().run()
    assert not app.exception
    assert app.session_state['shipment_draft']['items'][0]['price'] == 99.0
    assert app.session_state['shipment_draft']['items'][0]['notes'] == ''
    app.button(key='shipment_save').click().run()
    saved_product['standard_price'] = '150'
    save_product(config, saved_product)
    app.button(key='shipment_new').click().run()
    next(w for w in app.selectbox if w.label == '客戶').set_value('C01').run()
    next(w for w in app.selectbox if w.label == '貨品／配方').set_value('NEW').run()
    app.button(key='shipment_add_recipe').click().run()
    assert not app.exception
    assert app.session_state['shipment_draft']['items'][0]['price'] == 99.0
