from pathlib import Path

from utils.database import DatabaseConfig, connect_from_config, initialize_database_with_health
from utils.salary_calculator import calculate_leave_deduction, calculate_salary
from utils.salary_repository import (annual_leave_balance_before_month, delete_salary,
                                     get_month_salaries, get_settled_month_salaries,
                                     list_employees, save_annual_leave_setting, save_employee, save_salary)


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
    salary = {"employee_name_snapshot":"甲","base_salary_snapshot":29500,"attendance_bonus_snapshot":0,
              "cooling_allowance_snapshot":0,"allowance_snapshot":0,"position_allowance_snapshot":0,
              "leave_deduction":0,"insurance_snapshot":0,"late_deduction":0,"final_salary":29500,
              "adjustments":[],"system_note":"","manual_note":"", "standard_hours_snapshot":8,
              "annual_leave_days":1,"annual_leave_hours":4,"annual_leave_entitlement_snapshot":14,
              "annual_leave_balance_after":7.5,"annual_leave_note_snapshot":"歷年制特休14日"}
    from io import BytesIO
    workbook = load_workbook(BytesIO(generate_salary_workbook(2026, 8, [salary, {**salary,"employee_name_snapshot":"乙"}])))
    assert workbook.sheetnames == ["2026年08月薪資"]
    assert "甲" in workbook.active["A1"].value
    assert any("乙" in str(cell.value) for row in workbook.active for cell in row)
    assert any("歷年制特休（個人年度設定＋每月異動）" in str(cell.value) for row in workbook.active for cell in row)
