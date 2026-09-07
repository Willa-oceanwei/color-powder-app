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


def _save_salary_on_connection(conn, data, adjustments, settle, annual_leave_records, now):
    """Write one snapshot using an existing transaction/connection."""
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
    if annual_leave_records is not None:
        conn.execute("UPDATE annual_leave_history SET is_deleted=1,updated_at=? WHERE salary_id=?", (now, salary_id))
        standard_hours = float(data.get("standard_hours_snapshot") or 8)
        for record in annual_leave_records:
            leave_date = str(record.get("date") or "")
            days, hours = float(record.get("days") or 0), float(record.get("hours") or 0)
            equivalent = days + hours / standard_hours
            record_id = str(record.get("id") or uuid.uuid4())
            conn.execute("""INSERT INTO annual_leave_history
                (id,employee_id,date,type,days,hours,equivalent_days,year,month,salary_id,note,created_at,updated_at,is_deleted)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET
                date=excluded.date,days=excluded.days,hours=excluded.hours,equivalent_days=excluded.equivalent_days,
                year=excluded.year,month=excluded.month,salary_id=excluded.salary_id,note=excluded.note,
                updated_at=excluded.updated_at,is_deleted=0""",
                (record_id, data["employee_id"], leave_date, "usage", days, hours, equivalent,
                 data["year"], data["month"], salary_id, record.get("note", ""), now, now))
    return salary_id


def save_salary(config, data: Mapping, adjustments=(), settle=False, annual_leave_records=None):
    """Upsert the sole effective year/month/employee snapshot; never touches employee_master."""
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        return _save_salary_on_connection(
            conn, data, adjustments, settle, annual_leave_records, now,
        )


def save_salaries(config, salaries, settle=False):
    """Save a month of salary blocks through one connection and transaction."""
    now = utc_now_iso()
    salary_ids = []
    with connect_from_config(config) as conn:
        for data in salaries:
            salary_ids.append(_save_salary_on_connection(
                conn, data, data.get("adjustments", ()), settle,
                data.get("annual_leave_records", []), now,
            ))
    return salary_ids


def list_salaries(config, year=None, month=None, name="", employee_id=None):
    sql = "SELECT * FROM salary_monthly WHERE is_deleted=0 AND (? IS NULL OR year=?) AND (? IS NULL OR month=?) AND employee_name_snapshot LIKE ? AND (? IS NULL OR employee_id=?) ORDER BY year DESC,month DESC,employee_id"
    with connect_from_config(config) as conn:
        salaries = _rows(conn.execute(sql, (year, year, month, month, f"%{name.strip()}%", employee_id, employee_id)))
        _attach_salary_details(conn, salaries)
    return salaries


def _attach_salary_details(conn, salaries):
    """Attach child rows with two bulk queries instead of two queries per salary."""
    if not salaries:
        return
    salary_ids = [salary["salary_id"] for salary in salaries]
    placeholders = ",".join("?" for _ in salary_ids)
    adjustments = _rows(conn.execute(
        f"SELECT * FROM salary_adjustments WHERE salary_id IN ({placeholders}) "
        "ORDER BY salary_id,type,adjustment_id",
        tuple(salary_ids),
    ))
    leave_records = _rows(conn.execute(
        f"SELECT * FROM annual_leave_history WHERE salary_id IN ({placeholders}) AND is_deleted=0 "
        "ORDER BY salary_id,CASE WHEN date='' THEN 1 ELSE 0 END,date,id",
        tuple(salary_ids),
    ))
    adjustments_by_salary = {salary_id: [] for salary_id in salary_ids}
    records_by_salary = {salary_id: [] for salary_id in salary_ids}
    for item in adjustments:
        adjustments_by_salary[item["salary_id"]].append(item)
    for item in leave_records:
        records_by_salary[item["salary_id"]].append(item)
    for salary in salaries:
        salary_id = salary["salary_id"]
        salary["adjustments"] = adjustments_by_salary[salary_id]
        salary["annual_leave_records"] = records_by_salary[salary_id]


def get_month_salaries(config, year, month):
    return list_salaries(config, year, month)


def get_settled_month_salaries(config, year, month):
    """Return only persisted, settled snapshots for month-level reporting."""
    return [row for row in list_salaries(config, year, month) if row["status"] == "settled"]


def move_salary_drafts(config, source_year, source_month, target_year, target_month):
    """Atomically move every active draft in one payroll period to another."""
    source = (int(source_year), int(source_month))
    target = (int(target_year), int(target_month))
    if not 1 <= target[1] <= 12:
        raise ValueError("目標月份必須介於 1 到 12 月")
    if source == target:
        raise ValueError("目標月份不可與目前薪資歸屬月份相同")

    now = utc_now_iso()
    with connect_from_config(config) as conn:
        drafts = conn.execute(
            """SELECT salary_id,employee_id FROM salary_monthly
               WHERE year=? AND month=? AND status='draft' AND is_deleted=0""",
            source,
        ).fetchall()
        if not drafts:
            raise ValueError("目前月份沒有可搬移的草稿")

        employee_ids = [row[1] for row in drafts]
        placeholders = ",".join("?" for _ in employee_ids)
        conflicts = conn.execute(
            f"""SELECT employee_name_snapshot FROM salary_monthly
                WHERE year=? AND month=? AND employee_id IN ({placeholders}) AND is_deleted=0""",
            (*target, *employee_ids),
        ).fetchall()
        if conflicts:
            names = "、".join(row[0] for row in conflicts)
            raise ValueError(f"目標月份已有以下人員的薪資資料，未進行搬移：{names}")

        # A soft-deleted snapshot still occupies the database uniqueness key.
        # Remove only those invisible target rows so a previously deleted
        # mistake does not prevent the user from moving the replacement draft.
        deleted_targets = conn.execute(
            f"""SELECT salary_id FROM salary_monthly
                WHERE year=? AND month=? AND employee_id IN ({placeholders}) AND is_deleted=1""",
            (*target, *employee_ids),
        ).fetchall()
        deleted_target_ids = [row[0] for row in deleted_targets]
        if deleted_target_ids:
            deleted_placeholders = ",".join("?" for _ in deleted_target_ids)
            conn.execute(
                f"DELETE FROM salary_adjustments WHERE salary_id IN ({deleted_placeholders})",
                tuple(deleted_target_ids),
            )
            conn.execute(
                f"DELETE FROM annual_leave_history WHERE salary_id IN ({deleted_placeholders})",
                tuple(deleted_target_ids),
            )
            conn.execute(
                f"DELETE FROM salary_monthly WHERE salary_id IN ({deleted_placeholders})",
                tuple(deleted_target_ids),
            )

        conn.execute(
            """UPDATE salary_monthly SET year=?,month=?,updated_at=?
               WHERE year=? AND month=? AND status='draft' AND is_deleted=0""",
            (*target, now, *source),
        )
        salary_ids = [row[0] for row in drafts]
        salary_placeholders = ",".join("?" for _ in salary_ids)
        conn.execute(
            f"""UPDATE annual_leave_history SET year=?,month=?,updated_at=?
                WHERE salary_id IN ({salary_placeholders}) AND is_deleted=0""",
            (*target, now, *salary_ids),
        )
    return len(drafts)


def get_annual_leave_setting(config, employee_id, year):
    with connect_from_config(config) as conn:
        cursor = conn.execute("SELECT * FROM employee_annual_leave_settings WHERE employee_id=? AND year=?", (employee_id, year))
        rows = _rows(cursor)
    return rows[0] if rows else None


def get_annual_leave_contexts(config, employees, year, month):
    """Return settings and pre-month balances for several employees in one connection.

    This replaces the former per-employee setting lookup plus balance lookup, which
    was especially expensive when each statement opened a remote Turso session.
    """
    employees = list(employees)
    if not employees:
        return {}
    employee_ids = [employee["employee_id"] for employee in employees]
    placeholders = ",".join("?" for _ in employee_ids)
    with connect_from_config(config) as conn:
        settings = _rows(conn.execute(
            f"SELECT * FROM employee_annual_leave_settings WHERE year=? "
            f"AND employee_id IN ({placeholders})",
            (year, *employee_ids),
        ))
        # Sum all earlier settled months once.  The opening-month condition is
        # applied below because each employee can have a different opening month.
        usage = _rows(conn.execute(
            f"""SELECT employee_id,month,
                SUM(annual_leave_days + annual_leave_hours /
                    CASE WHEN standard_hours_snapshot > 0 THEN standard_hours_snapshot ELSE 8 END) AS used
                FROM salary_monthly
                WHERE employee_id IN ({placeholders}) AND year=? AND month<?
                  AND status='settled' AND is_deleted=0
                GROUP BY employee_id,month""",
            (*employee_ids, year, month),
        ))
    settings_by_employee = {row["employee_id"]: row for row in settings}
    usage_by_employee = {employee_id: [] for employee_id in employee_ids}
    for row in usage:
        usage_by_employee[row["employee_id"]].append(row)
    contexts = {}
    for employee in employees:
        employee_id = employee["employee_id"]
        setting = settings_by_employee.get(employee_id)
        if setting:
            opening_balance = float(setting["opening_balance"] or 0)
            opening_month = int(setting["opening_month"])
        else:
            opening_balance = float(employee.get("annual_leave_base") or 0)
            opening_month = month
        used = sum(
            float(row["used"] or 0)
            for row in usage_by_employee[employee_id]
            if opening_month <= int(row["month"]) < month
        )
        contexts[employee_id] = {
            "setting": setting,
            "balance": opening_balance - used,
        }
    return contexts


def save_annual_leave_setting(config, employee_id, year, annual_entitlement, opening_balance, opening_month, note=""):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        conn.execute("""INSERT INTO employee_annual_leave_settings
            (employee_id,year,annual_entitlement,opening_balance,opening_month,note,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(employee_id,year) DO UPDATE SET
            annual_entitlement=excluded.annual_entitlement,opening_balance=excluded.opening_balance,
            opening_month=excluded.opening_month,note=excluded.note,updated_at=excluded.updated_at""",
            (employee_id, year, annual_entitlement, opening_balance, opening_month, note, now, now))


def get_employee_salary_note(config, employee_id, year):
    with connect_from_config(config) as conn:
        rows = _rows(conn.execute(
            "SELECT * FROM employee_salary_notes WHERE employee_id=? AND year=?", (employee_id, year)
        ))
    return rows[0] if rows else None


def get_employee_salary_notes(config, employee_ids, year):
    """Return one year's personal salary notes keyed by employee ID."""
    employee_ids = list(dict.fromkeys(employee_ids))
    if not employee_ids:
        return {}
    placeholders = ",".join("?" for _ in employee_ids)
    with connect_from_config(config) as conn:
        rows = _rows(conn.execute(
            f"SELECT * FROM employee_salary_notes WHERE year=? AND employee_id IN ({placeholders})",
            (year, *employee_ids),
        ))
    return {row["employee_id"]: row for row in rows}


def save_employee_salary_note(config, employee_id, year, company_cost_note="", annual_leave_note=""):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        conn.execute("""INSERT INTO employee_salary_notes
            (employee_id,year,company_cost_note,annual_leave_note,created_at,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(employee_id,year) DO UPDATE SET
            company_cost_note=excluded.company_cost_note,annual_leave_note=excluded.annual_leave_note,
            updated_at=excluded.updated_at""",
            (employee_id, year, company_cost_note, annual_leave_note, now, now))


def get_salary_monthly_extras(config, year, month):
    with connect_from_config(config) as conn:
        rows = _rows(conn.execute("SELECT * FROM salary_monthly_extras WHERE year=? AND month=?", (year, month)))
    if not rows:
        return {"employee_values": {}, "previous_value": 0, "monthly_addition": 0, "monthly_total": 0}
    row = rows[0]
    row["employee_values"] = json.loads(row.pop("employee_values_json") or "{}")
    return row


def save_salary_monthly_extras(config, year, month, employee_values, previous_value, monthly_addition, monthly_total):
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        conn.execute("""INSERT INTO salary_monthly_extras
            (year,month,employee_values_json,previous_value,monthly_addition,monthly_total,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(year,month) DO UPDATE SET
            employee_values_json=excluded.employee_values_json,previous_value=excluded.previous_value,
            monthly_addition=excluded.monthly_addition,monthly_total=excluded.monthly_total,
            updated_at=excluded.updated_at""",
            (year, month, json.dumps(employee_values, ensure_ascii=False), previous_value,
             monthly_addition, monthly_total, now, now))


def annual_leave_balance_before_month(config, employee_id, year, month):
    setting = get_annual_leave_setting(config, employee_id, year)
    if setting:
        opening_balance = float(setting["opening_balance"])
        opening_month = int(setting["opening_month"])
    else:
        # Older employee records keep the current balance in annual_leave_base.
        # Treat it as current for the requested month; there is no reliable
        # historical opening month until an employee/year setting is saved.
        with connect_from_config(config) as conn:
            row = conn.execute(
                "SELECT annual_leave_base FROM employee_master WHERE employee_id=?", (employee_id,)
            ).fetchone()
        opening_balance = float(row[0] or 0) if row else 0.0
        opening_month = month
    with connect_from_config(config) as conn:
        row = conn.execute("""SELECT COALESCE(SUM(annual_leave_days + annual_leave_hours /
            CASE WHEN standard_hours_snapshot > 0 THEN standard_hours_snapshot ELSE 8 END), 0)
            FROM salary_monthly WHERE employee_id=? AND year=? AND month>=? AND month<?
            AND status='settled' AND is_deleted=0""",
            (employee_id, year, opening_month, month)).fetchone()
    return opening_balance - float(row[0] or 0)


def list_annual_leave_history(config, employee_id, year):
    with connect_from_config(config) as conn:
        return _rows(conn.execute("""SELECT h.*, s.status AS salary_status, s.is_deleted AS salary_deleted
            FROM annual_leave_history h LEFT JOIN salary_monthly s ON s.salary_id=h.salary_id
            WHERE h.employee_id=? AND h.year=? AND h.is_deleted=0
              AND (s.salary_id IS NULL OR s.is_deleted=0)
            ORDER BY CASE WHEN h.date='' THEN 1 ELSE 0 END,h.date,h.id""", (employee_id, year)))


def save_annual_leave_history_record(config, record):
    now = utc_now_iso()
    record_id = str(record.get("id") or uuid.uuid4())
    standard_hours = float(record.get("standard_hours") or 8)
    days, hours = float(record.get("days") or 0), float(record.get("hours") or 0)
    leave_date = str(record.get("date") or "")
    if leave_date:
        year, month = int(leave_date[:4]), int(leave_date[5:7])
    else:
        year, month = int(record["year"]), int(record["month"])
    with connect_from_config(config) as conn:
        conn.execute("""INSERT INTO annual_leave_history
            (id,employee_id,date,type,days,hours,equivalent_days,year,month,salary_id,note,created_at,updated_at,is_deleted)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET
            date=excluded.date,days=excluded.days,hours=excluded.hours,equivalent_days=excluded.equivalent_days,
            year=excluded.year,month=excluded.month,note=excluded.note,updated_at=excluded.updated_at,is_deleted=0""",
            (record_id, record["employee_id"], leave_date, "usage", days, hours, days + hours / standard_hours,
             year, month, record.get("salary_id"), record.get("note", ""), now, now))
    return record_id


def delete_annual_leave_history_record(config, record_id):
    with connect_from_config(config) as conn:
        conn.execute("UPDATE annual_leave_history SET is_deleted=1,updated_at=? WHERE id=?", (utc_now_iso(), record_id))


def list_settled_salaries_in_range(config, employee_id, start_year, start_month, end_year, end_month):
    start_key, end_key = start_year * 100 + start_month, end_year * 100 + end_month
    rows = list_salaries(config, employee_id=employee_id)
    selected = [row for row in rows if row["status"] == "settled" and start_key <= row["year"] * 100 + row["month"] <= end_key]
    return sorted(selected, key=lambda row: (row["year"], row["month"]))


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
        conn.execute("UPDATE annual_leave_history SET is_deleted=1,updated_at=? WHERE salary_id=?", (now, salary_id))
