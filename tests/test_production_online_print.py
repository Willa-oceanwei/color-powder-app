import ast
from html.parser import HTMLParser
from pathlib import Path
import re

from utils.production_print_preview import build_production_order_preview


def _source_document():
    module = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in
                 {"generate_production_order_print", "generate_print_page_content"}]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    order = {"配方編號": "69939BM", "顏色": "綠", "建立時間": "2026-10-29 09:00",
             "包裝重量1": "1", "包裝份數1": "2", "備註": "保留原有 A5 下載"}
    recipe = {"配方編號": "69939BM", "色粉類別": "色母", "合計類別": "料",
              "色粉編號1": "5012", "色粉重量1": "416", "淨重": "100000"}
    return namespace["generate_print_page_content"](order, recipe, [
        {"配方編號": "ADD1", "色粉編號1": "LA", "色粉重量1": "26000", "淨重": "26000"},
    ])


def test_online_preview_has_manual_print_and_preserves_download_print_rules():
    source = _source_document()
    before = source.encode("utf-8")
    preview = build_production_order_preview(source)
    assert 'onclick="window.print()"' in preview
    assert "列印 A5（位置測試）" in preview and "原有 A5 下載仍可使用" in preview
    assert "window.onload" not in preview
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", preview, re.S)
    assert not any("print(" in script for script in scripts)
    for style in re.findall(r"<style[^>]*>.*?</style>", source, re.S):
        assert style in preview
    assert "size: A5 landscape" in preview and "margin: 10mm" in preview
    assert "font-size: 22px" in preview and "translateX(0.2cm)" in preview
    assert "zoom:1!important" in preview and ".toolbar{display:none!important}" in preview
    assert source.encode("utf-8") == before
    assert "window.onload" in source and "window.print()" in source
    assert "production-online-preview" not in source


def test_production_content_values_notes_and_additional_recipes_are_identical():
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    source = _source_document()
    preview = build_production_order_preview(source)
    original_body = re.search(r"<body>(.*?)</body>", source, re.S).group(1)
    online_body = re.search(r'<section class="production-paper paper">(.*?)</section>', preview, re.S).group(1)
    a, b = Text(), Text()
    a.feed(original_body)
    b.feed(online_body)
    assert a.parts == b.parts
    for value in ("69939BM", "100K × 2", "5012", "416", "100000", "ADD1", "26000", "保留原有 A5 下載"):
        assert value in online_body


def test_online_preview_filters_body_scripts_events_and_body_styles():
    source = """<html><head><style>@page{size:A5 landscape;margin:10mm}</style></head>
<body onload="bad()"><pre onclick="evil()">x &amp; y</pre>
<script>bad()</script><style>.paper{display:none}</style><iframe src="bad"></iframe></body></html>"""
    preview = build_production_order_preview(source)
    assert "<pre>x &amp; y</pre>" in preview
    assert "bad()" not in preview and "evil()" not in preview
    assert "onload=" not in preview and "<iframe" not in preview
    assert ".paper{display:none}" not in preview
    assert "@page{size:A5 landscape;margin:10mm}" in preview


def test_all_production_entry_points_keep_a5_download_and_add_online_print():
    source = Path("app.py").read_text(encoding="utf-8")
    history = source.split("def render_order_download_actions(", 1)[1].split("def render_saved_label_section(", 1)[0]
    assert 'online_col.popover("線上列印 A5"' in history
    assert 'data=a5_data, file_name=a5_filename' in history
    assert 'key=f"download_a5_tab2_{order_no}"' in history
    assert 'with st.expander("線上列印 A5（位置測試）"' in source
    assert 'data=print_html.encode("utf-8")' in source and 'key="download_html_tab1"' in source
    assert 'build_production_order_preview(preview_a5_data.decode("utf-8"))' in source
    assert 'data=preview_a5_data' in source and 'key=f"download_a5_tab3_{current_order_no}"' in source
