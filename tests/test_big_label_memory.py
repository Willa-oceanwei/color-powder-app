import ast
from pathlib import Path

from utils.big_label_repository import (
    build_big_label_editor_defaults, expand_big_label_editor_rows,
    normalize_big_label_editor_rows, remember_big_label_rows,
)
from utils.database import DatabaseConfig, initialize_database


def test_only_identity_and_ratio_survive_new_database_connection(tmp_path):
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
    next_order = {**order, "生產日期": "2026-10-16", "包裝重量1": "30", "包裝份數1": "5"}
    restored = build_big_label_editor_defaults(fresh_config, next_order, namespace["build_big_label_rows"](next_order))
    assert restored == [{"編號": "Edited", "品名": "New name", "日期": "2026-10-16", "比例": "3:4", "數量": "30KG", "列印張數": 5}]
    assert len(expand_big_label_editor_rows(revised)) == 3
    assert build_big_label_editor_defaults(config, {"配方編號": "R002"}, [])[0]["編號"] == "R002"


def test_legacy_saved_rows_do_not_restore_old_date_counts_or_package_shape(tmp_path):
    import json
    from utils.database import connect_from_config

    config = DatabaseConfig(backend="sqlite", path=tmp_path / "legacy.db")
    initialize_database(config.path)
    legacy = [{"編號": "Edited", "品名": "New name", "比例": "4g/kg",
               "日期": "115/01/01", "列印張數": 99, "數量": "99KG"}] * 3
    with connect_from_config(config) as conn:
        for key in ("R001", json.dumps(["small", "R001"])):
            conn.execute("INSERT INTO big_label_templates VALUES (?, ?, ?)", (key, json.dumps(legacy), "old"))
    labels = [{"編號": "R001", "名稱": "Current", "日期": "115/10/16", "比例": "2g/kg", "數量": "25"}] * 2
    for kind in ("big", "small"):
        restored = build_big_label_editor_defaults(config, {"配方編號": "R001"}, labels, label_kind=kind)
        assert restored == [{"編號": "Edited", "品名": "New name", "比例": "4g/kg", "日期": "115/10/16", "數量": "25KG", "列印張數": 2}]
        remember_big_label_rows(config, {"配方編號": "R001"}, restored, label_kind=kind)
    with connect_from_config(config) as conn:
        for (payload,) in conn.execute("SELECT rows_json FROM big_label_templates"):
            assert set(json.loads(payload)[0]) == {"編號", "品名", "比例"}


def test_empty_cells_and_removed_rows_are_safe():
    rows = normalize_big_label_editor_rows([
        {"編號": None, "數量": float("nan"), "列印張數": float("nan")},
        {"品名": "Keep", "列印張數": 0},
    ])
    assert len(rows) == 1 and rows[0]["品名"] == "Keep"
    assert expand_big_label_editor_rows(rows) == []
