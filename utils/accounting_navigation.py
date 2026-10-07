"""Retain accounting widget drafts while visiting other pages."""

import re
from copy import deepcopy


def preserve_accounting_widgets(state):
    # Streamlit otherwise deletes widget values when their page is not rendered.
    for key in list(state):
        active = any(state.get(module + "_draft") is not None and
                     key.startswith(f"{module}_{state.get(module + '_epoch', 0)}_")
                     for module in ("shipment", "product"))
        if active and not re.search(r"_items(?:_\d+)?$", key):
            state[key] = state[key]


def stash_shipment_grid(state):
    if not state.get("shipment_draft"):
        return
    from .shipment_ui import COLUMNS
    epoch = state.get("shipment_grid_epoch", 0)
    key = f"shipment_{state.get('shipment_epoch', 0)}_items" + (f"_{epoch}" if epoch else "")
    delta = state.get(key, {})
    rows = deepcopy(state.get("shipment_editor_base", []))
    fields = {label: field for field, label in COLUMNS.items()}
    for index, changes in delta.get("edited_rows", {}).items():
        if int(index) < len(rows):
            rows[int(index)].update({fields[label]: value for label, value in changes.items() if label in fields})
    rows = [row for index, row in enumerate(rows) if index not in delta.get("deleted_rows", [])]
    for source in delta.get("added_rows", []):
        rows.append({field: source.get(label, "") for field, label in COLUMNS.items()})
    state["shipment_editor_base"] = rows
    state["shipment_grid_epoch"] = epoch + 1
