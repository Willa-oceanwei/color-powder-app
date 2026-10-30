import json
from dataclasses import replace

import pytest

from utils import customer_repository as customers
from utils.customer_repository import CustomerInput, CustomerError, CustomerAlreadyExists, create_customer, get_customer, update_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database
from utils.production_order_repository import create_production_order
from utils.recipe_repository import create_recipe
from utils.receipt_repository import save_receipt, save_receipt_batch
from utils.scheduled_quote_repository import save_scheduled_quote
from utils.shipment_repository import blank_shipment, get_shipment, save_shipment, ShipmentError
from utils.trial_repository import create_trial_record


@pytest.fixture
def config(tmp_path):
    result = DatabaseConfig(backend="sqlite", path=tmp_path / "rename.db")
    initialize_database(result.path)
    create_customer(result, CustomerInput("001", "First Legal", "notes", short_name="First", address="Address"))
    create_customer(result, CustomerInput("OTHER", "Other Legal"))
    return result


def renamed(config, **kwargs):
    old = get_customer(config, "001")
    return update_customer(config, CustomerInput("0009", old["name"], old["notes"]),
                           original_customer_id="001", expected_version=old["version"], **kwargs)


def seed(config):
    with connect_from_config(config) as conn:
        conn.execute("INSERT INTO color_powders(colorpowder_id,created_at,updated_at) VALUES ('P1','old','old')")
    create_recipe(config, {"配方編號": "R1", "客戶編號": "001", "客戶名稱": "First Legal",
                           "顏色": "Blue", "色粉編號1": "P1", "色粉重量1": "1.25", "淨重": "100"})
    create_production_order(config, {"生產單號": "ORDER1", "配方編號": "R1", "客戶編號": "001",
                                     "客戶名稱": "First Legal", "包裝重量1": "1", "包裝份數1": "2"})
    create_trial_record(config, {"_sync_id": "TRIAL1", "配方編號": "T1", "客戶編號": "001",
                                "客戶名稱": "First Legal", "試色日期": "2026-10-29", "原料": "PP"})
    shipments = []
    for code, number in (("001", "001"), ("OTHER", "002")):
        document = dict(blank_shipment(), customer_id=code, customer_name=code,
                        number_mode="manual", shipment_number=number, recipient_id="001")
        document["items"] = [dict(code="R1", name="Blue", quantity="2", unit="KG", price="100")]
        shipments.append(save_shipment(config, document))
    save_receipt(config, receipt_id="REC1", shipment_id=shipments[0]["id"],
                 shipment_version=shipments[0]["version"], receipt_date="2026-10-29", amount="10")
    save_receipt_batch(config, batch_id="BATCH1", customer_id="001", receipt_date="2026-10-29",
                       amount="25", allocations=[])
    save_scheduled_quote(config, dict(customer_id="001", product_code="R1", price="123.45",
                                     unit="KG", tax_mode="外加", effective_date="2026-10-29"))
    return [get_shipment(config, shipment["id"]) for shipment in shipments]


TABLES = ("customers", "customer_aliases", "recipes", "recipe_components", "production_orders",
          "trial_records", "shipment_orders", "shipment_order_items", "shipment_invoices",
          "shipment_receipts", "receipt_batches", "receipt_batch_allocations", "scheduled_quotes", "sync_outbox")


def snapshot(config):
    with connect_from_config(config) as conn:
        return {table: [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]
                for table in TABLES}


def test_rename_preserves_all_links_amounts_components_and_historical_snapshots(config):
    shipments = seed(config)
    before = snapshot(config)
    old = get_customer(config, "001")
    result = renamed(config)
    after = snapshot(config)
    assert result["customer_id"] == "0009"
    for field in ("name", "short_name", "notes", "address", "created_at"):
        assert result[field] == old[field]
    assert result["version"] == old["version"] + 1
    assert {c["customer_id"] for c in after["customers"]} == {"0009", "OTHER"}
    assert all(a["customer_id"] == "0009" for a in after["customer_aliases"] if a["alias"] in ("First Legal", "First"))
    for table in ("recipes", "trial_records", "receipt_batches", "scheduled_quotes"):
        assert after[table][0]["customer_id"] == "0009"
        assert after[table][0]["version"] == before[table][0]["version"] + 1
    for table in ("recipe_components", "shipment_order_items", "shipment_invoices",
                  "shipment_receipts", "receipt_batch_allocations"):
        assert after[table] == before[table]
    assert after["receipt_batches"][0]["request_json"] == before["receipt_batches"][0]["request_json"]
    assert after["receipt_batches"][0]["amount"] == before["receipt_batches"][0]["amount"]
    assert after["production_orders"][0]["recipe_snapshot_json"] == before["production_orders"][0]["recipe_snapshot_json"]
    assert json.loads(after["production_orders"][0]["payload_json"])["客戶編號"] == "0009"
    for index, shipment in enumerate(shipments):
        updated = get_shipment(config, shipment["id"])
        assert updated["customer_id"] == ("0009" if index == 0 else "OTHER")
        assert updated["recipient_id"] == "0009"
        assert updated["version"] == shipment["version"] + 1
        for field in ("items", "invoice", "net_amount", "tax_amount", "total_amount", "customer_name", "created_at"):
            assert updated[field] == shipment[field]
        with pytest.raises(ShipmentError, match="其他人"):
            save_shipment(config, shipment)
    latest = {(r["sheet_name"], r["row_key"]): r for r in after["sync_outbox"]}
    assert latest[("客戶名單", "001")]["operation"] == "delete"
    assert latest[("客戶名單", "0009")]["operation"] == "insert"
    for name, key in (("配方管理", "R1"), ("試色登錄", "TRIAL1"), ("生產單", "ORDER1")):
        assert json.loads(latest[(name, key)]["payload_json"])["客戶編號"] == "0009"
    with connect_from_config(config) as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    # A retry of the immutable original receipt request still resolves to its batch.
    retry = save_receipt_batch(config, batch_id="BATCH1", customer_id="001", receipt_date="2026-10-29",
                              amount="25", allocations=[])
    assert retry["id"] == "BATCH1" and retry["customer_id"] == "0009"


@pytest.mark.parametrize("target", ["OTHER", ""])
def test_invalid_or_duplicate_target_rolls_back_everything(config, target):
    seed(config)
    before = snapshot(config)
    with pytest.raises(CustomerError):
        update_customer(config, CustomerInput(target, "Changed"), original_customer_id="001", expected_version=1)
    assert snapshot(config) == before


def test_inactive_target_cannot_be_overwritten(config):
    customers.set_customer_active(config, "OTHER", active=False, reason="old")
    with pytest.raises(CustomerAlreadyExists):
        update_customer(config, CustomerInput("OTHER", "First Legal"), original_customer_id="001", expected_version=1)


def test_stale_missing_version_and_missing_source_are_rejected(config):
    before = snapshot(config)
    for original, version in (("001", 9), ("001", None), ("missing", 1)):
        with pytest.raises(CustomerError):
            update_customer(config, CustomerInput("0009", "First Legal"),
                            original_customer_id=original, expected_version=version)
    assert snapshot(config) == before


def test_late_outbox_failure_rolls_back_complete_rename(config, monkeypatch):
    seed(config)
    before = snapshot(config)
    enqueue = customers.enqueue_sheet_sync
    def fail_last(conn, **kwargs):
        if kwargs["sheet_name"] == "客戶名單" and kwargs["operation"] == "delete":
            raise RuntimeError("simulated failure")
        return enqueue(conn, **kwargs)
    monkeypatch.setattr(customers, "enqueue_sheet_sync", fail_last)
    with pytest.raises(RuntimeError, match="simulated failure"):
        renamed(config)
    assert snapshot(config) == before


def test_sync_in_progress_and_target_baseline_block_rename(config):
    seed(config)
    with connect_from_config(config) as conn:
        conn.execute("UPDATE sync_outbox SET status='processing' WHERE sheet_name='配方管理'")
    before = snapshot(config)
    with pytest.raises(CustomerError, match="正在同步"):
        renamed(config)
    assert snapshot(config) == before
    with connect_from_config(config) as conn:
        conn.execute("UPDATE sync_outbox SET status='pending'")
        from utils.database import upsert_sheet_row
        upsert_sheet_row(conn, "客戶名單", "0009", {"客戶編號": "0009"}, "hash")
    with pytest.raises(CustomerError, match="同步紀錄"):
        renamed(config)


def test_reusing_old_code_uses_version_after_pending_delete(config):
    renamed(config)
    created = create_customer(config, CustomerInput("001", "Different customer"))
    with connect_from_config(config) as conn:
        entries = conn.execute("SELECT operation,entity_version FROM sync_outbox WHERE sheet_name='客戶名單' AND row_key='001' ORDER BY entity_version").fetchall()
    assert [r["operation"] for r in entries] == ["insert", "delete", "insert"]
    assert created["version"] == entries[-1]["entity_version"] > entries[-2]["entity_version"]
    assert get_customer(config, "0009")["name"] == "First Legal"


def test_ordinary_update_keeps_related_document_versions(config):
    seed(config)
    before = snapshot(config)
    update_customer(config, CustomerInput("001", "First Legal", "new notes"), expected_version=1)
    after = snapshot(config)
    for table in TABLES:
        if table not in ("customers", "sync_outbox"):
            assert after[table] == before[table]


def test_ui_customer_code_edit_duplicate_and_cancel(config):
    from test_customer_contacts import customer_app
    app = customer_app(config)
    app.selectbox(key="customer_action_id").set_value("001").run()
    assert not app.exception
    field = next(w for w in app.tabs[0].text_input if w.label == "客戶編號")
    assert not field.disabled
    field.set_value("OTHER")
    next(w for w in app.button if w.label == "儲存變更").click().run()
    assert app.error and get_customer(config, "001")["name"] == "First Legal"
    next(w for w in app.tabs[0].text_input if w.label == "客戶編號").set_value("0009")
    next(w for w in app.button if w.label == "取消編輯").click().run()
    assert not app.exception
    assert get_customer(config, "001")["customer_id"] == "001"
    app.selectbox(key="customer_action_id").set_value("001").run()
    next(w for w in app.tabs[0].text_input if w.label == "客戶編號").set_value("0009")
    app.session_state["df_recipe"] = "old recipe cache"
    app.session_state["shipment_saved_view"] = "old shipment snapshot"
    next(w for w in app.button if w.label == "儲存變更").click().run()
    assert not app.exception and not app.error
    assert get_customer(config, "0009")["address"] == "Address"
    assert "df_recipe" not in app.session_state and "shipment_saved_view" not in app.session_state
    assert app.selectbox(key="customer_action_id").value is None
    assert any(option.startswith("0009") for option in app.selectbox(key="customer_action_id").options)


def test_sheet_push_renames_key_and_inbound_cannot_resurrect_retired_code(config):
    from utils.database import upsert_sheet_row
    from utils.sheet_export import sync_customer_outbox
    from utils.sheet_import import _row_hash, import_sheet_values
    old = customers.customer_sheet_payload(get_customer(config, "001"))
    headers = list(old)
    class Sheet:
        def __init__(self):
            self.values = [headers, [old[k] for k in headers]]
        def append_row(self, row):
            self.values.append(row)
        def update(self, cell, values):
            self.values[int(cell[1:]) - 1] = values[0]
        def delete_rows(self, index):
            self.values.pop(index - 1)
    sheet = Sheet()
    with connect_from_config(config) as conn:
        upsert_sheet_row(conn, "客戶名單", "001", old, _row_hash(old))
    renamed(config)
    result = sync_customer_outbox(sheet, sheet.values, db_config=config, dry_run=False, initialize_schema=False)
    assert result.conflicts == 0 and result.to_insert == 2 and result.to_delete == 1
    rows = [dict(zip(headers, values)) for values in sheet.values[1:]]
    assert {r["客戶編號"] for r in rows} == {"0009", "OTHER"}
    assert next(r for r in rows if r["客戶編號"] == "0009")["客戶名稱"] == "First Legal"
    # An edited or accidentally restored copy of the removed row is quarantined,
    # even after the delete event has completed and its baseline is gone.
    stale = dict(old, 客戶名稱="Edited stale Sheet name")
    imported = import_sheet_values("客戶名單", [headers, [stale[h] for h in headers]],
                                   db_config=config, initialize_schema=False)
    assert imported.conflicts == 1 and imported.inserted_or_updated == 0
    assert {r["customer_id"] for r in customers.list_customers(config)} == {"0009", "OTHER"}
    # Existing canonical data is still importable when its row is unchanged.
    unchanged = import_sheet_values("客戶名單", sheet.values, db_config=config, initialize_schema=False)
    assert unchanged.conflicts == 0 and unchanged.unchanged == 2


def test_changed_old_sheet_row_is_not_deleted(config):
    from utils.database import upsert_sheet_row
    from utils.sheet_export import sync_customer_outbox
    from utils.sheet_import import _row_hash
    old = customers.customer_sheet_payload(get_customer(config, "001"))
    headers = list(old)
    with connect_from_config(config) as conn:
        upsert_sheet_row(conn, "客戶名單", "001", old, _row_hash(old))
    renamed(config)
    changed = dict(old, 備註="Someone edited this Sheet row")
    class Sheet:
        def append_row(self, row):
            pass
        def update(self, cell, rows):
            pass
        def delete_rows(self, index):
            pytest.fail("changed source row must not be deleted")
    result = sync_customer_outbox(Sheet(), [headers, [changed[h] for h in headers]],
                                  db_config=config, dry_run=False, initialize_schema=False)
    assert result.conflicts == 1 and result.to_delete == 0


def test_guard_rejects_change_between_read_and_first_write(config, monkeypatch):
    from contextlib import contextmanager
    original = customers.connect_from_config
    @contextmanager
    def changed_after_read(configuration):
        with original(configuration) as conn:
            class Connection:
                def execute(self, sql, parameters=()):
                    if sql.startswith("UPDATE customers SET version=version"):
                        class Miss:
                            rowcount = 0
                        return Miss()
                    return conn.execute(sql, parameters)
            yield Connection()
    before = snapshot(config)
    monkeypatch.setattr(customers, "connect_from_config", changed_after_read)
    with pytest.raises(CustomerError, match="其他人"):
        renamed(config)
    assert snapshot(config) == before


def test_pending_reused_code_is_not_overwritten_by_old_sheet_data(config):
    from utils.database import upsert_sheet_row
    from utils.sheet_import import _row_hash, import_sheet_values
    old = customers.customer_sheet_payload(get_customer(config, "001"))
    with connect_from_config(config) as conn:
        upsert_sheet_row(conn, "客戶名單", "001", old, _row_hash(old))
    renamed(config)
    create_customer(config, CustomerInput("001", "Different customer", "fresh notes"))
    stale = dict(old, 客戶名稱="Different customer", 客戶簡稱="", 備註="stale notes")
    headers = list(stale)
    result = import_sheet_values("客戶名單", [headers, [stale[h] for h in headers]],
                                 db_config=config, initialize_schema=False)
    assert result.conflicts == 1
    assert get_customer(config, "001")["notes"] == "fresh notes"


def test_second_rename_back_before_sync_keeps_outbox_versions_increasing(config):
    seed(config)
    first = renamed(config)
    second = update_customer(config, CustomerInput("001", first["name"], first["notes"]),
                             original_customer_id="0009", expected_version=first["version"])
    assert second["customer_id"] == "001" and second["version"] == first["version"] + 1
    with connect_from_config(config) as conn:
        rows = conn.execute("SELECT operation,entity_version FROM sync_outbox WHERE sheet_name='客戶名單' AND row_key='001' ORDER BY entity_version").fetchall()
        assert [r["operation"] for r in rows] == ["insert", "delete", "insert"]
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert get_shipment(config, snapshot(config)["shipment_orders"][0]["id"])["customer_id"] == "001"


def test_stale_recipe_payload_cannot_restore_deleted_customer_code(config):
    from utils.recipe_repository import list_recipes, update_recipe, RecipeError
    seed(config)
    stale = next(r for r in list_recipes(config) if r["配方編號"] == "R1")
    renamed(config)
    before = snapshot(config)
    stale["備註"] = "An unrelated edit from an old session"
    with pytest.raises(RecipeError, match="已變更"):
        update_recipe(config, stale)
    assert snapshot(config) == before
    current = next(r for r in list_recipes(config) if r["配方編號"] == "R1")
    current["備註"] = "Current session"
    update_recipe(config, current)
    assert next(r for r in list_recipes(config) if r["配方編號"] == "R1")["客戶編號"] == "0009"


def test_new_documents_and_sheet_rows_reject_retired_customer_code(config):
    from utils.production_order_repository import ProductionOrderError
    from utils.trial_repository import TrialError
    from utils.recipe_repository import RecipeError
    from utils.sheet_import import import_sheet_values
    seed(config)
    renamed(config)
    before = snapshot(config)
    with pytest.raises(RecipeError, match="已變更"):
        create_recipe(config, {"配方編號": "R2", "客戶編號": "001"})
    with pytest.raises(TrialError, match="已變更"):
        create_trial_record(config, {"配方編號": "T2", "客戶編號": "001", "試色日期": "2026-10-30", "原料": "PP"})
    with pytest.raises(ProductionOrderError, match="已變更"):
        create_production_order(config, {"生產單號": "ORDER2", "配方編號": "R1", "客戶編號": "001"})
    draft = dict(blank_shipment(), customer_id="OTHER", customer_name="Other Legal",
                 number_mode="manual", shipment_number="003", recipient_id="001")
    draft["items"] = [dict(code="R1", name="Blue", quantity="1", unit="KG", price="100")]
    with pytest.raises(ShipmentError, match="已變更"):
        save_shipment(config, draft)
    assert snapshot(config) == before
    for sheet, values in (
        ("配方管理", [["配方編號", "客戶編號"], ["OLD-R", "001"]]),
        ("試色登錄", [["_sync_id", "配方編號", "客戶編號", "試色日期", "原料"], ["OLD-T", "T3", "001", "2026-10-30", "PP"]]),
        ("生產單", [["生產單號", "配方編號", "客戶編號"], ["OLD-O", "R1", "001"]]),
    ):
        result = import_sheet_values(sheet, values, db_config=config, initialize_schema=False)
        assert result.errors and result.inserted_or_updated == 0
    assert snapshot(config) == before
    # Legacy records with an unknown code that was never renamed retain compatibility.
    create_recipe(config, {"配方編號": "LEGACY", "客戶編號": "never-used-legacy-code"})




