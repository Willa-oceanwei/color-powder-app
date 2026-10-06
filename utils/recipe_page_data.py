"""Session-scoped reference reads shared by the recipe page's tabs."""
from copy import deepcopy
import logging
from time import perf_counter

import pandas as pd

from .color_powder_repository import list_color_powders


RECIPE_POWDER_CACHE_SECONDS = 10
LOGGER = logging.getLogger(__name__)
POWDER_COLUMNS = {
    "色粉編號": "colorpowder_id", "國際色號": "international_code",
    "名稱": "name", "色粉類別": "category", "包裝": "package", "備註": "notes",
    "生命週期": "lifecycle_status", "停用原因": "delete_reason",
}


def load_recipe_powders(config, state):
    started = perf_counter()
    entry = state.get("recipe_powder_reference")
    cached = (
        entry is not None and entry["config"] == config
        and started - entry["loaded_at"] < RECIPE_POWDER_CACHE_SECONDS
    )
    if cached:
        rows = entry["rows"]
    else:
        rows = list_color_powders(config, include_inactive=True)
        remember_recipe_powders(config, state, rows)
    LOGGER.warning(
        "[PERF] stage=recipe_powder_read cached=%s elapsed_ms=%.1f",
        cached, (perf_counter() - started) * 1000,
    )
    return deepcopy(rows)


def remember_recipe_powders(config, state, rows):
    state["recipe_powder_reference"] = {
        "config": config, "loaded_at": perf_counter(), "rows": deepcopy(rows),
    }


def recipe_powder_dataframe(rows, *, include_inactive=False):
    columns = POWDER_COLUMNS if include_inactive else dict(list(POWDER_COLUMNS.items())[:6])
    return pd.DataFrame([
        {label: row.get(field, "active" if field == "lifecycle_status" else "")
         for label, field in columns.items()}
        for row in rows
        if include_inactive or row.get("lifecycle_status", "active") == "active"
    ], columns=list(columns)).fillna("").astype(str)


def invalidate_recipe_powders(state):
    state.pop("recipe_powder_reference", None)
    state["recipe_data_loaded"] = False
