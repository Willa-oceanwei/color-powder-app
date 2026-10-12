"""Sales document code presentation without changing master-data identity."""


def display_code_options(code):
    code = str(code or "").strip()
    return [code, code[1:]] if code.upper().startswith("C0") and len(code) > 2 else [code]


def printed_code(item):
    code = str(item.get("code") or "").strip()
    chosen = str(item.get("display_code") or "").strip()
    return chosen if chosen in display_code_options(code) else code
