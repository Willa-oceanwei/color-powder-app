"""Regression coverage for legacy production-order colorant print previews."""

import ast
from pathlib import Path
import unittest


def _load_print_helpers():
    source = Path("app.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {"generate_production_order_print", "generate_print_page_content"}
    functions = [
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


class ProductionOrderPrintCategoryTests(unittest.TestCase):
    def setUp(self):
        self.helpers = _load_print_helpers()
        self.order = {"配方編號": "69939BM", "包裝重量1": "1", "包裝份數1": "2"}
        self.recipe = {
            "配方編號": "69939BM", "色粉類別": "色母", "計量單位": "kg",
            "合計類別": "料", "淨重": "100000",
            "色粉編號1": "5012", "色粉重量1": "416",
        }

    def test_legacy_order_uses_recipe_category_in_full_a5_preview(self):
        for category in ("missing", "", "   "):
            with self.subTest(category=category):
                order = dict(self.order)
                if category != "missing":
                    order["色粉類別"] = category
                before = dict(order)
                recipe_before = dict(self.recipe)
                result = self.helpers["generate_print_page_content"](order, self.recipe)
                self.assertIn("100K × 2", result)
                self.assertNotIn("1kg × 2", result)
                # Only the package heading changes; legacy totals stay unchanged.
                self.assertIn("100000", result)
                self.assertNotIn("99584", result)
                self.assertIn("＿" * 28, result)
                self.assertEqual(order, before)
                self.assertEqual(self.recipe, recipe_before)

    def test_fractional_colorant_headings_keep_counts_and_legacy_totals(self):
        self.order.update({"包裝重量1": "0.5", "包裝重量2": "1", "包裝份數2": "3"})
        result = self.helpers["generate_production_order_print"](self.order, self.recipe)
        self.assertIn("50K × 2", result)
        self.assertIn("100K × 3", result)
        self.assertIn("50000", result)
        self.assertIn("100000", result)
        self.assertNotIn("49792", result)
        self.assertNotIn("99584", result)

    def test_saved_category_takes_precedence_over_recipe(self):
        self.order["色粉類別"] = "色粉"
        result = self.helpers["generate_production_order_print"](self.order, self.recipe)
        self.assertIn("1kg × 2", result)
        self.assertIn("＿" * 28, result)
        self.assertNotIn("99584", result)

    def test_existing_colorant_order_still_works_without_recipe_category(self):
        self.order["色粉類別"] = " 色母 "
        self.recipe.pop("色粉類別")
        result = self.helpers["generate_production_order_print"](self.order, self.recipe)
        self.assertIn("100K × 2", result)
        self.assertIn("99584", result)

    def test_non_colorant_units_keep_existing_conversion(self):
        for unit, weight, heading in (
            ("kg", "1", "1kg × 2"),
            ("包", "1", "25K × 2"),
            ("桶", "1", "100K × 2"),
        ):
            with self.subTest(unit=unit):
                self.recipe.update({"色粉類別": "色粉", "計量單位": unit})
                self.order["包裝重量1"] = weight
                result = self.helpers["generate_production_order_print"](self.order, self.recipe)
                self.assertIn(heading, result)
                self.assertIn("＿" * 28, result)

    def test_missing_categories_keep_ordinary_kg_display(self):
        self.recipe.pop("色粉類別")
        result = self.helpers["generate_production_order_print"](self.order, self.recipe)
        self.assertIn("1kg × 2", result)


if __name__ == "__main__":
    unittest.main()
