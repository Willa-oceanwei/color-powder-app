import ast
from pathlib import Path


def test_accounting_between_production_and_warehouse_in_all_menus():
    source = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    menus = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MENU_ITEMS"
            for target in node.targets
        ):
            menus.append(ast.literal_eval(node.value))
    assert len(menus) == 3
    for menu in menus:
        groups = list(dict.fromkeys(item["group"] for item in menu))
        assert groups[:3] == ["生產", "會計", "倉儲"]
        assert sum(item["key"] == "出貨單" for item in menu) == 1
