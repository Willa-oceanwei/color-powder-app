"""Synthetic CPU benchmark; excludes browser, network, and database latency.

Run from the repository root: python scripts/benchmark_daily_workflows.py
"""

import ast
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from textwrap import dedent
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from utils.recipe_page_data import recipe_preview_labels
from utils.shipment_catalog import ProductMatcher

BASE = "a6bd81eb04d3bc1e8c07917c23f4f2e596a3ed10"


def baseline(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT).decode("utf-8")


def function(source, name, namespace):
    node = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.FunctionDef) and node.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), name, "exec"), namespace)
    return namespace[name]


def measure(call):
    call()
    samples = []
    for _ in range(9):
        start = perf_counter()
        call()
        samples.append((perf_counter() - start) * 1000)
    return round(median(samples), 3)


def compare(name, old, new):
    before, after = measure(old), measure(new)
    return {"operation": name, "before_ms": before, "after_ms": after,
            "reduction_percent": round((before - after) / before * 100, 1)}


def main():
    rows = 5000
    choices = {f"P{i:05}": {"name": f"Name {i}"} for i in range(rows)}
    codes = list(choices)[-30:]
    old_match = function(baseline("utils/shipment_catalog.py"), "matching_products", {})
    matcher = ProductMatcher(choices)
    frame = pd.DataFrame([
        {"配方編號": code, "顏色": "Blue", "客戶名稱": "Customer", "狀態": "",
         "生命週期": "active", "配方類別": "原始配方", **{f"extra_{i}": str(i) for i in range(40)}}
        for code in choices
    ])
    old_labels = function(baseline("utils/recipe_page_data.py"), "recipe_preview_labels",
                          {"recipe_is_inactive": lambda row: False})
    state = {}
    old_app = baseline("app.py")
    new_app = (ROOT / "app.py").read_text(encoding="utf-8")

    def production(source):
        workspace = source.split("def render_production_order_workspace():", 1)[1]
        section = workspace[workspace.index("        search_df ="):workspace.index("        # ===== 顯示選擇結果")]
        namespace = {"pd": pd, "df_recipe": frame, "keywords": [], "search_text_tab1": ""}
        function(source, "format_option", namespace)
        function(source, "format_option_with_status", namespace)
        code = compile(dedent(section), "production-options", "exec")
        return lambda: exec(code, namespace), namespace

    before_options, before_state = production(old_app)
    after_options, after_state = production(new_app)
    # Verify the measured operations return the same values before timing them.
    assert [old_match(choices, code) for code in codes] == [matcher.match(code) for code in codes]
    assert old_labels(frame) == recipe_preview_labels(frame, state)
    before_options()
    after_options()
    assert {key: {field: value for field, value in row.items() if field != "_search_text"}
            for key, row in before_state["option_map"].items()} == after_state["option_map"]
    results = [
        compare("shipment: 30 rows, three catalog-match passes",
                lambda: [old_match(choices, code) for _ in range(3) for code in codes],
                lambda: [matcher.match(code) for _ in range(3) for code in codes]),
        compare("recipe: two preview-label consumers per rerun",
                lambda: [old_labels(frame) for _ in range(2)],
                lambda: [recipe_preview_labels(frame, state) for _ in range(2)]),
        compare("production: unfiltered recipe dropdown preparation", before_options, after_options),
    ]
    print(json.dumps({"baseline": BASE, "catalog_rows": rows, "median_of": 9,
                      "runtime": {"pandas": pd.__version__},
                      "shipment_index_build_ms": measure(lambda: ProductMatcher(choices)),
                      "results": results}, indent=2))


if __name__ == "__main__":
    main()
