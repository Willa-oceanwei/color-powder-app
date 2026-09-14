import ast
from pathlib import Path

def _load_shipment_helpers():
    """Load pure formatting helpers without executing the Streamlit app."""
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"fmt_num", "parse_pack_value", "calculate_shipment_display"}
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {"re": __import__("re")}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["calculate_shipment_display"]


def test_barrel_recipe_displays_quarter_as_25k_even_with_stale_order_unit():
    calculate = _load_shipment_helpers()
    recipes = [{"配方編號": "R001", "計量單位": "桶", "色粉類別": "配方"}]
    order = {
        "配方編號": "R001",
        "計量單位": "包",
        "包裝重量1": "0.25",
        "包裝份數1": "8",
    }

    assert calculate(order, recipes) == "25K*8"


def test_shipment_display_formats_multiple_packages_and_unit_suffixes():
    calculate = _load_shipment_helpers()
    recipes = [{"配方編號": "R002", "計量單位": "kg", "色粉類別": "配方"}]
    order = {
        "配方編號": "R002",
        "包裝重量1": "25kg",
        "包裝份數1": "2",
        "包裝重量2": "10",
        "包裝份數2": "1.5",
    }

    assert calculate(order, recipes) == "25kg*2 + 10kg*1.5"
