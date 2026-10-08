"""One source of initial values for accounting widgets with retained drafts."""

import streamlit as st


def widget_default(key, default):
    """Seed state once; None avoids a competing value/index widget default."""
    if key not in st.session_state:
        st.session_state[key] = default
    return None
