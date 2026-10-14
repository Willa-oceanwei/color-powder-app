from pathlib import Path
from datetime import date
from uuid import uuid4

from streamlit.testing.v1 import AppTest
from test_receivable_report import config, shipment, receipt
from utils.receivable_report import monthly_receipt_summary
from utils.receipt_repository import save_receipt_batch, void_receipt_batch, update_receipt_amount
from utils.shipment_repository import get_shipment, void_shipment


def rows(config, as_of='2026-10-31', start='2026-10-01', end='2026-10-31'):
    return {r['customer_id']: r for r in monthly_receipt_summary(config, start, end, as_of)}


def test_customer_statuses_and_current_month_only(config):
    shipment(config, shipment_date='2026-09-30')
    first = shipment(config)
    receipt(config, first, amount=50)
    shipment(config, 'A02')
    third = shipment(config, 'A03')
    receipt(config, third, amount=210)
    result = rows(config)
    assert result['A01']['total'] == 210 and result['A01']['received'] == 50 and result['A01']['balance'] == 160
    assert result['A01']['status'] == '部分收款' and result['A01']['last_receipt'] == '2026-10-02'
    assert result['A02']['status'] == '尚未開始登錄'
    assert result['A03']['status'] == '已收齊'
    assert rows(config, start='2026-09-01', end='2026-09-30')['A01']['total'] == 0


def test_receipt_cutoff_edits_void_and_prepaid_are_not_double_counted(config):
    first = shipment(config)
    batch = save_receipt_batch(config, batch_id=str(uuid4()), customer_id='A01', receipt_date='2026-11-02',
                               amount=300, allocations=[dict(shipment_id=first['id'], shipment_version=first['version'], amount=210)],
                               tracking_start='2026-10-01')
    assert rows(config)['A01']['received'] == 0
    assert rows(config, as_of='2026-11-30')['A01']['received'] == 210
    void_receipt_batch(config, batch['id'], 'Wrong receipt')
    assert rows(config, as_of='2026-11-30')['A01']['received'] == 0
    current = get_shipment(config, first['id'])
    r = receipt(config, current, amount=50)
    update_receipt_amount(config, receipt_id=r['id'], shipment_version=get_shipment(config, first['id'])['version'], amount=70, reason='Corrected')
    assert rows(config)['A01']['received'] == 70


def test_cutoff_25_and_void_shipments(config):
    shipment(config, shipment_date='2026-10-25')
    shipment(config, shipment_date='2026-10-26')
    d = shipment(config, 'A02')
    void_shipment(config, d['id'], d['version'], 'Cancelled')
    assert rows(config, end='2026-10-25')['A01']['total'] == 210
    assert rows(config)['A01']['total'] == 420
    assert rows(config)['A02']['status'] == '本期無帳款'


def test_monthly_summary_tab_filters_customers(config):
    shipment(config)
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0,{root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receivable_statement
render_receivable_statement(DatabaseConfig(backend="sqlite",path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    assert '每月收款總覽' in [t.label for t in app.tabs]
    app.number_input(key='receipt_summary_year').set_value(2026).run()
    app.selectbox(key='receipt_summary_month').set_value(10).run()
    app.date_input(key='receipt_summary_as_of').set_value(date(2026, 10, 31)).run()
    app.text_input(key='receipt_summary_query').set_value('A01').run()
    assert not app.exception
    assert list(app.dataframe[-1].value['客戶編號']) == ['A01']

