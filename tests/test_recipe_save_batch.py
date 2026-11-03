from contextlib import contextmanager

import pytest

from utils import recipe_repository as repository
from utils.color_powder_repository import ColorPowderInput, create_color_powder
from utils.database import DatabaseConfig, initialize_database


@pytest.mark.parametrize("count", [0, 1, 8])
def test_component_save_batches_round_trips_and_keeps_positions(tmp_path, monkeypatch, count):
    config = DatabaseConfig("sqlite", tmp_path / "batch.db")
    initialize_database(config.path)
    row = {"配方編號": "B001", "顏色": "Blue"}
    for i in range(1, count + 1):
        create_color_powder(config, ColorPowderInput(f"P{i}"))
        row[f"色粉編號{i}"] = f"P{i}"
        row[f"色粉重量{i}"] = str(i * 10)
    statements = []
    original = repository.connect_from_config
    @contextmanager
    def capture(config):
        with original(config) as conn:
            conn.set_trace_callback(statements.append)
            yield conn
    monkeypatch.setattr(repository, "connect_from_config", capture)
    repository.create_recipe(config, row)
    row["備註"] = "Updated"
    statements.clear()
    repository.update_recipe(config, row)
    inserts = [s for s in statements if s.startswith("INSERT INTO recipe_components")]
    assert len(inserts) == (1 if count else 0)
    lookups = [s for s in statements if s.startswith("SELECT colorpowder_id FROM color_powders")]
    assert len(lookups) == (1 if count else 0)
    saved = repository.list_recipes(config)[0]
    assert saved["備註"] == "Updated"
    for i in range(1, count + 1):
        assert saved[f"色粉編號{i}"] == f"P{i}"
        assert float(saved[f"色粉重量{i}"]) == i * 10
    row["色粉編號1"] = "MISSING"
    with pytest.raises(repository.RecipeError, match="找不到色粉編號 MISSING"):
        repository.update_recipe(config, row)
    assert repository.list_recipes(config)[0] == saved
