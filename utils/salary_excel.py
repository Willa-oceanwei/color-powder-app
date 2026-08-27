"""Generate a compact, landscape, single-sheet monthly payroll report."""
from io import BytesIO


PAYROLL_HEADERS = (
    "月份／姓名", "底薪", "請假", "全勤", "涼水", "津貼", "職務津貼",
    "勞健保", "遲到", "小計", "特別加給", "扣除額", "薪資總計",
)


def _adjustment_total(salary, adjustment_type):
    return sum(
        int(item.get("amount") or 0)
        for item in salary.get("adjustments", [])
        if item.get("type") == adjustment_type
    )


def _leave_used_days(salary):
    hours_per_day = float(salary.get("standard_hours_snapshot") or 8)
    return float(salary.get("annual_leave_days") or 0) + float(salary.get("annual_leave_hours") or 0) / hours_per_day


def _payroll_leave_note(salary):
    """Excel notes contain personal annual-leave/leave facts, never adjustment notes."""
    parts = []
    annual_note = str(salary.get("annual_leave_note_snapshot") or "").strip()
    if annual_note:
        parts.append(annual_note)
    leave_days = float(salary.get("leave_days") or 0)
    leave_hours = float(salary.get("leave_hours") or 0)
    if leave_days or leave_hours:
        parts.append(f"請假{leave_days:g}日{leave_hours:g}小時")
    annual_days = float(salary.get("annual_leave_days") or 0)
    annual_hours = float(salary.get("annual_leave_hours") or 0)
    annual_used = _leave_used_days(salary)
    if annual_used:
        balance = float(salary.get("annual_leave_balance_after") or 0)
        parts.append(f"特休{annual_days:g}日{annual_hours:g}小時，共{annual_used:g}日，餘{balance:g}日")
    return "；".join(parts)


def generate_salary_workbook(year, month, salaries, monthly_extras=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    salaries = list(salaries)
    monthly_extras = monthly_extras or {}
    wb = Workbook()
    ws = wb.active
    ws.title = f"{year}年{month:02d}月薪資"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

    thin = Side(style="thin", color="777777")
    medium = Side(style="medium", color="444444")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    total_fill = PatternFill("solid", fgColor="FFF2CC")
    leave_fill = PatternFill("solid", fgColor="D9EAD3")
    centered = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Every employee receives the same five-row slip: header, values, personal
    # notes, monthly leave note, and one blank separator.
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(PAYROLL_HEADERS))
    title = ws.cell(1, 1, f"{year}年{month:02d}月薪資")
    title.font = Font(name="Microsoft JhengHei", size=14, bold=True)
    title.alignment = centered
    ws.row_dimensions[1].height = 25
    row = 2
    for salary in salaries:
        for column, header in enumerate(PAYROLL_HEADERS, 1):
            cell = ws.cell(row, column, header)
            cell.font = Font(name="Microsoft JhengHei", size=9, bold=True)
            cell.alignment = centered
            cell.fill = header_fill
            cell.border = border
        ws.row_dimensions[row].height = 28
        additions = _adjustment_total(salary, "addition")
        deductions = _adjustment_total(salary, "deduction")
        final_salary = int(salary.get("final_salary") or 0)
        subtotal = final_salary - additions + deductions
        values = (
            f"{month:02d}月份 {salary['employee_name_snapshot']}",
            int(salary.get("base_salary_snapshot") or 0),
            -int(salary.get("leave_deduction") or 0),
            int(salary.get("attendance_bonus_snapshot") or 0),
            int(salary.get("cooling_allowance_snapshot") or 0),
            int(salary.get("allowance_snapshot") or 0),
            int(salary.get("position_allowance_snapshot") or 0),
            -int(salary.get("insurance_snapshot") or 0),
            -int(salary.get("late_deduction") or 0),
            subtotal,
            additions,
            deductions,
            final_salary,
        )
        for column, value in enumerate(values, 1):
            cell = ws.cell(row + 1, column, value)
            cell.font = Font(name="Microsoft JhengHei", size=9, bold=column == 13)
            cell.alignment = centered
            cell.border = border
            if column > 1:
                cell.number_format = '#,##0;[Red]-#,##0;0'
            if column in (10, 13):
                cell.fill = total_fill
        ws.row_dimensions[row + 1].height = 24

        ws.merge_cells(start_row=row + 2, start_column=1, end_row=row + 2, end_column=3)
        ws.merge_cells(start_row=row + 2, start_column=4, end_row=row + 2, end_column=7)
        ws.merge_cells(start_row=row + 2, start_column=8, end_row=row + 2, end_column=13)
        ws.cell(row + 2, 1, "公司負擔：")
        ws.cell(row + 2, 4, salary.get("company_cost_note") or "")
        annual_text = salary.get("annual_leave_personal_note") or salary.get("annual_leave_note_snapshot") or ""
        ws.cell(row + 2, 8, f"歷年制特休：\n{annual_text}" if annual_text else "歷年制特休：")
        for start in (1, 4, 8):
            cell = ws.cell(row + 2, start)
            cell.font = Font(name="Microsoft JhengHei", size=8, bold=start in (1, 8))
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            cell.border = border
        ws.row_dimensions[row + 2].height = 48

        monthly_note = _payroll_leave_note({**salary, "annual_leave_note_snapshot": ""})
        ws.merge_cells(start_row=row + 3, start_column=1, end_row=row + 3, end_column=13)
        note_cell = ws.cell(row + 3, 1, f"當月說明：{monthly_note}" if monthly_note else "當月說明：")
        note_cell.font = Font(name="Microsoft JhengHei", size=8)
        note_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        note_cell.border = Border(left=thin, right=thin, top=thin, bottom=medium)
        ws.row_dimensions[row + 3].height = 22
        ws.row_dimensions[row + 4].height = 9
        row += 5

    # The legacy monthly manual-value area remains once at the bottom.
    extras_start = row
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    ws.cell(row, 1, "每月附加數值區").font = Font(name="Microsoft JhengHei", size=10, bold=True)
    ws.cell(row, 1).fill = leave_fill
    employee_values = monthly_extras.get("employee_values", {})
    for salary in salaries:
        row += 1
        ws.cell(row, 1, salary["employee_name_snapshot"])
        ws.cell(row, 2, float(employee_values.get(salary["employee_id"], 0) or 0))
    for label, key in (("上月", "previous_value"), ("+本月新增", "monthly_addition"), ("餘本月總計", "monthly_total")):
        row += 1
        ws.cell(row, 1, label)
        ws.cell(row, 2, float(monthly_extras.get(key, 0) or 0))
    for current_row in range(extras_start + 1, row + 1):
        for column in (1, 2):
            ws.cell(current_row, column).border = border
            ws.cell(current_row, column).font = Font(name="Microsoft JhengHei", size=9)
        ws.cell(current_row, 2).number_format = '0.##'

    widths = (18, 11, 10, 10, 10, 11, 12, 11, 9, 12, 12, 11, 13)
    for column, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(column)].width = width

    ws.print_area = f"A1:M{max(row, 1)}"
    ws.print_title_rows = "1:1"
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.35, bottom=0.35, header=0.15, footer=0.15)
    ws.sheet_properties.pageSetUpPr.autoPageBreaks = False

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
