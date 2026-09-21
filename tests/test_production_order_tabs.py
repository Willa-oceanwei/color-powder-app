from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "app.py"


def test_production_order_tabs_use_only_shared_persistence_controller():
    source = APP_SOURCE.read_text(encoding="utf-8")
    section = source.split("# =============== Tab 架構開始 ===============", 1)[1]
    section = section.split("# ======== 代工管理分頁 =========", 1)[0]

    assert "apply_tab_persistence_fix()" in source
    assert 'const storageKey = "order_mgmt_active_tab"' not in section
    assert "orderPersistBound" not in section
    assert "new MutationObserver" not in section
