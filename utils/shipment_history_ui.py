"""On-demand customer purchase history without rerunning the shipment editor."""

import pandas as pd
import streamlit as st

from .shipment_repository import customer_purchase_history
from .number_format import format_optional_decimals


def render_purchase_history(config, customer_id, customer_name):
    with st.popover("採購歷程", use_container_width=True):
        _render_history_contents(config, customer_id, customer_name)


@st.fragment
def _render_history_contents(config, customer_id, customer_name):
    # Keep fragment updates inside their own block, separate from the popover portal.
    with st.container():
        if not customer_id:
            st.caption("請先選擇出貨單客戶")
            return
        st.markdown(f"**{customer_id} · {customer_name}**")
        code = st.text_input("配方／貨品編號", key="shipment_purchase_history_code").strip()
        submitted = st.button("搜尋歷程", key="shipment_purchase_history_search", use_container_width=True)
        if submitted:
            try:
                rows = customer_purchase_history(config, customer_id, code)
            except Exception:
                st.error("歷程讀取失敗，請稍後重新搜尋")
                st.session_state.pop("shipment_purchase_history_result", None)
            else:
                st.session_state.shipment_purchase_history_result = (repr(config), customer_id, code, rows)
        result = st.session_state.get("shipment_purchase_history_result")
        st.caption("由新到舊；日期以出貨日為採購參考，排除作廢與未儲存單據。單價比較請留意單位及課稅方式。")
        if not result or result[:2] != (repr(config), customer_id):
            return
        rows = result[3]
        if not rows:
            st.info("沒有符合的採購紀錄")
            return
        st.caption(f"{result[2] or '全部貨品'} · {len(rows)} 筆")
        labels = {"shipment_date": "出貨日期／採購參考", "shipment_number": "出貨單號",
                  "code": "配方／貨品編號", "name": "品名", "quantity": "數量", "unit": "單位",
                  "price": "單價", "amount": "金額", "tax_mode": "課稅方式", "order_number": "採購單號"}
        frame = pd.DataFrame(rows, columns=list(labels)).rename(columns=labels)
        for field in ("數量", "單價", "金額"):
            frame[field] = frame[field].map(format_optional_decimals)
        st.dataframe(frame, hide_index=True, use_container_width=True, height=min(320, 38 * (len(rows) + 1)))
