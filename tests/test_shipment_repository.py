from copy import deepcopy
from decimal import Decimal

import pytest

from utils.customer_repository import CustomerInput, create_customer, update_customer
from utils.database import DatabaseConfig, connect, initialize_database, initialize_database_with_health
from utils.shipment_repository import (
    ShipmentError, blank_shipment, calculate, copy_shipment, get_shipment,
    list_shipments, printable_shipment, save_shipment, void_shipment,
    list_shipment_recipes, recent_shipment_price,
)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / 'shipments.db'
    initialize_database(path)
    config = DatabaseConfig(backend='sqlite', path=path)
    create_customer(config, CustomerInput('C01', '範例客戶'))
    return config


def document():
    result = blank_shipment()
    result.update(customer_id='C01', customer_name='範例客戶', recipient_id='R01', recipient_name='收貨方',
                  shipment_date='2026-10-01', account_date='2026-10-01')
    result['items'] = [dict(code='69570M', name='藍', quantity='50', unit='KG', price='260', order_number='O1', notes=''),
                       dict(code='69960M', name='白', quantity='100', unit='KG', price='241', order_number='O1', notes='')]
    return result


def test_customer_recipe_unit_price_history(config):
    from utils.recipe_repository import create_recipe
    create_recipe(config, {"配方編號": "69570M", "顏色": "藍", "客戶編號": "C01"})
    create_recipe(config, {"配方編號": "OTHER", "顏色": "白", "客戶編號": "C02"})
    assert [row['recipe_id'] for row in list_shipment_recipes(config, 'C01')] == ['69570M']
    first = save_shipment(config, document())
    args = dict(shipment_date='2026-10-07', tax_mode='外加')
    assert recent_shipment_price(config, 'C01', '69570m', 'kg', **args)['price'] == '260'
    assert recent_shipment_price(config, 'C02', '69570M', 'KG', **args) is None
    assert recent_shipment_price(config, 'C01', '69570M', '包', **args) is None
    assert recent_shipment_price(config, 'C01', '69570M', 'KG', shipment_date='2026-09-30', tax_mode='外加') is None
    assert recent_shipment_price(config, 'C01', '69570M', 'KG', shipment_date='2026-10-07', tax_mode='內含') is None
    second_doc = document()
    second_doc['shipment_date'] = '2026-10-02'
    second_doc['items'][0]['price'] = '0'
    second = save_shipment(config, second_doc)
    assert recent_shipment_price(config, 'C01', '69570M', 'KG', **args)['price'] == '0'
    assert recent_shipment_price(config, 'C01', '69570M', 'KG', exclude_id=second['id'], **args)['price'] == '260'
    void_shipment(config, second['id'], second['version'], 'test')
    assert recent_shipment_price(config, 'C01', '69570M', 'KG', **args)['shipment_number'] == first['shipment_number']


def test_reference_totals_and_half_up():
    d = document()
    assert calculate(d['items'], '外加', '5')['total_amount'] == '38955'
    assert calculate([dict(quantity='1', price='0.5')], '外加', '0')['net_amount'] == '1'
    assert calculate([dict(quantity='1', price='105')], '內含', '5')['tax_amount'] == '5'
    for mode in ('免稅', '零稅率'):
        assert calculate(d['items'], mode, '5')['tax_amount'] == '0'


@pytest.mark.parametrize('quantity,price,rate', [('0', '1', '5'), ('NaN', '1', '5'),
                        ('1', '-1', '5'), ('1', '1', '101'), ('1.0001', '1', '5')])
def test_reject_invalid_numbers(quantity, price, rate):
    with pytest.raises(ShipmentError):
        calculate([dict(quantity=quantity, price=price)], '外加', rate)


def test_roundtrip_filter_copy_and_historical_snapshot(config):
    d = document()
    d['shipment_number'] = '025619'
    d['number_mode'] = 'manual'
    saved = save_shipment(config, d)
    assert saved['shipment_number'] == '025619'
    assert saved['items'][0]['amount'] == '13000'
    assert 'source_reference' not in saved['items'][0]
    update_customer(config, CustomerInput('C01', '新名稱'))
    assert get_shipment(config, saved['id'])['customer_name'] == '範例客戶'
    assert len(list_shipments(config, query='69570M')) == 1
    assert not list_shipments(config, start='2026-10-02')
    copied = copy_shipment(saved)
    assert 'id' not in copied and copied['shipment_number'] == ''
    assert copied['invoice']['number'] == ''


def test_optimistic_conflict_does_not_replace_items(config):
    saved = save_shipment(config, document())
    stale = deepcopy(saved)
    saved['items'][0]['quantity'] = '60'
    updated = save_shipment(config, saved)
    with pytest.raises(ShipmentError, match='其他人修改'):
        save_shipment(config, stale)
    assert get_shipment(config, updated['id'])['items'][0]['quantity'] == '60'


def test_invoice_conflict_rolls_back_entire_update(config):
    first = document()
    first['invoice'].update(number='AB12345678', date='2026-10-01', amount='38955')
    save_shipment(config, first)
    second = save_shipment(config, document())
    second['items'][0]['quantity'] = '99'
    second['invoice'].update(number='AB12345678', date='2026-10-01')
    with pytest.raises(ShipmentError, match='其他出貨單'):
        save_shipment(config, second)
    actual = get_shipment(config, second['id'])
    assert actual['version'] == 1
    assert actual['items'][0]['quantity'] == '50'
    assert actual['invoice']['number'] == ''


def test_invoice_and_blank_invoice_amount(config):
    d = document()
    d['invoice']['number'] = 'AB12345678'
    with pytest.raises(ShipmentError, match='發票日期'):
        save_shipment(config, d)
    d['invoice'].update(date='2026-10-01', method='紙本', type='三聯式', amount='0')
    saved = save_shipment(config, d)
    assert saved['invoice']['amount'] == '0'
    assert saved['invoice']['method'] == '紙本'


def test_void_preserves_history_and_blocks_update(config):
    saved = save_shipment(config, document())
    with pytest.raises(ShipmentError, match='原因'):
        void_shipment(config, saved['id'], 1, '')
    void_shipment(config, saved['id'], 1, '誤建')
    assert not list_shipments(config)
    assert len(list_shipments(config, include_void=True)) == 1
    with pytest.raises(ShipmentError, match='已作廢'):
        save_shipment(config, saved)
    assert get_shipment(config, saved['id'])['items']


def test_upgrade_preserves_existing_data(config):
    with connect(config.path) as conn:
        for table in ('shipment_invoices', 'shipment_order_items', 'shipment_orders', 'shipment_number_sequences'):
            conn.execute(f'DROP TABLE {table}')
        conn.execute('DELETE FROM schema_migrations WHERE version=25')
        conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (22,'2026-10-01')")
    _, health = initialize_database_with_health(config)
    assert health.schema_version == 25
    assert health.schema_compatible
    with connect(config.path) as conn:
        assert conn.execute("SELECT name FROM customers WHERE customer_id='C01'").fetchone()[0] == '範例客戶'


def test_print_escapes_user_text(config):
    d = document()
    d['notes'] = '<script>alert(1)</script>'
    html = printable_shipment(save_shipment(config, d))
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '依據單號' not in html


def test_date_sequences_and_manual_numbers(config):
    d = document()
    d['shipment_date'] = '2026-10-07'
    first = save_shipment(config, d)
    assert first['shipment_number'] == '2610070001'
    assert save_shipment(config, d)['shipment_number'] == '2610070002'
    d.update(number_mode='manual', shipment_number='2610070009')
    save_shipment(config, d)
    d.update(number_mode='date', shipment_number='')
    assert save_shipment(config, d)['shipment_number'] == '2610070010'
    assert save_shipment(config, first)['shipment_number'] == '2610070001'
    first['number_mode'] = 'manual'
    first['shipment_number'] = '000123'
    first['version'] = 2
    assert save_shipment(config, first)['shipment_number'] == '000123'
    d['shipment_date'] = '2026-10-08'
    assert save_shipment(config, d)['shipment_number'] == '2610080001'


def test_manual_duplicate_and_empty_number(config):
    d = document()
    d.update(number_mode='manual', shipment_number='')
    with pytest.raises(ShipmentError, match='輸入出貨單號'):
        save_shipment(config, d)
    d['shipment_number'] = '000012'
    save_shipment(config, d)
    with pytest.raises(ShipmentError, match='已存在'):
        save_shipment(config, d)


def test_automatic_number_reservation_rolls_back(config):
    d = document()
    d['invoice'].update(number='X1', date='2026-10-01')
    save_shipment(config, d)
    with pytest.raises(ShipmentError):
        save_shipment(config, d)
    d['invoice']['number'] = ''
    assert save_shipment(config, d)['shipment_number'] == '2610010002'


def test_a5_price_free_print_and_pagination(config):
    d = document()
    d['items'][0]['price'] = '9876543'
    d['items'] *= 12
    saved = save_shipment(config, d)
    html = printable_shipment(saved, show_prices=False)
    assert 'size:A5 landscape' in html
    assert '佳味實業有限公司' in html
    assert '單價' not in html and '<span>合計' not in html and '<span>稅額' not in html
    assert '9876543' not in html
    assert saved['total_amount'] not in html
    assert html.count('class="sheet"') == 3
    assert html.count('69570M') == 12
    assert '簽收' in html and '採購單號' in html
