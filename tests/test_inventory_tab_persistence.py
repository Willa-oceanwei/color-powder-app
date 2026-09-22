from pathlib import Path


APP_SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def test_inventory_tabs_have_a_page_scoped_persistence_controller():
    assert 'const storageKey = "inventory_active_tab";' in APP_SOURCE
    assert "function bindInventoryTabs()" in APP_SOURCE
    assert "window.parent.sessionStorage.setItem(storageKey, String(idx));" in APP_SOURCE


def test_generic_controller_skips_inventory_tabs():
    inventory_labels = "📦 初始|📊 查詢|📋 盤點|🏆 排行|🧮 用量|🧴 色母|👤 客戶"
    assert inventory_labels in APP_SOURCE
    assert "if (PAGE_MANAGED_TAB_LABELS.has(getTabLabels(tabList))) return;" in APP_SOURCE


def test_inventory_controller_targets_the_complete_unique_tab_set():
    expected_labels = (
        '["📦 初始", "📊 查詢", "📋 盤點", "🏆 排行", '
        '"🧮 用量", "🧴 色母", "👤 客戶"]'
    )
    assert expected_labels in APP_SOURCE
    assert "labels.length === tabTexts.length" in APP_SOURCE
    assert "tabTexts.every((label, idx) => labels[idx] === label)" in APP_SOURCE


def test_carwash_movement_editor_only_shows_five_most_recent_records():
    editor_source = APP_SOURCE[
        APP_SOURCE.index('with edit_tab2:') : APP_SOURCE.index('\ndef parse_formula_root')
    ]

    assert '["紀錄日期排序", "sheet_idx"]' in editor_source
    assert "ascending=[False, False]" in editor_source
    assert ".head(5)" in editor_source
    assert "最近五筆" in editor_source


def test_carwash_movement_editor_can_archive_duplicate_records():
    editor_source = APP_SOURCE[
        APP_SOURCE.index('with edit_tab2:') : APP_SOURCE.index('\ndef parse_formula_root')
    ]

    assert "我確認這筆是重覆新增的資料" in editor_source
    assert "archive_carwash_inventory_movement(" in editor_source
    assert 'reason="使用者刪除重覆新增的出入庫資料"' in editor_source
