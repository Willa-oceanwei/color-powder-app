from pathlib import Path

import pytest

from utils import recipe_page_data as data
from utils.color_powder_repository import (
    ColorPowderInput, create_color_powder, set_color_powder_active,
)
from utils.database import DatabaseConfig, initialize_database_with_health


def test_shared_initial_read_and_reruns_do_not_repeat_query(monkeypatch):
    clock = [0.0]
    calls = []
    monkeypatch.setattr(data, "perf_counter", lambda: clock[0])
    rows = [{"colorpowder_id": "P1", "name": "Original"}]

    def read(config, *, include_inactive):
        assert include_inactive
        calls.append(config)
        return rows

    monkeypatch.setattr(data, "list_color_powders", read)
    state = {}
    data.remember_recipe_powders("db", state, rows)
    rows[0]["name"] = "Changed outside cache"
    first = data.load_recipe_powders("db", state)
    first[0]["name"] = "Edited in tab"
    assert data.load_recipe_powders("db", state)[0]["name"] == "Original"
    assert calls == []
    clock[0] = data.RECIPE_POWDER_CACHE_SECONDS
    data.load_recipe_powders("db", state)
    data.load_recipe_powders("db", state)
    assert calls == ["db"]
    data.load_recipe_powders("other-db", state)
    data.load_recipe_powders("other-db", {})
    assert calls == ["db", "other-db", "other-db"]


def test_failed_read_is_not_cached(monkeypatch):
    state = {}

    def fail(*args, **kwargs):
        raise ValueError("Unavailable")

    monkeypatch.setattr(data, "list_color_powders", fail)
    with pytest.raises(ValueError):
        data.load_recipe_powders("db", state)
    assert "recipe_powder_reference" not in state
    monkeypatch.setattr(data, "list_color_powders", lambda *args, **kwargs: [])
    assert data.load_recipe_powders("db", state) == []


def test_active_recipe_choices_and_management_share_same_rows():
    rows = [
        {"colorpowder_id": "P1", "name": "Active", "lifecycle_status": "active"},
        {"colorpowder_id": "P2", "name": "Inactive", "lifecycle_status": "inactive"},
    ]
    assert data.recipe_powder_dataframe(rows)["色粉編號"].tolist() == ["P1"]
    management = data.recipe_powder_dataframe(rows, include_inactive=True)
    assert management["色粉編號"].tolist() == ["P1", "P2"]
    assert management["生命週期"].tolist() == ["active", "inactive"]
    assert list(data.recipe_powder_dataframe([]).columns) == list(data.POWDER_COLUMNS)[:6]
    assert list(data.recipe_powder_dataframe([], include_inactive=True).columns) == list(data.POWDER_COLUMNS)


def test_successful_writes_can_refresh_choices_immediately(tmp_path, monkeypatch):
    config = DatabaseConfig("sqlite", tmp_path / "recipe-performance.db")
    initialize_database_with_health(config)
    monkeypatch.setattr(data, "perf_counter", lambda: 0.0)
    state = {"recipe_data_loaded": True}
    create_color_powder(config, ColorPowderInput("P1"))
    assert len(data.load_recipe_powders(config, state)) == 1
    create_color_powder(config, ColorPowderInput("P2"))
    data.invalidate_recipe_powders(state)
    assert not state["recipe_data_loaded"]
    assert len(data.load_recipe_powders(config, state)) == 2
    set_color_powder_active(config, "P1", active=False)
    data.invalidate_recipe_powders(state)
    rows = data.load_recipe_powders(config, state)
    assert data.recipe_powder_dataframe(rows)["色粉編號"].tolist() == ["P2"]
    assert len(data.recipe_powder_dataframe(rows, include_inactive=True)) == 2


def test_recipe_page_wires_shared_reads_and_write_invalidation():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    section = source.split('elif menu == "配方管理":', 1)[1].split('elif menu ==', 1)[0]
    assert "executor.submit(list_color_powders, DATABASE_CONFIG, include_inactive=True)" in section
    assert "remember_recipe_powders(DATABASE_CONFIG, st.session_state, initial_powders)" in section
    assert "recipe_powder_entities = load_recipe_powders(DATABASE_CONFIG, st.session_state)" in section
    assert "powder_entities = recipe_powder_entities" in section
    assert "powder_entities = list_color_powders" not in section
    # Reload, save, activation and replacement all invalidate only this page's cache.
    assert section.count("invalidate_recipe_powders(st.session_state)") == 4
