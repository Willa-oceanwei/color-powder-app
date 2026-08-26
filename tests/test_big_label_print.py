import ast
from html import escape
from pathlib import Path


def _load_generate_big_label_html():
    """Load the pure HTML helper without executing the Streamlit application."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "generate_big_label_html"
    )
    namespace = {"html_escape": type("HtmlEscape", (), {"escape": staticmethod(escape)})}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["generate_big_label_html"]


def test_big_label_html_uses_physical_stock_dimensions_and_anchors():
    generate = _load_generate_big_label_html()

    result = generate([{"編號": "A-01", "日期": "115/08/26"}])

    assert "@page { size: 12.0cm 32.0cm; margin: 0; }" in result
    assert "width: 10.8cm;" in result
    assert "height: 7.8cm;" in result
    assert 'style="top:0.0cm; left:0.6cm;"' in result
    assert 'class="field left" style="left:1.9cm; top:1.0cm;"' in result
    assert 'class="field right" style="left:7.4cm; top:1.0cm;"' in result
    assert 'class="field left" style="left:1.9cm; top:2.1cm;"' in result


def test_big_label_html_uses_point_three_centimetre_gaps():
    generate = _load_generate_big_label_html()
    rows = [{"編號": str(number)} for number in range(4)]

    result = generate(rows)

    for top in (0.0, 8.1, 16.2, 24.3):
        assert f'top:{top}cm; left:0.6cm;' in result


def test_big_label_html_escapes_user_content():
    generate = _load_generate_big_label_html()

    result = generate([{"名稱": "<script>alert(1)</script>"}])

    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result
