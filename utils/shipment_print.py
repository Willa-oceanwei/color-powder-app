"""A5 landscape shipment printout, with amounts omitted at the source when requested."""

from html import escape
from decimal import Decimal
from unicodedata import east_asian_width

COMPANY = {"name": "佳味實業有限公司", "address": "台南市永康區中正南路309號",
           "phone": "06-2536526", "fax": "06-2537869"}


def _wrap(value, width):
    lines, line, used = [], '', 0
    for char in str(value if value is not None else ''):
        size = 2 if east_asian_width(char) in ('W', 'F') else 1
        if char == '\n' or (line and used + size > width):
            lines.append(line)
            line, used = '', 0
        if char != '\n':
            line += char
            used += size
    return lines + [line]


def _text(value):
    return escape(str(value if value is not None else ''))


def display_price(value):
    text = format(Decimal(str(value)), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def render_shipment_print(document, *, show_prices=True):
    fields = [('code', '貨品編號', 16), ('name', '品名', 22), ('quantity', '數量', 10), ('unit', '單位', 6)]
    if show_prices:
        fields.extend([('price', '單價', 12), ('amount', '金額', 14)])
    fields.append(('order_number', '採購單號', 20 if show_prices else 30))
    pages, page_rows, used = [], [], 0
    for item in document['items']:
        cells = [_wrap(display_price(item[key]) if key == 'price' else item.get(key, ''), width) for key, _, width in fields]
        if item.get('notes'):
            cells[1].extend(_wrap(item['notes'], 22))
        height = max(map(len, cells))
        offset = 0
        while offset < height:
            if used == 9:
                pages.append(page_rows)
                page_rows, used = [], 0
            take = min(height - offset, 9 - used)
            page_rows.append([cell[offset:offset + take] for cell in cells])
            used += take
            offset += take
    if page_rows or not pages:
        pages.append(page_rows)
    notes = _wrap(document.get('notes', ''), 65)
    note_pages = [notes[index:index + 4] for index in range(0, len(notes), 4)]
    while len(pages) < len(note_pages):
        pages.append([])
    output = []
    for page_index, rows in enumerate(pages):
        invoice = document.get('invoice', {})
        table_rows = ''.join('<tr>' + ''.join('<td>' + '<br>'.join(_text(line) for line in cell) + '</td>' for cell in row) + '</tr>' for row in rows)
        headings = ''.join(f'<th>{label}</th>' for _, label, _ in fields)
        total = ''
        if show_prices and page_index == len(pages) - 1:
            total = '<div class="totals">' + ''.join(f'<div><span>{label}：</span><span>{_text(document[key])}</span></div>' for label, key in
                    (('合計', 'net_amount'), ('稅額', 'tax_amount'), ('總計', 'total_amount'))) + '</div>'
        footer_note = '<br>'.join(_text(line) for line in (note_pages[page_index] if page_index < len(note_pages) else []))
        output.append(f'''<section class="sheet" aria-label="出貨單第 {page_index + 1} 頁">
<header><div><h1>{_text(COMPANY['name'])}</h1><div>{_text(COMPANY['address'])}</div><div>Tel：{_text(COMPANY['phone'])}　Fax：{_text(COMPANY['fax'])}</div></div><h2>出 貨 單</h2></header>
<div class="metadata"><div>
<div>客戶名稱：{_text(document['customer_id'])}　{_text(document['customer_name'])}</div>
<div class="pair"><span>聯絡人：{_text(document.get('contact', ''))}</span><span>統一編號：{_text(document.get('tax_id', ''))}</span></div>
<div class="pair"><span>聯絡電話：{_text(document.get('phone', ''))}</span><span>傳真號碼：{_text(document.get('fax', ''))}</span></div>
<div>送貨地址：{_text(document.get('address', ''))}</div></div>
<div><div>頁次：{page_index + 1} / {len(pages)}</div><div>貨單日期：{_text(document['shipment_date'].replace('-', '/'))}</div><div>貨單編號：{_text(document['shipment_number'])}</div><div>發票號碼：{_text(invoice.get('number', ''))}</div></div></div>
<table><thead><tr>{headings}</tr></thead><tbody>{table_rows}</tbody></table>
<div class="end-marker">--------------以下空白--------------</div>
<footer><div class="footer-top"><div class="notes">備註：{footer_note}</div>{total}</div><div class="signatures"><span>審核：</span><span>經辦：</span><strong>簽收：</strong></div></footer>
</section>''')
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>出貨單</title>
<style>
@page {size:A5 landscape;margin:0;}
* {box-sizing:border-box;}
body {margin:0;background:#e5e7eb;color:#000;font-family:"DFKai-SB","KaiTi","Microsoft JhengHei",serif;font-size:9pt;letter-spacing:0;}
.print-toolbar {padding:8px;font-family:sans-serif;}
.print-toolbar button {padding:6px 14px;}
.sheet {width:210mm;height:148mm;padding:7mm 9mm;background:#fff;position:relative;margin:10px auto;break-after:page;page-break-after:always;}
.sheet:last-child {break-after:auto;page-break-after:auto;}
header {display:grid;grid-template-columns:1fr 48mm;gap:4mm;}
h1 {margin:0;font-size:16pt;font-weight:600;}h2 {margin:1mm 0;font-size:17pt;font-weight:400;text-align:center;}
.metadata {display:grid;grid-template-columns:1fr 48mm;gap:4mm;margin:3mm 0 2mm;line-height:4.8mm;overflow-wrap:anywhere;}
.pair {display:grid;grid-template-columns:1fr 1fr;gap:2mm;}
table {width:100%;border-collapse:collapse;table-layout:fixed;line-height:4mm;}
th {font-weight:400;text-align:left;border-top:.3mm solid #000;border-bottom:.3mm solid #000;}
th,td {padding:1mm .5mm;vertical-align:top;overflow-wrap:anywhere;}
th:nth-child(2) {width:24%;}th:last-child {width:20%;}
.end-marker {margin:1mm 0;}
footer {position:absolute;bottom:7mm;left:9mm;right:9mm;border-top:.3mm solid #000;padding-top:1mm;}
.footer-top {display:grid;grid-template-columns:1fr 46mm;gap:4mm;min-height:22mm;line-height:4.6mm;}
.notes {overflow-wrap:anywhere;}.totals>div {display:flex;justify-content:space-between;}
.signatures {display:grid;grid-template-columns:1fr 1fr 2fr;padding-top:2mm;}
@media screen {.sheet{zoom:.86;}}
@media print {body{background:#fff;}.sheet{margin:0;zoom:1;}.print-toolbar{display:none;}}
</style></head><body><div class="print-toolbar"><button onclick="window.print()">列印 A5</button></div>''' + ''.join(output) + '</body></html>'
