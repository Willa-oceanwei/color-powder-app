"""Retain production workspace inputs while their panel is not mounted."""

PRODUCTION_VIEW_KEY = "production_order_view"
PRODUCTION_VIEWS = {
    "create": "🛸 生產單建立",
    "history": "📜 生產單記錄表",
    "manage": "👀 生產單預覽/修改/取消",
}


def retain_production_widgets(state, active_view):
    if active_view is None and PRODUCTION_VIEW_KEY in state:
        state[PRODUCTION_VIEW_KEY] = state[PRODUCTION_VIEW_KEY]
    for key in list(state):
        # Buttons and table widgets have their own state rules.
        if key.startswith(("tab1_", "tab2_", "tab3_")) and any(
            marker in key for marker in ("_label_kind_", "_label_paper_", "_choose_positions_", "_position_")
        ):
            view = {"tab1": "create", "tab2": "history", "tab3": "manage"}[key[:4]]
        elif key.startswith(("merge_radio_", "show_big_label_", "print_mode_")) or key in (
            "search_text_tab1", "search_add_form_selected_recipe_tab1", "show_ids_tab1",
        ) or (key.startswith("form_") and key.endswith("_tab1")):
            view = "create"
        elif key in ("search_order_input_tab2", "selectbox_order_limit_tab2"):
            view = "history"
        elif key.startswith(("edit_packing_weight_tab3_", "edit_packing_count_tab3_", "cancel_order_reason_", "show_labels_tab3_")) or key in (
            "show_cancelled_orders_tab3", "search_order_input_tab3", "search_date_start_tab3", "search_date_end_tab3",
            "show_ids_mode_tab3", "edit_colorant_quantity_mode_tab3", "edit_customer_name_tab3", "edit_color_tab3",
            "edit_remark_tab3", "tab3_page_size",
        ):
            view = "manage"
        else:
            continue
        if view != active_view:
            state[key] = state[key]
