"""Pure, UI-independent salary rules. Monetary results are whole TWD."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def money(value) -> int:
    return int(_d(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_leave_deduction(base_salary, leave_days, leave_hours, monthly_days=30, standard_hours=8) -> int:
    days, hours = _d(monthly_days), _d(standard_hours)
    if days <= 0 or hours <= 0:
        raise ValueError("每月計薪天數與每日工時必須大於 0")
    return money(_d(base_salary) / days * _d(leave_days) + _d(base_salary) / days / hours * _d(leave_hours))


def validate_dated_leave_records(records: Iterable[Mapping], year: int, month: int,
                                 standard_hours=8) -> list[str]:
    """Return settlement-blocking problems in an employee's dated leave details."""
    hours_per_day = _d(standard_hours)
    if hours_per_day <= 0:
        return ["每日標準工時必須大於 0"]

    dated_totals: dict[str, Decimal] = {}
    dated_counts: dict[str, int] = {}
    problems: list[str] = []
    for index, record in enumerate(records, 1):
        raw_date = str(record.get("date") or "").strip()
        days, hours = _d(record.get("days")), _d(record.get("hours"))
        if days < 0 or hours < 0:
            problems.append(f"第 {index} 筆特休的日數／時數不可小於 0")
        if days == 0 and hours == 0:
            problems.append(f"第 {index} 筆特休尚未填寫日數或時數")
        if not raw_date:
            continue
        try:
            leave_date = date.fromisoformat(raw_date[:10])
        except ValueError:
            problems.append(f"第 {index} 筆特休日期格式不正確：{raw_date}")
            continue
        if (leave_date.year, leave_date.month) != (int(year), int(month)):
            problems.append(f"第 {index} 筆特休日期 {leave_date.isoformat()} 不在結算月份內")
        key = leave_date.isoformat()
        dated_counts[key] = dated_counts.get(key, 0) + 1
        dated_totals[key] = dated_totals.get(key, Decimal("0")) + days + hours / hours_per_day

    for leave_date, count in sorted(dated_counts.items()):
        if count > 1:
            problems.append(f"同一人於 {leave_date} 有 {count} 筆特休紀錄，請合併或確認後再結算")
        if dated_totals[leave_date] > 1:
            problems.append(f"同一人於 {leave_date} 合計 {dated_totals[leave_date]:g} 日，超過單日 1 日")
    return problems


def calculate_attendance_bonus(amount, has_leave: bool, rules: Mapping) -> int:
    return 0 if has_leave and rules.get("leave_affects_attendance", False) else money(amount)


def calculate_allowance(amount, has_leave: bool, rule_key: str, rules: Mapping) -> int:
    return 0 if has_leave and rules.get(rule_key, False) else money(amount)


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
        parts.append(f"特休{data.get('annual_leave_days', 0):g}日{data.get('annual_leave_hours', 0):g}小時，共{used:g}日，結餘{_d(data.get('annual_leave_balance_after')):g}日")
    for item in additions:
        if money(item.get("amount")):
            detail = f"（{item.get('note')}）" if item.get("note") else ""
            parts.append(f"另有{item.get('item_name') or '加給'}{money(item.get('amount')):,}元{detail}")
    for item in deductions:
        if money(item.get("amount")):
            detail = f"（{item.get('note')}）" if item.get("note") else ""
            parts.append(f"另扣{item.get('item_name') or '扣除'}{money(item.get('amount')):,}元{detail}")
    return "；".join(parts) + ("。" if parts else "")
