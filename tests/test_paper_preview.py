import ast
from pathlib import Path

from utils.paper_preview import build_paper_preview


def test_recipe_content_is_preserved_and_escaped():
    source = "```\n編號：R001 顏色：白\n302         6\nMA          25\n備註：<script>alert(1)</script>\n```"
    html = build_paper_preview(source, title="配方")
    assert "302         6\nMA          25" in html
    assert "```" not in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "background:#fff;color:#000" in html
    assert "符合寬度" in html and "整頁" in html and "200%" in html
    assert "overflow:auto" in html and "white-space:pre-wrap" in html


def test_production_reuses_print_body_without_auto_print():
    module = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and
                 n.name in {"generate_production_order_print", "generate_print_page_content"}]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    source = namespace["generate_print_page_content"](
        {"配方編號": "R001", "顏色": "白", "建立時間": "2026-10-08 09:00", "包裝重量1": "1", "包裝份數1": "2"},
        {"配方編號": "R001", "色粉編號1": "302", "色粉重量1": "6", "淨重": "25"},
        [{"配方編號": "A001", "色粉編號1": "200", "色粉重量1": "50"}],
    )
    html = build_paper_preview(source, title="生產單", document=True)
    assert "window.print()" in source and "window.print()" not in html
    assert "2026-10-08 09:00" in html and "R001" in html and "302" in html and "A001" in html
    assert "display:flex" in html and "<pre>" in html
    assert html.count("<html") == 1 and html.count("<body") == 1


def test_document_drops_active_elements_and_event_handlers():
    source = '<html><head><script>window.print()</script></head><body onload="alert(1)"><pre onclick="alert(2)">x &amp; y</pre><script>evil()</script><iframe src="bad"></iframe></body></html>'
    html = build_paper_preview(source, title="生產單", document=True)
    assert "onload=" not in html and "onclick=" not in html and "evil()" not in html
    assert "<iframe" not in html and "<pre>x &amp; y</pre>" in html
