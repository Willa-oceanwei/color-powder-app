"""Regression coverage for derived catalog work in the three daily workspaces."""

import pandas as pd
import pytest

from utils import recipe_page_data
from utils.shipment_catalog import ProductMatcher, editing_product_matcher, complete_items


def test_index_preserves_exact_alias_partial_and_historical_name_matching():
    choices = {
        "27706M": {"name": "Silver"}, "27706M-1": {"name": "Silver revision"},
        "C0757": {"name": "White"}, "p1": {"name": "First"}, "P1": {"name": "Second"},
    }
    matcher = ProductMatcher(choices)
    assert matcher.match(" 27706m ") == ["27706M"]
    assert matcher.match("27706") == ["27706M", "27706M-1"]
    assert matcher.match("0757") == ["C0757"]
    assert matcher.match("P1") == ["p1", "P1"]
    assert matcher.match("silver", by_name=True) == ["27706M"]
    assert matcher.match("revision", by_name=True) == ["27706M-1"]
    history = [{"code": "P1", "name": "Customer name"}]
    assert matcher.match("Customer name", by_name=True, history=history) == ["p1"]
    assert matcher.match("Customer name", by_name=True, history=[]) == []
    result = matcher.match("27706")
    result.clear()
    assert matcher.match("27706") == ["27706M", "27706M-1"]


def test_repeated_grid_edits_reuse_index_and_refresh_replaces_it():
    class Catalog(dict):
        scans = 0

        def __iter__(self):
            self.scans += 1
            return super().__iter__()

    choices = Catalog({f"P{i}": {"name": f"Name {i}"} for i in range(5000)})
    state = {}
    matcher = editing_product_matcher(state, choices)
    scans = choices.scans
    original = {"code": "P42", "name": "Custom", "unit": "KG", "quantity": 1, "price": 10}
    for quantity in range(2, 12):
        assert editing_product_matcher(state, choices) is matcher
        row = dict(original, quantity=quantity, price=20)
        result = complete_items(None, {}, [row], [original], choices=choices, history=[], matcher=matcher)
        assert result == [row]
        assert matcher.match("P42") == ["P42"]
    assert choices.scans == scans
    refreshed = dict(choices, **{"27706M": {"name": "Silver"}})
    replacement = editing_product_matcher(state, refreshed)
    assert replacement is not matcher
    assert replacement.match("27706M") == ["27706M"]


def test_recipe_label_cache_detects_in_place_edits_and_preserves_order(monkeypatch):
    frame = pd.DataFrame([
        {"配方編號": "R1", "顏色": "Blue", "客戶名稱": "C1", "狀態": "", "備註": ""},
        {"配方編號": "R1", "顏色": "White", "客戶名稱": "C2", "狀態": "停用", "備註": ""},
    ])
    state = {}
    expected = recipe_page_data.recipe_preview_labels(frame)
    assert recipe_page_data.recipe_preview_labels(frame, state) == expected
    cached = state["recipe_preview_label_cache"]
    original = recipe_page_data.recipe_is_inactive
    monkeypatch.setattr(recipe_page_data, "recipe_is_inactive", lambda row: pytest.fail("labels rebuilt"))
    result = recipe_page_data.recipe_preview_labels(frame, state)
    result["R1"] = "external edit"
    frame.loc[0, "備註"] = "Unrelated field"
    assert recipe_page_data.recipe_preview_labels(frame, state) == expected
    assert state["recipe_preview_label_cache"] is cached
    monkeypatch.setattr(recipe_page_data, "recipe_is_inactive", original)
    frame.loc[0, "狀態"] = "停用"
    assert "【停用配方】" in recipe_page_data.recipe_preview_labels(frame, state)["R1"]
    reversed_frame = frame.iloc[::-1]
    assert "White" in recipe_page_data.recipe_preview_labels(reversed_frame, state)["R1"]


