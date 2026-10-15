"""Read-only print preview for query results, independent of an open draft."""

import streamlit as st
import streamlit.components.v1 as components

from .paper_preview import theme_preview
from .shipment_repository import get_shipment, printable_shipment


def render_search_print(config, records, epoch):
    with st.popover("列印出貨單"):
        _contents(config, records, epoch)


@st.fragment
def _contents(config, records, epoch):
    with st.container():
        if not records:
            return
        selected = records[0]["id"]
        st.caption("已選取 · " + records[0]["shipment_number"])
        hide = st.toggle("不列出單價與金額", key="shipment_search_print_hide_prices")
        if st.button("產生列印預覽", key="shipment_search_print_generate"):
            try:
                document = get_shipment(config, selected)
            except Exception:
                st.error("單據讀取失敗，請稍後重試")
                st.session_state.pop("shipment_search_print_snapshot", None)
            else:
                st.session_state.shipment_search_print_snapshot = (repr(config), selected, document)
        snapshot = st.session_state.get("shipment_search_print_snapshot")
        if not snapshot or snapshot[:2] != (repr(config), selected):
            return
        document = snapshot[2]
        if document["status"] == "void":
            st.warning("此出貨單已作廢")
        html = printable_shipment(document, show_prices=not hide,
                                  orientation="portrait" if st.session_state.get("shipment_print_orientation") == "直式" else "landscape",
                                  feed_rotation=st.session_state.get("shipment_feed_rotation", 0),
                                  hole_margin=st.session_state.get("shipment_hole_margin", 12.5),
                                  paper_stock="a4_driver" if st.session_state.get("shipment_paper_stock", "A4") == "A4" else "triplicate" if st.session_state.get("shipment_paper_stock", "").startswith("三聯紙") else "standard",
                                  output_mode="pdf" if st.session_state.get("shipment_output_mode", "實體列印").startswith("另存 PDF") else "print")
        st.download_button("下載列印版", html, file_name=document["shipment_number"] + ".html", mime="text/html", key="shipment_search_print_download")
        components.html(theme_preview(html), height=500, scrolling=True)
