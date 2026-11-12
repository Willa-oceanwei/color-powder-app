"""Concurrent first-visit reads for the selected sidebar workspace."""

from functools import partial

from .read_cache import warm_reads
from .color_powder_repository import list_color_powders
from .customer_repository import list_customers
from .customer_inventory_repository import list_customer_inventory_records
from .inventory_repository import list_inventory_movements
from .inventory_navigation import MOVEMENT_VIEWS, ORDER_VIEWS, RECIPE_VIEWS, selected_inventory_view
from .outsourcing_repository import list_outsourcing_events, list_outsourcing_orders
from .production_order_repository import list_production_orders
from .recipe_repository import list_recipes
from .supplier_repository import list_suppliers
from .pantone_repository import list_pantone_records
from .sample_repository import list_sample_records
from .trial_repository import list_trial_records, get_trial_settings


def warm_navigation_reads(config, state, menu, customer_display):
    # First visits load the same data the selected page needs, concurrently. The
    # repositories' short-lived cache lets the normal loaders reuse these results.
    # No Streamlit calls are made in worker threads and no connection is shared.
    inventory_view = selected_inventory_view(state) if menu == "庫存區" else None
    navigation_identity = (config, menu, inventory_view)
    if config.backend == "turso" and state.get("_navigation_reads_identity") != navigation_identity:
        navigation_reads = []
        if menu == "庫存區":
            if inventory_view in MOVEMENT_VIEWS:
                navigation_reads.append(partial(list_inventory_movements, config))
            if inventory_view in RECIPE_VIEWS and "df_recipe" not in state:
                navigation_reads.append(partial(list_recipes, config))
            if inventory_view in ORDER_VIEWS:
                navigation_reads.append(partial(list_production_orders, config, include_cancelled=True))
            if inventory_view == "master":
                navigation_reads.append(partial(list_color_powders, config))
            if inventory_view == "customer":
                navigation_reads.extend([
                    partial(list_customer_inventory_records, config), partial(customer_display._load),
                ])
        elif menu == "代工管理":
            navigation_reads = [
                partial(customer_display._load),
                partial(list_outsourcing_events, config, "return"),
            ]
            if not state.get("oem_data_loaded", False):
                navigation_reads.extend([
                    partial(list_outsourcing_orders, config, include_inactive=True),
                    partial(list_outsourcing_events, config, "delivery"),
                ])
        elif menu == "採購管理":
            navigation_reads = [
                partial(list_inventory_movements, config),
                partial(list_suppliers, config),
                partial(list_suppliers, config, include_inactive=True),
            ]
        elif menu == "查詢區":
            navigation_reads = [
                partial(list_pantone_records, config),
                partial(list_sample_records, config),
                partial(customer_display._load),
            ]
        elif menu == "試色記錄分析":
            navigation_reads = [
                partial(list_trial_records, config),
                partial(get_trial_settings, config),
                partial(list_customers, config),
                partial(customer_display._load),
            ]
        # A single inventory dependency can be read directly by its panel.
        if menu != "庫存區" or len(navigation_reads) > 1:
            warm_reads(navigation_reads)
        state["_navigation_reads_identity"] = navigation_identity

