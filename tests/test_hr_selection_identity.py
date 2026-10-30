import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def source_functions(path, names):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return "\n\n".join(ast.unparse(node) for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name in names)


@pytest.mark.parametrize("index", [0, 1])
def test_equal_undated_leave_records_keep_the_selected_edit_target(index):
    source = source_functions("utils/hr_query_ui.py", {"_annual_leave_tab", "_employee_selector"})
    app = AppTest.from_string('''import streamlit as st
from datetime import date
employees = [{"employee_id":"E1", "name":"同名", "standard_hours":8}]
records = [dict(id=i, date="", year=2026, month=i, days=1., hours=0., equivalent_days=1., note=f"紀錄{i}") for i in (1,2)]
list_employees = lambda *a, **kw: employees
list_annual_leave_history = lambda *a: records
get_annual_leave_setting = lambda *a: {}
_summary_card = lambda *a: "摘要"
_detail_card = lambda *a: "明細"
_render_card_grid = lambda *a: None
def save_annual_leave_history_record(config, record):
    st.session_state.saved_record = record
''' + source + '\n_annual_leave_tab(None)').run()
    app.selectbox(key="hr_leave_year").set_value(2026).run()
    app.selectbox(key="hr_leave_employee").set_value("E1").run()
    next(b for b in app.button if b.label == "查詢特休").click().run()
    selector = next(s for s in app.selectbox if s.label == "選擇要修改／刪除的紀錄")
    assert len(set(selector.options)) == 2
    selector.set_value(index).run()
    app.run()
    assert not app.exception
    assert next(t for t in app.text_input if t.label == "備註").value == f"紀錄{index + 1}"
    next(b for b in app.button if b.label == "儲存修改").click().run()
    assert app.session_state["saved_record"]["id"] == index + 1


@pytest.mark.parametrize("employee_id", ["E1", "E2"])
def test_salary_history_distinguishes_employees_with_the_same_name(employee_id):
    source = source_functions("utils/salary_ui.py", {"_history_tab"})
    app = AppTest.from_string('''import streamlit as st
employees = [{"employee_id": key, "name":"同名"} for key in ("E1", "E2")]
def list_salaries(config, *args, **kwargs):
    st.session_state.queried_employee = kwargs.get("employee_id")
    return []
''' + source + '\n_history_tab(None, employees)').run()
    app.selectbox(key="salary_history_query_mode").set_value("依員工").run()
    selector = app.selectbox(key="salary_history_employee")
    assert len(set(selector.options)) == 2
    selector.set_value(employee_id).run()
    app.run()
    assert not app.exception
    assert app.session_state["queried_employee"] == employee_id


@pytest.mark.parametrize("index", [0, 1])
def test_same_month_and_name_salary_records_keep_the_delete_target(index):
    source = source_functions("utils/salary_ui.py", {"_history_tab"})
    app = AppTest.from_string('''import streamlit as st
import pandas as pd
rows = [dict(salary_id=key, year=2026, month=10, employee_name_snapshot="同名", status="settled",
             base_salary_snapshot=100, total_additions=0, total_deductions=0, leave_deduction=0,
             annual_leave_days=0, annual_leave_hours=0, final_salary=100, system_note="", updated_at="")
        for key in ("S1", "S2")]
list_salaries = lambda *a, **kw: rows
''' + source + '\n_history_tab(None, [])').run()
    app.selectbox(key="salary_history_query_mode").set_value("全部").run()
    selector = next(s for s in app.selectbox if s.label == "選擇薪資")
    assert len(set(selector.options)) == 2
    selector.set_value(index).run()
    app.run()
    next(b for b in app.button if b.label == "刪除薪資").click().run()
    assert not app.exception
    assert app.session_state["salary_delete_pending"] == f"S{index + 1}"

