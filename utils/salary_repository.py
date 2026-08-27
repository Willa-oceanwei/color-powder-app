"""Persistence for employee current settings and immutable-by-default salary snapshots."""
from __future__ import annotations

import uuid
from typing import Mapping

from .database import connect_from_config, utc_now_iso


def _rows(cursor):
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def list_employees(config, include_inactive=False, search=""):
    sql = "SELECT * FROM employee_master WHERE (? OR active=1) AND (employee_id LIKE ? OR name LIKE ?) ORDER BY active DESC, employee_id"
    pattern = f"%{search.strip()}%"
    with connect_from_config(config) as conn:
        return _rows(conn.execute(sql, (int(include_inactive), pattern, pattern)))


def save_employee(config, data: Mapping):
    employee_id, name = str(data.get("employee_id", "")).strip(), str(data.get("name", "")).strip()
    if not employee_id or not name:
        raise ValueError("員工編號與姓名為必填")
    now = utc_now_iso()
    fields = ("join_date", "active", "base_salary", "attendance_bonus", "cooling_allowance", "allowance",
              "position_allowance", "insurance", "standard_hours", "annual_leave_base",
              "special_addition_enabled", "special_addition_amount", "special_addition_note",
              "default_deduction_enabled", "default_deduction_amount", "default_deduction_note", "note")
    defaults = {"active": 1, "standard_hours": 8}
    values = [data.get(k, "" if k == "join_date" or k.endswith("note") else defaults.get(k, 0)) for k in fields]
    with connect_from_config(config) as conn:
        conn.execute(f"""INSERT INTO employee_master(employee_id,name,{','.join(fields)},created_at,updated_at)
            VALUES ({','.join(['?'] * 21)}) ON CONFLICT(employee_id) DO UPDATE SET name=excluded.name,
            {','.join(f'{k}=excluded.{k}' for k in fields)}, updated_at=excluded.updated_at""",
            (employee_id, name, *values, now, now))


def set_employee_active(config, employee_id, active):
    with connect_from_config(config) as conn:
        conn.execute("UPDATE employee_master SET active=?, updated_at=? WHERE employee_id=?", (int(active), utc_now_iso(), employee_id))


def get_rules(config):
    with connect_from_config(config) as conn:
        rows = _rows(conn.execute("SELECT rule_key, rule_value FROM salary_rules"))
    result = {}
    for row in rows:
        value = row["rule_value"]
        if value in ("true", "false"):
            value = value == "true"
        else:
            try: value = float(value)
            except ValueError: pass
        result[row["rule_key"]] = value
    return result


def save_rules(config, rules: Mapping):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        for key, value in rules.items():
            encoded = str(value).lower() if isinstance(value, bool) else str(value)
            conn.execute("INSERT INTO salary_rules VALUES(?,?,?) ON CONFLICT(rule_key) DO UPDATE SET rule_value=excluded.rule_value, updated_at=excluded.updated_at", (key, encoded, now))


def save_salary(config, data: Mapping, adjustments=(), settle=False):
    """Upsert the sole effective year/month/employee snapshot; never touches employee_master."""
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = conn.execute("SELECT salary_id FROM salary_monthly WHERE year=? AND month=? AND employee_id=?", (data["year"], data["month"], data["employee_id"])).fetchone()
        salary_id = old[0] if old else str(data.get("salary_id") or uuid.uuid4())
        columns = ["employee_name_snapshot", "base_salary_snapshot", "attendance_bonus_snapshot", "cooling_allowance_snapshot", "allowance_snapshot", "position_allowance_snapshot", "insurance_snapshot", "standard_hours_snapshot", "leave_days", "leave_hours", "leave_deduction", "annual_leave_days", "annual_leave_hours", "annual_leave_balance_before", "annual_leave_balance_after", "late_deduction", "total_additions", "total_deductions", "final_salary", "system_note", "manual_note"]
        values = [data.get(k, "" if k.endswith("note") else 0) for k in columns]
        status = "settled" if settle else "draft"
        conn.execute(f"""INSERT INTO salary_monthly(salary_id,year,month,employee_id,{','.join(columns)},status,created_at,updated_at,settled_at)
            VALUES ({','.join(['?'] * 29)}) ON CONFLICT(year,month,employee_id) DO UPDATE SET
            {','.join(f'{k}=excluded.{k}' for k in columns)},status=excluded.status,updated_at=excluded.updated_at,
            settled_at=CASE WHEN excluded.status='settled' THEN excluded.settled_at ELSE salary_monthly.settled_at END""",
            (salary_id, data["year"], data["month"], data["employee_id"], *values, status, now, now, now if settle else None))
        conn.execute("DELETE FROM salary_adjustments WHERE salary_id=?", (salary_id,))
        for item in adjustments:
            conn.execute("INSERT INTO salary_adjustments VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), salary_id, item["type"], item.get("item_name") or "未命名", int(item.get("amount") or 0), item.get("note", "")))
    return salary_id


def list_salaries(config, year=None, month=None, name=""):
    sql = "SELECT * FROM salary_monthly WHERE (? IS NULL OR year=?) AND (? IS NULL OR month=?) AND employee_name_snapshot LIKE ? ORDER BY year DESC,month DESC,employee_id"
    with connect_from_config(config) as conn:
        salaries = _rows(conn.execute(sql, (year, year, month, month, f"%{name.strip()}%")))
        for salary in salaries:
            salary["adjustments"] = _rows(conn.execute("SELECT * FROM salary_adjustments WHERE salary_id=? ORDER BY type, adjustment_id", (salary["salary_id"],)))
    return salaries


def get_month_salaries(config, year, month):
    return list_salaries(config, year, month)


def delete_salary(config, salary_id):
    """Explicitly delete one mistaken/test snapshot; employee settings are untouched."""
    with connect_from_config(config) as conn:
        exists = conn.execute("SELECT 1 FROM salary_monthly WHERE salary_id=?", (salary_id,)).fetchone()
        if not exists:
            raise ValueError("找不到要刪除的薪資資料")
        conn.execute("DELETE FROM salary_adjustments WHERE salary_id=?", (salary_id,))
        conn.execute("DELETE FROM salary_monthly WHERE salary_id=?", (salary_id,))
