"""Streamlit salary-management page; business rules and persistence live elsewhere."""
from datetime import date
import pandas as pd
import streamlit as st

from .salary_calculator import calculate_monthly_extra_totals, calculate_salary, generate_salary_note
from .salary_excel import generate_salary_workbook
from .salary_repository import (annual_leave_balance_before_month, delete_salary,
                                get_annual_leave_setting, get_employee_salary_note, get_employee_salary_notes,
                                get_month_salaries, get_rules,
                                get_salary_monthly_extras, list_employees, list_salaries,
                                save_annual_leave_setting, save_employee, save_employee_salary_note,
                                save_rules, save_salary, save_salary_monthly_extras,
                                set_employee_active)


MONEY_FIELDS = ("base_salary", "attendance_bonus", "cooling_allowance", "allowance", "position_allowance", "insurance")
SALARY_WORKBOOK_LAYOUT_VERSION = 2


@st.cache_data(show_spinner=False)
def _cached_salary_workbook(year, month, salaries, monthly_extras, layout_version):
    """Cache workbook rendering, explicitly scoped to its current layout."""
    del layout_version  # Its value is part of Streamlit's cache key.
    return generate_salary_workbook(year, month, salaries, monthly_extras)


def _should_reload_salary_blocks(state, period):
    """Reload persisted drafts when the period changes or session data is lost."""
    return state.get("salary_period") != period or "salary_blocks" not in state


def _annual_leave_editor_rows(records):
    """Return rows suitable for the batch annual-leave editor."""
    columns = ["日期（可留空）", "日數", "時數", "備註"]
    rows = [{
        "日期（可留空）": record.get("date") or "",
        "日數": float(record.get("days") or 0),
        # Keep zero hours blank in the editor, while allowing entered values to
        # retain two decimal places (for example, 1.25 hours).
        "時數": float(record.get("hours")) if record.get("hours") else None,
        "備註": record.get("note") or "",
    } for record in records]
    return pd.DataFrame(rows, columns=columns)


def _annual_leave_editor_key(period, index, employee_id):
    """Return an editor key scoped to the employee occupying a salary block."""
    return f"leave_editor_{period}_{index}_{employee_id}"


def _sync_generated_note_state(state, note_key, generated_note, saved_note=""):
    """Refresh an untouched generated note while preserving a user's edits."""
    generated_key = f"{note_key}_source"
    previous_generated = state.get(generated_key)
    if note_key not in state:
        state[note_key] = saved_note or generated_note
    elif state[note_key] == previous_generated:
        state[note_key] = generated_note
    state[generated_key] = generated_note


def _salary_report_rows(config, rows, year):
    """Attach the per-employee notes required by the salary workbook."""
    report_rows = []
    missing_notes = []
    notes_by_employee = get_employee_salary_notes(
        config, (salary["employee_id"] for salary in rows), year,
    )
    for salary in rows:
        personal_note = notes_by_employee.get(salary["employee_id"], {})
        report_rows.append({
            **salary,
            "company_cost_note": personal_note.get("company_cost_note", ""),
            "annual_leave_personal_note": personal_note.get("annual_leave_note", ""),
        })
        if not personal_note:
            missing_notes.append(salary["employee_name_snapshot"])
    return report_rows, missing_notes


def _deduplicate_salary_blocks(blocks):
    """Remove repeated employees while retaining their first salary block."""
    seen = set()
    unique = []
    for block in blocks:
        employee_id = block.get("employee_id")
        if employee_id in seen:
            continue
        seen.add(employee_id)
        unique.append(block)
    return unique


def _parse_annual_leave_date(value, default_year):
    """Parse YYYY-MM-DD, M/D, MMDD, or their Chinese equivalents."""
    if pd.isna(value) or not str(value).strip():
        return ""
    text = str(value).strip().replace("年", "-").replace("月", "-").replace("日", "")
    text = text.replace("/", "-")
    if text.isdigit() and len(text) == 4:
        parts = [str(default_year), text[:2], text[2:]]
    elif text.isdigit() and len(text) == 8:
        parts = [text[:4], text[4:6], text[6:]]
    else:
        parts = [part.strip() for part in text.split("-") if part.strip()]
    if len(parts) == 2:
        parts.insert(0, str(default_year))
    if len(parts) != 3:
        raise ValueError(f"日期「{value}」格式不正確，請輸入 08/07、0807 或 2026-08-07")
    try:
        return date(*(int(part) for part in parts)).isoformat()
    except ValueError as error:
        raise ValueError(f"日期「{value}」不是有效日期") from error


def _annual_leave_records_from_editor(rows, default_year=None):
    """Normalize batch-editor rows and discard its completely empty rows."""
    records = []
    for row in rows.to_dict("records") if isinstance(rows, pd.DataFrame) else rows:
        record_date = _parse_annual_leave_date(row.get("日期（可留空）"), default_year or date.today().year)
        days = 0.0 if pd.isna(row.get("日數")) else float(row.get("日數") or 0)
        hours = 0.0 if pd.isna(row.get("時數")) else float(row.get("時數") or 0)
        raw_note = row.get("備註")
        note = "" if pd.isna(raw_note) else str(raw_note).strip()
        if record_date or days or hours or note:
            records.append({"date": record_date, "days": days, "hours": hours, "note": note})
    return records


def _employee_tab(config):
    today = date.today()
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
    current_leave_setting = (get_annual_leave_setting(config, current["employee_id"], today.year)
                             if current else None) or {}
    current_leave_default = (annual_leave_balance_before_month(
        config, current["employee_id"], today.year, today.month
    ) if current else 0.0)
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
        st.markdown(f"##### {today.year} 年特休")
        st.caption("填寫目前實際剩餘天數；從本月起，每月會接續上月餘額並扣除當月使用量。")
        leave_columns = st.columns(3)
        current_leave_balance = leave_columns[0].number_input(
            "目前剩餘特休天數", min_value=0.0,
            value=float(current_leave_default),
            key=f"employee_current_leave_{employee_key}",
        )
        annual_leave_entitlement = leave_columns[1].number_input(
            "本年度核定特休天數", min_value=0.0,
            value=float(current_leave_setting.get("annual_entitlement", current.get("annual_leave_base", 0))),
            key=f"employee_leave_entitlement_{employee_key}",
        )
        leave_columns[2].text_input(
            "餘額開始計算月份", value=f"{today.month} 月", disabled=True,
            key=f"employee_leave_month_{employee_key}",
            help="目前餘額會從本月開始計算；下個月自動承接扣除後的餘額。",
        )
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
                **values, "standard_hours":standard_hours, "annual_leave_base":current_leave_balance,
                "special_addition_enabled":add_enabled, "special_addition_amount":add_amount, "special_addition_note":add_note,
                "default_deduction_enabled":deduct_enabled, "default_deduction_amount":deduct_amount,
                "default_deduction_note":deduct_note, "note":note})
            save_annual_leave_setting(
                config, employee_id, today.year, annual_leave_entitlement,
                current_leave_balance, today.month, current_leave_setting.get("note", ""),
            )
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
    entitlement = ((annual_setting or {}).get("annual_entitlement")
                   if annual_setting else employee.get("annual_leave_base", 0))
    return {"employee_id": employee["employee_id"], "employee_name_snapshot": employee["name"],
            **{f"{k}_snapshot": employee[k] for k in MONEY_FIELDS}, "standard_hours_snapshot": employee["standard_hours"],
            "annual_leave_entitlement_snapshot": entitlement or 0,
            "annual_leave_note_snapshot": (annual_setting or {}).get("note", ""),
            "annual_leave_balance_before": leave_balance, "leave_days":0.0, "leave_hours":0.0,
            "annual_leave_days":0.0, "annual_leave_hours":0.0, "late_deduction":0, "manual_note":"",
            "annual_leave_records":[], "adjustments":adjustments}


def _monthly_tab(config):
    now = date.today(); ycol, mcol = st.columns(2)
    year = ycol.selectbox("年份", range(now.year - 5, now.year + 3), index=5, key="salary_year")
    month = mcol.selectbox("月份", range(1, 13), index=now.month - 1, key="salary_month")
    period = f"{year:04d}-{month:02d}"
    if _should_reload_salary_blocks(st.session_state, period):
        st.session_state.salary_period = period
        st.session_state.salary_blocks = get_month_salaries(config, year, month)
    blocks = st.session_state.setdefault("salary_blocks", [])
    unique_blocks = _deduplicate_salary_blocks(blocks)
    if len(unique_blocks) != len(blocks):
        blocks[:] = unique_blocks
        st.toast("已自動移除重複新增的薪資人員")
    employees = list_employees(config)
    by_id = {x["employee_id"]: x for x in employees}
    def new_month_block(employee):
        setting = get_annual_leave_setting(config, employee["employee_id"], year)
        balance = annual_leave_balance_before_month(config, employee["employee_id"], year, month)
        return _new_block(employee, setting, balance)
    # Repair older drafts that were created with zero leave values even though
    # the employee has a current balance. Settled snapshots remain immutable.
    for block in blocks:
        employee = by_id.get(block.get("employee_id"))
        if (employee and block.get("status") != "settled"
                and not block.get("annual_leave_entitlement_snapshot")
                and not block.get("annual_leave_balance_before")):
            setting = get_annual_leave_setting(config, employee["employee_id"], year)
            entitlement = ((setting or {}).get("annual_entitlement")
                           if setting else employee.get("annual_leave_base", 0))
            balance = annual_leave_balance_before_month(config, employee["employee_id"], year, month)
            if entitlement or balance:
                block["annual_leave_entitlement_snapshot"] = entitlement or 0
                block["annual_leave_balance_before"] = balance
    rules = get_rules(config)
    existing_employee_ids = {block.get("employee_id") for block in blocks}
    available_employees = [x for x in employees if x["employee_id"] not in existing_employee_ids]
    if st.button("＋ 新增人員", disabled=not available_employees,
                 help="所有在職員工都已加入" if employees and not available_employees else None):
        new_block = new_month_block(available_employees[0])
        new_block.update(calculate_salary(new_block, rules=rules))
        new_block["system_note"] = generate_salary_note(new_block)
        new_block["salary_id"] = save_salary(
            config, {**new_block, "year": year, "month": month}, new_block["adjustments"],
            annual_leave_records=[],
        )
        blocks.append(new_block)
        st.toast("新增人員已自動儲存為草稿")
        st.rerun()
    for index, block in enumerate(list(blocks)):
        employee_label = block.get("employee_name_snapshot") or by_id.get(
            block.get("employee_id"), {"name": block.get("employee_id", "未指定員工")}
        )["name"]
        status_label = "已結算" if block.get("status") == "settled" else "草稿"
        with st.expander(
            f"👤 {employee_label}｜{period}｜{status_label}",
            expanded=index == 0,
        ):
            current_id = block.get("employee_id")
            top, remove = st.columns([5, 1])
            top.markdown(f"**薪資人員：{employee_label}**")
            if remove.button("－ 移除此人員", key=f"sal_remove_{period}_{index}"):
                removed_block = blocks.pop(index)
                if removed_block.get("salary_id") and removed_block.get("status") != "settled":
                    delete_salary(config, removed_block["salary_id"])
                st.rerun()
            labels = [("base_salary_snapshot","底薪"),("attendance_bonus_snapshot","全勤"),("cooling_allowance_snapshot","涼水"),("allowance_snapshot","固定津貼"),("position_allowance_snapshot","職務津貼"),("insurance_snapshot","勞健保")]
            cols = st.columns(3)
            for pos, (field, label) in enumerate(labels): block[field] = cols[pos % 3].number_input(label, min_value=0, value=int(block.get(field, 0)), key=f"{field}_{period}_{index}")
            cols = st.columns(2)
            for pos, (field, label) in enumerate((("leave_days","請假日數"),("leave_hours","請假時數"))):
                block[field] = cols[pos].number_input(label, min_value=0.0, value=float(block.get(field, 0)), key=f"{field}_{period}_{index}")
            st.markdown("##### 特休日期明細")
            records = block.setdefault("annual_leave_records", [])
            st.caption("可一次新增、修改或刪除多筆；編輯期間不會重跑頁面，完成後再按套用。")
            st.info("日期輸入方式：`08/07`、`0807` 或 `2026-08-07`；日期也可以留空白。")
            with st.form(f"annual_leave_records_{period}_{index}"):
                annual_leave_applied = False
                edited_records = st.data_editor(
                    _annual_leave_editor_rows(records),
                    key=_annual_leave_editor_key(period, index, block.get("employee_id")),
                    num_rows="dynamic",
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "日期（可留空）": st.column_config.TextColumn(
                            "日期（可留空）",
                            help="可直接輸入 08/07、0807 或 2026-08-07，不限制只能選薪資月份。",
                        ),
                        "日數": st.column_config.NumberColumn("日數", min_value=0.0, step=0.5),
                        "時數": st.column_config.NumberColumn(
                            "時數", min_value=0.0, step=0.01, format="%.2f",
                            help="可輸入至小數點後 2 位；0 會保持空白。",
                        ),
                        "備註": st.column_config.TextColumn("備註"),
                    },
                )
                if st.form_submit_button("套用並儲存特休明細", type="primary"):
                    try:
                        normalized_records = _annual_leave_records_from_editor(edited_records, year)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        records[:] = normalized_records
                        annual_leave_applied = True
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
            block.update(calculate_salary(block, additions, deductions, rules))
            generated_note = generate_salary_note(block, additions, deductions)
            system_note_key = f"system_note_{period}_{index}_{block.get('employee_id')}"
            _sync_generated_note_state(
                st.session_state, system_note_key, generated_note, block.get("system_note", ""),
            )
            block["manual_note"] = st.text_area(
                "人工備註", block.get("manual_note", ""),
                key=f"manual_{period}_{index}_{block.get('employee_id')}",
            )
            st.markdown("##### 儲存前備註預覽（可編輯）")
            st.caption("特休明細請先按「套用特休明細」；下方就是會儲存的自動備註，可直接點入修改。")
            block["system_note"] = st.text_area(
                "自動生成備註", key=system_note_key,
                placeholder="本月目前沒有自動生成的備註內容。",
                help="未修改時會隨薪資資料自動更新；手動修改後，系統會保留您的版本。",
            )
            if annual_leave_applied:
                block["salary_id"] = save_salary(
                    config, {**block, "year": year, "month": month}, block["adjustments"],
                    annual_leave_records=records,
                )
                st.toast("特休明細已套用並自動儲存草稿")
            elif block.get("status") != "settled":
                # Persist every rendered draft after all widgets have written
                # their current values back to the block.  Streamlit session
                # state is not durable across deployments or reconnects, so
                # relying only on the bottom-of-page save button can otherwise
                # lose edited notes when the process restarts.
                block["salary_id"] = save_salary(
                    config, {**block, "year": year, "month": month}, block["adjustments"],
                    annual_leave_records=records,
                )
            if block["manual_note"].strip():
                st.caption(f"人工備註預覽：{block['manual_note'].strip()}")
            if block.get("status") != "settled":
                st.caption("草稿內容已自動儲存；重新連線或系統更新後仍會從資料庫載入。")
            st.markdown(f"**薪資總計：{block['final_salary']:,} 元**")
    monthly_extras = get_salary_monthly_extras(config, year, month)
    previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
    previous_extras = get_salary_monthly_extras(config, previous_year, previous_month)
    previous_default = float(
        previous_extras.get("monthly_total", 0)
        if previous_extras.get("created_at") else monthly_extras.get("previous_value", 0)
    )
    with st.expander("每月附加數值區"):
        st.caption("上月會優先承接前一個月的餘額；若年中首次使用或前月尚無資料，也可直接填寫。")
        employee_values = {}
        extra_columns = st.columns(3)
        for position, employee in enumerate(employees):
            employee_values[employee["employee_id"]] = extra_columns[position % 3].number_input(
                employee["name"], value=float(monthly_extras["employee_values"].get(employee["employee_id"], 0)),
                key=f"monthly_extra_employee_{period}_{employee['employee_id']}",
            )
        previous_col, addition_col, total_col = st.columns(3)
        previous_value = previous_col.number_input(
            "上月", value=previous_default, key=f"monthly_extra_previous_{period}",
        )
        monthly_addition, monthly_total = calculate_monthly_extra_totals(previous_value, employee_values)
        addition_col.metric("+本月新增（員工總和）", f"{monthly_addition:g}")
        total_col.metric("餘本月總計", f"{monthly_total:g}")
        if st.button("儲存每月附加數值", key=f"save_monthly_extras_{period}"):
            save_salary_monthly_extras(
                config, year, month, employee_values, previous_value, monthly_addition, monthly_total,
            )
            st.toast("每月附加數值已儲存，Excel 將使用最新數值")
            st.rerun()

    current_monthly_extras = {
        **monthly_extras,
        "employee_values": employee_values,
        "previous_value": previous_value,
        "monthly_addition": monthly_addition,
        "monthly_total": monthly_total,
    }
    preview_rows, _ = _salary_report_rows(config, blocks, year)
    c1, c2, c3 = st.columns(3)
    if c1.button("儲存草稿", disabled=not blocks):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"], annual_leave_records=block.get("annual_leave_records", []))
        st.toast("草稿已儲存")
    if c2.button("結算薪資", type="primary", disabled=not blocks):
        for block in blocks: save_salary(config, {**block,"year":year,"month":month}, block["adjustments"], settle=True, annual_leave_records=block.get("annual_leave_records", []))
        st.toast("正式薪資快照已結算／更新")
    if blocks:
        c3.download_button(
            "草稿預覽（Excel）",
            _cached_salary_workbook(
                year, month, preview_rows, current_monthly_extras,
                SALARY_WORKBOOK_LAYOUT_VERSION,
            ),
            f"{year}年{month:02d}月薪資草稿預覽.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="直接使用目前畫面內容產生預覽，不必先儲存或結算。",
        )
    else:
        c3.button("草稿預覽（Excel）", disabled=True, help="請先新增薪資人員。")

    # 月份層級報表：只從資料庫重新讀取已結算快照，不使用畫面草稿。
    month_rows = get_month_salaries(config, year, month)
    settled_rows = [row for row in month_rows if row["status"] == "settled"]
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
        report_rows, missing_notes = _salary_report_rows(config, settled_rows, year)
        if missing_notes:
            st.warning(f"尚未設定 {year} 年個人薪資說明：{'、'.join(missing_notes)}；仍可結算與下載，Excel 將留白。")
        st.download_button(
            "下載本月薪資表",
            _cached_salary_workbook(
                year, month, report_rows, monthly_extras,
                SALARY_WORKBOOK_LAYOUT_VERSION,
            ),
            f"{year}年{month:02d}月薪資.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
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
    selected_employee = next(item for item in employees if item["employee_id"] == employee_id)
    setting = get_annual_leave_setting(config, employee_id, leave_year) or {
        "annual_entitlement": selected_employee.get("annual_leave_base", 0),
        "opening_balance": selected_employee.get("annual_leave_base", 0),
        "opening_month": 1,
        "note": "",
    }
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
    if config.backend == "turso":
        st.caption("薪資草稿儲存在雲端資料庫，更新程式不會清除已儲存草稿。")
    else:
        st.warning("目前使用本機資料庫；程式更新不會主動刪除草稿，但部署平台若重建磁碟，未使用雲端資料庫的資料可能遺失。")
    tabs = st.tabs(["👤 員工薪資設定", "📅 每月薪資", "📚 薪資歷史", "⚙️ 薪資規則"])
    with tabs[0]:
        _employee_tab(config)
    with tabs[1]:
        _monthly_tab(config)
    with tabs[2]:
        _history_tab(config)
    with tabs[3]:
        _rules_tab(config)
