from copy import deepcopy

import pytest

from utils.print_stock import stock_geometry
from utils.shipment_print import render_shipment_print
from utils.receivable_report import statement_pages, render_statement_print
from utils.accounting_export import statement_pdf


def document():
    return dict(customer_id="C1", customer_name="客戶", shipment_date="2026-10-01", shipment_number="S1",
                net_amount="200", tax_amount="10", total_amount="210", items=[
                    dict(code="C0757", name="藍", quantity="2", unit="桶", price="100", amount="200")])


def statements():
    return [dict(customer_id="C1", customer_name="客戶", start="2026-10-01", end="2026-10-31",
                 net="200", tax="10", total="210", quantities={"桶": "2"}, received="0", balance="210",
                 documents=[dict(date="2026-10-01", number="S1", items=document()["items"] * 12)])]


@pytest.mark.parametrize("rotation,size", [(0, (240, 140)), (90, (140, 240))])
def test_triplicate_geometry_and_shipment_do_not_mutate(rotation, size):
    width, height, x, y, scale = stock_geometry(rotation, 12.5)
    assert (width, height) == size
    assert scale > .9
    # Hole strips rotate with the physical stock, not with the report columns.
    if rotation == 0:
        assert x >= 12.5 and x + 210 * scale <= 240 - 12.5
        assert y >= 0 and y + 148 * scale <= 140
    else:
        assert y >= 12.5 and y + 210 * scale <= 240 - 12.5
        assert x - 148 * scale >= 0 and x <= 140
    doc = document()
    before = deepcopy(doc)
    html = render_shipment_print(doc, paper_stock="triplicate", feed_rotation=rotation, hole_margin=12.5)
    assert f"size:{width}mm {height}mm" in html
    assert f"rotate({rotation}deg)" in html
    assert '列印三聯紙' in html and 'querySelector(\'.stock-page\')' in html
    assert 'transform-origin:0 0' in html and 'zoom:1!important' in html
    assert doc == before


@pytest.mark.parametrize("rotation,dimensions", [(0, b"680.315 396.8504"), (90, b"396.8504 680.315")])
@pytest.mark.parametrize("title", ["應收帳款明細表", "客戶交易明細"])
def test_triplicate_statement_html_pdf_pagination_and_totals(rotation, dimensions, title):
    source = statements()
    before = deepcopy(source)
    pages = statement_pages(source, paper_size="A5")
    assert len(pages) > 1 and all(len(p["rows"]) <= 10 for p in pages)
    settings = dict(paper_stock="triplicate", feed_rotation=rotation, hole_margin=12.5)
    html = render_statement_print(pages, selected=1, title=title, **settings)
    assert html.count('class="stock-page') == len(pages)
    assert html.count('class="stock-page active"') == 1
    assert "querySelectorAll('.stock-page')" in html
    assert html.count("本期總計") == 1 and f"<h2>{title}</h2>" in html
    assert '.stock-page>.sheet' in html and 'page:auto!important' in html
    pdf = statement_pdf(pages, title=title, **settings)
    assert dimensions in pdf
    assert source == before


def test_invalid_stock_and_a4_not_silently_shrunk():
    for rotation, margin in ((45, 12.5), (0, -1), (90, 26)):
        with pytest.raises(ValueError):
            stock_geometry(rotation, margin)
    pages = statement_pages(statements(), paper_size="A4")
    for renderer in (render_statement_print, statement_pdf):
        with pytest.raises(ValueError, match="pagination"):
            renderer(pages, paper_stock="triplicate")
    with pytest.raises(ValueError, match="stock"):
        render_shipment_print(document(), paper_stock="unknown")
