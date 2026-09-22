from pathlib import Path


APP_SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def test_master_stock_table_shows_matching_carwash_quantity_in_rightmost_column():
    marker_assignment = 'df_result["洗車廠數量"] = df_result["色母編號"].map('
    marker_config = '"洗車廠數量": st.column_config.TextColumn("洗車廠數量", width="small")'

    assignment_position = APP_SOURCE.index(marker_assignment)
    dataframe_position = APP_SOURCE.index("st.dataframe(\n                    df_result", assignment_position)
    config_position = APP_SOURCE.index(marker_config, dataframe_position)

    assert "calculate_carwash_inventory_balances(" in APP_SOURCE[
        assignment_position - 500:assignment_position
    ]
    assert "carwash_quantity_labels.get(" in APP_SOURCE[assignment_position:dataframe_position]
    assert config_position > APP_SOURCE.index('"備註":', dataframe_position)
