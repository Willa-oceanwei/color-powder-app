from pathlib import Path

from utils.database import DatabaseConfig, connect_from_config, initialize_database_with_health
from utils.salary_calculator import calculate_leave_deduction, calculate_salary
from utils.salary_excel import _monthly_summary, _payroll_leave_note
from utils.salary_repository import (annual_leave_balance_before_month, delete_salary,
                                     get_annual_leave_setting, get_employee_salary_note, get_month_salaries,
                                     get_salary_monthly_extras, get_settled_month_salaries,
                                     list_employees, save_annual_leave_setting, save_employee, save_salary)
from utils.salary_repository import save_employee_salary_note, save_salary_monthly_extras


def test_salary_snapshot_survives_employee_raise(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "salary.db")
    initialize_database_with_health(config)
    employee = {"employee_id":"E001", "name":"王美文", "join_date":"2026-01-01", "active":1,
                "base_salary":29500, "attendance_bonus":2000, "cooling_allowance":500,
                "allowance":3100, "position_allowance":0, "insurance":1196,
                "standard_hours":8, "annual_leave_base":11,
                "special_addition_enabled":1, "special_addition_amount":1800,
                "special_addition_note":"每月預設", "default_deduction_enabled":1,
                "default_deduction_amount":500, "default_deduction_note":"借支", "note":""}
    save_employee(config, employee)
    snapshot = {"year":2026,"month":8,"employee_id":"E001","employee_name_snapshot":"王美文",
                "base_salary_snapshot":29500,"attendance_bonus_snapshot":2000,"cooling_allowance_snapshot":500,
                "allowance_snapshot":3100,"position_allowance_snapshot":0,"insurance_snapshot":1196,
                "standard_hours_snapshot":8,"leave_days":0,"leave_hours":0,"annual_leave_days":0,
                "annual_leave_hours":0,"annual_leave_balance_before":11,"annual_leave_balance_after":11,
                "late_deduction":0,"manual_note":"","system_note":""}
    snapshot.update(calculate_salary(snapshot))
    save_salary(config, snapshot, settle=True)
    save_employee(config, {**employee, "base_salary":32000})
    updated = list_employees(config)[0]
    assert updated["base_salary"] == 32000
    assert updated["special_addition_amount"] == 1800
    assert updated["default_deduction_note"] == "借支"
    assert get_month_salaries(config, 2026, 8)[0]["base_salary_snapshot"] == 29500


def test_mistaken_salary_can_be_deleted_without_deleting_employee(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "delete-salary.db")
    initialize_database_with_health(config)
    save_employee(config, {"employee_id":"E001", "name":"測試員工", "join_date":"2026-01-01"})
    data = {"year":2026, "month":7, "employee_id":"E001", "employee_name_snapshot":"測試員工"}
    data.update(calculate_salary(data))
    salary_id = save_salary(config, data, [{"type":"addition", "item_name":"特別加給", "amount":100, "note":"測試"}])
    assert get_settled_month_salaries(config, 2026, 7) == []

    delete_salary(config, salary_id)

    assert get_month_salaries(config, 2026, 7) == []
    assert list_employees(config)[0]["employee_id"] == "E001"
    with connect_from_config(config) as conn:
        assert conn.execute("SELECT is_deleted, deleted_at FROM salary_monthly WHERE salary_id=?", (salary_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM salary_deletion_audit WHERE salary_id=?", (salary_id,)).fetchone()[0] == 1


def test_month_report_returns_only_settled_snapshots(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "settled-report.db")
    initialize_database_with_health(config)
    for employee_id, name in (("E1", "甲"), ("E2", "乙")):
        save_employee(config, {"employee_id":employee_id, "name":name, "join_date":"2026-01-01"})
        data = {"year":2026, "month":7, "employee_id":employee_id, "employee_name_snapshot":name}
        data.update(calculate_salary(data))
        save_salary(config, data, settle=employee_id == "E1")

    settled = get_settled_month_salaries(config, 2026, 7)
    assert [row["employee_id"] for row in settled] == ["E1"]


def test_personal_annual_leave_opening_balance_and_monthly_usage(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "annual-leave.db")
    initialize_database_with_health(config)
    save_employee(config, {"employee_id":"E1", "name":"甲", "join_date":"2026-01-01", "standard_hours":8})
    save_annual_leave_setting(config, "E1", 2026, 14, 9, 8, "歷年制特休14日")
    august = {"year":2026, "month":8, "employee_id":"E1", "employee_name_snapshot":"甲",
              "standard_hours_snapshot":8, "annual_leave_days":1, "annual_leave_hours":4,
              "annual_leave_entitlement_snapshot":14, "annual_leave_note_snapshot":"歷年制特休14日",
              "annual_leave_balance_before":9, "annual_leave_balance_after":7.5}
    august.update(calculate_salary(august))
    save_salary(config, august, settle=True)

    assert annual_leave_balance_before_month(config, "E1", 2026, 9) == 7.5
    saved = get_settled_month_salaries(config, 2026, 8)[0]
    assert saved["annual_leave_entitlement_snapshot"] == 14
    assert saved["annual_leave_balance_after"] == 7.5


def test_leave_rounding_and_same_sheet_excel():
    import pytest
    openpyxl = pytest.importorskip("openpyxl")
    from openpyxl import load_workbook
    from utils.salary_excel import generate_salary_workbook
    assert calculate_leave_deduction(29500, 1, 2, 30, 8) == 1229
    salary = {"employee_id":"E1","employee_name_snapshot":"甲","base_salary_snapshot":29500,"attendance_bonus_snapshot":3000,
              "cooling_allowance_snapshot":500,"allowance_snapshot":3000,"position_allowance_snapshot":1000,
              "leave_days":1,"leave_hours":2,"leave_deduction":1229,"insurance_snapshot":2168,
              "late_deduction":30,"final_salary":35373,
              "adjustments":[{"type":"addition","item_name":"特別加給","amount":1800,"note":"餐費"}],
              "system_note":"另有特別加給1,800元（餐費）。","manual_note":"8/15補發制服費", "standard_hours_snapshot":8,
              "annual_leave_days":1,"annual_leave_hours":4,"annual_leave_entitlement_snapshot":14,
              "annual_leave_balance_after":7.5,"annual_leave_note_snapshot":"歷年制特休14日"}
    from io import BytesIO
    first = {**salary, "company_cost_note":"甲公司負擔", "annual_leave_personal_note":"甲歷年制說明"}
    salaries = [first] + [
        {**salary, "employee_id":f"E{index}", "employee_name_snapshot":name,
         "company_cost_note":f"{name}公司負擔", "annual_leave_personal_note":f"{name}歷年制說明"}
        for index, name in enumerate(("乙", "丙", "丁", "戊"), 2)
    ]
    extras = {"employee_values":{"E1":30,"E2":0,"E3":10,"E4":0,"E5":5}, "previous_value":13873,
              "monthly_addition":30, "monthly_total":13903}
    workbook = load_workbook(BytesIO(generate_salary_workbook(2026, 8, salaries, extras)))
    assert workbook.sheetnames == ["2026年08月薪資"]
    sheet = workbook.active
    assert sheet.max_column == 13
    assert sheet["A1"].value == "2026年08月薪資"
    assert [cell.value for cell in sheet[2]] == ["月份／姓名", "底薪", "請假", "全勤", "涼水", "津貼",
                                                   "職務津貼", "勞健保", "遲到", "小計", "特別加給", "扣除額", "薪資總計"]
    assert [cell.value for cell in sheet[3]] == ["08月份 甲", 29500, -1229, 3000, 500, 3000, 1000,
                                                   -2168, -30, 33573, 1800, 0, 35373]
    assert "請假1日2小時" in sheet["A4"].value
    assert "特休1日4小時，共1.5日，餘7.5日" in sheet["A4"].value
    assert "8/15補發制服費" in sheet["A4"].value
    assert sheet["D4"].value == "公司負擔：\n甲公司負擔"
    assert "甲歷年制說明" in sheet["H4"].value
    assert sheet["A5"].value == "上月13,873 + 本月新增30 = 本月總計13,903"
    assert "餐費" not in sheet["A4"].value
    assert sum(cell.value == "底薪" for row in sheet for cell in row) == 5
    assert any("乙" in str(cell.value) for row in sheet for cell in row)
    assert not any(cell.value == "歷年制特休" for row in sheet for cell in row)
    assert not any(cell.value == "每月附加數值區" for row in sheet for cell in row)
    assert sum(cell.value == "上月13,873 + 本月新增30 = 本月總計13,903" for row in sheet for cell in row) == 5
    assert sheet.max_row == 25
    assert sheet.sheet_properties.pageSetUpPr.fitToPage
    assert sheet.page_setup.orientation == "landscape"
    assert sheet.page_setup.fitToWidth == 1


def test_excel_note_contains_leave_only():
    salary = {"leave_days":1, "leave_hours":2, "annual_leave_days":1, "annual_leave_hours":4,
              "standard_hours_snapshot":8, "annual_leave_balance_after":7.5,
              "system_note":"另有特別加給1,800元（餐費）。"}
    note = _payroll_leave_note(salary)
    assert note == "請假1日2小時；特休1日4小時，共1.5日，餘7.5日"
    assert "餐費" not in note
    assert _monthly_summary({"previous_value":13873, "monthly_addition":30, "monthly_total":13903}) == (
        "上月13,873 + 本月新增30 = 本月總計13,903"
    )


def test_annual_leave_settings_are_scoped_by_employee_and_year(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "personal-annual-leave.db")
    initialize_database_with_health(config)
    for employee_id, name in (("E1", "甲"), ("E2", "乙")):
        save_employee(config, {"employee_id":employee_id, "name":name, "join_date":"2026-01-01"})
    save_annual_leave_setting(config, "E1", 2026, 14, 9, 8, "甲的2026年說明")
    save_annual_leave_setting(config, "E1", 2027, 15, 15, 1, "甲的2027年說明")
    save_annual_leave_setting(config, "E2", 2026, 10, 6, 8, "乙的2026年說明")

    assert get_annual_leave_setting(config, "E1", 2026)["note"] == "甲的2026年說明"
    assert get_annual_leave_setting(config, "E1", 2027)["annual_entitlement"] == 15
    assert get_annual_leave_setting(config, "E2", 2026)["note"] == "乙的2026年說明"


def test_personal_salary_notes_and_monthly_extras_are_editable(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "salary-notes.db")
    initialize_database_with_health(config)
    save_employee(config, {"employee_id":"E1", "name":"甲", "join_date":"2026-01-01"})
    save_employee_salary_note(config, "E1", 2026, "公司負擔A", "特休說明A")
    save_employee_salary_note(config, "E1", 2027, "公司負擔B", "特休說明B")
    save_employee_salary_note(config, "E1", 2026, "公司負擔A-更新", "特休說明A-更新")
    assert get_employee_salary_note(config, "E1", 2026)["company_cost_note"] == "公司負擔A-更新"
    assert get_employee_salary_note(config, "E1", 2027)["annual_leave_note"] == "特休說明B"

    save_salary_monthly_extras(config, 2026, 7, {"E1":30}, 13873, 30, 13903)
    extras = get_salary_monthly_extras(config, 2026, 7)
    assert extras["employee_values"] == {"E1":30}
    assert extras["monthly_total"] == 13903
