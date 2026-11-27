"""Only the production-order history preview reads this evidence."""

import json
import re
from html import escape

from .database import connect_from_config


def load_production_order_history_preview(config, order_id):
    with connect_from_config(config) as conn:
        row = conn.execute(
            "SELECT evidence_json FROM production_order_history_previews WHERE production_order_id=?",
            (order_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def render_production_order_history_preview(evidence, renderer, *, show_additional_ids):
    def safe(row):
        return {key: escape("" if value is None else str(value), quote=False) for key, value in row.items()}

    # The historical iframe is read-only and must never trigger the A5 print dialog.
    document = renderer(
        safe(evidence["order"]),
        safe(evidence["recipe"]),
        [safe(row) for row in evidence["additional_recipes"]],
        show_additional_ids=show_additional_ids,
        recipe_notice="歷史查閱副本，請勿依此生產。",
    )
    document = re.sub(r"<script\b[^>]*>.*?</script>", "", document, flags=re.IGNORECASE | re.DOTALL)
    return document.replace("</head>", """
<style id="production-history-paper">
@media screen {
    html, body { background: #fff; color: #000; color-scheme: light; }
}
</style>
</head>""", 1)
