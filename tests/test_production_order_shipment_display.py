import ast
import json
from pathlib import Path
from unittest import TestCase

import pandas as pd


def _load_shipment_helpers():
    """Load pure formatting helpers without executing the Streamlit app."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {
        "fmt_num", "parse_pack_value", "colorant_shipment_display_multiplier",
        "calculate_shipment_display", "build_a5_production_order_download",
        "generate_print_page_content", "generate_production_order_print",
    }
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {"pd": pd, "re": __import__("re")}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def _load_draft_reset_helper():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "reset_production_order_draft_state"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["reset_production_order_draft_state"]


def _load_recipe_widget_initializer():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "initialize_production_order_recipe_widgets"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["initialize_production_order_recipe_widgets"]


def _load_order_edit_state_helpers():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {
        "clear_production_order_edit_state",
        "sync_selected_production_order_state",
        "begin_production_order_edit",
    }
    nodes = [
        node for node in module.body
        if (
            isinstance(node, ast.FunctionDef) and node.name in wanted
        ) or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "PRODUCTION_ORDER_EDIT_WIDGET_KEYS"
                for target in node.targets
            )
        )
    ]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def _recipe_snapshot(recipe_id, unit, category="配方"):
    return json.dumps({
        "recipe_id": recipe_id,
        "measurement_unit": unit,
        "powder_category": category,
        "components": [],
        "additional_recipes": [],
    })


def test_shipment_display_uses_the_recorded_recipe_unit():
    calculate = _load_shipment_helpers()["calculate_shipment_display"]
    order = {
        "配方編號": "R001",
        "計量單位": "包",
        "包裝重量1": "0.25",
        "包裝份數1": "8",
        "_recipe_snapshot_json": _recipe_snapshot("R001", "桶"),
    }
    assert calculate(order) == "25K*8"


def test_shipment_display_uses_legacy_order_unit_when_snapshot_is_missing():
    calculate = _load_shipment_helpers()["calculate_shipment_display"]
    order = {
        "配方編號": "R002",
        "計量單位": "kg",
        "包裝重量1": "25kg",
        "包裝份數1": "2",
        "包裝重量2": "10",
        "包裝份數2": "1.5",
    }
    assert calculate(order) == "25kg*2 + 10kg*1.5"


def test_colorant_defaults_to_legacy_hundred_kg_multiplier():
    calculate = _load_shipment_helpers()["calculate_shipment_display"]
    order = {
        "配方編號": "M001", "包裝重量1": "1", "包裝份數1": "1",
        "_recipe_snapshot_json": _recipe_snapshot("M001", "kg", "色母"),
    }

    assert calculate(order) == "100K*1"


def test_colorant_can_use_actual_kg_for_stock_shipment():
    calculate = _load_shipment_helpers()["calculate_shipment_display"]
    order = {
        "配方編號": "M001",
        "出貨數量顯示方式": "實際公斤（1 = 1kg）",
        "包裝重量1": "1",
        "包裝份數1": "1",
        "_recipe_snapshot_json": _recipe_snapshot("M001", "kg", "色母"),
    }

    assert calculate(order) == "1kg*1"


def test_historical_a5_uses_saved_main_and_additional_recipes(tmp_path):
    from utils.color_powder_repository import ColorPowderInput, create_color_powder
    from utils.database import DatabaseConfig, initialize_database
    from utils.production_order_repository import (
        ProductionOrderError, create_production_order, list_production_orders, update_production_order,
    )
    from utils.recipe_repository import create_recipe, list_recipes, set_recipe_active, update_recipe

    db = tmp_path / "production.db"
    initialize_database(db)
    config = DatabaseConfig(backend="sqlite", path=db)
    for powder_id in ("OLD-MAIN", "OLD-EXTRA", "NEW-MAIN"):
        create_color_powder(config, ColorPowderInput(powder_id))

    main = {"配方編號": "R001", "計量單位": "包", "色粉編號1": "OLD-MAIN", "色粉重量1": "2"}
    extra = {
        "配方編號": "A001", "配方類別": "附加配方", "原始配方": "R001",
        "色粉編號1": "OLD-EXTRA", "色粉重量1": "3",
    }
    create_recipe(config, main)
    create_recipe(config, extra)

    old_order = {
        "生產單號": "O001", "配方編號": "R001", "包裝重量1": "1", "包裝份數1": "2",
    }
    recipes = {row["配方編號"]: row for row in list_recipes(config)}
    original_rows = [recipes["R001"], recipes["A001"]]
    create_production_order(config, old_order, expected_recipe_rows=original_rows)

    update_recipe(config, {**main, "計量單位": "桶", "色粉編號1": "NEW-MAIN"})
    set_recipe_active(config, "A001", active=False, reason="停用")
    current_rows = list_recipes(config)
    with TestCase().assertRaisesRegex(ProductionOrderError, "配方已更新"):
        create_production_order(config, {**old_order, "生產單號": "O002"}, expected_recipe_rows=original_rows)
    with TestCase().assertRaisesRegex(ProductionOrderError, "請選擇建立新單"):
        update_production_order(config, old_order, expected_recipe_rows=current_rows)

    update_production_order(config, {**old_order, "備註": "補充備註"})
    create_production_order(config, {**old_order, "生產單號": "O002"}, expected_recipe_rows=current_rows)
    old, new = list_production_orders(config, include_recipe_snapshot=True)
    helpers = _load_shipment_helpers()
    assert helpers["calculate_shipment_display"](old) == "25K*2"
    assert helpers["calculate_shipment_display"](new) == "100K*2"

    old_html = helpers["build_a5_production_order_download"](old)[0].decode()
    new_html = helpers["build_a5_production_order_download"](new)[0].decode()
    assert all(text in old_html for text in ("OLD-MAIN", "OLD-EXTRA", "附加配方 1：A001", "補充備註"))
    assert "NEW-MAIN" not in old_html
    assert "NEW-MAIN" in new_html
    assert "OLD-EXTRA" not in new_html


def test_legacy_a5_uses_saved_additional_rows_and_marks_missing_history():
    build = _load_shipment_helpers()["build_a5_production_order_download"]
    snapshot = json.loads(_recipe_snapshot("R001", "kg"))
    snapshot.pop("additional_recipes")
    order = {"生產單號": "O001", "配方編號": "R001", "_recipe_snapshot_json": json.dumps(snapshot)}
    legacy_additions = [{"配方編號": "A001", "色粉編號1": "LEGACY", "色粉重量1": "3"}]

    complete_html = build({**order, "附加配方": repr(legacy_additions)})[0].decode()
    partial_html = build(order)[0].decode()
    assert "LEGACY" in complete_html
    assert "缺少原始附加配方紀錄" not in complete_html
    assert "缺少原始附加配方紀錄" in partial_html


def test_preview_result_quantities_are_calculated_after_paging():
    source = Path("app.py").read_text(encoding="utf-8")
    section = source.split("# Tab 3: 生產單預覽/修改/取消", 1)[1].split("# ====== 修改面板", 1)[0]
    assert 'df_display_tab3["出貨數量"] = df_display_tab3.apply' not in section
    assert section.index("df_display_tab3.iloc[start_idx:end_idx].copy()") < section.index('df_page["出貨數量"] = df_page.apply')


def test_switching_recipe_clears_all_recipe_dependent_draft_widgets():
    reset_draft = _load_draft_reset_helper()
    state = {
        "new_order": {"生產單號": "20260914-001", "配方編號": "OLD"},
        "new_order_saved": False,
        "form_color_tab1": "舊顏色",
        "form_unit_tab1": "包",
        "form_weight1_tab1": "0.25",
        "form_count1_tab1": "8",
        "form_main_color_id_1_tab1": "OLD-POWDER",
        "form_add_color_wt_1_1_tab1": "5",
        "recipe_init_done": True,
        "recipe_row_cache": {"配方編號": "OLD"},
        "last_saved_order_snapshot": {"顏色": "舊顏色"},
    }

    changed = reset_draft(state, "20260914-001", "NEW")

    assert changed is True
    assert state == {
        "new_order": None,
        "show_confirm_panel": False,
        "new_order_saved": False,
        "downloaded_html_tab1": False,
    }


def test_switching_recipe_after_save_discards_saved_package_fields_and_snapshot():
    reset_draft = _load_draft_reset_helper()
    state = {
        "new_order": {
            "生產單號": "20260914-001",
            "配方編號": "OLD",
            "包裝重量1": "25",
            "包裝份數1": "4",
        },
        "new_order_saved": True,
        "show_confirm_panel": True,
        "form_weight1_tab1": "25",
        "form_count1_tab1": "4",
        "saved_label_snapshot": {"order": {"配方編號": "OLD"}},
    }

    changed = reset_draft(state, "20260914-002", "NEW")

    assert changed is True
    assert state == {
        "new_order": None,
        "show_confirm_panel": False,
        "new_order_saved": False,
        "downloaded_html_tab1": False,
    }


def test_same_unsaved_recipe_draft_keeps_widget_input_during_rerun():
    reset_draft = _load_draft_reset_helper()
    state = {
        "new_order": {"生產單號": "20260914-001", "配方編號": "R001"},
        "new_order_saved": False,
        "form_weight1_tab1": "0.25",
    }

    changed = reset_draft(state, "20260914-001", "R001")

    assert changed is False
    assert state["form_weight1_tab1"] == "0.25"


def test_same_saved_order_keeps_label_snapshot_when_toggle_reruns():
    reset_draft = _load_draft_reset_helper()
    order = {"生產單號": "P001", "配方編號": "R001", "包裝重量1": "25", "包裝份數1": "2"}
    snapshot = {"order": order.copy(), "a5_downloaded": False}
    state = {"new_order": order, "new_order_saved": True, "show_confirm_panel": True,
             "saved_label_snapshot": snapshot, "show_big_label_P001": True}
    assert reset_draft(state, "P001", "R001") is False
    assert state["saved_label_snapshot"] == snapshot
    assert state["new_order_saved"] is True
    assert state["show_confirm_panel"] is True


def test_new_order_widgets_are_initialized_from_selected_recipe():
    initialize = _load_recipe_widget_initializer()
    state = {}
    order = {"顏色": "海軍藍", "Pantone 色號": "19-3832", "備註": "先過篩"}

    changed = initialize(state, order, {"顏色": "不應覆蓋", "重要提醒": "低速攪拌"})

    assert changed is True
    assert state["form_color_tab1"] == "海軍藍"
    assert state["form_pantone_tab1"] == "19-3832"
    assert state["form_remark_tab1"] == "先過篩"
    assert state["form_important_note_tab1"] == "低速攪拌"
    assert state["recipe_init_done"] is True


def test_recipe_widget_initializer_preserves_user_edits_on_rerun():
    initialize = _load_recipe_widget_initializer()
    state = {"recipe_init_done": True, "form_color_tab1": "人工調整色"}

    changed = initialize(state, {"顏色": "配方原色"}, {"顏色": "配方原色"})

    assert changed is False
    assert state["form_color_tab1"] == "人工調整色"


def test_initialized_recipe_widgets_do_not_also_declare_widget_defaults():
    """Session State must be the only default source for initialized widgets."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    initialized_keys = {
        "form_color_tab1",
        "form_pantone_tab1",
        "form_raw_material_tab1",
        "form_important_note_tab1",
        "form_total_category_tab1",
        "form_remark_tab1",
    }

    calls_by_key = {}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        keywords = {keyword.arg: keyword for keyword in node.keywords if keyword.arg}
        key_node = keywords.get("key")
        if (
            key_node
            and isinstance(key_node.value, ast.Constant)
            and key_node.value.value in initialized_keys
        ):
            calls_by_key[key_node.value.value] = keywords

    assert calls_by_key.keys() == initialized_keys
    assert all("value" not in keywords for keywords in calls_by_key.values())


def test_changing_selected_order_closes_editor_and_old_confirmation():
    helpers = _load_order_edit_state_helpers()
    state = {
        "show_edit_panel": True,
        "editing_order": {"生產單號": "OLD"},
        "edit_customer_name_tab3": "舊客戶",
        "edit_packing_weight_tab3_1": "99",
        "confirm_order_lifecycle_id": "OLD",
        "pending_order_update_tab3": {"生產單號": "OLD"},
    }

    helpers["sync_selected_production_order_state"](state, "NEW")

    assert state == {
        "show_edit_panel": False,
        "editing_order": None,
        "selected_order_no_tab3": "NEW",
    }


def test_changing_selected_order_refreshes_open_editor_fields_immediately():
    helpers = _load_order_edit_state_helpers()
    state = {
        "show_edit_panel": True,
        "editing_order": {"生產單號": "OLD"},
        "edit_customer_name_tab3": "舊客戶",
        "edit_color_tab3": "舊顏色",
        "edit_packing_weight_tab3_1": "99",
        "confirm_order_lifecycle_id": "OLD",
    }
    new_order = {
        "生產單號": "NEW",
        "客戶名稱": "新客戶",
        "顏色": "新顏色",
        "備註": "新備註",
        "包裝重量1": "25",
        "包裝份數1": "4",
    }

    helpers["sync_selected_production_order_state"](state, "NEW", new_order)

    assert state["show_edit_panel"] is True
    assert state["editing_order"] == new_order
    assert state["edit_customer_name_tab3"] == "新客戶"
    assert state["edit_color_tab3"] == "新顏色"
    assert state["edit_remark_tab3"] == "新備註"
    assert state["edit_packing_weight_tab3_1"] == "25"
    assert state["edit_packing_count_tab3_1"] == "4"
    assert state["selected_order_no_tab3"] == "NEW"
    assert "confirm_order_lifecycle_id" not in state


def test_opening_editor_seeds_every_widget_from_selected_order():
    helpers = _load_order_edit_state_helpers()
    state = {
        "editing_order": {"生產單號": "OLD"},
        "edit_customer_name_tab3": "舊客戶",
    }
    order = {
        "生產單號": "NEW",
        "客戶名稱": "新客戶",
        "顏色": "寶藍",
        "備註": "新備註",
        "包裝重量1": "25",
        "包裝份數1": "4",
        "出貨數量顯示方式": "實際公斤（1 = 1kg）",
    }

    helpers["begin_production_order_edit"](state, order)

    assert state["editing_order"] == order
    assert state["show_edit_panel"] is True
    assert state["edit_customer_name_tab3"] == "新客戶"
    assert state["edit_color_tab3"] == "寶藍"
    assert state["edit_remark_tab3"] == "新備註"
    assert state["edit_packing_weight_tab3_1"] == "25"
    assert state["edit_packing_count_tab3_1"] == "4"
    assert state["edit_colorant_quantity_mode_tab3"] is True


def test_order_edit_widgets_use_only_synchronized_session_state_defaults():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    edit_key_prefixes = (
        "edit_customer_name_tab3",
        "edit_color_tab3",
        "edit_remark_tab3",
        "edit_colorant_quantity_mode_tab3",
        "edit_packing_weight_tab3_",
        "edit_packing_count_tab3_",
    )

    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        keywords = {keyword.arg: keyword for keyword in node.keywords if keyword.arg}
        key = keywords.get("key")
        if key and any(prefix in ast.unparse(key.value) for prefix in edit_key_prefixes):
            assert "value" not in keywords


def test_edit_and_cancel_actions_clear_the_opposite_lower_panel():
    source = Path("app.py").read_text(encoding="utf-8")
    assert (
        'begin_production_order_edit(st.session_state, order_dict)\n'
        '                        st.session_state.pop("confirm_order_lifecycle_id", None)'
    ) in source
    assert (
        'if st.button(toggle_label, key="toggle_order_cancel_btn_tab3"):\n'
        '                        clear_production_order_edit_state(st.session_state)\n'
        '                        st.session_state["confirm_order_lifecycle_id"] = current_order_no'
    ) in source
