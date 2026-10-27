from copy import deepcopy
from datetime import date

import pytest

from utils.advance_price_repository import (
    AdvancePriceError, applicable_price, cancel_advance_price, list_advance_prices,
    reminder_status, reprice_for_context, save_advance_price,
)
from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, database_health_check, initialize_database
from utils.product_repository import blank_product, save_product
from utils.shipment_catalog import complete_items, item_price
from utils.shipment_repository import (
    ShipmentError, blank_shipment, copy_shipment, get_shipment, list_shipments,
    save_shipment, void_shipment,
)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / 'advance.db'
    initialize_database(path)
    config = DatabaseConfig(backend='sqlite', path=path)
    for code in ('C1', 'C2'):
        create_customer(config, CustomerInput(code, 'Customer ' + code))
    save_product(config, dict(blank_product(), product_id='P1', name='Red', standard_price='100'))
    return config


def quote(config, **fields):
    return save_advance_price(config, dict(customer_id='C1', code='P1', name='Red', unit='KG',
                                         tax_mode='外加', price='110', effective_date='2026-11-01', **fields))


def document(when='2026-11-01', price='110'):
    doc = dict(blank_shipment(), customer_id='C1', customer_name='Customer C1',
               shipment_date=when, account_date=when)
    doc['items'] = [dict(code='P1', name='Red', quantity='20', unit='KG', price=price)]
    return doc


def test_effective_boundary_and_scope(config):
    q = quote(config)
    rows = list_advance_prices(config)
    assert applicable_price(rows, 'C1', 'p1', 'kg', '外加', '2026-10-31') is None
    assert applicable_price(rows, 'C1', 'p1', 'kg', '外加', '2026-11-01')['id'] == q['id']
    for customer, code, unit, tax in [('C2','P1','KG','外加'), ('C1','P2','KG','外加'),
                                      ('C1','P1','包','外加'), ('C1','P1','KG','免稅')]:
        assert applicable_price(rows, customer, code, unit, tax, '2027-01-01') is None
    assert database_health_check(config).schema_compatible


def test_price_priority_and_typed_items(config):
    from utils.shipment_catalog import shipment_choices
    quote(config)
    choices = shipment_choices(config, 'C1')
    doc = document('2026-10-31', '100')
    assert item_price(config, doc, 'P1', 'KG', choices['P1'], history=[]) == '100'
    doc['shipment_date'] = '2026-11-01'
    assert item_price(config, doc, 'P1', 'KG', choices['P1'], history=[]) == '110'
    row = dict(code='P1', name='', unit='', price='', quantity='2')
    completed = complete_items(config, doc, [row], [], choices=choices, history=[])
    assert completed[0]['price'] == '110'


def test_later_quote_supersedes_and_cancellation_restores_previous(config):
    first = quote(config)
    second = save_advance_price(config, dict(first, id='', effective_date='2026-12-01', price='120'))
    rows = list_advance_prices(config)
    assert reminder_status(first, rows, '2026-11-30') == '已生效未出貨'
    assert reminder_status(first, rows, '2026-12-01') == '已被後續報價取代'
    cancel_advance_price(config, second['id'], second['version'], '延期')
    rows = list_advance_prices(config)
    assert applicable_price(rows, 'C1', 'P1', 'KG', '外加', '2026-12-01')['id'] == first['id']


def test_reminder_clears_only_on_saved_matching_price_and_returns_after_void(config):
    q = quote(config)
    assert reminder_status(q, [q], '2026-10-31') == '待生效'
    with pytest.raises(ShipmentError, match='特殊議價'):
        save_shipment(config, document(price='100'))
    assert not list_shipments(config)
    doc = document(price='100')
    doc['items'][0]['advance_price_override_reason'] = '本次特別議價'
    saved_override = save_shipment(config, doc)
    assert saved_override['items'][0]['advance_price_override_reason'] == '本次特別議價'
    assert not list_advance_prices(config)[0]['used']
    with pytest.raises(AdvancePriceError, match='不可改寫'):
        save_advance_price(config, dict(q, price='120'))
    saved = save_shipment(config, document())
    assert saved['items'][0]['advance_price_id'] == q['id']
    rows = list_advance_prices(config)
    assert reminder_status(rows[0], rows, '2026-11-01') == '已套用'
    void_shipment(config, saved['id'], saved['version'], '取消')
    rows = list_advance_prices(config)
    assert reminder_status(rows[0], rows, '2026-11-01') == '已生效未出貨'


def test_existing_historical_price_survives_new_quote_and_quantity_edit(config):
    saved = save_shipment(config, document(price='100'))
    before = get_shipment(config, saved['id'])
    quote(config)
    assert get_shipment(config, saved['id']) == before
    saved['items'][0]['quantity'] = '25'
    edit = save_shipment(config, saved)
    assert edit['items'][0]['price'] == '100' and edit['items'][0]['amount'] == '2500'
    copied = copy_shipment(edit)
    with pytest.raises(ShipmentError, match='特殊議價'):
        save_shipment(config, copied)


def test_context_reprice_copied_and_date_change_without_affecting_unquoted_items(config):
    from utils.shipment_catalog import shipment_choices
    quote(config)
    doc = document(price='100')
    choices = shipment_choices(config, 'C1')
    rows = list_advance_prices(config)
    items = reprice_for_context(config, doc, doc['items'], None, rows, choices, [])
    assert items[0]['price'] == '110'
    doc['shipment_date'] = '2026-10-31'
    items = reprice_for_context(config, doc, items, ('C1','2026-11-01','外加'), rows, choices, [])
    assert items[0]['price'] == '100'
    manual = [dict(doc['items'][0], code='UNKNOWN', price='999')]
    assert reprice_for_context(config, doc, manual, ('C1','2026-11-01','外加'), rows, choices, []) == manual
    doc['id'] = 'existing'
    assert reprice_for_context(config, doc, doc['items'], None, rows, choices, []) == doc['items']


def test_duplicate_optimistic_edit_and_used_immutability(config):
    q = quote(config)
    with pytest.raises(AdvancePriceError, match='已有'):
        quote(config)
    updated = save_advance_price(config, dict(q, price='111'))
    with pytest.raises(AdvancePriceError, match='重新讀取'):
        save_advance_price(config, dict(q, price='112'))
    save_shipment(config, document(price='111'))
    with pytest.raises(AdvancePriceError, match='不可改寫'):
        save_advance_price(config, dict(updated, price='112'))
    with pytest.raises(AdvancePriceError, match='原因'):
        cancel_advance_price(config, updated['id'], updated['version'], '')


@pytest.mark.parametrize('price', ['NaN','Infinity','-1','1.0001','abc'])
def test_reject_invalid_prices(config, price):
    with pytest.raises(AdvancePriceError):
        save_advance_price(config, dict(customer_id='C1',code='P1',name='Red',unit='KG',tax_mode='外加',
                                      price=price,effective_date='2026-11-01'))


def test_repository_rechecks_quote_changed_since_draft(config):
    q = quote(config)
    doc = document()
    save_advance_price(config, dict(q, price='120'))
    with pytest.raises(ShipmentError, match='120'):
        save_shipment(config, doc)
    assert not list_shipments(config)


def test_unit_and_tax_mismatch_do_not_block_shipment(config):
    quote(config)
    doc = document(price='12')
    doc['items'][0]['unit'] = '包'
    assert save_shipment(config, doc)['items'][0]['price'] == '12'
    doc['items'][0].update(unit='KG', tax_exempt=True)
    assert save_shipment(config, doc)['items'][0]['price'] == '12'
