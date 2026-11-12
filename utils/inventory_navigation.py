"""Keep inventory navigation and the inactive panels' widget values in session."""

INVENTORY_VIEW_KEY = "inventory_view"
INVENTORY_VIEWS = {
    "initial": "📦 初始",
    "query": "📊 查詢",
    "audit": "📋 盤點",
    "rank": "🏆 排行",
    "usage": "🧮 用量",
    "master": "🧴 色母",
    "customer": "👤 客戶",
}

ORDER_VIEWS = {"query", "audit", "rank", "usage", "master"}
RECIPE_VIEWS = ORDER_VIEWS | {"customer"}
MOVEMENT_VIEWS = {"initial", "query", "audit"}

_PANEL_WIDGETS = {
    "initial": (
        "ini_color", "ini_qty", "ini_unit", "ini_date", "ini_note", "duplicate_initial_powder",
        "scan_all_duplicate_initials", "confirm_duplicate_initial_cleanup",
    ),
    "query": ("stock_use_date_range_cb", "stock_start_query", "stock_end_query", "stock_powder", "match_mode"),
    "audit": (
        "stock_audit_date", "stock_audit_normal_limit", "stock_audit_warning_limit",
        "stock_audit_only_abnormal", "stock_audit_allow_unregistered", "stock_audit_location_filter",
    ),
    "rank": ("rank_start_date", "rank_end_date", "rank_show_01_001"),
    "usage": ("usage_start_date", "usage_end_date", *(f"usage_color_{i}" for i in range(4))),
    "master": ("_tab5_use_date_range_cb", "master_stock_start", "master_stock_end", "master_powder", "master_match_mode"),
    "customer": (
        "cust_stock_action_mode", "cust_stock_edit_pick", "cust_stock_query_recipes",
        "cust_stock_query_customer", "cust_stock_query_color",
    ),
}
CUSTOMER_STOCK_INPUTS = tuple(f"cust_stock_form_{field}" for field in (
    "customer", "recipe", "color", "quantity", "unit", "note",
))
_PANEL_WIDGETS["customer"] += CUSTOMER_STOCK_INPUTS


def selected_inventory_view(state):
    return state.get(INVENTORY_VIEW_KEY, "initial")


def retain_inventory_widgets(state, active_view):
    # Streamlit drops widgets that are absent from a run. Reassign only hidden
    # input values. Action buttons and upload/editor widgets are never assigned.
    for view, keys in _PANEL_WIDGETS.items():
        if view != active_view:
            for key in keys:
                if key in state:
                    state[key] = state[key]
    if active_view is None and INVENTORY_VIEW_KEY in state:
        state[INVENTORY_VIEW_KEY] = state[INVENTORY_VIEW_KEY]
    if active_view != "audit":
        state.pop("stock_audit_editor_base", None)


def remember_audit_upload(state):
    state["stock_audit_uploaded_file"] = state.get("stock_audit_upload")
