from pathlib import Path

from utils.database import DatabaseConfig, initialize_database_with_health
from utils.salary_calculator import calculate_leave_deduction, calculate_salary
from utils.salary_repository import list_employees, save_employee, save_salary, get_month_salaries


def test_salary_snapshot_survives_employee_raise(tmp_path: Path):
    config = DatabaseConfig("sqlite", tmp_path / "salary.db")
    initialize_database_with_health(config)
    employee = {"employee_id":"E001", "name":"王美文", "join_date":"2026-01-01", "active":1,
                "base_salary":29500, "attendance_bonus":2000, "cooling_allowance":500,
                "allowance":3100, "position_allowance":0, "insurance":1196,
                "standard_hours":8, "annual_leave_base":11, "note":""}
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
    assert list_employees(config)[0]["base_salary"] == 32000
    assert get_month_salaries(config, 2026, 8)[0]["base_salary_snapshot"] == 29500


def test_leave_rounding_and_same_sheet_excel():
    import pytest
    openpyxl = pytest.importorskip("openpyxl")
    from openpyxl import load_workbook
    from utils.salary_excel import generate_salary_workbook
    assert calculate_leave_deduction(29500, 1, 2, 30, 8) == 1229
    salary = {"employee_name_snapshot":"甲","base_salary_snapshot":29500,"attendance_bonus_snapshot":0,
              "cooling_allowance_snapshot":0,"allowance_snapshot":0,"position_allowance_snapshot":0,
              "leave_deduction":0,"insurance_snapshot":0,"late_deduction":0,"final_salary":29500,
              "adjustments":[],"system_note":"","manual_note":""}
    from io import BytesIO
    workbook = load_workbook(BytesIO(generate_salary_workbook(2026, 8, [salary, {**salary,"employee_name_snapshot":"乙"}])))
    assert workbook.sheetnames == ["2026年08月薪資"]
    assert "甲" in workbook.active["A1"].value
    assert any("乙" in str(cell.value) for row in workbook.active for cell in row)
