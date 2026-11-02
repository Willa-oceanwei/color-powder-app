"""Lifecycle filtering and cache refresh for production-derived inventory."""
import hashlib
import pandas as pd

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
