from contextlib import contextmanager

import pytest

from utils import production_order_repository as repository
from utils.database import DatabaseConfig, initialize_database


@pytest.mark.parametrize("positions", [[], [1], [1, 2, 3, 4], [2, 4]])
def test_packages_use_one_insert_and_preserve_empty_slots_and_permanent_id(tmp_path, monkeypatch, positions):
    config = DatabaseConfig("sqlite", tmp_path / "packages.db")
    initialize_database(config.path)
    row = {"生產單號": "P001", "生產日期": "2026-11-03"}
    for i in positions:
        row[f"包裝重量{i}"] = str(i * 10)
        row[f"包裝份數{i}"] = str(i)
    statements = []
    original = repository.connect_from_config
    @contextmanager
    def capture(config):
        with original(config) as conn:
            conn.set_trace_callback(statements.append)
            yield conn
    monkeypatch.setattr(repository, "connect_from_config", capture)
    repository.create_production_order(config, row)
    statements.clear()
    repository.update_production_order(config, dict(row, 生產單號="OTHER", 備註="Updated"), original_order_id="P001")
    assert len([s for s in statements if s.startswith("INSERT INTO production_order_packages")]) == (1 if positions else 0)
    with original(config) as conn:
        packages = conn.execute("SELECT position,package_weight,package_count FROM production_order_packages WHERE production_order_id='P001' ORDER BY position").fetchall()
        assert [tuple(r) for r in packages] == [(i, i * 10, i) for i in positions]
        assert conn.execute("SELECT COUNT(*) FROM production_orders").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sync_outbox WHERE sheet_name='生產單'").fetchone()[0] == 2
    assert repository.list_production_orders(config)[0]["備註"] == "Updated"
