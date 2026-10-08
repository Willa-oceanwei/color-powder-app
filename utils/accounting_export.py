"""Downloadable statement PDF and Excel exports from the same report snapshot."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from .shipment_print import COMPANY, _wrap, display_price


def _workbook(sheets):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    book = Workbook()
    book.remove(book.active)
    for title, rows in sheets:
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
            # Business text is data, not a spreadsheet formula.
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(36, max(14, max(len(str(c.value or "")) for c in column) + 2))
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def statement_excel(statements, *, show_receipts=False):
    details = [["客戶編號", "客戶名稱", "交易日期", "出貨單號", "貨品編號", "品名", "數量", "單位", "單價", "金額", "備註"]]
    summary = [["客戶編號", "客戶名稱", "帳款起日", "帳款迄日", "未稅合計", "稅額", "出貨總額"] +
               (["截至期末已登錄收款", "帳面未收餘額"] if show_receipts else [])]
    for s in statements:
        summary.append([s["customer_id"], s["customer_name"], s["start"], s["end"]] +
                       [int(s[k]) for k in (("net", "tax", "total", "received", "balance") if show_receipts else ("net", "tax", "total"))])
        for d in s["documents"]:
            for item in d["items"]:
                details.append([s["customer_id"], s["customer_name"], d["date"], d["number"], item["code"], item["name"],
                                Decimal(item["quantity"]), item["unit"], Decimal(item["price"]), int(item["amount"]), item.get("notes", "")])
    return _workbook([("交易明細", details), ("客戶合計", summary)])


def _canvas(title, *, a5=False):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont, CIDEncoding
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import landscape, A4, A5
    font = UnicodeCIDFont("MSung-Light")
    # ReportLab's MSung default uses the GB map, but this font needs CNS.
    font.encodingName = "UniCNS-UCS2-H"
    font.encoding = CIDEncoding(font.encodingName)
    pdfmetrics.registerFont(font)
    pdfmetrics.registerFont(TTFont("CompanySansTC", str(Path(__file__).resolve().parents[1] / "assets/fonts/CompanySansTC.ttf")))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A5 if a5 else A4))
    pdf.setTitle(title)
    return buffer, pdf


def _line(pdf, x, y, text, width=100, size=10):
    pdf.setFont("MSung-Light", size)
    for index, line in enumerate(_wrap(text, width)):
        pdf.drawString(x, y - index * (size + 2), line)


def statement_pdf(pages, *, show_receipts=False):
    buffer, pdf = _canvas("應收帳款明細表", a5=True)
    labels = ("單別", "交易日期", "交易單號", "貨品編號", "品名", "數量", "單位", "單價", "金額", "備註說明")
    positions = (22, 45, 103, 174, 231, 333, 373, 401, 441, 492)
    for page in pages:
        s = page["statement"]
        pdf.setFont("CompanySansTC", 17)
        pdf.drawCentredString(297.5, 387, COMPANY["name"])
        pdf.setFont("MSung-Light", 12)
        pdf.drawCentredString(297.5, 369, "應收帳款明細表")
        _line(pdf, 22, 349, f"客戶：{s['customer_id']}  {s['customer_name']}", width=50, size=9)
        _line(pdf, 476, 349, f"頁數 {page['customer_page']} / {page['customer_pages']}", size=9)
        _line(pdf, 22, 329, f"聯絡人：{s.get('contact','')}  統一編號：{s.get('tax_id','')}", width=60, size=8)
        _line(pdf, 323, 329, f"帳款區間：{s['start']} ~ {s['end']}", size=8)
        _line(pdf, 22, 313, f"電話：{s.get('phone','')}  傳真：{s.get('fax','')}", width=60, size=8)
        if show_receipts:
            _line(pdf, 323, 313, "收款狀態：依已登錄紀錄", size=8)
        pdf.line(22, 302, 573, 302)
        for x, label in zip(positions, labels):
            _line(pdf, x, 290, label, size=8)
        pdf.line(22, 283, 573, 283)
        for index, row in enumerate(page["rows"]):
            for x, value in zip(positions, row):
                _line(pdf, x, 270 - index * 12, value, width=100, size=7.5)
        if page["last"]:
            y = 270 - len(page["rows"]) * 12
            pdf.line(22, y, 573, y)
            quantity = "  ".join(f"{display_price(amount)} {unit}" for unit, amount in s["quantities"].items())
            _line(pdf, 22, y - 15, "數量合計：" + quantity, width=60, size=9)
            totals = [("本期未稅合計", "net"), ("營業稅", "tax"), ("本期出貨總額", "total")]
            if show_receipts:
                totals += [("截至期末已登錄收款", "received"), ("帳面未收餘額", "balance")]
            for index, (label, key) in enumerate(totals):
                pdf.setFont("MSung-Light", 9)
                pdf.drawRightString(573, y - 15 - index * 14, f"{label}：{int(s[key]):,}")
        _line(pdf, 22, 33, COMPANY["address"], size=8)
        _line(pdf, 22, 21, f"Tel: {COMPANY['phone']}  Fax: {COMPANY['fax']}", size=8)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def ranking_rows(statements):
    rows = [["排名", "客戶編號", "客戶名稱", "出貨筆數", "未稅合計", "稅額", "出貨總額"]]
    for index, s in enumerate(sorted(statements, key=lambda s: (-Decimal(s["net"]), s["customer_id"]))):
        rows.append([index + 1, s["customer_id"], s["customer_name"], len(s["documents"]), int(s["net"]), int(s["tax"]), int(s["total"])])
    return rows


def ranking_excel(statements):
    return _workbook([("客戶交易排行", ranking_rows(statements))])


def ranking_pdf(statements):
    source = ranking_rows(statements)
    rows = []
    for row in source[1:]:
        cells = [_wrap(value, width) for value, width in zip(row, (10, 16, 40, 12, 20, 16, 18))]
        for index in range(max(map(len, cells))):
            rows.append([cell[index] if index < len(cell) else "" for cell in cells])
    buffer, pdf = _canvas("客戶交易排行")
    for offset in range(0, len(rows), 20):
        _line(pdf, 320, 550, COMPANY["name"], size=19)
        _line(pdf, 350, 523, "客戶交易排行", size=14)
        if statements:
            _line(pdf, 34, 493, f"帳款區間：{statements[0]['start']} ~ {statements[0]['end']}（依未稅合計排序）")
        positions = (34, 90, 180, 421, 500, 613, 710)
        for index, row in enumerate([source[0]] + rows[offset:offset + 20]):
            for x, value in zip(positions, row):
                _line(pdf, x, 466 - index * 17, value, width=100, size=9)
        _line(pdf, 34, 39, f"頁數 {offset // 20 + 1} / {(len(rows) - 1) // 20 + 1}", size=9)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()
