"""Read-only customer shipment statements; no inferred payment balances."""

import json
from decimal import Decimal
from html import escape

from .customer_repository import _mappings
from .database import connect_from_config
from .shipment_print import COMPANY, _wrap, display_price, purchase_order_text, PURCHASE_ORDER_FIT
from .shipment_repository import ShipmentError, _valid_date
from .shipment_codes import printed_code
from .print_stock import stock_sheet, stock_style


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
            "WHERE s.status='draft' AND s.shipment_date>=? "
            "AND s.shipment_date<=? "
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


def monthly_receipt_summary(config, start, end, as_of):
    start, end, as_of = (_valid_date(value, label) for value, label in
                         ((start, '帳款起日'), (end, '帳款迄日'), (as_of, '截至日期')))
    if start > end:
        raise ShipmentError('帳款起日不可晚於迄日')
    with connect_from_config(config) as conn:
        customers = _mappings(conn.execute('SELECT customer_id,name FROM customers ORDER BY customer_id'))
        tracking_rows = _mappings(conn.execute(
            "SELECT customer_id,start_date,request_json FROM ("
            "SELECT b.customer_id,substr(b.receipt_date,1,7)||'-01' AS start_date,b.request_json,b.created_at,b.id "
            "FROM receipt_batches b UNION ALL "
            "SELECT s.customer_id,substr(s.shipment_date,1,7)||'-01',NULL,r.created_at,r.id "
            "FROM shipment_receipts r JOIN shipment_orders s ON s.id=r.shipment_id "
            "WHERE NOT EXISTS(SELECT 1 FROM receipt_batch_allocations a WHERE a.receipt_id=r.id)"
            ") ORDER BY created_at,id"))
        documents = _mappings(conn.execute(
            "SELECT s.customer_id,s.shipment_date,s.total_amount,"
            "(SELECT COALESCE(SUM(CAST(r.amount AS INTEGER)),0) FROM shipment_receipts r "
            "WHERE r.shipment_id=s.id AND r.status='active' AND r.receipt_date<=?) AS received,"
            "(SELECT MAX(r.receipt_date) FROM shipment_receipts r "
            "WHERE r.shipment_id=s.id AND r.status='active' AND CAST(r.amount AS INTEGER)>0 AND r.receipt_date<=?) AS last_receipt "
            "FROM shipment_orders s WHERE s.status='draft' AND s.shipment_date>=? AND s.shipment_date<=?",
            (as_of, as_of, start, min(end, as_of))))
    tracking = {}
    for row in tracking_rows:
        request = json.loads(row['request_json']) if row['request_json'] else {}
        tracking.setdefault(row['customer_id'], request.get('ledger_start') or request.get('tracking_start') or row['start_date'])
    summary = {c['customer_id']: dict(customer_id=c['customer_id'], customer_name=c['name'],
               total=0, received=0, balance=0, last_receipt='', tracking_start=tracking.get(c['customer_id'], '')) for c in customers}
    for document in documents:
        row = summary[document['customer_id']]
        if row['tracking_start'] and document['shipment_date'] < row['tracking_start']:
            continue
        row['total'] += int(document['total_amount'])
        row['received'] += int(document['received'])
        row['last_receipt'] = max(row['last_receipt'], document['last_receipt'] or '')
    for row in summary.values():
        row['balance'] = row['total'] - row['received']
        row['status'] = ('本期無帳款' if not row['total'] else '尚未開始登錄' if not row['tracking_start'] else
                         '已收齊' if not row['balance'] else '部分收款' if row['received'] else '未收款')
    return list(summary.values())


FIELDS = (("kind", 6), ("date", 12), ("number", 16), ("code", 14), ("name", 10),
          ("quantity", 9), ("unit", 6), ("price", 8), ("amount", 12), ("order_number", 12))
REPORT_WIDTHS = (5, 13, 14, 11, 12, 7, 5, 8, 11, 14)


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
                               f"{int(item[key]):,}" if key == "amount" else printed_code(item) if key == "code" else item.get(key, ""), width) for key, width in FIELDS]
                cells[-1] = [purchase_order_text(item.get("order_number", ""))]
                for line in range(max(map(len, cells))):
                    rows.append([cell[line] if line < len(cell) else "" for cell in cells])
                    context.append(header)
        size = ("A5" if len(rows) <= 10 else "A4") if paper_size == "auto" else paper_size
        limit = capacity if capacity is not None else (6 if size == "A5" else 26)
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


def render_statement_print(pages, selected=0, *, embedded=False, show_receipts=False, title="應收帳款明細表", paper_stock="standard", feed_rotation=0, hole_margin=12.5, company_name=COMPANY["name"]):
    receivable = title == "應收帳款明細表"
    if paper_stock not in ("standard", "triplicate", "a4_driver"):
        raise ValueError("Invalid paper stock")
    if paper_stock == "triplicate" and any(p.get("paper_size", "A5") != "A5" for p in pages):
        raise ValueError("Triplicate stock requires A5 pagination")
    if paper_stock == "a4_driver" and any(p.get("paper_size", "A5") != "A4" for p in pages):
        raise ValueError("A4 feed requires A4 pagination")
    def text(value):
        return escape(str(value))
    company_info = f'<div class="company-info">{text(COMPANY["address"])}<br>Tel：{text(COMPANY["phone"])}　Fax：{text(COMPANY["fax"])}</div>'

    sheets = []
    for index, page in enumerate(pages):
        s = page["statement"]
        rows, previous_date = [], None
        for row in page["rows"]:
            new_date = bool(row[0] and row[1] != previous_date)
            if row[0]:
                previous_date = row[1]
            rows.append('<tr class="date-start">' if new_date else '<tr>')
            rows.append("".join(f'<td><span data-purchase-order>{text(cell)}</span></td>' if column == 9 else f"<td>{text(cell)}</td>"
                                for column, cell in enumerate(row)) + "</tr>")
        rows = "".join(rows)
        totals = ""
        if page["last"]:
            quantities = ''.join(f'<span class="quantity-label">數量合計：</span><span class="quantity-value">{text(display_price(amount))}</span><span class="quantity-unit">{text(unit)}</span>' for unit, amount in s["quantities"].items())
            total_fields = [("本期合計", "net"), ("（加）營業稅", "tax")]
            if show_receipts:
                total_fields += [("截至期末已登錄收款", "received"), ("帳面未收餘額", "balance")]
            total_fields += [("本期總計", "total")]
            total_rows = ''.join(f'<div><span>{label}：</span><span>{int(Decimal(s[key])):,}</span></div>' for label, key in total_fields)
            totals = f'<div class="summary"><div class="statement-left"><div class="quantity-summary">{quantities}</div>{company_info}</div><div class="statement-totals">{total_rows}</div></div>'
        sheets.append(f'''<section class="sheet {page.get('paper_size', 'A5').lower()}{' active' if index == selected else ''}">
<h1>{text(company_name)}</h1><h2>{text(title)}</h2>
<div class="metadata"><div class="customer">客戶名稱：{text(s['customer_id'])}　{text(s['customer_name'])}</div><div class="page-number">頁數 {page['customer_page']} / {page['customer_pages']}</div>
<div>聯絡人：{text(s.get('contact',''))}</div><div>統一編號：{text(s.get('tax_id',''))}</div><div></div>
<div>聯絡電話：{text(s.get('phone',''))}</div><div>傳真號碼：{text(s.get('fax',''))}</div><div class="period">帳款區間：{text(s['start'].replace('-', '/'))} ～ {text(s['end'].replace('-', '/'))}</div>
{'<div class="customer">收款狀態：依已登錄紀錄</div>' if show_receipts else ''}</div>
<table><thead><tr>{''.join('<th>'+label+'</th>' for label in ('單別','交易日期','交易單號','貨品編號','品名','數量','單位','單價','金額','採購單號'))}</tr></thead><tbody>{rows}</tbody></table>
{totals if page['last'] else company_info}</section>''')
    if paper_stock in ("triplicate", "a4_driver"):
        sheets = [stock_sheet(sheet, active=index == selected) for index, sheet in enumerate(sheets)]
    zoom = '<label for="zoom">縮放</label><select id="zoom" onchange="resize()"><option value="width">符合寬度</option><option value="page" selected>整頁</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option></select>'
    toolbar = '<button onclick="window.print()">列印全部</button>' if embedded else '<button onclick="move(-1)">上一頁</button><span id="page"></span><button onclick="move(1)">下一頁</button><button onclick="window.print()">列印全部</button>'
    preview_style = "@media screen{.sheet{zoom:var(--preview-zoom,.6)}}"
    if paper_stock == "triplicate":
        preview_style += stock_style(feed_rotation, hole_margin, paginated=True)
    elif paper_stock == "a4_driver":
        preview_style += stock_style(0, hole_margin, paginated=True, stock_height=280, offset=-25, a4_driver=True)
        if receivable:
            preview_style += ".stock-page>.sheet.a4{width:222mm}"
    preview_style += '''body{font-size:13pt}h1{font-size:20pt}h2{font-size:15pt}.metadata{line-height:5.5mm}.period{font-size:12pt}
table{font-size:12pt}td,th{line-height:5.2mm}.sheet{padding:8mm}th:nth-child(6),th:nth-child(8),th:nth-child(9){text-align:right}th:nth-child(7){text-align:center}
th:nth-child(1){width:5%}th:nth-child(2){width:13%}th:nth-child(3){width:14%}th:nth-child(4){width:11%}th:nth-child(5){width:12%}th:nth-child(6){width:7%}th:nth-child(7){width:5%}th:nth-child(8){width:8%}th:nth-child(9){width:11%}th:nth-child(10){width:14%}
td:nth-child(6),td:nth-child(8),td:nth-child(9){white-space:nowrap;padding-right:.2mm}
td:nth-child(1),td:nth-child(2),td:nth-child(3),td:nth-child(4),td:nth-child(7){white-space:nowrap}
th:nth-child(9),td:nth-child(9){padding-right:1mm}th:nth-child(10),td:nth-child(10){padding-left:2mm}
td:nth-child(10){font-size:9.5pt;white-space:nowrap;overflow-wrap:normal}
[data-purchase-order]{display:inline-block;white-space:nowrap;overflow-wrap:normal}
.summary{grid-template-columns:5% 13% 14% 11% 12% 7% 5% 8% 11% 14%;line-height:5.8mm}
.statement-left{grid-column:1/6;grid-row:1;align-self:start}
.quantity-summary{display:grid;grid-template-columns:max-content 20mm max-content;column-gap:2mm}
.quantity-label{grid-column:1}.quantity-value{grid-column:2;text-align:right}.quantity-unit{grid-column:3;text-align:left}
.statement-totals{grid-column:6/10;grid-row:1;align-self:start;font-size:12pt}.statement-totals>div{grid-template-columns:20fr 11fr}
.statement-totals span:last-child{padding-right:1mm}
.company-info{margin-top:5.8mm;font-size:12pt;line-height:5.8mm}
@media screen{.sheet.a4,.sheet.a5{height:auto}.stock-page>.sheet.a4{height:297mm}.stock-page>.sheet.a5{height:148mm}.stock-page{height:var(--statement-content-height)}}
'''
    if receivable:
        preview_style += ".quantity-summary{font-size:12pt}"
    html = '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>應收帳款明細表</title><style>
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
.summary{display:grid;grid-template-columns:5% 11% 14% 11% 23% 7% 5% 7% 9% 8%;border-top:1px dotted;padding-top:2mm;line-height:4.8mm}.quantity-summary{grid-column:1/6}.statement-totals{grid-column:6/10;font-size:9pt}.statement-totals>div{display:grid;grid-template-columns:19fr 9fr}.statement-totals span:first-child{text-align:right}.statement-totals span:last-child{text-align:right;padding-right:.2mm;font-variant-numeric:tabular-nums}footer{position:absolute;bottom:7mm;left:8mm;line-height:4mm}
@media print{body{background:white}.toolbar{display:none}.preview-stage{height:auto!important;overflow:visible;padding:0}.sheet{display:block!important;margin:0;zoom:1;page-break-after:always}.sheet:last-child{break-after:auto;page-break-after:auto}}
'''.replace('<title>應收帳款明細表</title>', '<title>' + text(title) + '</title>') + preview_style + '</style></head><body><div class="toolbar">' + toolbar + zoom + '</div><div class="preview-stage">' + "".join(sheets) + f'''
</div><script>let current={max(0, min(selected, len(pages)-1))};const sheets=Array.from(document.querySelectorAll('.sheet'));const stage=document.querySelector('.preview-stage');function move(delta){{current=Math.max(0,Math.min(sheets.length-1,current+delta));sheets.forEach((s,i)=>s.classList.toggle('active',i===current));const counter=document.getElementById('page');if(counter)counter.textContent=(sheets.length?current+1:0)+' / '+sheets.length;stage.scrollTo(0,0);resize();}}function resize(){{const value=document.getElementById('zoom').value;const height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight);stage.style.height=height+'px';const paper=sheets[current];const widthScale=(stage.clientWidth-24)/(paper?paper.offsetWidth:794);const scale=value==='width'?widthScale:value==='page'?Math.min(widthScale,(height-24)/(paper?paper.offsetHeight:559)):Number(value);document.documentElement.style.setProperty('--preview-zoom',Math.max(.2,scale));}}addEventListener('resize',resize);move(0);</script></body></html>'''
    if paper_stock in ("triplicate", "a4_driver"):
        html = html.replace("querySelectorAll('.sheet')", "querySelectorAll('.stock-page')")
        trim = '''function trimPages(){sheets.forEach(p=>{const sheet=p.querySelector('.sheet'),last=sheet.querySelector('.summary')||sheet.querySelector('.company-info');const m=new DOMMatrix(getComputedStyle(sheet).transform);if(last&&Math.abs(m.b)<.001){const end=last.offsetTop+last.offsetHeight+parseFloat(getComputedStyle(sheet).paddingBottom);p.style.setProperty('--statement-content-height',(end*m.a+m.f)+'px');}});}
'''
        html = html.replace("function resize(){", trim + "function resize(){trimPages();")
    return html.replace("</body>", PURCHASE_ORDER_FIT + "</body>")

