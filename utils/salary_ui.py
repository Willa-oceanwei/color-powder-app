"""Streamlit salary-management page; business rules and persistence live elsewhere."""
from datetime import date
from calendar import monthrange

import pandas as pd
import streamlit as st

from .salary_calculator import calculate_salary, generate_salary_note, validate_dated_leave_records
from .salary_excel import generate_salary_workbook
from .salary_repository import (annual_leave_balance_before_month, delete_salary,
                                get_annual_leave_setting, get_employee_salary_note, get_month_salaries, get_rules,
                                get_salary_monthly_extras,
                                get_settled_month_salaries, list_employees, list_salaries,
                                save_annual_leave_setting, save_employee, save_employee_salary_note,
                                save_rules, save_salary, save_salary_monthly_extras,
                                set_employee_active)


MONEY_FIELDS = ("base_salary", "attendance_bonus", "cooling_allowance", "allowance", "position_allowance", "insurance")


def _employee_tab(config):
    mode = st.radio("員工資料操作", ["新增員工", "修改員工"], horizontal=True)
    search = st.text_input("搜尋員工編號／姓名", key="salary_employee_search") if mode == "修改員工" else ""
    employees = list_employees(config, True, search)
    if mode == "修改員工" and not employees:
        st.info("找不到可修改的員工資料。")
        return
    current = {}
    if mode == "修改員工":
        selected_id = st.selectbox("選擇要修改的員工", [x["employee_id"] for x in employees],
                                   format_func=lambda value: next(f"{x['employee_id']}｜{x['name']} {'(停用)' if not x['active'] else ''}" for x in employees if x["employee_id"] == value))
        current = next(x for x in employees if x["employee_id"] == selected_id)
    employee_key = current.get("employee_id", "new")
    with st.form(f"employee_salary_setting_{employee_key}"):
        a, b, c, d = st.columns(4)
        employee_id = a.text_input("員工編號", value=str(current.get("employee_id", "")), disabled=bool(current), key=f"employee_id_{employee_key}")
        name = b.text_input("姓名", value=current.get("name", ""), key=f"employee_name_{employee_key}")
        join_date = c.date_input("到職日", value=date.fromisoformat(current.get("join_date") or date.today().isoformat()), key=f"employee_join_{employee_key}")
        active = d.toggle("在職狀態", value=bool(current.get("active", 1)), key=f"employee_active_{employee_key}")
        values = {}
        columns = st.columns(3)
        names = {"base_salary":"底薪", "attendance_bonus":"全勤", "cooling_allowance":"涼水", "allowance":"固定津貼", "position_allowance":"職務津貼", "insurance":"勞健保扣款"}
        for idx, field in enumerate(MONEY_FIELDS):
            values[field] = columns[idx % 3].number_input(names[field], min_value=0, step=100, value=int(current.get(field, 0)), key=f"employee_{field}_{employee_key}")
        standard_hours = st.number_input("每日標準工時", min_value=0.5, value=float(current.get("standard_hours", 8)), key=f"employee_hours_{employee_key}")
        st.markdown("##### 每月預設彈性項目")
        add_enabled = st.toggle("預設啟用特別加給", value=bool(current.get("special_addition_enabled", 0)), key=f"employee_special_enabled_{employee_key}")
        ca, cn = st.columns([1, 2])
        add_amount = ca.number_input("特別加給預設金額", min_value=0, value=int(current.get("special_addition_amount", 0)), key=f"employee_special_amount_{employee_key}")
        add_note = cn.text_input("特別加給預設說明", value=current.get("special_addition_note") or "", key=f"employee_special_note_{employee_key}")
        deduct_enabled = st.toggle("預設啟用扣除額", value=bool(current.get("default_deduction_enabled", 0)), key=f"employee_deduct_enabled_{employee_key}")
        da, dn = st.columns([1, 2])
        deduct_amount = da.number_input("扣除額預設金額", min_value=0, value=int(current.get("default_deduction_amount", 0)), key=f"employee_deduct_amount_{employee_key}")
        deduct_note = dn.text_input("扣除額預設說明", value=current.get("default_deduction_note") or "", key=f"employee_deduct_note_{employee_key}")
        note = st.text_area("備註", value=current.get("note", ""), key=f"employee_note_{employee_key}")
        submit_label = "新增員工" if not current else "儲存修改"
        if st.form_submit_button(submit_label, type="primary"):
            save_employee(config, {"employee_id":employee_id, "name":name, "join_date":join_date.isoformat(), "active":active,
                **values, "standard_hours":standard_hours, "annual_leave_base":current.get("annual_leave_base", 0),
                "special_addition_enabled":add_enabled, "special_addition_amount":add_amount, "special_addition_note":add_note,
                "default_deduction_enabled":deduct_enabled, "default_deduction_amount":deduct_amount,
                "default_deduction_note":deduct_note, "note":note})
            st.toast("員工目前設定已儲存；歷史快照不受影響"); st.rerun()
    if current and st.button("停用／離職" if current.get("active") else "恢復在職"):
        set_employee_active(config, current["employee_id"], not current.get("active")); st.rerun()
    active_count = len(list_employees(config))
    st.caption(f"目前共有 {active_count} 筆在職的員工資料。為保護薪資隱私，本頁不直接攤開完整清單；請使用上方「修改員工」搜尋及選取。")


def _new_block(employee, annual_setting=None, leave_balance=0):
    adjustments = []
    if employee.get("special_addition_enabled"):
        adjustments.append({"type":"addition", "item_name":"特別加給", "amount":employee.get("special_addition_amount", 0), "note":employee.get("special_addition_note") or ""})
    if employee.get("default_deduction_enabled"):
        adjustments.append({"type":"deduction", "item_name":"扣除額", "amount":employee.get("default_deduction_amount", 0), "note":employee.get("default_deduction_note") or ""})
    return {"employee_id": employee["employee_id"], "employee_name_snapshot": employee["name"],
            **{f"{k}_snapshot": employee[k] for k in MONEY_FIELDS}, "standard_hours_snapshot": employee["standard_hours"],
            "annual_leave_entitlement_snapshot": (annual_setting or {}).get("annual_entitlement", 0),
            "annual_leave_note_snapshot": (annual_setting or {}).get("note", ""),
            "annual_leave_balance_before": leave_balance, "leave_days":0.0, "leave_hours":0.0,
            "annual_leave_days":0.0, "annual_leave_hours":0.0, "late_deduction":0, "manual_note":"",
            "annual_leave_records":[], "adjustments":adjustments}


def _monthly_tab(config):
    now = date.today(); ycol, mcol = st.columns(2)
    year = ycol.selectbox("年份", range(now.year - 5, now.year + 3), index=5, key="salary_year")
    month = mcol.selectbox("月份", range(1, 13), index=now.month - 1, key="salary_month")
    period = f"{year:04d}-{month:02d}"
    if st.session_state.get("salary_period") != period:
        st.session_state.salary_period = period
        st.session_state.salary_blocks = get_month_salaries(config, year, month)
    blocks = st.session_state.setdefault("salary_blocks", [])
    employees = list_employees(config)
    by_id = {x["employee_id"]: x for x in employees}
    def new_month_block(employee):
        setting = get_annual_leave_setting(config, employee["employee_id"], year)
        balance = annual_leave_balance_before_month(config, employee["employee_id"], year, month)
        return _new_block(employee, setting, balance)
    if st.button("＋ 新增人員", disabled=not employees):
        available = next((x for x in employees if x["employee_id"] not in {b.get("employee_id") for b in blocks}), employees[0])
        blocks.append(new_month_block(available)); st.rerun()
    rules = get_rules(config)
    for index, block in enumerate(list(blocks)):
        with st.container(border=True):
            top, remove = st.columns([5, 1])
            options = list(by_id)
            current_id = block.get("employee_id")
            if current_id not in options: options.insert(0, current_id)
            selected_id = top.selectbox("姓名", options, index=options.index(current_id), format_func=lambda x: by_id.get(x, {"name":block.get("employee_name_snapshot", x)})["name"], key=f"sal_emp_{period}_{index}")
            if selected_id != current_id:
                blocks[index] = new_month_block(by_id[selected_id]); st.rerun()
            if remove.button("－ 移除此人員", key=f"sal_remove_{period}_{index}"):
                blocks.pop(index); st.rerun()
            labels = [("base_salary_snapshot","底薪"),("attendance_bonus_snapshot","全勤"),("cooling_allowance_snapshot","涼水"),("allowance_snapshot","固定津貼"),("position_allowance_snapshot","職務津貼"),("insurance_snapshot","勞健保")]
            cols = st.columns(3)
            for pos, (field, label) in enumerate(labels): block[field] = cols[pos % 3].number_input(label, min_value=0, value=int(block.get(field, 0)), key=f"{field}_{period}_{index}")
            cols = st.columns(2)
            for pos, (field, label) in enumerate((("leave_days","請假日數"),("leave_hours","請假時數"))):
                block[field] = cols[pos].number_input(label, min_value=0.0, value=float(block.get(field, 0)), key=f"{field}_{period}_{index}")
            st.markdown("##### 特休日期明細")
            records = block.setdefault("annual_leave_records", [])
            if st.button("＋ 新增特休紀錄", key=f"add_leave_record_{period}_{index}"):
                records.append({"date":"", "days":0.0, "hours":0.0, "note":""})
                st.rerun()
            for record_index, record in enumerate(list(records)):
                record_cols = st.columns([0.8, 1.4, 0.8, 0.8, 2, 0.7])
                has_date = record_cols[0].checkbox(
                    "記日期", value=bool(record.get("date")), key=f"leave_has_date_{period}_{index}_{record_index}",
                    help="日期為非必要欄位；若只想記錄本月合計可不勾選。",
                )
                raw_date = record.get("date") or date(year, month, 1).isoformat()
                record_date = date.fromisoformat(str(raw_date)[:10])
                selected_date = record_cols[1].date_input(
                    "特休日期（非必填）", value=record_date, min_value=date(year, month, 1),
                    max_value=date(year, month, monthrange(year, month)[1]),
                    key=f"leave_date_{period}_{index}_{record_index}",
                    disabled=not has_date,
                )
                record["date"] = selected_date.isoformat() if has_date else ""
                record["days"] = record_cols[2].number_input(
                    "日數", min_value=0.0, value=float(record.get("days", 0)),
                    key=f"leave_days_{period}_{index}_{record_index}",
                )
                record["hours"] = record_cols[3].number_input(
                    "時數", min_value=0.0, value=float(record.get("hours", 0)),
                    key=f"leave_hours_{period}_{index}_{record_index}",
                )
                record["note"] = record_cols[4].text_input(
                    "備註", value=record.get("note") or "", key=f"leave_note_{period}_{index}_{record_index}",
                )
                if record_cols[5].button("刪除", key=f"delete_leave_{period}_{index}_{record_index}"):
                    records.pop(record_index); st.rerun()
            if records:
                block["annual_leave_days"] = sum(float(record.get("days") or 0) for record in records)
                block["annual_leave_hours"] = sum(float(record.get("hours") or 0) for record in records)
            elif block.get("salary_id") and (block.get("annual_leave_days") or block.get("annual_leave_hours")):
                st.warning("此筆為舊有月合計，尚無日期明細；目前保留原合計。新增日期紀錄後將改以逐筆明細自動合計。")
            else:
                block["annual_leave_days"] = 0.0
                block["annual_leave_hours"] = 0.0
            block["late_deduction"] = st.number_input("遲到扣款", min_value=0, value=int(block.get("late_deduction", 0)), key=f"late_{period}_{index}")
            before = float(block.get("annual_leave_balance_before", 0)); used = block["annual_leave_days"] + block["annual_leave_hours"] / float(block.get("standard_hours_snapshot") or 8)
            block["annual_leave_balance_after"] = before - used
            entitlement = float(block.get("annual_leave_entitlement_snapshot", 0))
            st.caption(f"年度核定 {entitlement:g} 日；本月使用 {used:g} 日；使用前 {before:g} 日，使用後 {before-used:g} 日")
            st.markdown("##### 當月彈性項目")
            for kind, title, item_name in (("addition", "特別加給", "特別加給"), ("deduction", "扣除額", "扣除額")):
                adjustments = block.setdefault("adjustments", [])
                item = next((x for x in adjustments if x["type"] == kind), None)
                enabled = st.toggle(f"啟用{title}", value=item is not None, key=f"{kind}_enabled_{period}_{index}")
                if enabled:
                    if item is None:
                        item = {"type":kind, "item_name":item_name, "amount":0, "note":""}
                        adjustments.append(item)
                    amount_col, note_col = st.columns([1, 2])
                    item["item_name"] = item_name
                    item["amount"] = amount_col.number_input(f"{title}金額", min_value=0, value=int(item.get("amount", 0)), key=f"{kind}_amount_{period}_{index}")
                    item["note"] = note_col.text_input(f"{title}說明", value=item.get("note") or "", key=f"{kind}_note_{period}_{index}", help="餐費、獎金或借支原因等內容統一填在此處，不再細分類別。")
                elif item is not None:
                    adjustments.remove(item)
            additions = [x for x in block["adjustments"] if x["type"] == "addition"]; deductions = [x for x in block["adjustments"] if x["type"] == "deduction"]
            block.update(calculate_salary(block, additions, deductions, rules)); block["system_note"] = generate_salary_note(block, additions, deductions)
            block["manual_note"] = st.text_area("人工備註", block.get("manual_note", ""), key=f"manual_{period}_{index}")
            st.markdown(f"**薪資總計：{block['final_salary']:,} 元**"); st.caption(block["system_note"] or "本月無特殊說明")
    preflight_problems = []
    for block in blocks:
        employee_name = block.get("employee_name_snapshot") or block.get("employee_id") or "未指定人員"
        preflight_problems.extend(
            f"{employee_name}：{problem}" for problem in validate_dated_leave_records(
                block.get("annual_leave_records", []), year, month,
                block.get("standard_hours_snapshot") or 8,
            )
        )
    st.markdown("##### 結算前除錯")
    if preflight_problems:
        st.error("除錯未通過，請先修正下列資料；系統不會進行正式結算：\n\n- " + "\n- ".join(preflight_problems))
    else:
        st.success("除錯通過：未發現重複日期、單日超過 1 日或無效的特休明細。")
    if st.button("重新執行結算前除錯", disabled=not blocks):
        st.toast("除錯完成" if not preflight_problems else f"發現 {len(preflight_problems)} 個問題")

    c1,c2 = st.columns(2)
    if c1.button("儲存草稿", disabled=not blocks):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"], annual_leave_records=block.get("annual_leave_records", []))
        st.toast("草稿已儲存")
    if c2.button("結算薪資", type="primary", disabled=not blocks or bool(preflight_problems),
                 help="請先修正結算前除錯問題" if preflight_problems else None):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"], settle=True, annual_leave_records=block.get("annual_leave_records", []))
        st.toast("正式薪資快照已結算／更新")

    monthly_extras = get_salary_monthly_extras(config, year, month)
    with st.expander("每月附加數值區"):
        st.caption("可先完成所有欄位再一次儲存；儲存後會更新本月每位員工薪資條的當月說明。")
        with st.form(f"monthly_extras_form_{period}"):
            employee_values = {}
            extra_columns = st.columns(3)
            for position, employee in enumerate(employees):
                employee_values[employee["employee_id"]] = extra_columns[position % 3].number_input(
                    employee["name"], value=float(monthly_extras["employee_values"].get(employee["employee_id"], 0)),
                    key=f"monthly_extra_employee_{period}_{employee['employee_id']}",
                )
            previous_col, addition_col, total_col = st.columns(3)
            previous_value = previous_col.number_input("上月", value=float(monthly_extras.get("previous_value", 0)), key=f"monthly_extra_previous_{period}")
            monthly_addition = addition_col.number_input("+本月新增", value=float(monthly_extras.get("monthly_addition", 0)), key=f"monthly_extra_addition_{period}")
            monthly_total = total_col.number_input("餘本月總計", value=float(monthly_extras.get("monthly_total", 0)), key=f"monthly_extra_total_{period}")
            if st.form_submit_button("儲存每月附加數值"):
                save_salary_monthly_extras(config, year, month, employee_values, previous_value, monthly_addition, monthly_total)
                st.toast("每月附加數值已儲存，Excel 將使用最新數值")
                st.rerun()

    # 月份層級報表：只從資料庫重新讀取已結算快照，不使用畫面草稿。
    month_rows = get_month_salaries(config, year, month)
    settled_rows = get_settled_month_salaries(config, year, month)
    payroll_employee_ids = {employee["employee_id"] for employee in employees}
    payroll_employee_ids.update(row["employee_id"] for row in month_rows)
    total_people = len(payroll_employee_ids)
    settled_people = len({row["employee_id"] for row in settled_rows})
    st.divider()
    st.markdown("<div style='font-size:16px;font-weight:700;'>本月薪資表</div>", unsafe_allow_html=True)
    st.caption(f"當月已結算 {settled_people} / 總人數 {total_people}")
    if settled_people < total_people:
        st.warning("目前仍有人尚未結算；下載的 Excel 僅包含已結算人員。")
    if settled_rows:
        report_rows = []
        missing_notes = []
        for salary in settled_rows:
            personal_note = get_employee_salary_note(config, salary["employee_id"], year) or {}
            report_rows.append({**salary,
                "company_cost_note": personal_note.get("company_cost_note", ""),
                "annual_leave_personal_note": personal_note.get("annual_leave_note", ""),
            })
            if not personal_note:
                missing_notes.append(salary["employee_name_snapshot"])
        if missing_notes:
            st.warning(f"尚未設定 {year} 年個人薪資說明：{'、'.join(missing_notes)}；仍可結算與下載，Excel 將留白。")
        st.download_button("下載本月薪資表", generate_salary_workbook(year, month, report_rows, monthly_extras), f"{year}年{month:02d}月薪資.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.button("下載本月薪資表", disabled=True, help="目前沒有已結算薪資可供下載。")


def _history_tab(config):
    query_mode = st.selectbox("查詢方式", ["請選擇", "全部", "依月份", "依員工"], key="salary_history_query_mode")
    if query_mode == "請選擇":
        return
    if query_mode == "全部":
        rows = list_salaries(config)
    elif query_mode == "依月份":
        y, m = st.columns(2)
        year = y.selectbox("年份", range(date.today().year - 10, date.today().year + 3), index=10,
                           key="salary_history_year")
        month = m.selectbox("月份", range(1, 13), index=date.today().month - 1, key="salary_history_month")
        rows = list_salaries(config, year, month)
    else:
        employees = list_employees(config, include_inactive=True)
        if not employees:
            st.info("目前沒有員工資料。")
            return
        employee_id = st.selectbox("員工姓名", [item["employee_id"] for item in employees],
                                   format_func=lambda value: next(item["name"] for item in employees if item["employee_id"] == value),
                                   key="salary_history_employee")
        rows = list_salaries(config, employee_id=employee_id)
    rows = [row for row in rows if row["status"] == "settled"]
    if not rows:
        st.info("查無已結算薪資資料。草稿請回「每月薪資」繼續修改。")
        return
    display = pd.DataFrame([{ "年月":f"{x['year']}/{x['month']:02d}", "姓名":x["employee_name_snapshot"], "當月底薪":x["base_salary_snapshot"], "加給":x["total_additions"], "扣除":x["total_deductions"], "請假":x["leave_deduction"], "特休":f"{x['annual_leave_days']}日{x['annual_leave_hours']}時", "薪資總計":x["final_salary"], "說明":x["system_note"], "狀態":x["status"], "最後修改":x["updated_at"]} for x in rows])
    st.dataframe(display, use_container_width=True, hide_index=True)
    chosen = st.selectbox("選擇薪資", range(len(rows)), format_func=lambda i:f"{rows[i]['year']}/{rows[i]['month']:02d} {rows[i]['employee_name_snapshot']}")
    selected_salary = rows[chosen]
    pending_id = st.session_state.get("salary_delete_pending")
    if pending_id != selected_salary["salary_id"]:
        if st.button("刪除薪資"):
            st.session_state.salary_delete_pending = selected_salary["salary_id"]
            st.rerun()
        return
    st.warning(f"確定刪除「{selected_salary['employee_name_snapshot']} {selected_salary['year']}年{selected_salary['month']:02d}月」已結算薪資？")
    st.caption("刪除後，此筆資料將不再納入薪資歷史與本月 Excel，可回「每月薪資」重新建立。")
    confirm, cancel = st.columns(2)
    if confirm.button("確認刪除", type="primary"):
        delete_salary(config, selected_salary["salary_id"])
        st.session_state.pop("salary_delete_pending", None)
        period = f"{selected_salary['year']:04d}-{selected_salary['month']:02d}"
        if st.session_state.get("salary_period") == period:
            st.session_state.salary_blocks = get_month_salaries(config, selected_salary["year"], selected_salary["month"])
        st.toast("薪資已刪除，可回每月薪資重新建立")
        st.rerun()
    if cancel.button("取消"):
        st.session_state.pop("salary_delete_pending", None)
        st.rerun()


def _rules_tab(config):
    rules = get_rules(config)
    with st.form("salary_rules"):
        days = st.number_input("每月計薪天數", min_value=1.0, value=float(rules.get("monthly_days",30)))
        hours = st.number_input("預設每日標準工時", min_value=0.5, value=float(rules.get("standard_hours",8)))
        attendance = st.toggle("請假影響全勤", value=bool(rules.get("leave_affects_attendance")))
        cooling = st.toggle("請假影響涼水", value=bool(rules.get("leave_affects_cooling")))
        allowance = st.toggle("請假影響津貼", value=bool(rules.get("leave_affects_allowance")))
        if st.form_submit_button("儲存薪資規則", type="primary"):
            save_rules(config, {"monthly_days":days,"standard_hours":hours,"leave_affects_attendance":attendance,"leave_affects_cooling":cooling,"leave_affects_allowance":allowance}); st.toast("薪資規則已儲存")

    st.divider()
    st.markdown("<div style='font-size:16px;font-weight:700;'>員工個人薪資說明設定</div>", unsafe_allow_html=True)
    st.caption("公司負擔與歷年制特休說明均以員工＋年度保存，不會套用至其他員工。每月使用量與剩餘量仍由每月薪資快照管理。")
    employees = list_employees(config, include_inactive=True)
    if not employees:
        st.info("請先至「員工薪資設定」建立員工資料。")
        return
    selector_year, selector_employee = st.columns(2)
    leave_year = selector_year.selectbox(
        "年度", range(date.today().year - 5, date.today().year + 3), index=5,
        key="rules_annual_leave_year",
    )
    employee_id = selector_employee.selectbox(
        "員工", [item["employee_id"] for item in employees],
        format_func=lambda value: next(
            f"{item['employee_id']}｜{item['name']}" for item in employees if item["employee_id"] == value
        ),
        key="rules_annual_leave_employee",
    )
    setting = get_annual_leave_setting(config, employee_id, leave_year) or {}
    personal_note = get_employee_salary_note(config, employee_id, leave_year) or {}
    with st.form(f"rules_annual_leave_setting_{employee_id}_{leave_year}"):
        c1, c2, c3 = st.columns(3)
        entitlement = c1.number_input(
            "當年度特休總天數", min_value=0.0, value=float(setting.get("annual_entitlement", 0))
        )
        opening_balance = c2.number_input(
            "期初剩餘天數", min_value=0.0, value=float(setting.get("opening_balance", 0)),
            help="系統於年度中導入時，填寫截至導入月份的實際剩餘天數。",
        )
        opening_month = c3.selectbox(
            "開始計算月份", range(1, 13), index=int(setting.get("opening_month", 1)) - 1
        )
        company_cost_note = st.text_area(
            "公司負擔說明", value=personal_note.get("company_cost_note") or "",
            help="例如：勞保2582+健保1428+勞退1770+職保62=5842。此文字不會自動計算。",
        )
        leave_note = st.text_area(
            "歷年制特休說明", value=personal_note.get("annual_leave_note") or setting.get("note") or "",
            help="例如：歷年制特休14日。此文字只屬於目前選擇的員工與年度。",
        )
        if st.form_submit_button("儲存員工年度特休說明", type="primary"):
            save_annual_leave_setting(
                config, employee_id, leave_year, entitlement, opening_balance, opening_month, leave_note
            )
            save_employee_salary_note(config, employee_id, leave_year, company_cost_note, leave_note)
            st.toast("員工個人薪資說明已儲存／更新")
            st.rerun()


def render_salary_management(config):
    st.markdown("<div style='font-size:20px;font-weight:700;margin:0 0 0.6rem;'>人力｜薪資管理</div>", unsafe_allow_html=True)
    tabs = st.tabs(["員工薪資設定", "每月薪資", "薪資歷史", "薪資規則"])
    with tabs[0]: _employee_tab(config)
    with tabs[1]: _monthly_tab(config)
    with tabs[2]: _history_tab(config)
    with tabs[3]: _rules_tab(config)
