"""Presentation-only theme helpers for the Streamlit application shell."""

from __future__ import annotations

import os
from collections.abc import Mapping


LEGACY_VISUAL_STYLE = "legacy"
REFINED_VISUAL_STYLE = "refined"


def selected_visual_style(environ: Mapping[str, str] | None = None) -> str:
    """Return the selected shell style, defaulting safely to the refined layout.

    Setting ``VISUAL_STYLE=legacy`` restores the previous presentation without
    changing application data, navigation, or business behavior.
    """
    source = os.environ if environ is None else environ
    value = str(source.get("VISUAL_STYLE", REFINED_VISUAL_STYLE)).strip().lower()
    return value if value in {LEGACY_VISUAL_STYLE, REFINED_VISUAL_STYLE} else REFINED_VISUAL_STYLE


REFINED_SHELL_CSS = """
<style>
/* Presentation-only shell. All colors intentionally reuse the existing theme. */
:root {
    --cp-shell: #0b2f4a;
    --cp-canvas: #0a0a0a;
    --cp-accent: #c6582f;
    --cp-text: #ffffff;
    --cp-muted: #9fb6cc;
    --cp-hover: #124466;
}

/* A compact ERP header like the visual reference, without changing page text. */
.cp-app-header {
    position: fixed;
    inset: 0 0 auto 0;
    z-index: 999991;
    height: 60px;
    display: flex;
    align-items: center;
    padding: 0 20px;
    box-sizing: border-box;
    background: var(--cp-shell);
    color: var(--cp-text);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.02em;
}

header[data-testid="stHeader"] {
    top: 60px;
    height: 0;
    background: transparent;
}

section[data-testid="stSidebar"] {
    top: 60px;
    width: 250px !important;
    min-width: 250px !important;
    max-width: 250px !important;
    height: calc(100vh - 60px);
    border-right: 1px solid rgba(255,255,255,0.12);
    box-shadow: none;
    transition: transform .3s ease, width .3s ease;
}

section[data-testid="stSidebar"] > div:first-child {
    padding: 18px 14px 24px;
}

section[data-testid="stSidebar"] .erp-title {
    margin: 0 8px 2px;
    font-size: 14px;
    line-height: 1.5;
}

section[data-testid="stSidebar"] .erp-sub {
    margin: 0 8px 18px;
}

section[data-testid="stSidebar"] .erp-group {
    margin: 17px 10px 7px;
    font-size: 9.5px;
    line-height: 1.4;
}

section[data-testid="stSidebar"] div.stButton {
    margin: 2px 0;
}

section[data-testid="stSidebar"] div.stButton > button {
    min-height: 42px;
    justify-content: flex-start;
    gap: 9px;
    padding: 9px 12px !important;
    border-radius: 3px !important;
    border-left: 3px solid transparent !important;
    line-height: 1.35;
    transition: background-color .15s ease, border-color .15s ease;
}

section[data-testid="stSidebar"] div.stButton > button p {
    width: 100%;
    text-align: left;
    white-space: nowrap;
}

section[data-testid="stSidebar"] div.stButton > button:hover {
    background: var(--cp-hover) !important;
    border-left-color: var(--cp-accent) !important;
}

section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
    background: var(--cp-accent) !important;
    border-left-color: #ffb199 !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] div[data-testid="stExpander"] {
    border: 0;
    background: transparent;
}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary {
    min-height: 38px;
    padding: 8px 10px !important;
    border-radius: 3px;
}

section[data-testid="stSidebar"] div[data-testid="stExpander"] details summary:hover {
    background: var(--cp-hover);
}

/* Style Streamlit's native collapse control as the round edge control. */
button[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapsedControl"] {
    position: fixed;
    top: 72px;
    width: 34px;
    height: 34px;
    border-radius: 50% !important;
    background: var(--cp-shell) !important;
    color: var(--cp-text) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.24) !important;
    transition: left .3s ease, background-color .15s ease;
}

button[data-testid="stSidebarCollapseButton"] {
    left: 234px;
}

button[data-testid="stSidebarCollapsedControl"] {
    left: 10px;
}

button[data-testid="stSidebarCollapseButton"]:hover,
button[data-testid="stSidebarCollapsedControl"]:hover {
    background: var(--cp-hover) !important;
}

.stApp, [data-testid="stAppViewContainer"] {
    background: var(--cp-canvas) !important;
}

div[data-testid="stAppViewBlockContainer"],
.main .block-container {
    padding-top: 80px !important;
    padding-left: 30px !important;
    padding-right: 30px !important;
    max-width: none;
}

/* Keep existing colors while giving the right-hand controls one visual rhythm. */
div[data-testid="stForm"],
div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
    box-shadow: 0 8px 24px rgba(0,0,0,0.16);
}

div.block-container .stButton > button,
div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea {
    min-height: 40px;
}

@media (max-width: 768px) {
    .cp-app-header {
        height: 48px;
        padding-left: 14px;
    }
    section[data-testid="stSidebar"] {
        top: 48px;
        height: calc(100vh - 48px);
        width: 250px !important;
        min-width: 250px !important;
        max-width: 250px !important;
    }
    div[data-testid="stAppViewBlockContainer"],
    .main .block-container {
        padding: 62px 14px 24px !important;
    }
}
</style>
"""


def apply_refined_shell(st) -> bool:
    """Render the optional visual shell and return whether it was enabled."""
    if selected_visual_style() != REFINED_VISUAL_STYLE:
        return False
    st.markdown(
        '<div class="cp-app-header">配方管理系統</div>' + REFINED_SHELL_CSS,
        unsafe_allow_html=True,
    )
    return True
