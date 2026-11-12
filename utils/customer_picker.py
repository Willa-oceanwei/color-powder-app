"""Search the already sorted customer options without changing their order."""

from pathlib import Path

import streamlit.components.v1 as components


_picker = components.declare_component(
    "ordered_customer_picker",
    path=str(Path(__file__).resolve().parents[1] / "components" / "customer_picker"),
)


def render_customer_picker(matches, names, *, key):
    return _picker(
        options=[{"id": customer_id, "label": names[customer_id]} for customer_id in matches],
        key=key,
        default=None,
    )
