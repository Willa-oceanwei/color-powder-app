from pathlib import Path
import json
import sqlite3
import pytest

from utils.database import DatabaseConfig, SCHEMA_VERSION, MAIN_TABLES, connect_from_config, initialize_database, initialize_database_with_health
from utils.recipe_repository import create_recipe, list_recipes, RecipeError
from utils.production_order_repository import create_production_order, list_production_orders
from utils.outsourcing_repository import create_outsourcing_order, list_outsourcing_orders
from utils.recipe_code_review import suggested_recipe_code, reviewed_recipe_codes, recipe_code_preview, confirm_recipe_code
from test_production_workspace import workspace_app


@pytest.fixture
def config(tmp_path):
    config = DatabaseConfig("sqlite", tmp_path / "review.db")
    initialize_database(config.path)
    with connect_from_config(config) as conn:
        conn.execute("INSERT INTO color_powders(colorpowder_id,created_at,updated_at) VALUES ('P1','2026-01-01','2026-01-01')")
    for code in ("C0541A", "C0542", "NORMAL"):
        create_recipe(config, {"配方編號": code, "顏色": "透明藍", "客戶名稱": "甲庚",
            "配方類別": "原始配方", "色粉類別": "配方", "比例1": "1", "比例2": "100",
            "計量單位": "kg", "色粉編號1": "P1", "色粉重量1": "12.5", "淨重": "1000", "代工倍率": "3"})
    create_recipe(config, {"配方編號": "EXTRA", "配方類別": "附加配方", "原始配方": "C0541A", "色粉編號1": "P1", "色粉重量1": "2"})
    create_production_order(config, {"生產單號": "P001", "配方編號": "C0541A", "生產日期": "2026-10-01",
        "建立時間": "2026-10-01 09:00:00", "包裝重量1": "25", "包裝份數1": "3", "色粉重量1": "37.5"})
    create_outsourcing_order(config, {"代工單號": "O001", "生產單號": "P001", "配方編號": "C0541A",
        "代工數量": "75", "目標載回數量": "225", "轉換倍率": "3"})
    return config


def records(config, table):
    with connect_from_config(config) as conn:
        cur = conn.execute(f"SELECT * FROM {table}")
        return [dict(row) for row in cur.fetchall()]


def confirm(config, code="C0541A", rename=True):
    p = recipe_code_preview(config, code)
    return confirm_recipe_code(config, code, p["token"], rename=rename)


@pytest.mark.parametrize("old,new", [("C0541A","0541"),("C0542","0542"),("AB00123XY","00123"),("0541",None),("C10492",None),("69960A",None),("C0A",None),("C0541-A",None)])
def test_suggestions_only_offer_leading_zero_candidates(old,new):
    assert suggested_recipe_code(old) == new


def test_confirm_changes_only_identifiers_and_preserves_every_numeric_source(config):
    recipe = next(row for row in records(config,"recipes") if row["recipe_id"]=="C0541A")
    components = records(config,"recipe_components")
    packages = records(config,"production_order_packages")
    snapshot = records(config,"production_orders")[0]["recipe_snapshot_json"]
    order_before = list_production_orders(config)[0]
    oem_before = list_outsourcing_orders(config)[0]
    assert confirm(config) == "0541"
    renamed = next(row for row in records(config,"recipes") if row["recipe_id"]=="0541")
    for key in recipe.keys() - {"recipe_id","version","updated_at","last_synced_at"}:
        assert renamed[key] == recipe[key]
    assert records(config,"recipe_components") == [dict(row,recipe_id="0541") if row["recipe_id"]=="C0541A" else row for row in components]
    assert records(config,"production_order_packages") == packages
    assert records(config,"production_orders")[0]["recipe_snapshot_json"] == snapshot
    assert list_production_orders(config)[0] == dict(order_before,配方編號="0541")
    assert list_outsourcing_orders(config)[0] == dict(oem_before,配方編號="0541")
    assert next(r for r in list_recipes(config) if r["配方編號"]=="EXTRA")["原始配方"] == "0541"
    events = records(config,"sync_outbox")
    assert any(e["sheet_name"]=="配方管理" and e["row_key"]=="C0541A" and e["operation"]=="delete" for e in events)
    assert any(e["sheet_name"]=="代工管理" and e["row_key"]=="O001" and json.loads(e["payload_json"])["配方編號"]=="0541" for e in events)
    # Other candidates are not implicitly reviewed.
    assert not any(r["source_code"]=="C0542" for r in reviewed_recipe_codes(config))
    create_production_order(config, {"生產單號":"P002","配方編號":"0541","包裝重量1":"25","包裝份數1":"2"})
    assert list_production_orders(config)[-1]["配方編號"] == "0541"


def test_keep_is_durable_and_does_not_change_existing_business_rows(config):
    tables = ["recipes","recipe_components","production_orders","production_order_packages","outsourcing_orders","sync_outbox"]
    before = {t:records(config,t) for t in tables}
    confirm(config,rename=False)
    assert all(records(config,t)==rows for t,rows in before.items())
    assert reviewed_recipe_codes(DatabaseConfig("sqlite",config.path))[0]["choice"] == "keep"


def test_duplicate_destination_and_stale_preview_never_rename(config):
    preview = recipe_code_preview(config,"C0541A")
    with connect_from_config(config) as conn:
        conn.execute("UPDATE recipes SET notes='edited',version=version+1 WHERE recipe_id='C0541A'")
    with pytest.raises(RecipeError,match="變更"):
        confirm_recipe_code(config,"C0541A",preview["token"],rename=True)
    create_recipe(config,{"配方編號":"0541","色粉編號1":"P1","色粉重量1":"99"})
    before = {t:records(config,t) for t in ("recipes","recipe_components","production_orders","sync_outbox")}
    with pytest.raises(RecipeError,match="已存在"):
        confirm(config)
    assert all(records(config,t)==rows for t,rows in before.items())
    assert reviewed_recipe_codes(config) == []


def test_write_failure_rolls_back_all_linked_identifiers(config,monkeypatch):
    from utils import recipe_code_review as module
    before = {t:records(config,t) for t in MAIN_TABLES}
    def fail(*a,**kw):
        raise RuntimeError("sync failed")
    monkeypatch.setattr(module,"enqueue_sheet_sync",fail)
    with pytest.raises(RuntimeError,match="sync failed"):
        confirm(config)
    assert all(records(config,t)==rows for t,rows in before.items())


def test_confirm_locks_before_reading_validation_snapshot(config,monkeypatch):
    from utils import recipe_code_review as module
    preview = recipe_code_preview(config,"C0541A")
    original = module._preview
    def locked(conn,source):
        other = sqlite3.connect(config.path,timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError,match="locked"):
                other.execute("UPDATE recipes SET ratio1='999' WHERE recipe_id='C0541A'")
        finally:
            other.close()
        return original(conn,source)
    monkeypatch.setattr(module,"_preview",locked)
    confirm_recipe_code(config,"C0541A",preview["token"],rename=True)


def test_ui_requires_individual_choice_and_reload_uses_numeric_string(config):
    app = workspace_app(config).run(timeout=30)
    app.text_input(key="search_text_tab1").set_value("0541").run()
    assert not app.exception
    assert app.button(key="recipe_code_review_rename").label == "改成 0541"
    assert not app.session_state["show_confirm_panel"]
    assert not any(b.label=="💾 僅儲存生產單" for b in app.button)
    app.button(key="recipe_code_review_rename").click().run(timeout=30)
    assert not app.exception
    assert app.text_input(key="search_text_tab1").value == "0541"
    assert app.session_state["new_order"]["配方編號"] == "0541"
    assert app.session_state["recipe_row_cache"]["配方編號"] == "0541"
    assert not any(b.key=="recipe_code_review_rename" for b in app.button)
    app.text_input(key="search_text_tab1").set_value("0542").run()
    assert app.button(key="recipe_code_review_rename").label == "改成 0542"
    app.button(key="recipe_code_review_keep").click().run()
    assert not app.exception and app.session_state["new_order"]["配方編號"] == "C0542"
    again = workspace_app(config).run(timeout=30)
    again.text_input(key="search_text_tab1").set_value("0542").run()
    assert not again.exception
    assert not any(b.key=="recipe_code_review_keep" for b in again.button)
    assert again.session_state["new_order"]["配方編號"] == "C0542"


def test_v33_upgrade_only_adds_empty_review_metadata(config):
    before = {t:records(config,t) for t in MAIN_TABLES-{"recipe_code_reviews"}}
    with connect_from_config(config) as conn:
        conn.execute("DROP TABLE recipe_code_reviews")
        conn.execute("DELETE FROM schema_migrations WHERE version>=34")
        conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (33,'2026-11-02')")
    _,health = initialize_database_with_health(config)
    assert health.schema_version == SCHEMA_VERSION and health.schema_compatible
    assert all(records(config,t)==rows for t,rows in before.items())
    assert reviewed_recipe_codes(config)==[]

def test_manual_picker_and_existing_destination_are_safe(config):
    create_recipe(config, {"配方編號":"0541","顏色":"Existing"})
    app = workspace_app(config).run(timeout=30)
    app.text_input(key="search_text_tab1").set_value("透明藍").run()
    picker = app.selectbox(key="search_add_form_selected_recipe_tab1")
    picker.set_value(next(v for v in picker.options if v.startswith("C0541A |"))).run()
    assert not app.exception
    assert app.button(key="recipe_code_review_rename").disabled
    assert not app.session_state["show_confirm_panel"]
    app.button(key="recipe_code_review_keep").click().run()
    assert not app.exception and app.session_state["new_order"]["配方編號"] == "C0541A"
    assert {r["配方編號"] for r in list_recipes(config)} >= {"0541","C0541A"}


def test_reused_source_code_has_to_be_confirmed_again(config):
    confirm(config,rename=False)
    with connect_from_config(config) as conn:
        conn.execute("UPDATE recipes SET created_at='2099-01-01' WHERE recipe_id='C0541A'")
    assert reviewed_recipe_codes(config) == []
