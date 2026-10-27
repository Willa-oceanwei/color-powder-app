from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.scheduled_quote_repository import (
    QuoteError, effective_quote_notices, list_scheduled_quotes, save_scheduled_quote,
)
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig('sqlite', tmp_path / 'quotes.db')
    initialize_database(config.path)
    for code in ('C01', 'C02'):
        create_customer(config, CustomerInput(code, 'Customer ' + code))
    return config


def quote(**changes):
    return dict(dict(customer_id='C01', product_code='68146DM', price='250.50', unit='KG',
        tax_mode='外加', effective_date='2026-10-27', notes='新報價', active=True), **changes)


def test_due_date_customer_exact_code_latest_price_and_distinct_units(config):
    old = save_scheduled_quote(config, quote(effective_date='2026-10-01', price='100'))
    current = save_scheduled_quote(config, quote())
    future = save_scheduled_quote(config, quote(effective_date='2026-11-01', price='300'))
    save_scheduled_quote(config, quote(customer_id='C02', price='999'))
    save_scheduled_quote(config, quote(product_code='68146D', price='888'))
    items = [{'code': ' 68146dm ', 'price': '1'}]
    assert effective_quote_notices(config, 'C01', items, today=date(2026, 9, 30)) == []
    assert effective_quote_notices(config, 'C01', items, today=date(2026, 10, 26))[0]['quote_id'] == old['quote_id']
    due = effective_quote_notices(config, 'C01', items, today=date(2026, 10, 27))
    assert len(due) == 1 and due[0]['quote_id'] == current['quote_id']
    assert effective_quote_notices(config, 'C01', items, today=date(2026, 11, 1))[0]['quote_id'] == future['quote_id']
    assert items == [{'code': ' 68146dm ', 'price': '1'}]
    assert effective_quote_notices(config, 'C01', [{'code': '68146'}], today=date(2026, 10, 27)) == []
    assert effective_quote_notices(config, '', items) == []
    assert effective_quote_notices(config, 'C01', []) == []
    save_scheduled_quote(config, quote(unit='包', price='500'))
    save_scheduled_quote(config, quote(tax_mode='內含', price='260'))
    due = effective_quote_notices(config, 'C01', items * 2, today=date(2026, 10, 27))
    assert len(due) == 3
    assert {(q['unit'], q['tax_mode']) for q in due} == {('KG', '外加'), ('KG', '內含'), ('包', '外加')}


def test_modify_disable_and_concurrent_edit_protection(config):
    first = save_scheduled_quote(config, quote(product_code=' 68146dm ', unit='kg'))
    assert first['product_code'] == '68146DM' and first['unit'] == 'KG'
    changed = save_scheduled_quote(config, dict(first, price='999'))
    assert changed['version'] == 2
    with pytest.raises(QuoteError, match='其他人修改'):
        save_scheduled_quote(config, dict(first, price='123'))
    disabled = save_scheduled_quote(config, dict(changed, active=False))
    assert disabled['active'] == 0
    assert not list_scheduled_quotes(config)
    assert len(list_scheduled_quotes(config, include_inactive=True)) == 1
    assert not effective_quote_notices(config, 'C01', [{'code': '68146DM'}], today=date(2026, 10, 27))


@pytest.mark.parametrize('changes', [
    {'price': '-1'}, {'price': 'NaN'}, {'price': 'Infinity'}, {'price': 'abc'},
    {'customer_id': 'UNKNOWN'}, {'product_code': ''}, {'unit': ''},
    {'effective_date': '2026-02-30'}, {'tax_mode': 'wrong'},
])
def test_invalid_quote_never_persists(config, changes):
    with pytest.raises(QuoteError):
        save_scheduled_quote(config, quote(**changes))
    assert not list_scheduled_quotes(config, include_inactive=True)


def test_schema_initialization_preserves_existing_quotes(config):
    saved = save_scheduled_quote(config, quote())
    initialize_database(config.path)
    assert list_scheduled_quotes(config)[0]['quote_id'] == saved['quote_id']
    with connect_from_config(config) as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 32


def test_quote_settings_create_edit_disable(config):
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.scheduled_quote_ui import render_scheduled_quotes
render_scheduled_quotes(DatabaseConfig('sqlite',Path({str(config.path)!r})))
''').run()
    assert not app.exception
    next(w for w in app.selectbox if w.label == '客戶').set_value('C01')
    next(w for w in app.text_input if w.label == '貨品編號').set_value('68146DM')
    next(w for w in app.text_input if w.label == '新單價').set_value('250.50')
    next(w for w in app.button if w.label == '儲存預告報價').click().run()
    assert not app.exception and app.success
    saved = list_scheduled_quotes(config)[0]
    app.selectbox(key='scheduled_quote_selected').set_value(saved['quote_id']).run()
    next(w for w in app.text_input if w.label == '新單價').set_value('300')
    next(w for w in app.checkbox if w.label == '啟用此報價提醒').set_value(False)
    next(w for w in app.button if w.label == '儲存預告報價').click().run()
    assert not app.exception
    updated = list_scheduled_quotes(config, include_inactive=True)[0]
    assert updated['price'] == '300' and not updated['active']


def test_shipment_notice_does_not_change_price_and_disappears_when_disabled(config, monkeypatch):
    import utils.scheduled_quote_repository as repo
    monkeypatch.setattr(repo, 'quote_today', lambda: date(2026, 10, 27))
    saved_quote = save_scheduled_quote(config, quote())
    doc = dict(blank_shipment(), customer_id='C01', customer_name='Customer C01')
    doc['items'] = [dict(code='68146DM', name='Blue', quantity='1', unit='KG', price='100')]
    saved = save_shipment(config, doc)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig('sqlite',Path({str(config.path)!r})))
''').run()
    assert not app.exception and not app.warning
    app.button(key='shipment_edit').click().run()
    assert not app.exception
    assert any('已有新報價' in w.value and '250.50' in w.value for w in app.warning)
    assert Decimal(str(app.session_state['shipment_draft']['items'][0]['price'])) == Decimal('100')
    assert get_shipment(config, saved['id'])['items'][0]['price'] == '100'
    save_scheduled_quote(config, dict(saved_quote, active=False))
    app.run()
    assert not app.exception and not app.warning


def test_sidebar_quote_entry_follows_receivables():
    import ast
    tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
    sidebar = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_sidebar')
    menus = next(n.value for n in sidebar.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'MENU_ITEMS' for t in n.targets))
    keys = [row['key'] for row in ast.literal_eval(menus)]
    assert keys[keys.index('應收帳款明細表') + 1] == '預告報價'


def test_entering_shipment_code_notifies_only_when_effective_date_arrives(config, monkeypatch):
    import utils.scheduled_quote_repository as repo
    today = [date(2026, 10, 26)]
    monkeypatch.setattr(repo, 'quote_today', lambda: today[0])
    save_scheduled_quote(config, quote())
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.shipment_ui import render_shipment_management
render_shipment_management(DatabaseConfig('sqlite',Path({str(config.path)!r})),start_new_on_entry=True)
''').run()
    prefix = f"shipment_{app.session_state['shipment_epoch']}_"
    app.selectbox(key=prefix + 'customer_picker').set_value('C01').run()
    app.session_state[prefix + 'items'] = {'edited_rows': {}, 'deleted_rows': [], 'added_rows': [
        {'貨品編號': '68146DM', '品名': 'Blue', '數量': 1.0, '單位': 'KG', '單價': 100.0}]}
    app.run()
    assert not app.exception and not app.warning
    today[0] = date(2026, 10, 27)
    app.run()
    assert not app.exception
    assert any('已有新報價' in w.value and '68146DM' in w.value for w in app.warning)
    assert Decimal(str(app.session_state['shipment_draft']['items'][0]['price'])) == Decimal('100')
    app.selectbox(key=prefix + 'customer_picker').set_value('C02').run()
    assert not app.exception and not app.warning


def test_remote_quote_writes_invalidate_cached_customer_quotes(config, monkeypatch):
    import sqlite3
    from utils import database, read_cache
    remote = DatabaseConfig('turso', None, str(config.path), 'test-token')
    def connect(_config):
        conn = sqlite3.connect(_config.turso_database_url)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr(database, '_connect_turso', connect)
    read_cache.invalidate_read_cache(remote)
    assert list_scheduled_quotes(remote, 'C01') == []
    saved = save_scheduled_quote(remote, quote())
    assert list_scheduled_quotes(remote, 'C01')[0]['quote_id'] == saved['quote_id']
    save_scheduled_quote(remote, dict(saved, active=False))
    assert list_scheduled_quotes(remote, 'C01') == []
