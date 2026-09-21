from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "app.py"


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
