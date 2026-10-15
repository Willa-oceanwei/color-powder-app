import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils.customer_display import CustomerDisplay
from utils.customer_repository import (CustomerError, CustomerInput, create_customer,
                                       customer_display_name, get_customer, update_customer)
from utils.database import DatabaseConfig, connect, initialize_database
from utils.receivable_report import build_statements, render_statement_print, statement_pages
from utils.sheet_import import import_sheet_values
from utils.shipment_repository import blank_shipment, list_shipments, printable_shipment, save_shipment
from utils.sheet_export import sync_customer_outbox


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'names.db')
    initialize_database(config.path)
    return config


def test_migration_preserves_legal_name_and_legacy_updates(config):
    create_customer(config, CustomerInput('C01', '範例企業有限公司'))
    with connect(config.path) as conn:
        conn.execute('ALTER TABLE customers DROP COLUMN short_name')
    initialize_database(config.path)
    assert customer_display_name(get_customer(config, 'C01')) == '範例企業有限公司'
    update_customer(config, CustomerInput('C01', '範例企業有限公司', short_name=' 範例 '))
    customer = update_customer(config, CustomerInput('C01', '範例企業有限公司', notes='舊版更新'))
    assert customer['short_name'] == '範例'
    with connect(config.path) as conn:
        payload = json.loads(conn.execute('SELECT payload_json FROM sync_outbox ORDER BY id DESC LIMIT 1').fetchone()[0])
    assert payload['客戶名稱'] == '範例企業有限公司' and payload['客戶簡稱'] == '範例'
    assert customer_display_name(update_customer(config, CustomerInput('C01', customer['name'], short_name=''))) == customer['name']


def test_alias_collisions_and_presentation_preserve_identity(config):
    create_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例'))
    with pytest.raises(CustomerError):
        create_customer(config, CustomerInput('C02', '第二家公司', short_name='範例'))
    update_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例新稱'))
    display = CustomerDisplay(config)
    source = pd.DataFrame([{'客戶編號': 'C01', '客戶名稱': '範例', '數量': 12}], index=[8])
    shown = display.frame(source)
    assert shown.loc[8, '客戶名稱'] == '範例新稱'
    assert source.loc[8, '客戶名稱'] == '範例' and shown.loc[8, '數量'] == 12
    assert display.label('配方1 | 藍 | 範例企業有限公司') == '配方1 | 藍 | 範例新稱'
    assert display.name('未建檔客戶') == '未建檔客戶'
    styled = source.style.format({'數量': '{:,.0f}'})
    assert '範例新稱' in display.frame(styled).to_html()


def test_sheet_names_roundtrip_and_legacy_missing_short_name(config):
    values = [['客戶編號', '客戶名稱', '客戶簡稱'], ['C01', '範例企業有限公司', '範例']]
    assert not import_sheet_values('客戶名單', values, db_config=config).errors
    # A sheet missing the new optional short-name column must retain it.
    assert not import_sheet_values('客戶名單', [['客戶編號', '客戶名稱'], ['C01', '範例企業有限公司']], db_config=config).errors
    assert get_customer(config, 'C01')['short_name'] == '範例'
    assert not import_sheet_values('客戶名單', [['客戶編號', '客戶名稱', '客戶簡稱'], ['C01', '範例企業有限公司', '']], db_config=config).errors
    assert get_customer(config, 'C01')['short_name'] == ''


def test_external_documents_keep_full_names_and_amounts(config):
    create_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例'))
    document = blank_shipment()
    document.update(customer_id='C01', customer_name='範例', shipment_date='2026-10-01')
    document['items'] = [dict(code='P1', name='藍', quantity='2', unit='包', price='100', notes='', order_number='')]
    saved = save_shipment(config, document)
    assert saved['customer_name'] == '範例企業有限公司'
    assert '範例企業有限公司' in printable_shipment(saved)
    assert list_shipments(config, query='範例')[0]['id'] == saved['id']
    statements = build_statements(config, '2026-10-01', '2026-10-31')
    assert statements[0]['total'] == '210'
    for title in ('應收帳款明細表', '客戶交易明細表'):
        assert '範例企業有限公司' in render_statement_print(statement_pages(statements), title=title)


def test_summary_search_short_full_name_and_unpaid(config):
    create_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例'))
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.receivable_ui import render_monthly_receipt_summary
render_monthly_receipt_summary(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run()
    assert not app.exception
    assert app.dataframe[0].value['客戶簡稱'].tolist() == ['範例']
    for query in ('範例', '企業有限公司', 'C01'):
        app.text_input(key='receipt_summary_query').set_value(query).run()
        assert not app.exception and len(app.dataframe[0].value) == 1
    app.toggle(key='receipt_summary_unpaid').set_value(True).run()
    assert not app.exception and len(app.dataframe) == 0


@pytest.mark.parametrize('legacy', [True, False])
def test_export_preserves_legal_name_with_old_and_new_headers(config, legacy):
    create_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例'))
    headers = ['客戶編號', '客戶簡稱'] if legacy else ['客戶編號', '客戶名稱', '客戶簡稱']

    class Worksheet:
        def append_row(self, row, **kwargs):
            self.row = row

    sheet = Worksheet()
    result = sync_customer_outbox(sheet, [headers], db_config=config, dry_run=False)
    assert result.ok and result.written == 1
    row = dict(zip(headers, sheet.row))
    if legacy:
        assert row['客戶簡稱'] == '範例企業有限公司' and result.warnings
    else:
        assert row['客戶名稱'] == '範例企業有限公司' and row['客戶簡稱'] == '範例'


def test_dropdown_formats_only_the_label(config):
    create_customer(config, CustomerInput('C01', '範例企業有限公司', short_name='範例'))

    class Picker:
        def selectbox(self, label, options, **kwargs):
            assert kwargs['format_func'](options[0]) == 'C01 · 範例'
            return options[0]

    assert CustomerDisplay(config).selectbox(Picker(), '客戶', ['C01 · 範例企業有限公司']) == 'C01 · 範例企業有限公司'
