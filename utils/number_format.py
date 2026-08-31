"""Shared number formatting helpers for user-facing values."""


def format_optional_decimals(value, digits=2):
    """Show up to ``digits`` decimals, omitting the decimal part when it is zero."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")
