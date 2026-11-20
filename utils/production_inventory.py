"""Lifecycle filtering and cache refresh for production-derived inventory."""
import hashlib
import json
import pandas as pd

from .production_consumption import (
    FROZEN_CONSUMPTION_KEY, consumption_in_grams, package_total, parse_pack_value,
)
from .production_order_repository import production_order_recipe_rows
from .recipe_repository import normalize_color_powder_id

RESULT_KEYS = (
    "stock_calc_time", "last_final_stock", "stock_query_result", "stock_query_signature",
    "master_stock_query_result", "stock_audit_result", "rank_result", "rank_signature",
    "tab4_usage_result", "tab4_signature",
)


def invalidate_inventory_results(state):
    for key in RESULT_KEYS:
        state.pop(key, None)
    state["stock_need_reload"] = True
    state["stock_audit_editor_revision"] = state.get("stock_audit_editor_revision", 0) + 1


def active_production_orders(frame):
    """Keep audit/history snapshots intact; cancel flags only affect consumption."""
    active = pd.Series(True, index=frame.index)
    if "取消狀態" in frame.columns:
        active &= frame["取消狀態"].fillna("").astype(str).str.strip().ne("已取消")
    if "取消時間" in frame.columns:
        active &= frame["取消時間"].fillna("").astype(str).str.strip().eq("")
    return frame.loc[active].copy()


def prepare_inventory_orders(state, frame):
    # Include lifecycle and quantities so old persisted query results expire too.
    signature = hashlib.sha256(frame.fillna("").astype(str).to_json(
        orient="split", force_ascii=False, date_format="iso").encode("utf-8")).hexdigest()
    if state.get("inventory_production_signature") != signature:
        invalidate_inventory_results(state)
        state["inventory_production_signature"] = signature
    return active_production_orders(frame)


def _recipe_id(value):
    code = normalize_color_powder_id(value)
    return code.zfill(4) if code.isdigit() else code


def _json_object(value):
    try:
        decoded = json.loads(value or "null")
    except (ValueError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _approved_recovery_consumption(order, code):
    evidence = _json_object(order.get("_inventory_evidence_json"))
    source = evidence.get("source")
    if not isinstance(source, str) or not source.startswith("原始試算表版本 "):
        return None

    archived_order = evidence.get("order")
    main = evidence.get("recipe")
    additions = evidence.get("additional_recipes")
    if (not isinstance(archived_order, dict)
            or archived_order.get("生產單號") != order.get("生產單號")
            or _recipe_id(archived_order.get("配方編號")) != code
            or not isinstance(main, dict) or _recipe_id(main.get("配方編號")) != code
            or not isinstance(additions, list)
            or any(not isinstance(recipe, dict) or not _recipe_id(recipe.get("配方編號")) for recipe in additions)):
        return None

    for index in range(1, 5):
        for field in (f"包裝重量{index}", f"包裝份數{index}"):
            if parse_pack_value(archived_order.get(field)) != parse_pack_value(order.get(field)):
                return None

    return consumption_in_grams(main, additions, package_total(order))


def recorded_inventory_consumption(orders, recipes):
    """Read frozen debits and recover skipped legacy orders from verified evidence."""
    active_codes = {
        _recipe_id(code) for code in recipes.get("配方編號", ()) if code
    }
    results = []
    for order in orders.to_dict("records"):
        result = None
        code = _recipe_id(order.get("配方編號"))
        snapshot = _json_object(order.get("_recipe_snapshot_json"))
        if code and _recipe_id(snapshot.get("recipe_id")) == code:
            frozen = snapshot.get(FROZEN_CONSUMPTION_KEY)
            if frozen is not None or code not in active_codes:
                total = package_total(order)
                if isinstance(frozen, dict) and frozen.get("package_total") == total:
                    grams = frozen.get("grams")
                    if isinstance(grams, dict) and all(
                        isinstance(grams.get(group), dict) for group in ("pigments", "categories")
                    ):
                        result = grams
                if result is None:
                    # An explicit correction to the package quantity still uses
                    # the original recipe, including when imported from Sheets.
                    main, additions = production_order_recipe_rows(order)
                    if main and additions is not None:
                        result = consumption_in_grams(main, additions, total)
        if result is None and code and code not in active_codes:
            result = _approved_recovery_consumption(order, code)
        results.append(result)
    return results
