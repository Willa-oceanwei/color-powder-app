import ast
from html import escape
from pathlib import Path


def _load_generate_big_label_html():
    """Load the pure HTML helper without executing the Streamlit application."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    functions = [
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"chunk_label_pages", "generate_big_label_html"}
    ]
    namespace = {"html_escape": type("HtmlEscape", (), {"escape": staticmethod(escape)})}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["generate_big_label_html"]


def _load_quick_label_helpers():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    functions = [
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"build_quick_labels", "chunk_label_pages"}
    ]
    namespace = {
        "format_label_ratio": lambda order: order.get("比例", ""),
        "to_roc_date": lambda value: value,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def _load_get_saved_label_order():
    """Load the snapshot selector without executing the Streamlit app."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_saved_label_order"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["get_saved_label_order"]


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


def test_quick_rows_expand_weights_and_ignore_zero_counts():
    helpers = _load_quick_label_helpers()
    labels = helpers["build_quick_labels"](
        {"配方編號": "R001", "顏色": "原名稱", "比例": "1:2", "生產日期": "115/09/01"},
        "修改後名稱",
        [
            {"weight": "25K", "qty": 5},
            {"weight": "30K", "qty": 1},
            {"weight": "", "qty": 0},
        ],
    )

    assert [label["數量"] for label in labels] == ["25K"] * 5 + ["30K"]
    assert all(label["名稱"] == "修改後名稱" for label in labels)


def test_labels_are_chunked_into_real_four_label_pages():
    helpers = _load_quick_label_helpers()

    assert helpers["chunk_label_pages"](list(range(10))) == [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [8, 9],
    ]

    html = _load_generate_big_label_html()([{"數量": str(i)} for i in range(5)])
    assert html.count('class="sheet"') == 2
    assert "break-after: page;" in html
    assert "break-inside: avoid-page;" in html


def test_saved_label_order_is_independent_of_live_draft_flow():
    get_saved_order = _load_get_saved_label_order()
    saved_order = {"生產單號": "P001", "配方編號": "R001"}

    assert get_saved_order({"order": saved_order, "a5_downloaded": False}) is saved_order


def test_saved_label_order_rejects_incomplete_snapshots():
    get_saved_order = _load_get_saved_label_order()

    assert get_saved_order(None) is None
    assert get_saved_order({}) is None
    assert get_saved_order({"order": {"配方編號": "R001"}}) is None
