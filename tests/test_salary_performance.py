from collections import Counter
from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, initialize_database_with_health
from utils.salary_calculator import calculate_salary
from utils.salary_repository import save_employee, save_salary
from utils import salary_ui


def test_reference_cache_expires_and_returns_independent_values(monkeypatch):
    state = {}
    clock = [0.0]
    calls = []
    monkeypatch.setattr(salary_ui.st, "session_state", state)
    monkeypatch.setattr(salary_ui, "perf_counter", lambda: clock[0])

    def load():
        calls.append(1)
        return {"E1": {"note": "Original"}}

    first = salary_ui._salary_reference_read("database-a", ("notes", 2026), load)
    first["E1"]["note"] = "Edited locally"
    assert salary_ui._salary_reference_read("database-a", ("notes", 2026), load)["E1"]["note"] == "Original"
    assert len(calls) == 1
    clock[0] = salary_ui.SALARY_REFERENCE_CACHE_SECONDS
    salary_ui._salary_reference_read("database-a", ("notes", 2026), load)
    assert len(calls) == 2
    salary_ui._salary_reference_read("database-b", ("notes", 2026), load)
    assert len(calls) == 3
    salary_ui._invalidate_salary_reference_cache()
    salary_ui._salary_reference_read("database-b", ("notes", 2026), load)
    assert len(calls) == 4


def test_reference_cache_does_not_cache_failed_reads(monkeypatch):
    import pytest

    monkeypatch.setattr(salary_ui.st, "session_state", {})
    with pytest.raises(ValueError):
        salary_ui._salary_reference_read("db", ("master",), lambda: (_ for _ in ()).throw(ValueError()))
    assert salary_ui._salary_reference_read("db", ("master",), lambda: "Recovered") == "Recovered"


def test_salary_reruns_reuse_references_but_read_payroll_fresh(tmp_path, monkeypatch):
    config = DatabaseConfig("sqlite", tmp_path / "performance.db")
    initialize_database_with_health(config)
    save_employee(config, {"employee_id": "E1", "name": "Test", "base_salary": 32000})
    salary = {
        "employee_id": "E1", "employee_name_snapshot": "Test", "year": 2026, "month": 9,
        "base_salary_snapshot": 32000, "standard_hours_snapshot": 8,
    }
    salary.update(calculate_salary(salary))
    save_salary(config, salary, settle=True)
    calls = Counter()
    for name in ("list_employees", "get_rules", "get_annual_leave_contexts",
                 "get_month_salaries", "get_salary_monthly_extras",
                 "get_employee_salary_notes", "get_annual_leave_setting", "get_employee_salary_note"):
        original = getattr(salary_ui, name)

        def counted(*args, _original=original, _name=name, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(salary_ui, name, counted)
    # Keep cache expiry deterministic even on a slow CI worker.
    monkeypatch.setattr(salary_ui, "perf_counter", lambda: 0.0)
    app = AppTest.from_string(
        "from pathlib import Path\n"
        "from utils.database import DatabaseConfig\n"
        "from utils.salary_ui import render_salary_management\n"
        f"render_salary_management(DatabaseConfig('sqlite', Path({str(config.path)!r})))\n"
    )
    app.session_state["salary_year"] = 2026
    app.session_state["salary_month"] = 9
    app.run()
    assert not app.exception
    assert calls["get_employee_salary_notes"] == 1
    first = calls.copy()
    app.number_input(key="base_salary_snapshot_2026-09_0").set_value(33000).run()
    assert not app.exception
    for name in ("list_employees", "get_rules", "get_annual_leave_contexts",
                 "get_employee_salary_notes", "get_annual_leave_setting", "get_employee_salary_note"):
        assert calls[name] == first[name], name
    assert calls["get_month_salaries"] == first["get_month_salaries"] + 1
    assert calls["get_salary_monthly_extras"] == first["get_salary_monthly_extras"] + 2
    next(button for button in app.button if button.label == "結算薪資").click().run()
    assert not app.exception
    assert calls["list_employees"] > first["list_employees"]
    assert calls["get_annual_leave_contexts"] > first["get_annual_leave_contexts"]
    assert calls["get_employee_salary_notes"] > first["get_employee_salary_notes"]
    download = next(item for item in app.get("download_button") if item.proto.label == "下載本月薪資表")
    assert not download.proto.disabled
