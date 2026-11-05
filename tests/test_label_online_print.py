import re

import pytest

from test_big_label_print import _load_generate_big_label_html
from utils.label_print_preview import build_label_print_preview
from utils.small_label_print import generate_small_label_html


@pytest.mark.parametrize("small", [False, True])
@pytest.mark.parametrize("paper_stock", ["a4_driver", "custom"])
def test_online_labels_preserve_print_layout_and_require_manual_print(small, paper_stock):
    rows = [{"編號": "69783DM", "名稱": "<白>", "日期": "115/10/29",
             "比例": "25:1", "數量": "100KG"}] * 11
    generate = generate_small_label_html if small else _load_generate_big_label_html()
    source = generate(rows, paper_stock=paper_stock)
    preview = build_label_print_preview(source)
    assert 'onclick="window.print()"' in preview
    assert "列印標籤" in preview
    assert "window.print();" in source
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", preview, re.S)
    assert all("window.print" not in script for script in scripts)
    assert "fitLabelText" in preview and "beforeprint" in preview
    for style in re.findall(r"<style[^>]*>.*?</style>", source, re.S):
        assert style in preview
    original_sheets = re.search(r"<body>(.*?)</body>", source, re.S).group(1)
    assert original_sheets in preview
    assert preview.count('class="sheet"') == (2 if small else 3)
    assert '&lt;<span class="label-chinese">白</span>&gt;' in preview
    assert ".label-chinese { font-weight: 700;" in preview
    assert '<span class="label-chinese">69783DM</span>' not in preview
    assert "zoom:1!important" in preview
    assert ".toolbar{display:none!important}" in preview
    assert "列印比例請選 100%" in preview


def test_online_small_labels_keep_selected_positions():
    source = generate_small_label_html(
        [{"編號": "001", "名稱": "白"}] * 3, selected_positions=[4, 6, 8],
    )
    preview = build_label_print_preview(source)
    assert preview.count('class="sheet"') == 1
    assert preview.count('class="label-slot"') == 3
    assert 'left:0.6cm;top:18.25cm;' in preview
