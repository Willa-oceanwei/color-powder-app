import ast
from datetime import date, datetime
from pathlib import Path


APP_SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def _load_balance_helper():
    module = ast.parse(APP_SOURCE)
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_calculate_carwash_inventory_balances"
    )
    namespace = {"datetime": datetime}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["_calculate_carwash_inventory_balances"]


def test_master_stock_table_shows_matching_carwash_quantity_in_rightmost_column():
    marker_assignment = 'df_result["洗車廠數量"] = df_result["色母編號"].map('
    marker_config = '"洗車廠數量": st.column_config.TextColumn("洗車廠數量", width="small")'

    assignment_position = APP_SOURCE.index(marker_assignment)
    dataframe_position = APP_SOURCE.index("st.dataframe(\n                    df_result", assignment_position)
    config_position = APP_SOURCE.index(marker_config, dataframe_position)

    assert "_calculate_carwash_inventory_balances(" in APP_SOURCE[
        assignment_position - 500:assignment_position
    ]
    assert "carwash_quantity_labels.get(" in APP_SOURCE[assignment_position:dataframe_position]
    assert config_position > APP_SOURCE.index('"備註":', dataframe_position)


def test_carwash_balance_helper_uses_latest_initial_and_following_movements():
    calculate = _load_balance_helper()
    records = [
        {"movement_type": "初始庫存", "initial_date": "2026-01-01", "initial_quantity": 20,
         "product_id": " MB-01 ", "unit": "KG"},
        {"movement_type": "入庫", "inbound_date": "2026-01-03", "quantity": 7,
         "product_id": "mb-01", "unit": "KG"},
        {"movement_type": "初始庫存", "initial_date": "2026-02-01", "initial_quantity": 10,
         "product_id": "MB-01", "unit": "KG"},
        {"movement_type": "出庫", "outbound_date": "2026-02-02", "quantity": 2.5,
         "product_id": "MB-01", "unit": "KG"},
        {"movement_type": "入庫", "inbound_date": "2026-04-01", "quantity": 99,
         "product_id": "MB-01", "unit": "KG"},
    ]

    assert calculate(records, as_of=date(2026, 3, 1)) == {"mb-01": (7.5, "KG")}


def test_app_does_not_import_new_carwash_helper_during_deployment():
    import_start = APP_SOURCE.index("from utils.carwash_inventory_repository import (")
    import_block = APP_SOURCE[import_start:APP_SOURCE.index(")", import_start)]
    assert "calculate_carwash_inventory_balances" not in import_block
