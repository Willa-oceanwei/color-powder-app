from copy import deepcopy
from io import BytesIO

from openpyxl import load_workbook

from utils.accounting_export import statement_excel, statement_pdf
from utils.receivable_report import statement_pages, render_statement_print
from utils.shipment_print import render_shipment_print


def statement():
    item = dict(code="C0757", name="藍", quantity="2", unit="桶", price="100", amount="200",
                order_number="PO-20261001", notes="Not a purchase order")
    return dict(customer_id="C1", customer_name="測試客戶", contact="王先生", phone="06-1234567", fax="06-7654321",
                tax_id="12345678", start="2026-10-01", end="2026-10-31", quantities={"桶": "2"},
                net="200", tax="10", total="210", received="0", balance="210",
                documents=[dict(date="2026-10-01", number="S1", items=[item])])


def test_a4_driver_shared_feed_preserves_data_and_blanks_prices():
    s = statement()
    doc = dict(customer_id=s["customer_id"], customer_name=s["customer_name"], shipment_number="S1",
               shipment_date="2026-10-01", items=s["documents"][0]["items"], net_amount="200", tax_amount="10", total_amount="210")
    before = deepcopy(doc)
    html = render_shipment_print(doc, paper_stock="a4_driver", feed_rotation=90, hole_margin=12.5, show_prices=False)
    assert 'size:A4 portrait' in html and 'width:210mm;height:297mm;' in html
    assert 'rotate(0deg)' in html and 'width:240mm;height:140mm' in html
    assert '<th class="price">單價</th>' in html and '<th class="amount">金額</th>' in html
    assert '<td class="price"></td>' in html and '<td class="amount"></td>' in html
    assert '<span>合計' not in html and doc == before


def test_a4_statement_headers_alignment_company_and_purchase_order():
    s = statement()
    before = deepcopy(s)
    pages = statement_pages([s], paper_size="A4")
    html = render_statement_print(pages, paper_stock="a4_driver", title="客戶交易明細")
    assert 'width:240mm;height:280mm' in html and 'size:A4 portrait' in html
    assert '<th>採購單號</th>' in html and 'PO-20261001' in html and 'Not a purchase order' not in html
    assert 'font-size:12pt' in html and 'table{font-size:11pt}' in html
    assert 'th:nth-child(6),th:nth-child(8),th:nth-child(9){text-align:right}' in html
    assert '<footer>' not in html and 'class="company-info"' in html
    assert '.company-info{margin-top:5.8mm' in html
    pdf = statement_pdf(pages, paper_stock="a4_driver", title="客戶交易明細")
    assert b'595.2756 841.8898' in pdf
    assert s == before


def test_statement_excel_print_sheet_keeps_company_and_safe_text():
    s = statement()
    s["documents"][0]["items"][0]["name"] = '=HYPERLINK("danger")'
    book = load_workbook(BytesIO(statement_excel([s], title="客戶交易明細")))
    sheet = book["列印版"]
    assert book.active.title == "列印版"
    assert sheet['A1'].value == "佳咊實業有限公司" and sheet['A2'].value == "客戶交易明細"
    assert sheet['A4'].value == "客戶名稱：C1　測試客戶"
    assert sheet['J8'].value == "採購單號" and sheet['J10'].value == "PO-20261001"
    assert sheet['E10'].value.startswith('=HYPERLINK') and sheet['E10'].data_type == 's'
    assert sheet['A14'].value == "台南市永康區中正南路309號"
    assert sheet['F12'].value == 2 and sheet['I13'].value == 200
    assert str(sheet.page_setup.paperSize) == sheet.PAPERSIZE_A4
    assert sheet.page_setup.fitToWidth == 1
    assert book['交易明細']['L2'].value == 'PO-20261001'
