"""Privacy-first HR queries for dated annual leave and settled salary totals."""
from datetime import date

import pandas as pd
import streamlit as st

from .salary_excel import generate_salary_total_workbook
from .salary_repository import (
    delete_annual_leave_history_record,
    get_annual_leave_setting,
    list_annual_leave_history,
    list_employees,
    list_settled_salaries_in_range,
    save_annual_leave_history_record,
)


def _employee_selector(employees, key):
    values = [""] + [item["employee_id"] for item in employees]
    return st.selectbox(
        "員工", values, key=key,
        format_func=lambda value: "請選擇" if not value else next(
            f"{item['employee_id']}｜{item['name']}" for item in employees if item["employee_id"] == value
        ),
    )


def _annual_leave_tab(config):
    employees = list_employees(config, include_inactive=True)
    years = [""] + list(range(date.today().year - 10, date.today().year + 3))
    first, second = st.columns(2)
    year = first.selectbox("年度", years, format_func=lambda value: "請選擇" if value == "" else str(value), key="hr_leave_year")
    with second:
        employee_id = _employee_selector(employees, "hr_leave_employee")
    if st.button("查詢特休", disabled=not year or not employee_id):
        st.session_state.hr_leave_query = (employee_id, int(year))
    if not year or not employee_id:
        return
    query = st.session_state.get("hr_leave_query")
    if not query or query != (employee_id, int(year)):
        return
    employee = next(item for item in employees if item["employee_id"] == employee_id)
    setting = get_annual_leave_setting(config, employee_id, int(year)) or {}
    records = list_annual_leave_history(config, employee_id, int(year))
    used = sum(float(item.get("equivalent_days") or 0) for item in records)
    opening = float(setting.get("opening_balance", 0))
    st.markdown(f"<div style='font-size:16px;font-weight:700;'>{year} {employee['name']}</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年度特休", f"{float(setting.get('annual_entitlement', 0)):g} 日")
    c2.metric("期初剩餘", f"{opening:g} 日")
    c3.metric("本年度已使用", f"{used:g} 日")
    c4.metric("目前剩餘", f"{opening-used:g} 日")
    if not records:
        st.info("此年度尚無逐筆特休紀錄。請至「每月薪資」新增特休日期。")
        return
    display = pd.DataFrame([{
        "月份": f"{int(item['month']):02d}", "日期": item["date"] or "未填日期", "日數": item["days"],
        "時數": item["hours"], "換算日數": item["equivalent_days"], "備註": item.get("note", ""),
        "薪資狀態": item.get("salary_status") or "未關聯",
    } for item in records])
    st.dataframe(display, use_container_width=True, hide_index=True)
    selected = st.selectbox("選擇要修改／刪除的紀錄", range(len(records)),
                            format_func=lambda index: f"{records[index]['date'] or '未填日期'}｜{records[index]['equivalent_days']:g}日")
    record = records[selected]
    if record.get("salary_status") == "settled":
        st.warning(f"此特休紀錄已納入 {record['year']}/{int(record['month']):02d} 薪資，修改後請重新確認該月薪資。")
    with st.form(f"edit_leave_record_{record['id']}"):
        has_date = st.checkbox("記錄特休日期", value=bool(record.get("date")), help="日期為非必要欄位。")
        cols = st.columns(3)
        default_date = date.fromisoformat(record["date"][:10]) if record.get("date") else date(int(record["year"]), int(record["month"]), 1)
        leave_date = cols[0].date_input("日期（非必填）", value=default_date, disabled=not has_date)
        days = cols[1].number_input("日數", min_value=0.0, value=float(record["days"]))
        hours = cols[2].number_input("時數", min_value=0.0, value=float(record["hours"]))
        note = st.text_input("備註", value=record.get("note") or "")
        if st.form_submit_button("儲存修改"):
            save_annual_leave_history_record(config, {**record, "date":leave_date.isoformat() if has_date else "", "days":days,
                                                       "hours":hours, "note":note,
                                                       "standard_hours":employee.get("standard_hours", 8)})
            st.toast("特休紀錄已修改；已結算薪資快照不會自動變動")
            st.rerun()
    confirm = st.checkbox("確認刪除此筆特休紀錄", key=f"confirm_delete_leave_{record['id']}")
    if st.button("刪除特休紀錄", disabled=not confirm, key=f"delete_leave_record_{record['id']}"):
        delete_annual_leave_history_record(config, record["id"]); st.toast("特休紀錄已刪除"); st.rerun()


def _salary_total_tab(config):
    employees = list_employees(config, include_inactive=True)
    employee_id = _employee_selector(employees, "hr_salary_employee")
    year_options = [""] + list(range(date.today().year - 10, date.today().year + 3))
    c1, c2, c3, c4 = st.columns(4)
    start_year = c1.selectbox("起始年", year_options, format_func=lambda value:"請選擇" if value == "" else str(value), key="hr_salary_start_year")
    start_month = c2.selectbox("起始月", [""]+list(range(1,13)), format_func=lambda value:"請選擇" if value == "" else f"{value:02d}", key="hr_salary_start_month")
    end_year = c3.selectbox("結束年", year_options, format_func=lambda value:"請選擇" if value == "" else str(value), key="hr_salary_end_year")
    end_month = c4.selectbox("結束月", [""]+list(range(1,13)), format_func=lambda value:"請選擇" if value == "" else f"{value:02d}", key="hr_salary_end_month")
    ready = all(value != "" for value in (employee_id, start_year, start_month, end_year, end_month))
    if st.button("查詢薪資總計", disabled=not ready):
        if int(start_year)*100+int(start_month) > int(end_year)*100+int(end_month):
            st.error("起始年月不可晚於結束年月。")
        else:
            st.session_state.hr_salary_query = (employee_id, int(start_year), int(start_month), int(end_year), int(end_month))
    query = st.session_state.get("hr_salary_query")
    current = (employee_id, int(start_year), int(start_month), int(end_year), int(end_month)) if ready else None
    if not query or query != current:
        return
    rows = list_settled_salaries_in_range(config, *query)
    employee = next(item for item in employees if item["employee_id"] == employee_id)
    st.caption("薪資為月結資料，本查詢以月份為單位統計，且只包含已結算、未刪除的薪資快照。")
    total = sum(float(item.get("final_salary") or 0) for item in rows)
    st.markdown(f"**員工：{employee['name']}　期間：{start_year}/{int(start_month):02d}～{end_year}/{int(end_month):02d}**")
    a, b = st.columns(2); a.metric("已結算月份", f"{len(rows)} 個月"); b.metric("薪資總計", f"{total:,.0f}")
    details = []
    for item in rows:
        additions = sum(int(x.get("amount") or 0) for x in item["adjustments"] if x["type"] == "addition")
        deductions = sum(int(x.get("amount") or 0) for x in item["adjustments"] if x["type"] == "deduction")
        details.append({"年月":f"{item['year']}/{item['month']:02d}", "底薪":item["base_salary_snapshot"],
                        "小計":item["final_salary"]-additions+deductions, "特別加給":additions,
                        "扣除額":deductions, "薪資總計":item["final_salary"]})
    st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)
    if rows:
        start = f"{start_year}{int(start_month):02d}"; end = f"{end_year}{int(end_month):02d}"
        st.download_button("下載薪資總計", generate_salary_total_workbook(employee["name"], start, end, rows),
                           f"{employee['name']}_{start}-{end}_薪資總計.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def render_hr_query(config):
    st.markdown("<div style='font-size:20px;font-weight:700;margin-bottom:0.6rem;'>人力查詢</div>", unsafe_allow_html=True)
    leave_tab, salary_tab = st.tabs(["🏖️ 特休管理", "💰 薪資總計"])
    with leave_tab: _annual_leave_tab(config)
    with salary_tab: _salary_total_tab(config)
