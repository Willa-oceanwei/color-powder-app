"""Turso-first production orders with recipe snapshots and Sheet outbox events."""

from __future__ import annotations

import ast
import json
from typing import Any

from .read_cache import cached_read
from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso
from .outsourcing_repository import _set_outsourcing_lifecycle
from .production_consumption import FROZEN_CONSUMPTION_KEY, consumption_in_grams, package_total
from .recipe_repository import _recipe_sheet_payload, normalize_color_powder_id


class ProductionOrderError(RuntimeError):
    pass


def _mapping(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip((column[0] for column in cursor.description), row))


def _mappings(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _number(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _payload(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): "" if value is None else str(value).strip()
        for key, value in row.items()
        if not str(key).startswith("_")
    }


def merge_production_order_packages(
    existing: dict[str, Any], delta: dict[str, Any], *, note: str = ""
) -> dict[str, Any]:
    """Return one production-order payload containing old and added packages.

    Package slots are matched by numeric package weight instead of slot number.  This
    is intentionally independent of persistence so the caller can update the linked
    outsourcing order only after the complete merged payload has been validated.
    """
    merged = dict(existing)
    counts_by_weight: dict[float, float] = {}
    weight_order: list[float] = []

    for source in (existing, delta):
        for position in range(1, 5):
            weight = _number(source.get(f"包裝重量{position}"))
            count = _number(source.get(f"包裝份數{position}"))
            if weight <= 0 or count <= 0:
                continue
            if weight not in counts_by_weight:
                counts_by_weight[weight] = 0
                weight_order.append(weight)
            counts_by_weight[weight] += count

    if len(weight_order) > 4:
        raise ProductionOrderError("合併後超過 4 種包裝重量，無法完整保存生產單")

    def format_number(value: float) -> str:
        return str(int(value)) if value.is_integer() else str(value)

    for position in range(1, 5):
        merged[f"包裝重量{position}"] = ""
        merged[f"包裝份數{position}"] = ""
    for position, weight in enumerate(weight_order, start=1):
        merged[f"包裝重量{position}"] = format_number(weight)
        merged[f"包裝份數{position}"] = format_number(counts_by_weight[weight])

    if note.strip():
        merged["備註"] = "\n".join(
            part for part in (str(existing.get("備註") or "").strip(), note.strip()) if part
        )
    return merged


def _recipe_snapshot(conn, recipe_id: str) -> tuple[int, str]:
    if not recipe_id:
        raise ProductionOrderError("建立生產單前必須選擇配方。")
    rows = _mappings(conn.execute(
        """SELECT r.*, c.position AS component_position, c.colorpowder_id AS component_id,
                  c.weight AS component_weight
           FROM recipes r LEFT JOIN recipe_components c ON c.recipe_id=r.recipe_id
           WHERE r.recipe_id=? OR
                 (r.original_recipe=? AND r.recipe_category='附加配方' AND r.lifecycle_status='active')
           ORDER BY r.recipe_id, c.position""",
        (recipe_id, recipe_id),
    ))
    snapshots = {}
    for row in rows:
        position = row.pop("component_position")
        powder_id = row.pop("component_id")
        weight = row.pop("component_weight")
        snapshot = snapshots.setdefault(row["recipe_id"], {**row, "components": []})
        if position is not None:
            snapshot["components"].append({
                "position": position, "colorpowder_id": powder_id, "weight": weight,
            })
    main = snapshots.pop(recipe_id, None)
    if main is None:
        raise ProductionOrderError(f"找不到配方編號 {recipe_id}")
    main["additional_recipes"] = list(snapshots.values())
    return int(main["version"]), json.dumps(main, ensure_ascii=False, default=str)


def production_order_recipe_rows(order) -> tuple[dict, list[dict] | None]:
    """Return the recorded main and additional recipes, if available."""
    snapshot_json = order.get("_recipe_snapshot_json")
    try:
        snapshot = json.loads(snapshot_json) if snapshot_json else None
        if not isinstance(snapshot, dict) or not snapshot.get("recipe_id"):
            return {}, None
        main = _recipe_sheet_payload(snapshot, snapshot["components"])
        if "additional_recipes" in snapshot:
            return main, [
                _recipe_sheet_payload(recipe, recipe["components"])
                for recipe in snapshot["additional_recipes"]
            ]
    except (ValueError, TypeError, KeyError, AttributeError):
        return {}, None

    # Older app orders stored the attached rows in the order payload.
    recorded_additions = order.get("附加配方")
    try:
        if isinstance(recorded_additions, str):
            recorded_additions = ast.literal_eval(recorded_additions)
    except (ValueError, SyntaxError, RecursionError):
        return main, None
    if isinstance(recorded_additions, list) and all(
        isinstance(recipe, dict) and recipe.get("配方編號") for recipe in recorded_additions
    ):
        return main, recorded_additions
    return main, None


def _recipe_signature(rows):
    fields = (
        "色粉類別", "計量單位", "比例1", "比例2", "比例3", "淨重", "淨重單位", "合計類別", "代工倍率",
        *(f"{prefix}{position}" for position in range(1, 9) for prefix in ("色粉編號", "色粉重量")),
    )
    return [
        (normalize_color_powder_id(row.get("配方編號")), *(str(row.get(field) or "").strip() for field in fields))
        for row in rows
    ]


@cached_read
def list_production_orders(
    config: DatabaseConfig, *, include_cancelled: bool = False, include_recipe_snapshot: bool = False,
    include_inventory_evidence: bool = False,
) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        where = "" if include_cancelled else "WHERE cancelled_at IS NULL"
        snapshot_columns = recipe_joins = ""
        if include_recipe_snapshot:
            # Older orders may have only a unit in their payload. Read just the
            # display metadata; never use it as a production recipe snapshot.
            snapshot_columns = """
                , recipe_snapshot_json
                , COALESCE(NULLIF(TRIM(json_extract(history.evidence_json, '$.recipe."計量單位"')), ''),
                           recipe.measurement_unit) AS display_unit
                , COALESCE(NULLIF(TRIM(json_extract(history.evidence_json, '$.recipe."色粉類別"')), ''),
                           recipe.powder_category) AS display_category
            """
            recipe_joins = """
                LEFT JOIN production_order_history_previews AS history
                  ON history.production_order_id = production_orders.production_order_id
                  AND trim(coalesce(recipe_snapshot_json, '')) = ''
                LEFT JOIN recipes AS recipe
                  ON recipe.recipe_id = COALESCE(NULLIF(TRIM(production_orders.recipe_id), ''),
                                                 TRIM(json_extract(production_orders.payload_json, '$."配方編號"')))
                  AND trim(coalesce(recipe_snapshot_json, '')) = ''
            """
        evidence_column = """
            , CASE WHEN trim(coalesce(recipe_snapshot_json, '')) = '' THEN (
                SELECT evidence_json FROM production_order_inventory_recoveries AS recovery
                WHERE recovery.production_order_id = production_orders.production_order_id
            ) END AS inventory_evidence
        """ if include_inventory_evidence else ""
        rows = _mappings(conn.execute(
            f"""SELECT production_orders.payload_json, cancelled_at, cancel_reason{snapshot_columns}{evidence_column}
                FROM production_orders {recipe_joins} {where}
                ORDER BY production_date, production_orders.production_order_id"""
        ))
    result = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        if include_recipe_snapshot:
            payload["_recipe_snapshot_json"] = row["recipe_snapshot_json"] or ""
            payload["_package_recipe_unit"] = row["display_unit"] or ""
            payload["_package_recipe_category"] = row["display_category"] or ""
        if include_inventory_evidence and row["inventory_evidence"]:
            payload["_inventory_evidence_json"] = row["inventory_evidence"]
        payload.update({
            "取消狀態": "已取消" if row.get("cancelled_at") else "有效",
            "取消時間": str(row.get("cancelled_at") or ""),
            "取消原因": str(row.get("cancel_reason") or ""),
        })
        result.append(payload)
    return result


def _save(
    config: DatabaseConfig, row: dict[str, Any], *, create: bool,
    expected_recipe_rows: list[dict] | None = None,
) -> dict[str, str]:
    from .customer_repository import CustomerError, require_current_customer_code
    payload = _payload(row)
    order_id = payload.get("生產單號", "")
    if not order_id:
        raise ProductionOrderError("缺少生產單號")
    recipe_id = payload.get("配方編號", "")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        try:
            require_current_customer_code(conn, payload.get("客戶編號", ""))
        except CustomerError as error:
            raise ProductionOrderError(str(error)) from error
        existing = _mapping(conn.execute(
            "SELECT * FROM production_orders WHERE production_order_id=?", (order_id,)
        ))
        if create and existing is not None:
            raise ProductionOrderError(f"生產單號 {order_id} 已存在")
        if not create and existing is None:
            raise ProductionOrderError(f"找不到生產單號 {order_id}")
        if existing is not None and existing.get("cancelled_at"):
            raise ProductionOrderError("已取消的生產單不可修改；請先恢復生產單")
        if create or expected_recipe_rows is not None:
            recipe_version, snapshot_json = _recipe_snapshot(conn, recipe_id)
            main, additions = production_order_recipe_rows({"_recipe_snapshot_json": snapshot_json})
            if not main or additions is None:
                raise ProductionOrderError("無法保存完整的生產單配方副本，請重新載入配方。")
            if expected_recipe_rows is not None:
                if _recipe_signature([main, *additions]) != _recipe_signature(expected_recipe_rows):
                    raise ProductionOrderError("配方已更新，請重新載入配方後再建立生產單。")
            if create:
                snapshot = json.loads(snapshot_json)
                total = package_total(payload)
                snapshot[FROZEN_CONSUMPTION_KEY] = {
                    "package_total": total,
                    "grams": consumption_in_grams(main, additions, total),
                }
                snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        if existing is not None:
            existing_payload = json.loads(existing["payload_json"])
            linked_recipe_id = existing["recipe_id"] or ""
            if recipe_id not in (linked_recipe_id, existing_payload.get("配方編號", "")):
                raise ProductionOrderError("既有生產單的配方編號須保留。")
            recipe_id = linked_recipe_id
            if expected_recipe_rows is not None:
                old_main, old_additions = production_order_recipe_rows({
                    **existing_payload, "_recipe_snapshot_json": existing["recipe_snapshot_json"],
                })
                if not old_main or old_additions is None or (
                    _recipe_signature([old_main, *old_additions]) != _recipe_signature(expected_recipe_rows)
                ):
                    raise ProductionOrderError("原生產單的配方版本不同或資料不完整，請選擇建立新單。")
            recipe_version = existing["recipe_version"]
            snapshot_json = existing["recipe_snapshot_json"]
            payload.pop("附加配方", None)
            if "附加配方" in existing_payload:
                payload["附加配方"] = existing_payload["附加配方"]
        version = 1 if existing is None else int(existing["version"]) + 1
        created_at = now if existing is None else existing["created_at"]
        persisted_values = (
            payload.get("生產日期", ""), recipe_id or None,
            payload.get("顏色", ""), payload.get("客戶名稱", ""),
            json.dumps(payload, ensure_ascii=False), recipe_version, snapshot_json,
            version, now,
        )
        if create:
            conn.execute(
                """INSERT INTO production_orders(
                       production_order_id, production_date, recipe_id, color, customer_name,
                       status, payload_json, recipe_version, recipe_snapshot_json, source,
                       version, created_at, updated_at, last_synced_at)
                   VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, 'app', ?, ?, ?, NULL)""",
                (order_id, *persisted_values[:-1], created_at, persisted_values[-1]),
            )
            conn.execute(
                """INSERT INTO production_order_history_previews
                   (production_order_id, evidence_json, verified_at) VALUES (?, ?, ?)""",
                (order_id, json.dumps({
                    "order": payload,
                    "recipe": main,
                    "additional_recipes": additions,
                    "source": "開單時保存的生產單與配方",
                }, ensure_ascii=False), now),
            )
        else:
            # An edit must be an UPDATE in both intent and SQL.  Using an upsert here
            # could recreate a row if it disappeared between the existence check and
            # the write, making a weight/count edit look like a brand-new order.
            cursor = conn.execute(
                """UPDATE production_orders
                   SET production_date=?, recipe_id=?, color=?, customer_name=?,
                       payload_json=?, recipe_version=?, recipe_snapshot_json=?, source='app',
                       version=?, updated_at=?
                   WHERE production_order_id=? AND version=?""",
                (*persisted_values, order_id, existing["version"]),
            )
            if cursor.rowcount != 1:
                raise ProductionOrderError(f"生產單 {order_id} 已變更，請重新載入。")
        conn.execute("DELETE FROM production_order_packages WHERE production_order_id=?", (order_id,))
        packages = []
        for position in range(1, 5):
            weight = _number(payload.get(f"包裝重量{position}"))
            count = _number(payload.get(f"包裝份數{position}"))
            if not weight and not count:
                continue
            packages.append((order_id, position, weight, count, now, now))
        if packages:
            conn.execute(
                "INSERT INTO production_order_packages(production_order_id, position, package_weight, package_count, created_at, updated_at) VALUES "
                + ",".join(["(?,?,?,?,?,?)"] * len(packages)),
                tuple(value for package in packages for value in package),
            )
        enqueue_sheet_sync(
            conn, sheet_name="生產單", row_key=order_id,
            operation="insert" if create else "update", payload=payload, entity_version=version,
        )
    return payload


def create_production_order(
    config: DatabaseConfig, row: dict[str, Any], *, expected_recipe_rows: list[dict] | None = None,
) -> dict[str, str]:
    return _save(config, row, create=True, expected_recipe_rows=expected_recipe_rows)


def update_production_order(
    config: DatabaseConfig,
    row: dict[str, Any],
    *,
    original_order_id: str | None = None,
    expected_recipe_rows: list[dict] | None = None,
) -> dict[str, str]:
    """Update an order without allowing its permanent ID to be replaced.

    ``original_order_id`` should be supplied by editing UIs from the selected
    persisted record.  Restoring it into the payload prevents stale widget or
    session-state values from accidentally turning an edit into another order.
    The optional argument keeps repository callers that already submit the
    persisted ID backwards compatible.
    """
    updated_row = dict(row)
    if original_order_id is not None:
        original_order_id = str(original_order_id).strip()
        if not original_order_id:
            raise ProductionOrderError("缺少原生產單號")
        updated_row["生產單號"] = original_order_id
    return _save(config, updated_row, create=False, expected_recipe_rows=expected_recipe_rows)


def upsert_production_order(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    order_id = str(row.get("生產單號") or "").strip()
    with connect_from_config(config) as conn:
        exists = _mapping(conn.execute(
            "SELECT production_order_id FROM production_orders WHERE production_order_id=?", (order_id,)
        )) is not None
    return _save(config, row, create=not exists)


def set_production_order_cancelled(
    config: DatabaseConfig,
    order_id: str,
    *,
    cancelled: bool,
    reason: str = "",
) -> dict[str, str]:
    """Cancel or restore an order without deleting its payload or recipe snapshot."""
    order_id = str(order_id or "").strip()
    reason = str(reason or "").strip()
    if not order_id:
        raise ProductionOrderError("缺少生產單號")
    if cancelled and not reason:
        raise ProductionOrderError("請輸入取消原因")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM production_orders WHERE production_order_id=?", (order_id,)
        ))
        if existing is None:
            raise ProductionOrderError(f"找不到生產單號 {order_id}")
        if cancelled and existing.get("cancelled_at"):
            raise ProductionOrderError("此生產單已取消")
        if not cancelled and not existing.get("cancelled_at"):
            raise ProductionOrderError("此生產單目前未取消")

        payload = json.loads(existing["payload_json"])
        # Remember exact archive versions so restoration cannot undo later manual changes.
        archive_key = "_cancelled_outsourcing_orders"
        if cancelled:
            linked = _mappings(conn.execute(
                "SELECT outsourcing_order_id, version FROM outsourcing_orders "
                "WHERE production_order_id=? AND lifecycle_status='active'",
                (order_id,),
            ))
            archived = []
            for order in linked:
                oem_id = order["outsourcing_order_id"]
                _set_outsourcing_lifecycle(
                    conn, oem_id, restore=False,
                    reason=f"生產單 {order_id} 取消：{reason}",
                )
                archived.append([oem_id, int(order["version"]) + 1])
            payload[archive_key] = json.dumps(archived, ensure_ascii=False)
        else:
            for oem_id, archive_version in json.loads(payload.pop(archive_key, "[]")):
                order = _mapping(conn.execute(
                    "SELECT production_order_id, lifecycle_status, version FROM outsourcing_orders "
                    "WHERE outsourcing_order_id=?", (oem_id,),
                ))
                if (order and order["production_order_id"] == order_id
                        and order["lifecycle_status"] == "inactive"
                        and int(order["version"]) == archive_version):
                    _set_outsourcing_lifecycle(conn, oem_id, restore=True)
        payload.update({
            "取消狀態": "已取消" if cancelled else "有效",
            "取消時間": now if cancelled else "",
            "取消原因": reason if cancelled else "",
        })
        version = int(existing["version"]) + 1
        conn.execute(
            """UPDATE production_orders
               SET status=?, cancelled_at=?, cancel_reason=?, payload_json=?,
                   source='app', version=?, updated_at=?
               WHERE production_order_id=?""",
            (
                "cancelled" if cancelled else "draft", now if cancelled else None,
                reason if cancelled else None, json.dumps(payload, ensure_ascii=False),
                version, now, order_id,
            ),
        )
        enqueue_sheet_sync(
            conn, sheet_name="生產單", row_key=order_id,
            operation="delete" if cancelled else "update",
            payload=None if cancelled else payload, entity_version=version,
        )
        return payload


