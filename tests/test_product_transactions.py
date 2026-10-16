from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.product_transaction_report import product_transactions
from utils.product_transaction_ui import taiwan_timestamp
from utils.shipment_repository import ShipmentError, blank_shipment, save_shipment, void_shipment


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'product-history.db')
    initialize_database(config.path)
    for code in ('C01', 'C02', 'C03'):
        create_customer(config, CustomerInput(code, '客戶' + code))
    return config


def shipment(config, number, customer='C01', day='2026-10-01', code='P1', count=1):
    doc = dict(blank_shipment(), shipment_number=number, number_mode='manual', customer_id=customer,
               customer_name='客戶' + customer, shipment_date=day)
    doc['items'] = [dict(code=code, name='歷史品名', quantity='1.125', unit='包', price='160',
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
