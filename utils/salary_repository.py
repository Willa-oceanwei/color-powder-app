"""Persistence for employee current settings and immutable-by-default salary snapshots."""
from __future__ import annotations

import json
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
        columns = ["employee_name_snapshot", "base_salary_snapshot", "attendance_bonus_snapshot", "cooling_allowance_snapshot", "allowance_snapshot", "position_allowance_snapshot", "insurance_snapshot", "standard_hours_snapshot", "leave_days", "leave_hours", "leave_deduction", "annual_leave_days", "annual_leave_hours", "annual_leave_balance_before", "annual_leave_balance_after", "annual_leave_entitlement_snapshot", "annual_leave_note_snapshot", "late_deduction", "total_additions", "total_deductions", "final_salary", "system_note", "manual_note"]
        values = [data.get(k, "" if "note" in k else 0) for k in columns]
        status = "settled" if settle else "draft"
        conn.execute(f"""INSERT INTO salary_monthly(salary_id,year,month,employee_id,{','.join(columns)},status,created_at,updated_at,settled_at)
            VALUES ({','.join(['?'] * 31)}) ON CONFLICT(year,month,employee_id) DO UPDATE SET
            {','.join(f'{k}=excluded.{k}' for k in columns)},status=excluded.status,updated_at=excluded.updated_at,
            settled_at=CASE WHEN excluded.status='settled' THEN excluded.settled_at ELSE salary_monthly.settled_at END,
            is_deleted=0,deleted_at=NULL""",
            (salary_id, data["year"], data["month"], data["employee_id"], *values, status, now, now, now if settle else None))
        conn.execute("DELETE FROM salary_adjustments WHERE salary_id=?", (salary_id,))
        for item in adjustments:
            conn.execute("INSERT INTO salary_adjustments VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), salary_id, item["type"], item.get("item_name") or "未命名", int(item.get("amount") or 0), item.get("note", "")))
    return salary_id


def list_salaries(config, year=None, month=None, name="", employee_id=None):
    sql = "SELECT * FROM salary_monthly WHERE is_deleted=0 AND (? IS NULL OR year=?) AND (? IS NULL OR month=?) AND employee_name_snapshot LIKE ? AND (? IS NULL OR employee_id=?) ORDER BY year DESC,month DESC,employee_id"
    with connect_from_config(config) as conn:
        salaries = _rows(conn.execute(sql, (year, year, month, month, f"%{name.strip()}%", employee_id, employee_id)))
        for salary in salaries:
            salary["adjustments"] = _rows(conn.execute("SELECT * FROM salary_adjustments WHERE salary_id=? ORDER BY type, adjustment_id", (salary["salary_id"],)))
    return salaries


def get_month_salaries(config, year, month):
    return list_salaries(config, year, month)


def get_settled_month_salaries(config, year, month):
    """Return only persisted, settled snapshots for month-level reporting."""
    return [row for row in list_salaries(config, year, month) if row["status"] == "settled"]


def get_annual_leave_setting(config, employee_id, year):
    with connect_from_config(config) as conn:
        cursor = conn.execute("SELECT * FROM employee_annual_leave_settings WHERE employee_id=? AND year=?", (employee_id, year))
        rows = _rows(cursor)
    return rows[0] if rows else None


def save_annual_leave_setting(config, employee_id, year, annual_entitlement, opening_balance, opening_month, note=""):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        conn.execute("""INSERT INTO employee_annual_leave_settings
            (employee_id,year,annual_entitlement,opening_balance,opening_month,note,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(employee_id,year) DO UPDATE SET
            annual_entitlement=excluded.annual_entitlement,opening_balance=excluded.opening_balance,
            opening_month=excluded.opening_month,note=excluded.note,updated_at=excluded.updated_at""",
            (employee_id, year, annual_entitlement, opening_balance, opening_month, note, now, now))


def annual_leave_balance_before_month(config, employee_id, year, month):
    setting = get_annual_leave_setting(config, employee_id, year)
    if not setting:
        return 0.0
    with connect_from_config(config) as conn:
        row = conn.execute("""SELECT COALESCE(SUM(annual_leave_days + annual_leave_hours /
            CASE WHEN standard_hours_snapshot > 0 THEN standard_hours_snapshot ELSE 8 END), 0)
            FROM salary_monthly WHERE employee_id=? AND year=? AND month>=? AND month<?
            AND status='settled' AND is_deleted=0""",
            (employee_id, year, setting["opening_month"], month)).fetchone()
    return float(setting["opening_balance"]) - float(row[0] or 0)


def delete_salary(config, salary_id):
    """Soft-delete a snapshot while archiving its complete pre-delete state."""
    with connect_from_config(config) as conn:
        cursor = conn.execute("SELECT * FROM salary_monthly WHERE salary_id=? AND is_deleted=0", (salary_id,))
        rows = _rows(cursor)
        if not rows:
            raise ValueError("找不到要刪除的薪資資料")
        adjustments = _rows(conn.execute("SELECT * FROM salary_adjustments WHERE salary_id=?", (salary_id,)))
        now = utc_now_iso()
        conn.execute("INSERT INTO salary_deletion_audit VALUES(?,?,?,?,?)",
                     (str(uuid.uuid4()), salary_id, json.dumps(rows[0], ensure_ascii=False),
                      json.dumps(adjustments, ensure_ascii=False), now))
        conn.execute("UPDATE salary_monthly SET is_deleted=1,deleted_at=?,updated_at=? WHERE salary_id=?",
                     (now, now, salary_id))
