from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.product_transaction_report import product_transactions, product_price_changes
from utils.product_transaction_ui import taiwan_timestamp
from utils.shipment_repository import ShipmentError, blank_shipment, save_shipment, void_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'product-history.db')
    initialize_database(config.path)
    for code in ('C01', 'C02', 'C03'):
        create_customer(config, CustomerInput(code, '客戶' + code))
    return config


def shipment(config, number, customer='C01', day='2026-10-01', code='P1', count=1,
             price='160', unit='包', tax_mode='外加'):
    doc = dict(blank_shipment(), shipment_number=number, number_mode='manual', customer_id=customer,
               customer_name='客戶' + customer, shipment_date=day, tax_mode=tax_mode)
    doc['items'] = [dict(code=code, name='歷史品名', quantity='1.125', unit=unit, price=price,
                         notes='明細說明', order_number='PO001')] * count
    return save_shipment(config, doc)


def test_history_all_dates_exact_codes_customers_lines_and_void(config):
    shipment(config, '001', day='2025-01-01', count=2)
    shipment(config, '002', customer='C02', day='2026-10-16')
    shipment(config, '003', code='P10')
    cancelled = shipment(config, '004', customer='C03')
    void_shipment(config, cancelled['id'], cancelled['version'], '取消')
    rows = product_transactions(config, ' p1 ')
    assert len(rows) == 3
    assert [r['shipment_number'] for r in rows] == ['002', '001', '001']
    assert {r['customer_id'] for r in rows} == {'C01', 'C02'}
    assert {r['line_number'] for r in rows if r['shipment_number'] == '001'} == {1, 2}
    assert rows[0]['quantity'] == '1.125' and rows[0]['name'] == '歷史品名'
    assert rows[0]['notes'] == '明細說明' and rows[0]['order_number'] == 'PO001'
    assert rows[0]['created_at']
    assert not product_transactions(config, "P1' OR 1=1 --")


def test_history_optional_date_boundaries_and_validation(config):
    for number, day in [('01', '2026-09-30'), ('02', '2026-10-01'), ('03', '2026-10-31'), ('04', '2026-11-01')]:
        shipment(config, number, day=day, code='R1')
    assert len(product_transactions(config, 'R1')) == 4
    assert len(product_transactions(config, 'R1', start='2026-10-01')) == 3
    assert len(product_transactions(config, 'R1', end='2026-10-31')) == 3
    assert len(product_transactions(config, 'R1', start='2026-10-01', end='2026-10-31')) == 2
    with pytest.raises(ShipmentError, match='編號'):
        product_transactions(config, '')
    with pytest.raises(ShipmentError, match='晚於'):
        product_transactions(config, 'R1', '2026-11-01', '2026-10-01')
    with pytest.raises(ShipmentError, match='有效'):
        product_transactions(config, 'R1', 'invalid')


def test_history_timestamps_are_original_registration_times_in_taiwan(config):
    doc = shipment(config, '001', day='2020-01-01')
    with connect_from_config(config) as conn:
        conn.execute('UPDATE shipment_orders SET created_at=? WHERE id=?', ('2026-10-16T17:20:30+00:00', doc['id']))
    row = product_transactions(config, 'P1')[0]
    assert row['shipment_date'] == '2020-01-01'
    assert taiwan_timestamp(row['created_at']) == '2026-10-17 01:20:30'
    assert taiwan_timestamp('2026-10-16T17:20:30Z') == '2026-10-17 01:20:30'
    assert taiwan_timestamp(None) == ''


def history_app(config):
    root = str(Path(__file__).resolve().parents[1])
    return AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_transaction_ui import render_product_transactions
render_product_transactions(DatabaseConfig(backend='sqlite',path=Path({str(config.path)!r})))
''').run(timeout=30)


def search(app, code):
    app.text_input(key='product_history_code').set_value(code)
    next(w for w in app.button if w.label == '查詢').click().run()


def test_history_customer_checkboxes_filter_union_clear_and_reset(config, monkeypatch):
    shipment(config, '001', customer='C01', count=2)
    shipment(config, '002', customer='C02')
    shipment(config, '003', customer='C03', code='R2')
    import utils.product_transaction_ui as ui
    calls = []
    original = ui.product_transactions
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(ui, 'product_transactions', counted)
    app = history_app(config)
    assert not app.exception and not calls
    assert all(w.value is None for w in app.date_input)
    search(app, 'P1')
    assert not app.exception and len(app.checkbox) == 2
    assert len(app.dataframe[0].value) == 3
    first_key, second_key = app.checkbox[0].key, app.checkbox[1].key
    app.checkbox(key=first_key).check().run()
    assert set(app.dataframe[0].value['客戶編號']) == {'C01'}
    app.checkbox(key=second_key).check().run()
    assert len(app.dataframe[0].value) == 3
    app.checkbox(key=first_key).uncheck().run()
    assert set(app.dataframe[0].value['客戶編號']) == {'C02'}
    app.checkbox(key=second_key).uncheck().run()
    assert len(app.dataframe[0].value) == 3 and len(calls) == 1
    app.checkbox(key=first_key).check().run()
    search(app, 'R2')
    assert not app.exception and not app.checkbox
    assert set(app.dataframe[0].value['客戶編號']) == {'C03'}
    search(app, 'P1')
    assert not any(w.value for w in app.checkbox)
    assert len(app.dataframe[0].value) == 3


def test_history_dates_single_customer_empty_and_invalid_clear_old_results(config):
    shipment(config, '001', day='2025-01-01')
    shipment(config, '002', customer='C02', day='2026-10-16')
    app = history_app(config)
    app.date_input(key='product_history_start').set_value(date(2026, 10, 1))
    search(app, 'P1')
    assert not app.exception and not app.checkbox
    assert len(app.dataframe[0].value) == 1
    app.date_input(key='product_history_end').set_value(date(2026, 9, 1))
    search(app, 'P1')
    assert app.error and not app.dataframe
    app.date_input(key='product_history_start').set_value(None)
    app.date_input(key='product_history_end').set_value(None)
    search(app, 'UNKNOWN')
    assert app.info and not app.checkbox and not app.dataframe


def test_price_history_exact_comparisons_groups_reversals_and_void(config):
    for number, price in [('01', '100'), ('02', '100.000'), ('03', '100.125'),
                          ('04', '100.125'), ('05', '95'), ('06', '100')]:
        shipment(config, number, day=f'2026-10-{number}', price=price)
    shipment(config, '07', customer='C02', price='200')
    shipment(config, '08', unit='kg', price='300')
    shipment(config, '09', tax_mode='內含', price='400')
    cancelled = shipment(config, '10', day='2026-10-10', price='900')
    void_shipment(config, cancelled['id'], cancelled['version'], '取消')
    rows = product_transactions(config, 'P1')
    before = [dict(row) for row in rows]
    changes = product_price_changes(rows)
    base = [r for r in changes if r['customer_id'] == 'C01' and r['unit'] == '包' and r['tax_mode'] == '外加']
    assert [r['shipment_number'] for r in base] == ['06', '05', '03', '01']
    assert [r['price_event'] for r in base] == ['調漲', '調降', '調漲', '初始售價']
    assert base[-1]['previous_price'] == base[-1]['price_change'] == '—'
    assert base[2]['previous_price'] == '100' and base[2]['price_change'] == '+0.125'
    assert base[1]['price_change'] == '-5.125'
    assert len(changes) == 7 and sum(r['price_event'] == '初始售價' for r in changes) == 4
    assert rows == before


def test_price_history_same_day_line_order_is_deterministic(config):
    row = product_transactions(config, 'P1')
    assert product_price_changes(row) == []
    shipment(config, '01')
    row = product_transactions(config, 'P1')[0]
    rows = [dict(row, line_number=i, price=p) for i, p in [(3, '11'), (1, '0'), (2, '11')]]
    changes = product_price_changes(rows)
    assert [(r['line_number'], r['price_event']) for r in changes] == [(2, '調漲'), (1, '初始售價')]
    assert changes[0]['previous_price'] == '0'


def test_price_tab_uses_earlier_baseline_and_shares_customer_filter(config, monkeypatch):
    shipment(config, '01', day='2026-09-01', price='100')
    shipment(config, '02', day='2026-10-01', price='100')
    shipment(config, '03', day='2026-10-02', price='120')
    shipment(config, '04', day='2026-10-03', price='120')
    shipment(config, '05', customer='C02', day='2026-10-04', price='150')
    import utils.product_transaction_ui as ui
    calls = []
    original = ui.product_transactions
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(ui, 'product_transactions', counted)
    app = history_app(config)
    app.date_input(key='product_history_start').set_value(date(2026, 10, 1))
    search(app, 'P1')
    assert not app.exception and [tab.label for tab in app.tabs] == ['交易明細', '售價異動']
    prices = app.tabs[1].dataframe[0].value
    assert prices['異動類型'].tolist() == ['初始售價', '調漲']
    assert prices.iloc[1]['原單價'] == '100' and prices.iloc[1]['漲跌'] == '+20'
    app.checkbox[0].check().run()
    assert set(app.tabs[1].dataframe[0].value['客戶編號']) == {'C01'}
    assert len(calls) == 1
    app.checkbox[0].uncheck().run()
    app.date_input(key='product_history_start').set_value(None)
    search(app, 'P1')
    assert sum(app.tabs[1].dataframe[0].value['異動類型'] == '初始售價') == 2
