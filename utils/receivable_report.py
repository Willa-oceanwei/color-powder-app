"""Read-only customer shipment statements; no inferred payment balances."""

import json
from decimal import Decimal
from html import escape

from .customer_repository import _mappings
from .database import connect_from_config
from .shipment_print import COMPANY, _wrap
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
          ("quantity", 10), ("unit", 6), ("price", 12), ("amount", 14), ("notes", 24))


def statement_pages(statements, capacity=15):
    pages = []
    for statement in statements:
        rows, context = [], []
        for document in statement["documents"]:
            header = ["出貨", document["date"].replace("-", "/"), document["number"]] + [""] * 7
            rows.append(header)
            context.append(header)
            for item in document["items"]:
                cells = [_wrap(item.get(key, ""), width) for key, width in FIELDS]
                for line in range(max(map(len, cells))):
                    rows.append([cell[line] if line < len(cell) else "" for cell in cells])
                    context.append(header)
        chunks, offset = [], 0
        while offset < len(rows):
            continuation = [context[offset]] if not rows[offset][0] else []
            take = capacity - len(continuation)
            chunks.append(continuation + rows[offset:offset + take])
            offset += take
        chunks = chunks or [[]]
        for index, chunk in enumerate(chunks):
            pages.append(dict(statement=statement, rows=chunk, customer_page=index + 1,
                              customer_pages=len(chunks), last=index == len(chunks) - 1))
    return pages


def render_statement_print(pages, selected=0, *, embedded=False):
    def text(value):
        return escape(str(value))

    sheets = []
    for index, page in enumerate(pages):
        s = page["statement"]
        rows = "".join("<tr>" + "".join(f"<td>{text(cell)}</td>" for cell in row) + "</tr>" for row in page["rows"])
        totals = ""
        if page["last"]:
            quantities = "　".join(f"{text(amount)} {text(unit)}" for unit, amount in s["quantities"].items())
            totals = f'''<div class="summary"><div>數量合計：{quantities}</div><div>
<div>本期未稅合計：{int(Decimal(s['net'])):,}</div><div>營業稅：{int(Decimal(s['tax'])):,}</div>
<div>本期出貨總額：{int(Decimal(s['total'])):,}</div><div>截至期末已登錄收款：{int(Decimal(s['received'])):,}</div>
<div>帳面未收餘額：{int(Decimal(s['balance'])):,}</div></div></div>'''
        sheets.append(f'''<section class="sheet{' active' if index == selected else ''}">
<h1>{text(COMPANY['name'])}</h1><h2>應收帳款明細表</h2>
<div class="metadata"><div>客戶名稱：{text(s['customer_id'])}　{text(s['customer_name'])}</div><div>頁數 {page['customer_page']} / {page['customer_pages']}</div>
<div>聯絡人：{text(s.get('contact',''))}　統一編號：{text(s.get('tax_id',''))}</div>
<div>帳款區間：{text(s['start'])} ～ {text(s['end'])}</div>
<div>聯絡電話：{text(s.get('phone',''))}　傳真號碼：{text(s.get('fax',''))}</div><div>收款狀態：依已登錄紀錄</div></div>
<table><thead><tr>{''.join('<th>'+label+'</th>' for label in ('單別','交易日期','交易單號','貨品編號','品名','數量','單位','單價','金額','備註說明'))}</tr></thead><tbody>{rows}</tbody></table>
{totals}<footer>{text(COMPANY['address'])}<br>Tel：{text(COMPANY['phone'])}　Fax：{text(COMPANY['fax'])}</footer></section>''')
    zoom = '<label>縮放 <select id="zoom" onchange="resize()"><option value="auto">符合頁面</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option><option value="1.5">150%</option></select></label>'
    toolbar = '<button onclick="window.print()">列印全部</button>' if embedded else '<button onclick="move(-1)">上一頁</button><span id="page"></span><button onclick="move(1)">下一頁</button><button onclick="window.print()">列印全部</button>'
    preview_style = "@media screen{.sheet{zoom:var(--preview-zoom,.6)}}"
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>應收帳款明細表</title><style>
@page{size:A4 landscape;margin:0}*{box-sizing:border-box}body{margin:0;background:#e5e7eb;color:#000;font:10pt "Microsoft JhengHei",sans-serif;letter-spacing:0}
.toolbar{display:flex;gap:8px;align-items:center;padding:8px}.toolbar button{padding:5px 10px}.sheet{display:none;width:297mm;height:210mm;padding:12mm;background:white;margin:8px auto;position:relative;break-after:page}.sheet.active{display:block}
h1{font-size:20pt;margin:0;text-align:center}h2{font-size:15pt;font-weight:400;margin:2mm 0 5mm;text-align:center}
.metadata{display:grid;grid-template-columns:1fr 1fr;gap:2mm;margin-bottom:3mm;overflow-wrap:anywhere;line-height:5mm}
table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9pt}th{border-top:1px solid;border-bottom:1px solid;text-align:left}td,th{padding:1mm .6mm;vertical-align:top;overflow-wrap:anywhere;line-height:4mm}
th:nth-child(1),th:nth-child(7){width:5%}th:nth-child(3){width:13%}th:nth-child(5){width:12%}th:nth-child(10){width:17%}
.summary{display:flex;justify-content:space-between;border-top:1px dotted;padding-top:3mm;line-height:6mm}.summary>div:last-child{text-align:right}footer{position:absolute;bottom:10mm;left:12mm;line-height:5mm}
@media screen and (max-width:1150px){.sheet{zoom:.75}}@media screen and (max-width:870px){.sheet{zoom:.55}}
@media print{body{background:white}.toolbar{display:none}.sheet{display:block!important;margin:0;zoom:1;page-break-after:always}.sheet:last-child{break-after:auto;page-break-after:auto}}
''' + preview_style + '</style></head><body><div class="toolbar">' + toolbar + zoom + '</div>' + "".join(sheets) + f'''
<script>let current={max(0, min(selected, len(pages)-1))};const sheets=Array.from(document.querySelectorAll('.sheet'));function move(delta){{current=Math.max(0,Math.min(sheets.length-1,current+delta));sheets.forEach((s,i)=>s.classList.toggle('active',i===current));const counter=document.getElementById('page');if(counter)counter.textContent=(sheets.length?current+1:0)+' / '+sheets.length;}}function resize(){{const value=document.getElementById('zoom').value;const scale=value==='auto'?Math.min((innerWidth-24)/1123,(innerHeight-64)/794,.95):Number(value);document.documentElement.style.setProperty('--preview-zoom',Math.max(.2,scale));}}addEventListener('resize',resize);move(0);resize();</script></body></html>'''
