"""Compact, same-sheet salary slips modelled after the supplied legacy layout."""
from io import BytesIO

def generate_salary_workbook(year, month, salaries):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = f"{year}年{month:02d}月薪資"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 16
    thin = Side(style="thin", color="666666")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    row = 1
    for salary in salaries:
        additions = [x for x in salary.get("adjustments", []) if x["type"] == "addition"]
        deductions = [x for x in salary.get("adjustments", []) if x["type"] == "deduction"]
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        cell = ws.cell(row, 1, f"{month:02d}月份　{salary['employee_name_snapshot']}")
        cell.font = Font(size=14, bold=True); cell.alignment = Alignment(horizontal="center")
        cell.fill = PatternFill("solid", fgColor="D9EAF7")
        items = [("底薪", salary["base_salary_snapshot"]), ("+全勤", salary["attendance_bonus_snapshot"]),
                 ("+涼水", salary["cooling_allowance_snapshot"]), ("+津貼", salary["allowance_snapshot"]),
                 ("+職務津貼", salary["position_allowance_snapshot"]), ("-請假", -salary["leave_deduction"]),
                 ("-勞健保", -salary["insurance_snapshot"]), ("-遲到", -salary["late_deduction"])]
        items += [(f"+{x['item_name']}", x["amount"]) for x in additions]
        items += [(f"-{x['item_name']}", -x["amount"]) for x in deductions]
        items.append(("薪資總計", salary["final_salary"]))
        for offset, (label, amount) in enumerate(items, 1):
            ws.cell(row + offset, 1, label); ws.cell(row + offset, 2, amount)
            ws.cell(row + offset, 2).number_format = '#,##0;[Red]-#,##0'
            if label == "薪資總計":
                ws.cell(row + offset, 1).font = ws.cell(row + offset, 2).font = Font(bold=True)
            for col in (1, 2): ws.cell(row + offset, col).border = border
        note_row = row + len(items) + 1
        ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=2)
        ws.cell(note_row, 1, " ".join(filter(None, [salary.get("system_note", ""), salary.get("manual_note", "")])))
        ws.cell(note_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[note_row].height = 34
        row = note_row + 2
    ws.print_area = f"A1:B{max(row - 1, 1)}"
    ws.page_setup.fitToWidth = 1; ws.sheet_properties.pageSetUpPr.fitToPage = True
    output = BytesIO(); wb.save(output); output.seek(0)
    return output.getvalue()
