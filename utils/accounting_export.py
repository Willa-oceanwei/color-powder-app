"""Downloadable statement PDF and Excel exports from the same report snapshot."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from hashlib import sha256

from .shipment_print import COMPANY, _wrap, display_price
from .shipment_codes import printed_code
from .print_stock import stock_geometry


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


def statement_excel(statements, *, show_receipts=False, title="應收帳款明細表", company_name=COMPANY["name"]):
    details = [["客戶編號", "客戶名稱", "交易日期", "出貨單號", "貨品編號", "品名", "數量", "單位", "單價", "金額", "備註", "採購單號"]]
    summary = [["客戶編號", "客戶名稱", "帳款起日", "帳款迄日", "未稅合計", "稅額", "出貨總額"] +
               (["截至期末已登錄收款", "帳面未收餘額"] if show_receipts else [])]
    for s in statements:
        summary.append([s["customer_id"], s["customer_name"], s["start"], s["end"]] +
                       [int(s[k]) for k in (("net", "tax", "total", "received", "balance") if show_receipts else ("net", "tax", "total"))])
        for d in s["documents"]:
            for item in d["items"]:
                details.append([s["customer_id"], s["customer_name"], d["date"], d["number"], printed_code(item), item["name"],
                                Decimal(item["quantity"]), item["unit"], Decimal(item["price"]), int(item["amount"]), item.get("notes", ""), item.get("order_number", "")])
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.worksheet.pagebreak import Break
    from openpyxl.worksheet.page import PageMargins
    from .receivable_report import statement_pages
    book = load_workbook(BytesIO(_workbook([("交易明細", details), ("客戶合計", summary)])))
    sheet = book.create_sheet("列印版", 0)
    sheet.sheet_view.showGridLines = False
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_margins = PageMargins(left=0, right=0, top=0, bottom=0, header=0, footer=0)
    for column, width in zip("ABCDEFGHIJ", (5, 13, 14, 13, 24, 9, 6, 10, 14, 10) if title == "應收帳款明細表" else (5, 14, 16, 13, 16, 9, 6, 10, 14, 15)):
        sheet.column_dimensions[column].width = width

    def put(row, column, value, *, end=None, size=13, bold=False, align="left"):
        if end:
            sheet.merge_cells(start_row=row, start_column=column, end_row=row, end_column=end)
        cell = sheet.cell(row, column, value)
        if isinstance(value, str):
            cell.data_type = "s"
        cell.font = Font(name="Microsoft JhengHei", size=size, bold=bold, color="000000")
        cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=column not in (2, 3, 6, 7, 8, 9, 10))
        if column in (6, 8, 9) and not isinstance(value, str):
            cell.number_format = '#,##0.##########'
        sheet.row_dimensions[row].height = max(sheet.row_dimensions[row].height or 0, size + 8)
        return cell

    base = 0
    for page in statement_pages(statements, paper_size="A4", name_width=18 if title == "應收帳款明細表" else 10):
        s = page["statement"]
        put(base + 1, 1, company_name, end=10, size=22, bold=True, align="center")
        put(base + 2, 1, title, end=10, size=17, align="center")
        put(base + 4, 1, f"客戶名稱：{s['customer_id']}　{s['customer_name']}", end=8)
        put(base + 4, 9, f"頁數 {page['customer_page']} / {page['customer_pages']}", end=10, align="right")
        put(base + 5, 1, "聯絡人：" + s.get("contact", ""), end=4)
        put(base + 5, 5, "統一編號：" + s.get("tax_id", ""), end=7)
        put(base + 6, 1, "聯絡電話：" + s.get("phone", ""), end=4)
        put(base + 6, 5, "傳真號碼：" + s.get("fax", ""), end=7)
        put(base + 6, 8, f"帳款區間：{s['start']} ～ {s['end']}", end=10, size=12)
        for column, label in enumerate(("單別", "交易日期", "交易單號", "貨品編號", "品名", "數量", "單位", "單價", "金額", "採購單號"), 1):
            cell = put(base + 8, column, label, bold=True, align="right" if column in (6, 8, 9) else "center" if column == 7 else "left")
            cell.border = Border(top=Side(style="thin"), bottom=Side(style="thin"))
        for index, row in enumerate(page["rows"], base + 9):
            for column, value in enumerate(row, 1):
                number = Decimal(value.replace(",", "")) if value and column in (6, 8, 9) else value
                cell = put(index, column, number, size=11 if column == 10 else 13, align="right" if column in (6, 8, 9) else "center" if column == 7 else "left")
                if column == 10:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False, shrink_to_fit=True)
                if row[0] and index > base + 9:
                    cell.border = Border(top=Side(style="dotted", color="000000"))
        end = base + 9 + len(page["rows"])
        if page["last"]:
            quantity_size = 12 if title == "應收帳款明細表" else 13
            for index, (unit, amount) in enumerate(s["quantities"].items(), end):
                put(index, 1, "數量合計：", end=2, size=quantity_size)
                put(index, 3, Decimal(amount), align="right", size=quantity_size)
                put(index, 4, unit, size=quantity_size)
            total_start = end
            fields = [("本期合計", "net"), ("（加）營業稅", "tax")]
            if show_receipts:
                fields += [("截至期末已登錄收款", "received"), ("帳面未收餘額", "balance")]
            fields += [("本期總計", "total")]
            for index, (label, key) in enumerate(fields, total_start):
                put(index, 6, label + "：", end=8, align="right")
                put(index, 9, int(s[key]), align="right")
            company_row = end + len(s["quantities"]) + 1
            end = total_start + len(fields)
        else:
            company_row = end + 1
        put(company_row, 1, COMPANY["address"], end=5)
        put(company_row + 1, 1, f"Tel：{COMPANY['phone']}　Fax：{COMPANY['fax']}", end=5)
        base = max(end, company_row + 2)
        sheet.row_breaks.append(Break(id=base))
    sheet.print_area = f"A1:J{max(1, base)}"
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def _company_pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    data = (Path(__file__).resolve().parents[1] / "assets/fonts/CompanySansTC.ttf").read_bytes()
    name = "CompanySansTC-" + sha256(data).hexdigest()[:16]
    if name not in pdfmetrics.getRegisteredFontNames():
        font = TTFont(name, BytesIO(data))
        # ReportLab otherwise aliases a refreshed subset to the old cached face.
        font.face.name = name.encode("ascii")
        pdfmetrics.registerFont(font)
    return name


def _canvas(title, *, a5=False):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont, CIDEncoding
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import landscape, A4, A5
    font = UnicodeCIDFont("MSung-Light")
    # ReportLab's MSung default uses the GB map, but this font needs CNS.
    font.encodingName = "UniCNS-UCS2-H"
    font.encoding = CIDEncoding(font.encodingName)
    pdfmetrics.registerFont(font)
    _company_pdf_font()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A5 if a5 else A4))
    pdf.setTitle(title)
    return buffer, pdf


def _line(pdf, x, y, text, width=100, size=10):
    pdf.setFont("MSung-Light", size)
    for index, line in enumerate(_wrap(text, width)):
        pdf.drawString(x, y - index * (size + 2), line)


def statement_pdf(pages, *, show_receipts=False, title="應收帳款明細表", paper_stock="standard", feed_rotation=0, hole_margin=12.5, company_name=COMPANY["name"]):
    from reportlab.lib.pagesizes import A4, A5, landscape
    from reportlab.lib.units import mm
    if paper_stock not in ("standard", "triplicate", "a4_driver"):
        raise ValueError("Invalid paper stock")
    if paper_stock == "triplicate" and any(p.get("paper_size", "A5") != "A5" for p in pages):
        raise ValueError("Triplicate stock requires A5 pagination")
    if paper_stock == "a4_driver" and any(p.get("paper_size", "A5") != "A4" for p in pages):
        raise ValueError("A4 feed requires A4 pagination")
    receivable = title == "應收帳款明細表"
    geometry = stock_geometry(0, hole_margin, height=280, offset=-25, preserve_holes=False) if paper_stock == "a4_driver" else stock_geometry(feed_rotation, hole_margin) if paper_stock == "triplicate" else None
    buffer, pdf = _canvas(title, a5=True)
    from .receivable_report import REPORT_WIDTHS, RECEIVABLE_WIDTHS
    labels = ("單別", "交易日期", "交易單號", "貨品編號", "品名", "數量", "單位", "單價", "金額", "採購單號")
    widths = RECEIVABLE_WIDTHS if receivable else REPORT_WIDTHS
    extra_width = 12 * mm if receivable and paper_stock == "a4_driver" else 0
    column_unit = (551 + extra_width) / 100
    positions = [22 + sum(widths[:i]) * column_unit for i in range(10)]
    right = 573 + extra_width
    for page in pages:
        size = A4 if page.get("paper_size", "A5") == "A4" else landscape(A5)
        pdf.setPageSize(size)
        if geometry:
            width, height, x, y, scale = geometry
            pdf.setPageSize(A4 if paper_stock == "a4_driver" else (width * mm, height * mm))
            pdf.saveState()
            pdf.translate(x * mm, (y + 297 - height if paper_stock == "a4_driver" else y) * mm)
            pdf.rotate(0 if paper_stock == "a4_driver" else feed_rotation)
            pdf.scale(scale, scale)
        top = size[1]
        s = page["statement"]
        pdf.setFont(_company_pdf_font(), 20)
        pdf.drawCentredString(297.5 + extra_width / 2, top - 32, company_name)
        pdf.setFont("MSung-Light", 15)
        pdf.drawCentredString(297.5 + extra_width / 2, top - 50, title)
        _line(pdf, 22, top - 73, f"客戶名稱：{s['customer_id']}  {s['customer_name']}", width=60, size=13)
        _line(pdf, 476 + extra_width, top - 73, f"頁數 {page['customer_page']} / {page['customer_pages']}", size=12)
        _line(pdf, 22, top - 94, f"聯絡人：{s.get('contact','')}", width=32, size=12)
        _line(pdf, 194 + extra_width * .3, top - 94, f"統一編號：{s.get('tax_id','')}", width=32, size=12)
        _line(pdf, 22, top - 115, f"聯絡電話：{s.get('phone','')}", width=32, size=12)
        _line(pdf, 194 + extra_width * .3, top - 115, f"傳真號碼：{s.get('fax','')}", width=32, size=12)
        _line(pdf, 367 + extra_width * .6, top - 115, f"帳款區間：{s['start'].replace('-', '/')} ~ {s['end'].replace('-', '/')}", size=11)
        if show_receipts:
            _line(pdf, 367 + extra_width * .6, top - 94, "收款狀態：依已登錄紀錄", size=11)
        pdf.line(22, top - 130, right, top - 130)
        for column, (x, label) in enumerate(zip(positions, labels)):
            pdf.setFont("MSung-Light", 11)
            if column in (5, 7, 8):
                pdf.drawRightString(x + widths[column] * column_unit - 3, top - 144, label)
            elif column == 6:
                pdf.drawCentredString(x + widths[column] * column_unit / 2, top - 144, label)
            else:
                pdf.drawString(x + (2 * mm if column == 9 else 0), top - 144, label)
        pdf.line(22, top - 151, right, top - 151)
        spacing = 18 if page.get("paper_size") == "A4" else 16
        previous_date = None
        for index, row in enumerate(page["rows"]):
            y = top - 167 - index * spacing
            if row[0] and row[1] != previous_date:
                if index:
                    pdf.setDash(1, 2)
                    pdf.line(22, y + 10, right, y + 10)
                    pdf.setDash()
                previous_date = row[1]
            pdf.setFont("MSung-Light", 11.5)
            for column, (x, value) in enumerate(zip(positions, row)):
                size = 9.5 if column == 9 else 11.5
                if column == 9 and value:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    available = widths[column] * column_unit - 2 * mm - 3
                    measured = stringWidth(str(value), "MSung-Light", size)
                    if measured > available:
                        size *= available / measured
                pdf.setFont("MSung-Light", size)
                if column in (5, 7, 8):
                    pdf.drawRightString(x + widths[column] * column_unit - 3, y, str(value))
                elif column == 6:
                    pdf.drawCentredString(x + widths[column] * column_unit / 2, y, str(value))
                else:
                    pdf.drawString(x + (2 * mm if column == 9 else 0), y, str(value))
        if page["last"]:
            y = top - 167 - len(page["rows"]) * spacing
            pdf.line(22, y, right, y)
            for index, (unit, amount) in enumerate(s["quantities"].items()):
                pdf.setFont("MSung-Light", 11 if receivable else 12)
                pdf.drawString(22, y - 17 - index * 17, "數量合計：")
                pdf.drawRightString(150, y - 17 - index * 17, display_price(amount))
                pdf.drawString(160, y - 17 - index * 17, unit)
            summary_y = y - 17
            totals = [("本期合計", "net"), ("（加）營業稅", "tax")]
            if show_receipts:
                totals += [("截至期末已登錄收款", "received"), ("帳面未收餘額", "balance")]
            totals += [("本期總計", "total")]
            for index, (label, key) in enumerate(totals):
                pdf.setFont("MSung-Light", 12)
                pdf.drawRightString(positions[8] - 4, summary_y - index * 17, f"{label}：")
                pdf.drawRightString(positions[8] + widths[8] * column_unit - 3, summary_y - index * 17, f"{int(s[key]):,}")
            company_y = summary_y - (len(s["quantities"]) + 1) * 17
        else:
            company_y = top - 167 - len(page["rows"]) * spacing - 17
        _line(pdf, 22, company_y, COMPANY["address"], size=11)
        _line(pdf, 22, company_y - 16, f"Tel: {COMPANY['phone']}  Fax: {COMPANY['fax']}", size=11)
        if geometry:
            pdf.restoreState()
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def ranking_rows(statements):
    rows = [["排名", "客戶編號", "客戶名稱", "出貨筆數", "未稅合計", "稅額", "出貨總額"]]
    for index, s in enumerate(sorted(statements, key=lambda s: (-Decimal(s["net"]), s["customer_id"]))):
        rows.append([index + 1, s["customer_id"], s["customer_name"], len(s["documents"]), int(s["net"]), int(s["tax"]), int(s["total"])])
    return rows


def ranking_excel(statements):
    rows = ranking_rows(statements)
    rows.append(["", "", "未稅金額總計", "", int(sum((Decimal(s["net"]) for s in statements), Decimal(0))), "", ""])
    return _workbook([("客戶交易排行", rows)])


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
        if offset + 20 >= len(rows):
            _line(pdf, 500, 63, f"未稅金額總計：{int(sum((Decimal(s['net']) for s in statements), Decimal(0))):,}", size=10)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()

