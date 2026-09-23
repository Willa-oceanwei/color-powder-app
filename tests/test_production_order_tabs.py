import ast
from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "app.py"


def _load_package_total_helper():
    source = APP_SOURCE.read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"safe_float_convert", "calculate_production_package_total_kg"}
    functions = [
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    pd_stub = type("PandasStub", (), {"isna": staticmethod(lambda value: value is None)})
    namespace = {"pd": pd_stub}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["calculate_production_package_total_kg"]


def test_production_order_tabs_are_excluded_from_shared_persistence_controller():
    source = APP_SOURCE.read_text(encoding="utf-8")
    section = source.split("# =============== Tab 架構開始 ===============", 1)[1]
    section = section.split("# ======== 代工管理分頁 =========", 1)[0]

    labels = "🛸 生產單建立|📜 生產單記錄表|👀 生產單預覽/修改/取消"
    assert f'"{labels}"' in source
    assert "PAGE_MANAGED_TAB_LABELS.has(getTabLabels(tabList))" in source
    assert 'const storageKey = "order_mgmt_active_tab"' in section
    assert "window.parent.sessionStorage" in section
    assert "orderPersistBound" in section


def test_production_order_controller_targets_the_exact_tab_group():
    source = APP_SOURCE.read_text(encoding="utf-8")
    section = source.split("# =============== Tab 架構開始 ===============", 1)[1]
    section = section.split("# ======== 代工管理分頁 =========", 1)[0]

    assert "labels.length === tabTexts.length" in section
    assert "tabTexts.every((label, idx) => labels[idx] === label)" in section


def test_colorant_package_total_converts_hundred_kg_multipliers():
    calculate_total = _load_package_total_helper()
    existing = {"包裝重量1": "1", "包裝份數1": "1"}
    delta = {"包裝重量1": "1.5", "包裝份數1": "1"}

    delta_total_kg = calculate_total(delta, is_colorant=True)
    merged_total_kg = delta_total_kg + calculate_total(existing, is_colorant=True)

    assert delta_total_kg == 150
    assert merged_total_kg == 250


def test_initial_production_queries_run_in_parallel_without_duplicate_recipe_load():
    source = APP_SOURCE.read_text(encoding="utf-8")
    section = source.split('elif menu == "生產單管理":', 1)[1]
    section = section.split("# ======== 代工管理分頁 =========", 1)[0]

    assert "ThreadPoolExecutor(max_workers=3)" in section
    assert "inventory_future = executor.submit(list_inventory_movements" in section
    assert 'st.session_state["_initial_production_inventory"]' in section
    assert "load_recipe(force_reload=False)" not in section
    assert '"production_initial_data"' in section
    assert '"production_stock_calculation"' in section
    assert "main_recipe_by_id = {}" in section
    assert "additions_by_original = {}" in section
    assert 'df_recipe_hist[df_recipe_hist["配方編號"]' not in section


def test_streamlit_widgets_do_not_use_empty_keyword_labels():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert 'label=""' not in source
