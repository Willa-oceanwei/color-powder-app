from copy import deepcopy

import pytest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect, initialize_database, initialize_database_with_health
from utils.product_repository import (
    ProductError, blank_product, get_product, list_products, save_product, set_product_active, shipment_products,
)
from utils.recipe_repository import create_recipe, update_recipe
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "products.db"
    initialize_database(path)
    return DatabaseConfig(backend="sqlite", path=path)


def product(**updates):
    data = blank_product()
    data.update(product_id="68146AM", name="特濃白", specification="25 KG / 包", inner_unit="包",
                inner_quantity="25", outer_unit="箱", outer_quantity="4", standard_price="260.125",
                standard_cost="100", price_a="250")
    data.update(updates)
    return data


def test_product_crud_prices_and_optimistic_lock(config):
    saved = save_product(config, product(product_id="68146am"))
    assert saved['product_id'] == '68146AM'
    assert saved['standard_price'] == '260.125'
    assert saved['inner_quantity'] == '25'
    stale = deepcopy(saved)
    saved['name'] = '新名稱'
    saved['standard_price'] = '280'
    updated = save_product(config, saved)
    assert updated['version'] == 2
    with pytest.raises(ProductError, match='其他人修改'):
        save_product(config, stale)
    with pytest.raises(ProductError, match='已存在'):
        save_product(config, product())
    with pytest.raises(ProductError, match='刪除原因'):
        set_product_active(config, updated['product_id'], 2, active=False)
    removed = set_product_active(config, updated['product_id'], 2, active=False, reason='停止販售')
    assert not list_products(config)
    assert list_products(config, include_inactive=True)[0]['lifecycle_status'] == 'inactive'
    with pytest.raises(ProductError, match='先恢復'):
        save_product(config, removed)
    restored = set_product_active(config, removed['product_id'], removed['version'], active=True)
    assert restored['delete_reason'] == ''
    assert list_products(config, query='25 KG')[0]['name'] == '新名稱'
    assert get_product(config, restored['product_id'])['standard_price'] == '280'


@pytest.mark.parametrize('updates', [dict(product_id=''), dict(name=''), dict(sales_unit=''),
                                    dict(base_unit=''), dict(standard_price='-1'), dict(price_e='NaN'),
                                    dict(inner_quantity='1.0001'), dict(inner_unit=''),
                                    dict(recipe_id='missing'), dict(supplier_id='missing')])
def test_product_invalid_data(config, updates):
    with pytest.raises(ProductError):
        save_product(config, product(**updates))
    assert not list_products(config)


def test_recipe_filter_and_rename_preserve_product_code(config):
    create_recipe(config, {'配方編號': 'R1', '顏色': '白', '客戶編號': 'C01'})
    save_product(config, product(recipe_id='R1'))
    save_product(config, product(product_id='SHARED', name='共用貨品'))
    assert len(shipment_products(config, 'C01')) == 2
    assert [row['product_id'] for row in shipment_products(config, 'C02')] == ['SHARED']
    update_recipe(config, {'配方編號': 'R2', '顏色': '白', '客戶編號': 'C01'}, original_recipe_id='R1')
    assert get_product(config, '68146AM')['recipe_id'] == 'R2'
    with connect(config.path) as conn:
        conn.execute("UPDATE recipes SET lifecycle_status='inactive' WHERE recipe_id='R2'")
    assert [row['product_id'] for row in shipment_products(config, 'C01')] == ['SHARED']


def test_product_changes_and_deletion_do_not_modify_shipment(config):
    saved = save_product(config, product())
    create_customer(config, CustomerInput('C01', '客戶'))
    shipment = blank_shipment()
    shipment.update(customer_id='C01', customer_name='客戶')
    shipment['items'] = [dict(code=saved['product_id'], name=saved['name'], quantity='1', unit='KG',
                              price=saved['standard_price'], notes=saved['specification'])]
    historical = save_shipment(config, shipment)
    saved['name'] = '新名稱'
    saved['standard_price'] = '999'
    updated = save_product(config, saved)
    set_product_active(config, updated['product_id'], updated['version'], active=False, reason='停用')
    assert get_shipment(config, historical['id'])['items'][0]['price'] == '260.125'
    assert get_shipment(config, historical['id'])['items'][0]['name'] == '特濃白'


def test_schema_25_upgrade_keeps_recipe_and_shipment(config):
    create_recipe(config, {'配方編號': 'R1', '顏色': '白'})
    with connect(config.path) as conn:
        conn.execute('DROP TABLE products')
        conn.execute('DELETE FROM schema_migrations WHERE version=25')
        conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (24,'2026-10-07')")
    _, health = initialize_database_with_health(config)
    assert health.schema_version == 25
    assert health.schema_compatible
    save_product(config, product(recipe_id='R1'))

