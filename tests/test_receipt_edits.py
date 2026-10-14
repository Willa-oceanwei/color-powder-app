from uuid import uuid4
import pytest
from test_receivable_report import config, shipment, receipt
from utils.receipt_repository import (update_receipt_amount, update_receipt_batch_amounts, receipt_changes,
                                      save_receipt_batch, receipt_batch_details, list_receipt_batches, outstanding_shipments,
                                      void_receipt_batch)
from utils.shipment_repository import get_shipment, ShipmentError


def test_single_edit_updates_balance_logs_and_rejects_stale_and_overpaid(config):
    d = shipment(config)
    r = receipt(config, d, amount=50)
    version = get_shipment(config, d['id'])['version']
    update_receipt_amount(config, receipt_id=r['id'], shipment_version=version, amount=80, reason='Wrong amount')
    assert outstanding_shipments(config, 'A01')[0]['balance'] == 130
    assert len(receipt_changes(config, r['id'])) == 1
    with pytest.raises(ShipmentError):
        update_receipt_amount(config, receipt_id=r['id'], shipment_version=version, amount=90, reason='Stale')
    version = get_shipment(config, d['id'])['version']
    with pytest.raises(ShipmentError):
        update_receipt_amount(config, receipt_id=r['id'], shipment_version=version, amount=211, reason='Overpaid')
    with pytest.raises(ShipmentError):
        update_receipt_amount(config, receipt_id=r['id'], shipment_version=version, amount=20, reason='')
    assert outstanding_shipments(config, 'A01')[0]['balance'] == 130
    assert len(receipt_changes(config, r['id'])) == 1


def setup_batch(config):
    first, second = shipment(config), shipment(config)
    b = save_receipt_batch(config, batch_id=str(uuid4()), customer_id='A01', receipt_date='2026-10-31', amount=300,
                           allocations=[dict(shipment_id=d['id'], shipment_version=d['version'], amount=a)
                                        for d, a in [(first, 210), (second, 90)]])
    return b, receipt_batch_details(config, b['id'])


def edits(details, amounts):
    return [dict(receipt_id=r['id'], shipment_version=r['shipment_version'], amount=amount)
            for r, amount in zip(details, amounts)]


def test_batch_edit_reduces_allocations_and_void_restores_balances(config):
    batch, details = setup_batch(config)
    update_receipt_batch_amounts(config, batch_id=batch['id'], batch_version=1, amount=200,
                                 allocations=edits(details, [150, 50]), reason='Mistyped total')
    b = list_receipt_batches(config, 'A01')[0]
    assert b['amount'] == '200' and b['allocated'] == 200 and b['version'] == 2
    assert sum(d['balance'] for d in outstanding_shipments(config, 'A01')) == 220
    assert len(receipt_changes(config, batch['id'])) == 1
    void_receipt_batch(config, batch['id'], 'Cancel')
    assert sum(d['balance'] for d in outstanding_shipments(config, 'A01')) == 420


@pytest.mark.parametrize('amount,amounts,reason', [(200, [210, 90], 'Sum'), (400, [211, 90], 'Overpaid'), (200, [150, 50], '')])
def test_batch_edit_failures_roll_back_everything(config, amount, amounts, reason):
    batch, details = setup_batch(config)
    with pytest.raises(ShipmentError):
        update_receipt_batch_amounts(config, batch_id=batch['id'], batch_version=1, amount=amount,
                                     allocations=edits(details, amounts), reason=reason)
    b = list_receipt_batches(config, 'A01')[0]
    assert b['amount'] == '300' and b['allocated'] == 300 and b['version'] == 1
    assert not receipt_changes(config, batch['id'])
    assert all(get_shipment(config, d['shipment_id'])['version'] == d['shipment_version'] for d in details)


def test_batch_edit_rejects_stale_and_single_child_edits(config):
    batch, details = setup_batch(config)
    with pytest.raises(ShipmentError):
        update_receipt_amount(config, receipt_id=details[0]['id'], shipment_version=details[0]['shipment_version'], amount=1, reason='Child')
    d = get_shipment(config, details[1]['shipment_id'])
    receipt(config, d, amount=1)
    with pytest.raises(ShipmentError):
        update_receipt_batch_amounts(config, batch_id=batch['id'], batch_version=1, amount=200,
                                     allocations=edits(details, [150, 50]), reason='Stale')
    assert list_receipt_batches(config, 'A01')[0]['version'] == 1


def test_receipt_edit_history_renders_without_nested_expanders(config):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    document = shipment(config)
    received = receipt(config, document, amount=50)
    version = get_shipment(config, document['id'])['version']
    update_receipt_amount(config, receipt_id=received['id'], shipment_version=version, amount=80, reason='Correction')
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_receipt_entry
render_receipt_entry(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    assert app.selectbox(key='receipt_customer').value == 'A01'
    assert app.selectbox(key='receipt_shipment').value == document['id']
    assert any(expander.label == '收款修改紀錄' for expander in app.expander)

