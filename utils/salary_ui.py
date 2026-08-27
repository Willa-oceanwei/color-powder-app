"""Streamlit salary-management page; business rules and persistence live elsewhere."""
from datetime import date

import pandas as pd
import streamlit as st

from .salary_calculator import calculate_salary, generate_salary_note
from .salary_excel import generate_salary_workbook
from .salary_repository import (get_month_salaries, get_rules, list_employees, list_salaries,
                                save_employee, save_rules, save_salary, set_employee_active)


MONEY_FIELDS = ("base_salary", "attendance_bonus", "cooling_allowance", "allowance", "position_allowance", "insurance")


def _employee_tab(config):
    mode = st.radio("員工資料操作", ["➕ 新增員工", "✏️ 修改員工"], horizontal=True)
    search = st.text_input("搜尋員工編號／姓名", key="salary_employee_search") if mode.startswith("✏️") else ""
    employees = list_employees(config, True, search)
    if mode.startswith("✏️") and not employees:
        st.info("找不到可修改的員工資料。")
        return
    current = {}
    if mode.startswith("✏️"):
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
        h, leave = st.columns(2)
        standard_hours = h.number_input("每日標準工時", min_value=0.5, value=float(current.get("standard_hours", 8)), key=f"employee_hours_{employee_key}")
        annual_leave = leave.number_input("特休期初餘額", min_value=0.0, value=float(current.get("annual_leave_base", 0)), key=f"employee_leave_{employee_key}", help="開始使用薪資模組時可用的特休餘額，不代表依法或年度給予天數。")
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
        submit_label = "➕ 新增員工" if not current else "💾 儲存修改"
        if st.form_submit_button(submit_label, type="primary"):
            save_employee(config, {"employee_id":employee_id, "name":name, "join_date":join_date.isoformat(), "active":active,
                **values, "standard_hours":standard_hours, "annual_leave_base":annual_leave,
                "special_addition_enabled":add_enabled, "special_addition_amount":add_amount, "special_addition_note":add_note,
                "default_deduction_enabled":deduct_enabled, "default_deduction_amount":deduct_amount,
                "default_deduction_note":deduct_note, "note":note})
            st.toast("員工目前設定已儲存；歷史快照不受影響", icon="✅"); st.rerun()
    if current and st.button("停用／離職" if current.get("active") else "恢復在職"):
        set_employee_active(config, current["employee_id"], not current.get("active")); st.rerun()
    st.caption(f"目前共有 {len(employees)} 筆符合條件的員工資料。為保護薪資隱私，本頁不直接攤開完整清單；請使用上方「修改員工」搜尋及選取。")


def _new_block(employee):
    adjustments = []
    if employee.get("special_addition_enabled"):
        adjustments.append({"type":"addition", "item_name":"特別加給", "amount":employee.get("special_addition_amount", 0), "note":employee.get("special_addition_note") or ""})
    if employee.get("default_deduction_enabled"):
        adjustments.append({"type":"deduction", "item_name":"扣除額", "amount":employee.get("default_deduction_amount", 0), "note":employee.get("default_deduction_note") or ""})
    return {"employee_id": employee["employee_id"], "employee_name_snapshot": employee["name"],
            **{f"{k}_snapshot": employee[k] for k in MONEY_FIELDS}, "standard_hours_snapshot": employee["standard_hours"],
            "annual_leave_balance_before": employee["annual_leave_base"], "leave_days":0.0, "leave_hours":0.0,
            "annual_leave_days":0.0, "annual_leave_hours":0.0, "late_deduction":0, "manual_note":"", "adjustments":adjustments}


def _monthly_tab(config):
    pending = st.session_state.pop("salary_pending_revision", None)
    if pending:
        st.session_state.salary_year = pending["year"]
        st.session_state.salary_month = pending["month"]
        st.session_state.salary_period = f"{pending['year']:04d}-{pending['month']:02d}"
        st.session_state.salary_blocks = [pending]
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
    if st.button("＋ 新增人員", disabled=not employees):
        available = next((x for x in employees if x["employee_id"] not in {b.get("employee_id") for b in blocks}), employees[0])
        blocks.append(_new_block(available)); st.rerun()
    rules = get_rules(config)
    for index, block in enumerate(list(blocks)):
        with st.container(border=True):
            top, remove = st.columns([5, 1])
            options = list(by_id)
            current_id = block.get("employee_id")
            if current_id not in options: options.insert(0, current_id)
            selected_id = top.selectbox("姓名", options, index=options.index(current_id), format_func=lambda x: by_id.get(x, {"name":block.get("employee_name_snapshot", x)})["name"], key=f"sal_emp_{period}_{index}")
            if selected_id != current_id:
                blocks[index] = _new_block(by_id[selected_id]); st.rerun()
            if remove.button("－ 移除此人員", key=f"sal_remove_{period}_{index}"):
                blocks.pop(index); st.rerun()
            labels = [("base_salary_snapshot","底薪"),("attendance_bonus_snapshot","全勤"),("cooling_allowance_snapshot","涼水"),("allowance_snapshot","固定津貼"),("position_allowance_snapshot","職務津貼"),("insurance_snapshot","勞健保")]
            cols = st.columns(3)
            for pos, (field, label) in enumerate(labels): block[field] = cols[pos % 3].number_input(label, min_value=0, value=int(block.get(field, 0)), key=f"{field}_{period}_{index}")
            cols = st.columns(4)
            for pos, (field, label) in enumerate((("leave_days","請假日數"),("leave_hours","請假時數"),("annual_leave_days","特休日數"),("annual_leave_hours","特休時數"))):
                block[field] = cols[pos].number_input(label, min_value=0.0, value=float(block.get(field, 0)), key=f"{field}_{period}_{index}")
            block["late_deduction"] = st.number_input("遲到扣款", min_value=0, value=int(block.get("late_deduction", 0)), key=f"late_{period}_{index}")
            before = float(block.get("annual_leave_balance_before", 0)); used = block["annual_leave_days"] + block["annual_leave_hours"] / float(block.get("standard_hours_snapshot") or 8)
            block["annual_leave_balance_after"] = before - used
            st.caption(f"本月特休共 {used:g} 日；使用前 {before:g} 日，使用後 {before-used:g} 日")
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
    c1,c2 = st.columns(2)
    if c1.button("💾 儲存草稿", disabled=not blocks):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"])
        st.toast("草稿已儲存", icon="💾")
    if c2.button("🔒 結算薪資", type="primary", disabled=not blocks):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"], settle=True)
        st.toast("正式薪資快照已結算／更新", icon="✅")
    source = get_month_salaries(config, year, month) or [{**b,"year":year,"month":month} for b in blocks]
    if source:
        st.download_button("📥 下載本月薪資表", generate_salary_workbook(year, month, source), f"{year}年{month:02d}月薪資.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.button("📥 下載本月薪資表", disabled=True, help="請先新增人員或儲存本月薪資。")


def _history_tab(config):
    y,m,n = st.columns(3); year = y.number_input("年", min_value=2000, max_value=2100, value=date.today().year); month = m.selectbox("月", [0]+list(range(1,13)), format_func=lambda x:"全部" if x==0 else str(x)); name=n.text_input("姓名")
    rows = list_salaries(config, int(year), month or None, name)
    if rows:
        display = pd.DataFrame([{ "年月":f"{x['year']}/{x['month']:02d}", "姓名":x["employee_name_snapshot"], "當月底薪":x["base_salary_snapshot"], "加給":x["total_additions"], "扣除":x["total_deductions"], "請假":x["leave_deduction"], "特休":f"{x['annual_leave_days']}日{x['annual_leave_hours']}時", "薪資總計":x["final_salary"], "說明":x["system_note"], "狀態":x["status"], "最後修改":x["updated_at"]} for x in rows])
        st.dataframe(display, use_container_width=True, hide_index=True)
        chosen = st.selectbox("選擇要修正的薪資", range(len(rows)), format_func=lambda i:f"{rows[i]['year']}/{rows[i]['month']:02d} {rows[i]['employee_name_snapshot']}")
        if st.button("✏️ 修正薪資"):
            st.session_state.salary_pending_revision = rows[chosen]
            st.toast("已載入當時快照；請至「每月薪資」修正後重新結算", icon="✏️"); st.rerun()
    else: st.info("查無薪資快照")


def _rules_tab(config):
    rules = get_rules(config)
    with st.form("salary_rules"):
        days = st.number_input("每月計薪天數", min_value=1.0, value=float(rules.get("monthly_days",30)))
        hours = st.number_input("預設每日標準工時", min_value=0.5, value=float(rules.get("standard_hours",8)))
        attendance = st.toggle("請假影響全勤", value=bool(rules.get("leave_affects_attendance")))
        cooling = st.toggle("請假影響涼水", value=bool(rules.get("leave_affects_cooling")))
        allowance = st.toggle("請假影響津貼", value=bool(rules.get("leave_affects_allowance")))
        if st.form_submit_button("儲存薪資規則", type="primary"):
            save_rules(config, {"monthly_days":days,"standard_hours":hours,"leave_affects_attendance":attendance,"leave_affects_cooling":cooling,"leave_affects_allowance":allowance}); st.toast("薪資規則已儲存", icon="✅")


def render_salary_management(config):
    st.markdown("## 👥 人力｜💰 薪資管理")
    tabs = st.tabs(["👤 員工薪資設定", "🧾 每月薪資", "📚 薪資歷史", "⚙️ 薪資規則"])
    with tabs[0]: _employee_tab(config)
    with tabs[1]: _monthly_tab(config)
    with tabs[2]: _history_tab(config)
    with tabs[3]: _rules_tab(config)
