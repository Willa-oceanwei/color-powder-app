import ast
from html.parser import HTMLParser
from pathlib import Path

import pytest

from utils.paper_preview import build_paper_preview


def print_functions():
    module = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"generate_production_order_print", "generate_print_page_content"}]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("category,label,expected", [
    ("色母", "料", "料"), ("色母", "原料", "料"),
    ("配方", "料", "料"), ("配方", "其他", "其他"),
    ("配方", "CA", "CA"), ("配方", "無", "="),
])
def test_total_labels_share_numeric_font_and_fixed_width(category, label, expected):
    functions = print_functions()
    order = {"色粉類別": category, "包裝重量1": "1", "包裝份數1": "5"}
    recipe = {"配方編號": "52474AM", "色粉編號1": "302", "色粉重量1": "1160",
              "淨重": "60000", "合計類別": label}
    document = functions["generate_print_page_content"](order, recipe, [recipe])
    preview = build_paper_preview(document, title="生產單", document=True)

    class Labels(HTMLParser):
        def __init__(self):
            super().__init__()
            self.labels = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("class") == "production-total-label":
                self.labels.append(attrs["style"])

    for html in (document, preview):
        labels = Labels()
        labels.feed(html)
        assert len(labels.labels) == 2
        assert all("width:12ch" in style and "font-size:inherit" in style for style in labels.labels)
        assert f">{expected}</b>" in html
        assert "font-size:22px" not in html
        assert "scale(0.7)" not in html
        assert "1160" in html
        assert "58840" in html if category == "色母" else "60000" in html
