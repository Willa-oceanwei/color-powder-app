from pathlib import Path
from datetime import date
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from test_receivable_report import config, shipment, receipt
from utils.database import connect, initialize_database, database_health_check
from utils.receipt_repository import (save_receipt_batch, list_receipt_batches, receipt_batch_details,
                                      outstanding_shipments, apply_prepaid_batch, void_receipt_batch, void_receipt,
                                      receipt_tracking_start)
from utils.receivable_report import build_statements
from utils.shipment_repository import ShipmentError, get_shipment


def allocation(d, amount):
    return dict(shipment_id=d['id'], shipment_version=d['version'], amount=amount)


def save_batch(config, allocations, amount=300, token=None):
    return save_receipt_batch(config, batch_id=token or str(uuid4()), customer_id='A01',
                              receipt_date='2026-10-31', amount=amount, allocations=allocations,
                              reference='BANK-123', notes='Monthly receipt')


def test_batch_partial_idempotent_and_whole_void(config):
    first, second = shipment(config), shipment(config)
    allocations = [allocation(first, 210), allocation(second, 90)]
    token = str(uuid4())
    batch = save_batch(config, allocations, token=token)
    assert save_batch(config, allocations, token=token)['id'] == batch['id']
    assert len(receipt_batch_details(config, batch['id'])) == 2
    assert [r['balance'] for r in outstanding_shipments(config, 'A01')] == [120]
    assert list_receipt_batches(config, 'A01')[0]['allocated'] == 300
    assert build_statements(config, '2026-10-01', '2026-10-31')[0]['received'] == '300'
    assert build_statements(config, '2026-10-01', '2026-10-30')[0]['received'] == '0'
    with pytest.raises(ShipmentError):
        save_batch(config, allocations, amount=301, token=token)
    with pytest.raises(ShipmentError, match='批次'):
        void_receipt(config, receipt_batch_details(config, batch['id'])[0]['id'], 'Wrong entry')
    void_receipt_batch(config, batch['id'], 'Wrong bank receipt')
    assert len(outstanding_shipments(config, 'A01')) == 2
    assert build_statements(config, '2026-10-01', '2026-10-31')[0]['received'] == '0'
    assert all(r['status'] == 'void' for r in receipt_batch_details(config, batch['id']))


@pytest.mark.parametrize('invalid', ['other_customer', 'stale', 'overpaid', 'future'])
def test_batch_failure_rolls_back_all_allocations(config, invalid):
    first = shipment(config)
    second = shipment(config, customer='A02' if invalid == 'other_customer' else 'A01',
                      shipment_date='2026-11-01' if invalid == 'future' else '2026-10-01')
    if invalid == 'stale':
        receipt(config, second)
    rows = [allocation(first, 50), allocation(second, 211 if invalid == 'overpaid' else 50)]
    token = str(uuid4())
    with pytest.raises(ShipmentError):
        save_batch(config, rows, amount=400, token=token)
    assert get_shipment(config, first['id'])['version'] == first['version']
    assert not list_receipt_batches(config, 'A01')
    with connect(config.path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM receipt_batch_allocations').fetchone()[0] == 0


@pytest.mark.parametrize('amount,rows_kind', [(0, 'valid'), (100, 'sum'), (300, 'duplicate'), (300, 'fraction'), (300, 'negative')])
def test_invalid_batch_amounts(config, amount, rows_kind):
    d = shipment(config)
    rows = [allocation(d, 101 if rows_kind == 'sum' else 0.5 if rows_kind == 'fraction' else -1 if rows_kind == 'negative' else 50)]
    if rows_kind == 'duplicate':
        rows.append(allocation(d, 50))
    with pytest.raises(ShipmentError):
        save_batch(config, rows, amount=amount)
    assert not list_receipt_batches(config, 'A01')


def test_prepaid_can_be_used_later_without_counting_money_twice(config):
    first = shipment(config)
    batch = save_batch(config, [allocation(first, 210)], amount=300)
    second = shipment(config, shipment_date='2026-11-01')
    request = dict(batch_id=batch['id'], batch_version=1, request_id=str(uuid4()),
                   allocation_date='2026-11-02', allocations=[allocation(second, 90)])
    apply_prepaid_batch(config, **request)
    apply_prepaid_batch(config, **request)
    assert list_receipt_batches(config, 'A01')[0]['allocated'] == 300
    assert len(receipt_batch_details(config, batch['id'])) == 2
    assert build_statements(config, '2026-11-01', '2026-11-30')[0]['received'] == '90'
    with pytest.raises(ShipmentError):
        apply_prepaid_batch(config, batch_id=batch['id'], batch_version=2, request_id=str(uuid4()),
                            allocation_date='2026-11-02', allocations=[allocation(get_shipment(config, second['id']), 1)])
    void_receipt_batch(config, batch['id'], 'Cancelled receipt')
    assert [r['balance'] for r in outstanding_shipments(config, 'A01')] == [210, 210]


def test_schema_27_upgrade_preserves_single_receipts(config):
    d = shipment(config)
    receipt(config, d)
    with connect(config.path) as conn:
        conn.execute('DROP TABLE receipt_batch_allocations')
        conn.execute('DROP TABLE receipt_batches')
        conn.execute('DELETE FROM schema_migrations WHERE version=28')
        conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (27,'old')")
    initialize_database(config.path)
    assert database_health_check(config).schema_version == 31
    assert outstanding_shipments(config, 'A01')[0]['balance'] == 160


def test_batch_entry_ui_saves_and_resets_amount(config):
    shipment(config)
    shipment(config)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receipt_entry
render_receipt_entry(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.radio(key='receipt_mode').set_value('月結／批次收款').run()
    assert not app.exception
    next(w for w in app.number_input if w.label == '本次收款金額').set_value(300).run()
    next(w for w in app.button if w.label == '登錄批次收款').click().run()
    assert not app.exception, [e.message for e in app.exception]
    batches = list_receipt_batches(config, 'A01')
    assert len(batches) == 1 and batches[0]['allocated'] == 300
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 0
    next(w for w in app.number_input if w.label == '修改收款總額').set_value(350)
    next(w for w in app.text_input if w.label == '修改原因').set_value('Wrong total')
    next(w for w in app.button if w.label == '儲存收款修改').click().run()
    assert not app.exception, [e.message for e in app.exception]
    updated = list_receipt_batches(config, 'A01')[0]
    assert updated['amount'] == '350' and updated['allocated'] == 300


@pytest.mark.parametrize('year,month,closing,last', [(2026, 10, 25, 25), (2026, 10, 31, 31),
                                                   (2026, 2, 31, 28), (2028, 2, 31, 29), (2026, 4, 31, 30)])
def test_month_period_handles_closing_day_and_short_months(year, month, closing, last):
    from utils.receivable_ui import month_receipt_period
    start, end = month_receipt_period(year, month, closing)
    assert start.day == 1 and end.day == last and start.month == end.month == month


def test_month_totals_cutoff_custom_range_and_prior_balance_ui(config):
    shipment(config, shipment_date='2026-09-30')
    shipment(config, shipment_date='2026-10-01')
    shipment(config, shipment_date='2026-10-26')
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receipt_entry
render_receipt_entry(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.radio(key='receipt_mode').set_value('月結／批次收款').run()
    next(w for w in app.number_input if w.label == '年度').set_value(2026).run()
    next(w for w in app.selectbox if w.label == '月份').set_value(10).run()
    next(w for w in app.date_input if w.label == '收款日期').set_value(date(2026, 10, 31)).run()
    next(w for w in app.radio if w.label == '結帳日').set_value('25 號').run()
    assert next(w for w in app.metric if w.label == '本期應收總額').value == '210'
    assert not next(w for w in app.toggle if w.label == '包含前期未收').value
    assert next(w for w in app.metric if w.label == '前期未收金額').value == '未納入'
    next(w for w in app.button if w.label == '全額收款').click().run()
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 210
    next(w for w in app.toggle if w.label == '包含前期未收').set_value(True).run()
    next(w for w in app.button if w.label == '全額收款').click().run()
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 210
    assert next(w for w in app.metric if w.label == '前期未收金額').value == '0'
    next(w for w in app.toggle if w.label == '包含前期未收').set_value(False).run()
    next(w for w in app.button if w.label == '全額收款').click().run()
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 210
    next(w for w in app.radio if w.label == '結帳日').set_value('31 號／月底').run()
    assert next(w for w in app.metric if w.label == '本期應收總額').value == '420'
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 0
    next(w for w in app.radio if w.label == '帳款期間').set_value('自訂日期').run()
    next(w for w in app.date_input if w.label == '帳款起日').set_value(date(2026, 10, 26)).run()
    next(w for w in app.date_input if w.label == '帳款迄日').set_value(date(2026, 10, 31)).run()
    assert not app.exception
    assert next(w for w in app.metric if w.label == '本期應收總額').value == '210'


def test_tracking_starts_with_first_recorded_period_and_survives_void(config):
    old = shipment(config, shipment_date='2026-09-30')
    october = shipment(config, shipment_date='2026-10-01')
    assert receipt_tracking_start(config, 'A01') is None
    batch = save_receipt_batch(config, batch_id=str(uuid4()), customer_id='A01', receipt_date='2026-11-05',
                               amount=50, allocations=[allocation(october, 50)], tracking_start='2026-10-01')
    assert receipt_tracking_start(config, 'A01') == '2026-10-01'
    with pytest.raises(ShipmentError, match='起算日'):
        save_receipt_batch(config, batch_id=str(uuid4()), customer_id='A01', receipt_date='2026-11-05',
                           amount=10, allocations=[allocation(old, 10)], tracking_start='2026-09-01')
    void_receipt_batch(config, batch['id'], 'Cancelled')
    assert receipt_tracking_start(config, 'A01') == '2026-10-01'
    assert receipt_tracking_start(config, 'A02') is None


def test_next_month_only_carries_unpaid_since_tracking_start(config):
    shipment(config, shipment_date='2026-09-30')
    october = shipment(config, shipment_date='2026-10-01')
    save_receipt_batch(config, batch_id=str(uuid4()), customer_id='A01', receipt_date='2026-10-31',
                       amount=50, allocations=[allocation(october, 50)], tracking_start='2026-10-01')
    shipment(config, shipment_date='2026-11-01')
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receipt_entry
render_receipt_entry(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.radio(key='receipt_mode').set_value('月結／批次收款').run()
    next(w for w in app.number_input if w.label == '年度').set_value(2026).run()
    next(w for w in app.selectbox if w.label == '月份').set_value(11).run()
    next(w for w in app.date_input if w.label == '收款日期').set_value(date(2026, 11, 30)).run()
    next(w for w in app.toggle if w.label == '包含前期未收').set_value(True).run()
    assert next(w for w in app.metric if w.label == '前期未收金額').value == '160'
    next(w for w in app.button if w.label == '全額收款').click().run()
    assert not app.exception
    assert next(w for w in app.number_input if w.label == '本次收款金額').value == 370

