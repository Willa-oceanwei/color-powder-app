import ast
from pathlib import Path

from utils.big_label_repository import (
    build_big_label_editor_defaults, expand_big_label_editor_rows,
    normalize_big_label_editor_rows, remember_big_label_rows,
)
from utils.database import DatabaseConfig, initialize_database


def test_package_counts_and_all_edits_survive_new_database_connection(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "labels.db")
    initialize_database(config.path)
    module = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    helper = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "build_big_label_rows")
    namespace = {"format_label_ratio": lambda order: "1:2", "to_roc_date": lambda value: value}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "app.py", "exec"), namespace)
    order = {"配方編號": "R001", "顏色": "Blue", "生產日期": "2026-10-14", "包裝重量1": "25", "包裝份數1": "2"}
    rows = build_big_label_editor_defaults(config, order, namespace["build_big_label_rows"](order))
    assert rows[0]["數量"] == "25KG"
    assert rows[0]["列印張數"] == 2
    assert len(expand_big_label_editor_rows(rows)) == 2
    revised = [{"編號": "Edited", "品名": "New name", "日期": "115/10/15", "比例": "3:4", "數量": "10KG", "列印張數": 3}]
    remember_big_label_rows(config, order, revised)
    fresh_config = DatabaseConfig(backend="sqlite", path=config.path)
    assert build_big_label_editor_defaults(fresh_config, {"配方編號": "R001"}, []) == revised
    assert len(expand_big_label_editor_rows(revised)) == 3
    assert build_big_label_editor_defaults(config, {"配方編號": "R002"}, [])[0]["編號"] == "R002"


def test_empty_cells_and_removed_rows_are_safe():
    rows = normalize_big_label_editor_rows([
        {"編號": None, "數量": float("nan"), "列印張數": float("nan")},
        {"品名": "Keep", "列印張數": 0},
    ])
    assert len(rows) == 1 and rows[0]["品名"] == "Keep"
    assert expand_big_label_editor_rows(rows) == []
