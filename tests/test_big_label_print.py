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
    assert 'class="field left" style="left:-0.1cm; top:0.5cm;"' in result
    assert 'class="field right" style="left:1.4cm; top:0.5cm;"' in result
    assert 'class="field right" style="left:1.4cm; top:1.5cm;"' in result
    assert 'class="field left" style="left:-0.1cm; top:2.5cm;"' in result
    assert 'class="field right" style="left:1.4cm; top:2.5cm;"' in result
    assert "width: 1.0cm;" in result
    assert "context.measureText(field.textContent)" in result
    assert "await document.fonts.ready;" in result


def test_big_label_html_uses_point_two_centimetre_gaps():
    generate = _load_generate_big_label_html()
    rows = [{"編號": str(number)} for number in range(4)]

    result = generate(rows)

    for top in (0.0, 8.0, 16.0, 24.0):
        assert f'top:{top}cm; left:0.6cm;' in result
    assert 24.0 + 7.8 <= 32.0


def test_big_label_html_escapes_user_content():
    generate = _load_generate_big_label_html()

    result = generate([{"名稱": "<script>alert(1)</script>"}])

    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result


def test_a4_carrier_keeps_text_inside_page_and_compensates_right_fields():
    generate = _load_generate_big_label_html()
    result = generate([{"編號": "10032", "名稱": "黑色母", "數量": "30KG"}] * 4,
                      paper_stock="a4_driver")
    assert "@page { size: A4; margin: 0; }" in result
    assert "width: 21.0cm;" in result and "height: 29.7cm;" in result
    assert "overflow: hidden;" in result
    assert 'class="field left" style="left:0.9cm; top:0.5cm; width:4.5cm;"' in result
    assert 'class="field right" style="left:5.9cm; top:0.5cm;"' in result
    assert 'class="field right" style="left:5.9cm; top:1.5cm;"' in result
    assert 'class="field left" style="left:0.9cm; top:2.5cm; width:4.5cm;"' in result
    assert 'class="field right" style="left:5.9cm; top:2.5cm;"' in result
    assert "width: 5.5cm;" in result
    assert 0.6 - 0.1 > 0
    assert 24 + 2.5 + 18 * 2.54 / 72 < 29.7
    assert result.count('class="sheet"') == 1
    assert result.count("10032") == 4


def test_short_number_and_name_shift_together_without_moving_date_or_weight():
    generate = _load_generate_big_label_html()
    short = generate([{"編號": "00123", "名稱": "紅色", "日期": "115/10/14", "數量": "25KG"}],
                     paper_stock="a4_driver")
    assert 'left:0.9cm; top:0.5cm; width:4.5cm;">00123' in short
    assert 'left:0.9cm; top:2.5cm; width:4.5cm;">紅色' in short
    assert 'left:5.9cm; top:0.5cm;">115/10/14' in short
    assert 'left:5.9cm; top:2.5cm;">25KG' in short
    for number, name in [("1234567", "紅色"), ("12345", "黑色母粉"), ("A123", "紅色"), ("", "紅色"), ("12345", "")]:
        normal = generate([{"編號": number, "名稱": name}], paper_stock="a4_driver")
        assert 'left:-0.1cm; top:0.5cm;' in normal
        assert 'left:-0.1cm; top:2.5cm;' in normal
    mixed = generate([{"編號": "12345", "名稱": "紅色"}, {"編號": "12345", "名稱": "黑色母"}],
                     paper_stock="a4_driver")
    assert mixed.count('left:0.9cm;') == 4


def test_six_digit_and_three_character_limits_use_the_same_short_label_position():
    generate = _load_generate_big_label_html()
    for number, name in [("10032", "黑色母"), ("123456", "天空藍"), ("123456", "紅色")]:
        result = generate([{"編號": number, "名稱": name, "日期": "115/10/14", "數量": "30KG"}],
                          paper_stock="a4_driver")
        assert f'left:0.9cm; top:0.5cm; width:4.5cm;">{number}' in result
        assert f'left:0.9cm; top:2.5cm; width:4.5cm;">{name}' in result
        assert 'left:5.9cm; top:0.5cm;">115/10/14' in result
        assert 'left:5.9cm; top:2.5cm;">30KG' in result


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


def test_saved_order_a5_download_has_print_setup_and_safe_filename():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"generate_production_order_print", "generate_print_page_content", "build_a5_production_order_download"}
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in wanted]

    # Filename behavior can be validated without a pandas fixture by using an empty recipe table.
    class EmptyRecipes:
        empty = True

    namespace = {"pd": type("PD", (), {"isna": staticmethod(lambda _: False)}), "re": __import__("re")}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)

    data, filename = namespace["build_a5_production_order_download"](
        {"生產單號": "PO/001", "配方編號": "R:01", "建立時間": "2026-09-02"},
        EmptyRecipes(),
    )

    html = data.decode("utf-8")
    assert filename == "PO-001_R-01_A5列印.html"
    assert "size: A5 landscape" in html
    assert "window.print()" in html


def test_a5_print_ignores_malformed_additional_recipe_rows():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"generate_production_order_print", "generate_print_page_content"}
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)

    html = namespace["generate_print_page_content"](
        order={"生產單號": "P001"},
        recipe_row={"配方編號": "R001"},
        additional_recipe_rows=["stale recipe id", None, {"配方編號": "A001"}],
    )

    assert "附加配方 1：A001" in html
    assert "stale recipe id" not in html
