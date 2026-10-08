"""Read-only customer shipment statements; no inferred payment balances."""

import json
from decimal import Decimal
from html import escape

from .customer_repository import _mappings
from .database import connect_from_config
from .shipment_print import COMPANY, _wrap, display_price
from .shipment_repository import ShipmentError, _valid_date


def build_statements(config, start, end, customer_start="", customer_end="", hide_empty=True):
    start, end = _valid_date(start, "起始帳款日期"), _valid_date(end, "結束帳款日期")
    if start > end:
        raise ShipmentError("起始帳款日期不可晚於結束日期")
    if customer_start and customer_end and customer_start > customer_end:
        raise ShipmentError("起始客戶編號不可大於結束編號")
    clauses, args = [], []
    for value, operator in ((customer_start, ">="), (customer_end, "<=")):
        if value:
            clauses.append(f"customer_id {operator} ?")
            args.append(value)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    # One SELECT snapshots headers and lines, rather than a query per shipment.
    with connect_from_config(config) as conn:
        customers = _mappings(conn.execute(f"SELECT customer_id,name FROM customers {where} ORDER BY customer_id", tuple(args)))
        records = _mappings(conn.execute(
            "SELECT s.id,s.shipment_number,s.shipment_date,s.customer_id,s.customer_name,s.payload_json,"
            "s.net_amount,s.tax_amount,s.total_amount,i.line_number,i.payload_json AS item_json,"
            "(SELECT COALESCE(SUM(CAST(r.amount AS INTEGER)),0) FROM shipment_receipts r "
            "WHERE r.shipment_id=s.id AND r.status='active' AND r.receipt_date<=?) AS received "
            "FROM shipment_orders s JOIN shipment_order_items i ON i.shipment_id=s.id "
            "WHERE s.status='draft' AND json_extract(s.payload_json,'$.account_date')>=? "
            "AND json_extract(s.payload_json,'$.account_date')<=? "
            + ("AND s.customer_id>=? " if customer_start else "")
            + ("AND s.customer_id<=? " if customer_end else "")
            + "ORDER BY s.customer_id,s.shipment_date,s.shipment_number,s.id,i.line_number",
            tuple([end, start, end] + ([customer_start] if customer_start else []) + ([customer_end] if customer_end else []))))
    grouped = {c["customer_id"]: dict(customer_id=c["customer_id"], customer_name=c["name"],
               start=start, end=end, documents=[], contact="", phone="", fax="", tax_id="") for c in customers}
    documents = {}
    for row in records:
        statement = grouped.setdefault(row["customer_id"], dict(customer_id=row["customer_id"], customer_name=row["customer_name"],
                    start=start, end=end, documents=[]))
        if row["id"] not in documents:
            header = json.loads(row["payload_json"])
            document = dict(id=row["id"], number=row["shipment_number"], date=row["shipment_date"], items=[],
                            net=row["net_amount"], tax=row["tax_amount"], total=row["total_amount"], received=str(row["received"]))
            documents[row["id"]] = document
            statement["documents"].append(document)
            for key in ("contact", "phone", "fax", "tax_id"):
                statement[key] = header.get(key, "")
        documents[row["id"]]["items"].append(json.loads(row["item_json"]))
    result = []
    for code in sorted(grouped):
        statement = grouped[code]
        if hide_empty and not statement["documents"]:
            continue
        for name in ("net", "tax", "total", "received"):
            statement[name] = str(sum((Decimal(d[name]) for d in statement["documents"]), Decimal(0)))
        statement["balance"] = str(Decimal(statement["total"]) - Decimal(statement["received"]))
        quantities = {}
        for document in statement["documents"]:
            for item in document["items"]:
                unit = item["unit"]
                quantities[unit] = quantities.get(unit, Decimal(0)) + Decimal(item["quantity"])
        statement["quantities"] = {unit: str(amount) for unit, amount in quantities.items()}
        result.append(statement)
    return result


FIELDS = (("kind", 6), ("date", 12), ("number", 16), ("code", 14), ("name", 18),
          ("quantity", 9), ("unit", 6), ("price", 8), ("amount", 12), ("notes", 10))


def statement_pages(statements, capacity=None, *, paper_size="auto"):
    if paper_size not in ("auto", "A5", "A4"):
        raise ValueError("Invalid paper size")
    if capacity is not None and capacity < 2:
        raise ValueError("Page capacity must be at least two")
    pages = []
    for statement in statements:
        rows, context = [], []
        for document in statement["documents"]:
            header = ["出貨", document["date"].replace("-", "/"), document["number"]] + [""] * 7
            rows.append(header)
            context.append(header)
            for item in document["items"]:
                cells = [_wrap(display_price(item[key]) if key in ("price", "quantity") else
                               f"{int(item[key]):,}" if key == "amount" else item.get(key, ""), width) for key, width in FIELDS]
                for line in range(max(map(len, cells))):
                    rows.append([cell[line] if line < len(cell) else "" for cell in cells])
                    context.append(header)
        size = ("A5" if len(rows) <= 10 else "A4") if paper_size == "auto" else paper_size
        limit = capacity if capacity is not None else (10 if size == "A5" else 32)
        chunks, offset = [], 0
        while offset < len(rows):
            continuation = [context[offset]] if not rows[offset][0] else []
            take = limit - len(continuation)
            if offset + take < len(rows) and rows[offset + take - 1][0] and take > 1:
                take -= 1
            chunks.append(continuation + rows[offset:offset + take])
            offset += take
        chunks = chunks or [[]]
        for index, chunk in enumerate(chunks):
            pages.append(dict(statement=statement, rows=chunk, customer_page=index + 1,
                              customer_pages=len(chunks), last=index == len(chunks) - 1, paper_size=size))
    return pages


def render_statement_print(pages, selected=0, *, embedded=False, show_receipts=False):
    def text(value):
        return escape(str(value))

    sheets = []
    for index, page in enumerate(pages):
        s = page["statement"]
        rows, previous_date = [], None
        for row in page["rows"]:
            new_date = bool(row[0] and row[1] != previous_date)
            if row[0]:
                previous_date = row[1]
            rows.append('<tr class="date-start">' if new_date else '<tr>')
            rows.append("".join(f"<td>{text(cell)}</td>" for cell in row) + "</tr>")
        rows = "".join(rows)
        totals = ""
        receipt_totals = (f"<div>截至期末已登錄收款：{int(Decimal(s['received'])):,}</div>"
                          f"<div>帳面未收餘額：{int(Decimal(s['balance'])):,}</div>") if show_receipts else ""
        if page["last"]:
            quantities = "　".join(f"{text(display_price(amount))} {text(unit)}" for unit, amount in s["quantities"].items())
            totals = f'''<div class="summary"><div>數量合計：{quantities}</div><div>
<div>本期合計：{int(Decimal(s['net'])):,}</div><div>（加）營業稅：{int(Decimal(s['tax'])):,}</div>
{receipt_totals}<div>本期總計：{int(Decimal(s['total'])):,}</div></div></div>'''
        sheets.append(f'''<section class="sheet {page.get('paper_size', 'A5').lower()}{' active' if index == selected else ''}">
<h1>{text(COMPANY['name'])}</h1><h2>應收帳款明細表</h2>
<div class="metadata"><div class="customer">客戶名稱：{text(s['customer_id'])}　{text(s['customer_name'])}</div><div class="page-number">頁數 {page['customer_page']} / {page['customer_pages']}</div>
<div>聯絡人：{text(s.get('contact',''))}</div><div>統一編號：{text(s.get('tax_id',''))}</div><div></div>
<div>聯絡電話：{text(s.get('phone',''))}</div><div>傳真號碼：{text(s.get('fax',''))}</div><div class="period">帳款區間：{text(s['start'].replace('-', '/'))} ～ {text(s['end'].replace('-', '/'))}</div>
{'<div class="customer">收款狀態：依已登錄紀錄</div>' if show_receipts else ''}</div>
<table><thead><tr>{''.join('<th>'+label+'</th>' for label in ('單別','交易日期','交易單號','貨品編號','品名','數量','單位','單價','金額','備註說明'))}</tr></thead><tbody>{rows}</tbody></table>
{totals}<footer>{text(COMPANY['address'])}<br>Tel：{text(COMPANY['phone'])}　Fax：{text(COMPANY['fax'])}</footer></section>''')
    zoom = '<label for="zoom">縮放</label><select id="zoom" onchange="resize()"><option value="width">符合寬度</option><option value="page">整頁</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option></select>'
    toolbar = '<button onclick="window.print()">列印全部</button>' if embedded else '<button onclick="move(-1)">上一頁</button><span id="page"></span><button onclick="move(1)">下一頁</button><button onclick="window.print()">列印全部</button>'
    preview_style = "@media screen{.sheet{zoom:var(--preview-zoom,.6)}}"
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>應收帳款明細表</title><style>
@page{size:A5 landscape;margin:0}@page a5{size:A5 landscape;margin:0}@page a4{size:A4 portrait;margin:0}*{box-sizing:border-box}body{margin:0;background:#e5e7eb;color:#000;font:10pt "Microsoft JhengHei",sans-serif;letter-spacing:0}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:8px;font:16px "Microsoft JhengHei",sans-serif}.toolbar button,.toolbar select{font:inherit;min-height:38px;padding:5px 10px;border-radius:4px}.toolbar select{min-width:140px}.preview-stage{overflow:auto;padding:12px}.sheet{display:none;width:210mm;height:148mm;padding:8mm;background:white;margin:0 auto;position:relative;break-after:page}.sheet.active{display:block}
h1{font-size:17pt;margin:0;text-align:center}h2{font-size:12pt;font-weight:400;margin:1mm 0 3mm;text-align:center}
.sheet.a5{page:a5}.sheet.a4{page:a4;height:297mm}
.metadata{display:grid;grid-template-columns:30% 30% 40%;row-gap:1mm;margin-bottom:2mm;overflow-wrap:anywhere;line-height:4.5mm}.customer{grid-column:span 2}.page-number,.period{text-align:right}.period{font-size:9pt}
table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9pt}th{border-top:1px solid;border-bottom:1px solid;text-align:left;white-space:nowrap}td,th{padding:.5mm .2mm;vertical-align:top;overflow-wrap:anywhere;line-height:4mm}
th:nth-child(1){width:5%}th:nth-child(2){width:11%}th:nth-child(3){width:14%}th:nth-child(4){width:11%}th:nth-child(5){width:23%}th:nth-child(6){width:7%}th:nth-child(7){width:5%}th:nth-child(8){width:7%}th:nth-child(9){width:9%}th:nth-child(10){width:8%}
tr.date-start{border-top:1px dotted #000}
td:nth-child(6),td:nth-child(8),td:nth-child(9){text-align:right;font-variant-numeric:tabular-nums}
td:nth-child(6){padding-right:2mm}td:nth-child(7){text-align:center}
.summary{display:flex;justify-content:space-between;border-top:1px dotted;padding-top:2mm;line-height:4.8mm}.summary>div:last-child{text-align:right}footer{position:absolute;bottom:7mm;left:8mm;line-height:4mm}
@media print{body{background:white}.toolbar{display:none}.preview-stage{height:auto!important;overflow:visible;padding:0}.sheet{display:block!important;margin:0;zoom:1;page-break-after:always}.sheet:last-child{break-after:auto;page-break-after:auto}}
''' + preview_style + '</style></head><body><div class="toolbar">' + toolbar + zoom + '</div><div class="preview-stage">' + "".join(sheets) + f'''
</div><script>let current={max(0, min(selected, len(pages)-1))};const sheets=Array.from(document.querySelectorAll('.sheet'));const stage=document.querySelector('.preview-stage');function move(delta){{current=Math.max(0,Math.min(sheets.length-1,current+delta));sheets.forEach((s,i)=>s.classList.toggle('active',i===current));const counter=document.getElementById('page');if(counter)counter.textContent=(sheets.length?current+1:0)+' / '+sheets.length;stage.scrollTo(0,0);resize();}}function resize(){{const value=document.getElementById('zoom').value;const height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight);stage.style.height=height+'px';const paper=sheets[current];const widthScale=(stage.clientWidth-24)/(paper?paper.offsetWidth:794);const scale=value==='width'?widthScale:value==='page'?Math.min(widthScale,(height-24)/(paper?paper.offsetHeight:559)):Number(value);document.documentElement.style.setProperty('--preview-zoom',Math.max(.2,scale));}}addEventListener('resize',resize);move(0);</script></body></html>'''
