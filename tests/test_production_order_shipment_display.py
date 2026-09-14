import ast
from pathlib import Path

def _load_shipment_helpers():
    """Load pure formatting helpers without executing the Streamlit app."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"fmt_num", "parse_pack_value", "calculate_shipment_display"}
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {"re": __import__("re")}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["calculate_shipment_display"]


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


def test_barrel_recipe_displays_quarter_as_25k_even_with_stale_order_unit():
    calculate = _load_shipment_helpers()
    recipes = [{"配方編號": "R001", "計量單位": "桶", "色粉類別": "配方"}]
    order = {
        "配方編號": "R001",
        "計量單位": "包",
        "包裝重量1": "0.25",
        "包裝份數1": "8",
    }

    assert calculate(order, recipes) == "25K*8"


def test_shipment_display_formats_multiple_packages_and_unit_suffixes():
    calculate = _load_shipment_helpers()
    recipes = [{"配方編號": "R002", "計量單位": "kg", "色粉類別": "配方"}]
    order = {
        "配方編號": "R002",
        "包裝重量1": "25kg",
        "包裝份數1": "2",
        "包裝重量2": "10",
        "包裝份數2": "1.5",
    }

    assert calculate(order, recipes) == "25kg*2 + 10kg*1.5"


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
    assert state == {"new_order": {"生產單號": "20260914-001", "配方編號": "OLD"},
                     "new_order_saved": False, "downloaded_html_tab1": False}


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
