"""HTML builders for the HR query result cards."""
from html import escape


CARD_COLORS = {
    "blue": ("#5aa9e6", "rgba(58,141,214,0.15)", "rgba(58,141,214,0.35)"),
    "green": ("#4fd17a", "rgba(45,163,95,0.15)", "rgba(45,163,95,0.35)"),
    "orange": ("#ff9b6a", "rgba(198,88,47,0.18)", "rgba(198,88,47,0.40)"),
    "gold": ("#f3c74f", "rgba(230,171,2,0.15)", "rgba(230,171,2,0.35)"),
}


def safe_text(value):
    """Return user/database text that is safe to embed in an HTML card."""
    return escape(str(value if value not in (None, "") else "—"))


def summary_card(label, value, tone="blue", hint=""):
    fg, _bg, border = CARD_COLORS[tone]
    hint_html = f'<div style="font-size:11px;color:#8196aa;margin-top:3px;">{safe_text(hint)}</div>' if hint else ""
    return (
        f'<div style="background:linear-gradient(145deg,#0d1b2a,#102338);border:1px solid {border};'
        f'border-radius:12px;padding:12px 15px;min-height:76px;box-shadow:0 5px 15px rgba(0,0,0,.12);">'
        f'<div style="font-size:11px;color:#9fb6cc;margin-bottom:5px;">{safe_text(label)}</div>'
        f'<div style="font-size:21px;font-weight:750;color:{fg};">{safe_text(value)}</div>{hint_html}</div>'
    )


def detail_card(title, badge, fields, tone="blue"):
    """Build a compact annual-leave or salary result card."""
    fg, bg, border = CARD_COLORS[tone]
    field_html = "".join(
        f'<div style="display:flex;justify-content:space-between;gap:10px;padding:4px 0;'
        f'border-bottom:1px solid rgba(255,255,255,.05);font-size:12px;">'
        f'<span style="color:#8fa7bc;">{safe_text(label)}</span>'
        f'<span style="color:#e7eef5;text-align:right;font-weight:550;">{safe_text(value)}</span></div>'
        for label, value in fields
    )
    return (
        '<div style="background:#0d1b2a;border:1px solid rgba(255,255,255,.09);border-radius:12px;'
        'padding:13px 15px;margin-bottom:10px;min-height:178px;box-shadow:0 5px 15px rgba(0,0,0,.10);">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;">'
        f'<div style="font-size:14px;color:#fff;font-weight:700;">{safe_text(title)}</div>'
        f'<div style="font-size:11px;font-weight:650;padding:3px 9px;border-radius:999px;background:{bg};'
        f'color:{fg};border:1px solid {border};white-space:nowrap;">{safe_text(badge)}</div></div>{field_html}</div>'
    )
