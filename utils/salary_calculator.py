"""Pure, UI-independent salary rules. Monetary results are whole TWD."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping


def default_salary_period(today) -> tuple[int, int]:
    """Return the preceding payroll month, including the January rollover."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def money(value) -> int:
    return int(_d(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_leave_deduction(base_salary, leave_days, leave_hours, monthly_days=30, standard_hours=8) -> int:
    days, hours = _d(monthly_days), _d(standard_hours)
    if days <= 0 or hours <= 0:
        raise ValueError("每月計薪天數與每日工時必須大於 0")
    return money(_d(base_salary) / days * _d(leave_days) + _d(base_salary) / days / hours * _d(leave_hours))


def calculate_attendance_bonus(amount, has_leave: bool, rules: Mapping) -> int:
    return 0 if has_leave and rules.get("leave_affects_attendance", False) else money(amount)


def calculate_allowance(amount, has_leave: bool, rule_key: str, rules: Mapping) -> int:
    return 0 if has_leave and rules.get(rule_key, False) else money(amount)


def calculate_monthly_extra_totals(previous_value, employee_values: Mapping) -> tuple[float, float]:
    """Return the employee-value sum and the carried-forward monthly total."""
    monthly_addition = sum((_d(value) for value in employee_values.values()), Decimal("0"))
    monthly_total = _d(previous_value) + monthly_addition
    return float(monthly_addition), float(monthly_total)


def calculate_annual_leave_balance(balance_before, leave_days, leave_hours, standard_hours=8) -> float:
    """Return remaining annual leave without allowing a negative balance."""
    hours_per_day = _d(standard_hours or 8)
    if hours_per_day <= 0:
        raise ValueError("每日標準工時必須大於 0")
    used = _d(leave_days) + _d(leave_hours) / hours_per_day
    return float(max(Decimal("0"), _d(balance_before) - used))


def reclassify_annual_leave_when_exhausted(
    balance_before, leave_days, leave_hours, annual_leave_days, annual_leave_hours,
) -> tuple[float, float, float, float]:
    """Move requested annual leave to unpaid leave when no balance is available.

    Days and hours stay in their original units so the normal salary deduction
    calculation can process them without introducing rounding conversions.
    """
    if _d(balance_before) > 0:
        return tuple(float(_d(value)) for value in (
            leave_days, leave_hours, annual_leave_days, annual_leave_hours,
        ))
    return (
        float(_d(leave_days) + _d(annual_leave_days)),
        float(_d(leave_hours) + _d(annual_leave_hours)),
        0.0,
        0.0,
    )


def calculate_salary(data: Mapping, additions: Iterable[Mapping] = (), deductions: Iterable[Mapping] = (), rules: Mapping | None = None) -> dict:
    rules = rules or {}
    has_leave = _d(data.get("leave_days")) > 0 or _d(data.get("leave_hours")) > 0
    leave = calculate_leave_deduction(data.get("base_salary_snapshot"), data.get("leave_days"), data.get("leave_hours"), rules.get("monthly_days", 30), data.get("standard_hours_snapshot") or rules.get("standard_hours", 8))
    attendance = calculate_attendance_bonus(data.get("attendance_bonus_snapshot"), has_leave, rules)
    cooling = calculate_allowance(data.get("cooling_allowance_snapshot"), has_leave, "leave_affects_cooling", rules)
    allowance = calculate_allowance(data.get("allowance_snapshot"), has_leave, "leave_affects_allowance", rules)
    extra_add = sum(money(x.get("amount")) for x in additions)
    extra_deduct = sum(money(x.get("amount")) for x in deductions)
    insurance, late = money(data.get("insurance_snapshot")), money(data.get("late_deduction"))
    fixed = money(data.get("base_salary_snapshot")) + attendance + cooling + allowance + money(data.get("position_allowance_snapshot"))
    total_deductions = insurance + leave + late + extra_deduct
    return {"attendance_bonus_snapshot": attendance, "cooling_allowance_snapshot": cooling,
            "allowance_snapshot": allowance, "leave_deduction": leave,
            "total_additions": extra_add, "total_deductions": total_deductions,
            "final_salary": fixed + extra_add - total_deductions}


def generate_salary_note(data: Mapping, additions: Iterable[Mapping] = (), deductions: Iterable[Mapping] = ()) -> str:
    parts = []
    if _d(data.get("leave_days")) or _d(data.get("leave_hours")):
        parts.append(f"本月請假{data.get('leave_days', 0):g}日{data.get('leave_hours', 0):g}小時，請假扣款{money(data.get('leave_deduction')):,}元")
    used = _d(data.get("annual_leave_days")) + _d(data.get("annual_leave_hours")) / _d(data.get("standard_hours_snapshot") or 8)
    if used:
        leave_dates = []
        for record in data.get("annual_leave_records", ()):
            leave_date = str(record.get("date") or "")
            if leave_date:
                display_date = leave_date[5:].replace("-", "/") if len(leave_date) >= 10 else leave_date
                if display_date not in leave_dates:
                    leave_dates.append(display_date)
        date_note = f"，日期{'、'.join(leave_dates)}" if leave_dates else ""
        balance = max(Decimal("0"), _d(data.get("annual_leave_balance_after")))
        parts.append(f"特休{data.get('annual_leave_days', 0):g}日{data.get('annual_leave_hours', 0):g}小時，共{used:g}日{date_note}，結餘{balance:g}日")
    else:
        balance = max(Decimal("0"), _d(data.get(
            "annual_leave_balance_after", data.get("annual_leave_balance_before")
        )))
        parts.append(f"本月特休0日，餘{balance:g}日")
    for item in additions:
        if money(item.get("amount")):
            detail = f"（{item.get('note')}）" if item.get("note") else ""
            parts.append(f"另有{item.get('item_name') or '加給'}{money(item.get('amount')):,}元{detail}")
    for item in deductions:
        if money(item.get("amount")):
            detail = f"（{item.get('note')}）" if item.get("note") else ""
            parts.append(f"另扣{item.get('item_name') or '扣除'}{money(item.get('amount')):,}元{detail}")
    return "；".join(parts) + ("。" if parts else "")
