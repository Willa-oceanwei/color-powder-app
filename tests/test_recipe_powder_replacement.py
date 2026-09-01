from datetime import date

import pytest

from utils.color_powder_repository import ColorPowderInput, create_color_powder, list_color_powders
from utils.database import DatabaseConfig, connect, initialize_database
from utils.recipe_repository import (
    RecipeError,
    create_recipe,
    find_recipes_using_color_powder,
    list_recipes,
    replace_color_powder_in_recipes,
)


def config_for(tmp_path):
    path = tmp_path / "powder-replacement.db"
    initialize_database(path)
    return path, DatabaseConfig(backend="sqlite", path=path)


def test_preview_and_atomic_replacement_only_change_current_recipes(tmp_path):
    path, config = config_for(tmp_path)
    for powder_id in ("H135", "AH135", "H135A"):
        create_color_powder(config, ColorPowderInput(powder_id, name=powder_id))
    notice = "115/03/07原色粉編號H135更換成AH135"
    create_recipe(config, {
        "配方編號": "A001", "客戶名稱": "XX公司", "顏色": "黑色",
        "色粉編號1": "H135A", "色粉重量1": "1",
        "色粉編號2": "H135", "色粉重量2": "2",
        "色粉編號5": "H135", "色粉重量5": "5",
        "重要提醒": f"此配方夏季需降低5%\n{notice}",
    })
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO production_orders(
                   production_order_id, payload_json, recipe_snapshot_json,
                   source, version, created_at, updated_at)
               VALUES ('P001', ?, ?, 'app', 1, 'now', 'now')""",
            ('{"色粉編號2":"H135"}', '{"色粉編號2":"H135"}'),
        )

    assert find_recipes_using_color_powder(config, " h 135 ") == [{
        "配方編號": "A001", "客戶": "XX公司", "顏色": "黑色", "使用位置": "色粉2、色粉5",
    }]
    updated = replace_color_powder_in_recipes(config, "h135", " ah135 ", date(2026, 3, 7))

    assert updated[0]["更換欄位"] == "色粉2、色粉5"
    recipe = list_recipes(config, include_inactive=True)[0]
    assert recipe["色粉編號1"] == "H135A"
    assert recipe["色粉編號2"] == "AH135"
    assert recipe["色粉編號5"] == "AH135"
    assert recipe["重要提醒"].splitlines().count(notice) == 1
    powders = {row["colorpowder_id"]: row for row in list_color_powders(config, include_inactive=True)}
    assert powders["H135"]["lifecycle_status"] == "inactive"
    assert powders["AH135"]["lifecycle_status"] == "active"
    with connect(path) as conn:
        historical = conn.execute(
            "SELECT payload_json, recipe_snapshot_json FROM production_orders WHERE production_order_id='P001'"
        ).fetchone()
        recipe_events = conn.execute(
            "SELECT COUNT(*) FROM sync_outbox WHERE sheet_name='配方管理' AND row_key='A001'"
        ).fetchone()[0]
    assert tuple(historical) == ('{"色粉編號2":"H135"}', '{"色粉編號2":"H135"}')
    assert recipe_events == 2  # create plus replacement update


def test_replacement_validation_rolls_back_without_new_powder(tmp_path):
    _, config = config_for(tmp_path)
    create_color_powder(config, ColorPowderInput("H135"))
    create_recipe(config, {
        "配方編號": "A001", "色粉編號1": "H135", "色粉重量1": "1",
    })

    with pytest.raises(RecipeError, match="找不到新色粉編號 AH135"):
        replace_color_powder_in_recipes(config, "H135", "AH135", date(2026, 3, 7))

    assert list_recipes(config)[0]["色粉編號1"] == "H135"
    assert list_color_powders(config)[0]["lifecycle_status"] == "active"


def test_replacement_rejects_same_normalized_id(tmp_path):
    _, config = config_for(tmp_path)
    with pytest.raises(RecipeError, match="新舊色粉編號不可相同"):
        replace_color_powder_in_recipes(config, "H 135", "h135", date(2026, 3, 7))
