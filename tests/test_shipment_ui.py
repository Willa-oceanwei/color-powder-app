from pathlib import Path
from copy import deepcopy

import pytest

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, initialize_database
from utils.shipment_repository import blank_shipment, get_shipment, list_shipments, save_shipment


def test_shipment_styles_are_html_not_visible_markdown(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "style-delivery.db")
    initialize_database(config.path)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    styles = [element for element in app.get("html") if 'id="shipment-page"' in element.proto.body]
    assert len(styles) == 1
    assert "<style>" in styles[0].proto.body and "shipment-item-heading" in styles[0].proto.body
    assert not any("Keep item actions" in element.value or "#shipment-page" in element.value
                   for element in app.markdown)


def test_saved_document_skips_reads_until_navigation_or_refresh_and_can_leave_page(tmp_path, monkeypatch):
    import ast
    import utils.shipment_ui as ui
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'saved-view.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Customer legal name', short_name='Customer'))
    for number in ('001', '003'):
        doc = dict(blank_shipment(), customer_id='C01', customer_name='Customer legal name',
                   number_mode='manual', shipment_number=number)
        doc['items'] = [dict(code='P1', name='Blue', quantity='1', unit='KG', price='100')]
        save_shipment(config, doc)
    calls = []
    for name in ('list_shipments', 'get_shipment'):
        original = getattr(ui, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(ui, name, counted)
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'app.py').read_text(encoding='utf-8'))
    sidebar = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_sidebar')
    script = f'''import sys
sys.path.insert(0,{str(root)!r})
from pathlib import Path
import streamlit as st
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
def request_logout(): pass
''' + ast.unparse(sidebar) + f'''
render_sidebar()
if st.session_state.menu == '出貨單':
    render_shipment_management(DatabaseConfig(backend='sqlite',path=Path({str(config.path)!r})),start_new_on_entry=True)
else:
    st.session_state.pop('shipment_entry_ready',None)
'''
    app = AppTest.from_string(script).run(timeout=30)
    app.button(key='出貨單').click().run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.selectbox(key=prefix + 'customer_picker').set_value('C01').run()
    app.text_input(key=prefix + 'shipment_number').set_value('002')
    app.session_state[prefix + 'items'] = {'edited_rows': {}, 'deleted_rows': [], 'added_rows': [
        {'貨品編號': 'P1', '品名': 'Blue', '數量': 2.0, '單位': 'KG', '單價': 100.0}]}
    app.run()
    app.session_state['receivable_pages'] = ['stale report']
    app.toggle(key=prefix + 'paid_in_full').set_value(True).run()
    app.button(key='shipment_save').click().run()
    assert not app.exception and not calls
    assert 'shipment_draft' not in app.session_state and 'receivable_pages' not in app.session_state
    saved_id = app.session_state['shipment_selected']
    saved_view = app.session_state['shipment_saved_view']['document']
    assert saved_view == get_shipment(config, saved_id)
    assert saved_view['shipment_number'] == '002' and saved_view['items'][0]['amount'] == '200'
    assert saved_view['paid_in_full'] is True
    app.button(key='shipment_edit').click().run()
    next(w for w in app.text_area if w.label == '備註').set_value('Discard this edit').run()
    app.button(key='shipment_cancel').click().run()
    assert not app.exception and not calls
    assert app.session_state['shipment_saved_view']['document'] == saved_view
    assert get_shipment(config, saved_id)['notes'] != 'Discard this edit'
    # Normal viewing and print settings must not re-query the list, document,
    # or customer labels after a successful save.
    original_name = ui.CustomerDisplay.name
    monkeypatch.setattr(ui.CustomerDisplay, 'name', lambda *args, **kwargs: pytest.fail('saved customer label should be reused'))
    app.toggle(key='shipment_print_preview').set_value(True).run()
    app.toggle(key='shipment_hide_prices').set_value(True).run()
    app.toggle(key='shipment_print_preview').set_value(False).run()
    assert not app.exception and not calls
    monkeypatch.setattr(ui.CustomerDisplay, 'name', original_name)
    app.button(key='shipment_nav_上一筆').click().run()
    assert not app.exception and calls == ['list_shipments', 'get_shipment']
    assert next(w for w in app.text_input if w.label == '出貨單號').value == '001'
    assert app.button(key='shipment_nav_上一筆').disabled
    app.button(key='shipment_nav_下一筆').click().run()
    assert next(w for w in app.text_input if w.label == '出貨單號').value == '002'
    app.button(key='shipment_edit').click().run()
    next(w for w in app.text_area if w.label == '備註').set_value('Updated')
    calls.clear()
    app.button(key='shipment_save').click().run()
    assert not app.exception and not calls
    assert app.session_state['shipment_saved_view']['document']['version'] == 2
    # An explicit refresh must discard the saved snapshot and see outside edits.
    external = get_shipment(config, saved_id)
    external['notes'] = 'Changed elsewhere'
    save_shipment(config, external)
    app.button(key='shipment_reload_data').click().run()
    assert not app.exception and calls == ['list_shipments', 'get_shipment']
    assert next(w for w in app.text_area if w.label == '備註').value == 'Changed elsewhere'
    app.button(key='shipment_edit').click().run()
    app.button(key='shipment_save').click().run()
    next(w for w in app.text_input if w.label == '出貨單號 / 客戶 / 貨品編號').set_value('003')
    next(w for w in app.button if w.label == '查詢').click().run()
    assert not app.exception and 'shipment_saved_view' not in app.session_state
    assert next(w for w in app.text_input if w.label == '出貨單號').value == '003'
    # Saving once more and leaving through the real sidebar needs no list read.
    app.button(key='shipment_edit').click().run()
    app.button(key='shipment_save').click().run()
    calls.clear()
    app.button(key='客戶名單').click().run()
    assert not app.exception and app.session_state['menu'] == '客戶名單' and not calls


def test_failed_save_keeps_editing_and_does_not_publish_a_saved_view(tmp_path, monkeypatch, caplog):
    import utils.shipment_ui as ui
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'failed-save.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Customer'))
    doc = dict(blank_shipment(), customer_id='C01', customer_name='Customer')
    doc['items'] = [dict(code='P1', name='Blue', quantity='1', unit='KG', price='100')]
    saved = save_shipment(config, doc)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend='sqlite',path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.button(key='shipment_edit').click().run()
    next(w for w in app.text_area if w.label == '備註').set_value('Keep unsaved notes')
    def fail(*args, **kwargs):
        raise ui.ShipmentError('暫時無法儲存')
    monkeypatch.setattr(ui, 'save_shipment', fail)
    app.button(key='shipment_save').click().run()
    assert not app.exception and app.error
    assert app.session_state['shipment_draft']['notes'] == 'Keep unsaved notes'
    assert 'shipment_saved_view' not in app.session_state
    assert get_shipment(config, saved['id'])['notes'] == ''
    assert 'stage=shipment_save' in caplog.text and 'outcome=error' in caplog.text
    assert 'Keep unsaved notes' not in caplog.text


def test_editing_preview_uses_current_grid_values_without_saving(tmp_path, monkeypatch):
    import utils.shipment_ui as ui
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'draft-preview.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Customer'))
    doc = dict(blank_shipment(), customer_id='C01', customer_name='Customer')
    doc['items'] = [dict(code='P1', name='Original', quantity='1', unit='KG', price='100', order_number='', notes='')]
    saved = save_shipment(config, doc)
    rendered = []
    original = ui.components.html
    def capture(html, **kwargs):
        rendered.append(html)
        return original(html, **kwargs)
    monkeypatch.setattr(ui.components, 'html', capture)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.button(key='shipment_edit').click().run()
    assert not app.toggle(key='shipment_print_preview').disabled
    assert not app.toggle(key='shipment_hide_prices').disabled
    epoch = app.session_state['shipment_epoch']
    app.session_state[f'shipment_{epoch}_items'] = {'edited_rows': {0: {'品名': 'Draft Name', '數量': 2, '單價': 150}}, 'added_rows': [], 'deleted_rows': []}
    app.toggle(key='shipment_print_preview').set_value(True).run()
    assert not app.exception
    assert 'Draft Name' in rendered[-1] and '<td class="amount">300</td>' in rendered[-1]
    app.toggle(key='shipment_hide_prices').set_value(True).run()
    assert not app.exception and '<td class="amount"></td>' in rendered[-1]
    assert app.session_state['shipment_draft']['items'][0]['name'] == 'Draft Name'
    assert get_shipment(config, saved['id'])['items'][0]['name'] == 'Original'
    snapshot_before = deepcopy(app.session_state['shipment_draft'])
    ui._draft_print_document(app.session_state['shipment_draft'])
    assert app.session_state['shipment_draft'] == snapshot_before


def test_exact_number_search_browses_following_numbers_not_only_search_hits(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'number-navigation.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Customer'))
    saved = {}
    for number, day in [('029541', '2026-10-02'), ('029542', '2026-10-01'), ('029543', '2026-10-03')]:
        doc = blank_shipment()
        doc.update(customer_id='C01', customer_name='Customer', shipment_number=number, shipment_date=day)
        doc['items'] = [dict(code='P1', name='Blue', quantity='2', unit='KG', price='100', order_number='', notes='')]
        saved[number] = save_shipment(config, doc)['id']
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    next(w for w in app.text_input if w.label == '出貨單號 / 客戶 / 貨品編號').set_value('029541')
    next(b for b in app.button if b.label == '查詢').click().run()
    assert not app.exception and app.session_state['shipment_selected'] == saved['029541']
    app.button(key='shipment_nav_下一筆').click().run()
    assert not app.exception and app.session_state['shipment_selected'] == saved['029542']
    assert not app.button(key='shipment_edit').disabled and not app.button(key='shipment_copy').disabled
    app.button(key='shipment_nav_下一筆').click().run()
    assert not app.exception and app.session_state['shipment_selected'] == saved['029543']
    assert app.button(key='shipment_nav_下一筆').disabled
    app.button(key='shipment_nav_上一筆').click().run()
    assert app.session_state['shipment_selected'] == saved['029542']


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
    assert app.selectbox(key='shipment_paper_stock').value == 'A4'
    app.selectbox(key='shipment_paper_stock').set_value('A5').run()
    layout = app.selectbox(key='shipment_print_orientation')
    assert layout.options == ['列印：橫式', '列印：直式']
    layout.set_value('直式').run()
    assert not app.exception and app.selectbox(key='shipment_print_orientation').value == '直式'
    epoch = app.session_state['shipment_epoch']
    next(w for w in app.text_area if w.label == '備註').set_value('保留草稿').run()
    assert not app.exception and app.session_state['shipment_epoch'] == epoch
    assert app.session_state['shipment_draft']['notes'] == '保留草稿'
    monkeypatch.setattr(ui, 'list_shipments', lambda *args, **kwargs: [])
    next(b for b in app.button if b.label == '查詢').click().run()
    assert not app.exception
    assert app.session_state['shipment_suspended_drafts'][-1]['notes'] == '保留草稿'


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
    assert app.text_input(key='shipment_purchase_history_code').value == 'P1'
    app.text_input(key='shipment_purchase_history_code').set_value('NO-MATCH')
    app.button(key='shipment_purchase_history_search').click().run()
    assert not app.exception and calls['history'] == 2
    assert app.session_state['shipment_purchase_history_result'][3] == []
    assert app.text_input(key='shipment_purchase_history_code').value == 'NO-MATCH'
    app.button(key='shipment_edit').click().run()
    assert not app.exception and calls['records'] == 1 and calls['document'] == 1
    next(w for w in app.text_area if w.label == '備註').set_value('Discard this edit').run()
    # Even after a long edit, cancellation restores the existing browse snapshot.
    cache = app.session_state['shipment_page_cache']
    for identity, entry in list(cache.items()):
        cache[identity] = (entry[0] - 3600, entry[1])
    app.button(key='shipment_cancel').click().run()
    assert not app.exception and calls['records'] == 1 and calls['document'] == 1
    assert 'shipment_purchase_history_result' not in app.session_state
    app.toggle(key='shipment_print_preview').set_value(False).run()
    assert next(w for w in app.text_area if w.label == '備註').value == ''
    assert get_shipment(config, list_shipments(config)[0]['id'])['notes'] == ''
    app.button(key='shipment_reload_data').click().run()
    assert not app.exception and calls['records'] == 2 and calls['document'] == 2


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
    app.session_state['receivable_pages'] = ['old report']
    app.session_state['ranking_statements'] = ['old ranking']
    app.button(key='shipment_save').click().run()
    assert not app.exception
    assert 'receivable_pages' not in app.session_state and 'ranking_statements' not in app.session_state
    assert len(list_shipments(config)) == 2
    assert get_shipment(config, app.session_state['shipment_selected'])['invoice']['number'] == 'AB12345678'
    app.button(key='shipment_edit').click().run()
    next(widget for widget in app.text_area if widget.label == '備註').set_value('不要儲存').run()
    app.session_state['receivable_pages'] = ['current report']
    app.button(key='shipment_cancel').click().run()
    assert not app.exception
    assert app.session_state['receivable_pages'] == ['current report']
    assert next(widget for widget in app.text_area if widget.label == '備註').value == ''
    app.button(key='shipment_new').click().run()
    next(w for w in app.selectbox if w.label == '單號方式').set_value('依日期生成').run()
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
    assert app.toggle(key='shipment_print_preview').value
    assert app.session_state['shipment_preview_preference']
    app.toggle(key='shipment_hide_prices').set_value(True).run()
    assert app.toggle(key='shipment_print_preview').value, {k: app.session_state[k] for k in ('shipment_print_preview', 'shipment_preview_preference', 'shipment_hide_prices', 'shipment_hide_preference')}
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
    next(w for w in app.selectbox if w.label == '單號方式').set_value('依日期生成').run()
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
    next(w for w in app.selectbox if w.label == '單號方式').set_value('依日期生成').run()
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
    next(w for w in app.selectbox if w.label == '單號方式').set_value('依日期生成').run()
    next(w for w in app.selectbox if w.label == '客戶').set_value('C01').run()
    next(w for w in app.selectbox if w.label == '貨品／配方').set_value('NEW').run()
    app.button(key='shipment_add_recipe').click().run()
    assert not app.exception
    assert app.session_state['shipment_draft']['items'][0]['price'] == 99.0

