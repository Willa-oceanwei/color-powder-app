"""Compact product history filters and optional customer checkboxes."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from .product_transaction_report import product_transactions
from .shipment_repository import ShipmentError
from .shipment_ui import COMPACT_STYLE


def taiwan_timestamp(value):
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def render_product_transactions(config):
    st.markdown(COMPACT_STYLE.replace("shipment-page", "product-history-page"), unsafe_allow_html=True)
    st.markdown('''<style>
    .main:has(#product-history-page) .block-container {margin-top:0!important;padding-top:60px!important;}
    .main:has(#product-history-page) :is([data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"]) {margin:0!important;display:flow-root;}
    </style>''', unsafe_allow_html=True)
    st.subheader("貨品交易明細")
    with st.form("product_history_filters"):
        code_col, start_col, end_col, submit_col = st.columns([2, 1, 1, 0.7], vertical_alignment="bottom")
        code = code_col.text_input("貨品／配方編號", key="product_history_code").strip()
        start = start_col.date_input("起始出貨日期（選填）", value=None, key="product_history_start")
        end = end_col.date_input("結束出貨日期（選填）", value=None, key="product_history_end")
        submitted = submit_col.form_submit_button("查詢", use_container_width=True)
    st.caption("依出貨明細保存的編號精確查詢；日期留白即查全部期間。登錄時間為台灣時間，作廢單不列入。")
    if submitted:
        try:
            rows = product_transactions(config, code, start, end)
        except ShipmentError as error:
            st.session_state.pop("product_history_result", None)
            st.error(str(error))
        except Exception:
            st.session_state.pop("product_history_result", None)
            st.error("交易明細讀取失敗，請稍後重新查詢")
        else:
            epoch = st.session_state.get("product_history_epoch", 0) + 1
            st.session_state.product_history_epoch = epoch
            st.session_state.product_history_result = {
                "config": repr(config), "code": code.upper(), "start": start, "end": end,
                "rows": rows, "epoch": epoch}
    result = st.session_state.get("product_history_result")
    if not result or result["config"] != repr(config):
        return
    rows = result["rows"]
    st.caption(f"查詢：{result['code']} · {result['start'] or '不限起日'} ～ {result['end'] or '不限迄日'}")
    if not rows:
        st.info("沒有符合條件的出貨記錄")
        return
    customers = {}
    for row in rows:
        customers.setdefault(row["customer_id"], row["customer_name"])
    selected = []
    if len(customers) > 1:
        table_col, customer_col = st.columns([3, 1])
        with customer_col:
            st.markdown("**客戶篩選**")
            st.caption("可複選；未勾選顯示全部客戶")
            counts = Counter(row["customer_id"] for row in rows)
            with st.container(height=min(360, max(160, 56 * len(customers) + 24)), border=True):
                for index, customer_id in enumerate(sorted(customers)):
                    if st.checkbox(f"{customer_id} · {customers[customer_id]}（{counts[customer_id]} 筆）",
                                   key=f"product_history_customer_{result['epoch']}_{index}"):
                        selected.append(customer_id)
    else:
        table_col = st.container()
    visible = [row for row in rows if not selected or row["customer_id"] in selected]
    with table_col:
        st.caption(f"{len(visible)} 筆明細 · {len({r['shipment_id'] for r in visible})} 張出貨單 · {len({r['customer_id'] for r in visible})} 位客戶")
        labels = {"shipment_date": "出貨日期", "created_at": "登錄時間（台灣）", "shipment_number": "出貨單號",
                  "customer_id": "客戶編號", "customer_name": "客戶名稱", "code": "貨品／配方編號", "name": "品名",
                  "quantity": "數量", "unit": "單位", "price": "單價", "amount": "明細金額", "tax_mode": "課稅方式",
                  "order_number": "採購單號", "notes": "明細備註"}
        frame = pd.DataFrame(visible, columns=list(labels))
        frame["created_at"] = frame["created_at"].map(taiwan_timestamp)
        st.dataframe(frame.rename(columns=labels), hide_index=True, use_container_width=True,
                     height=min(550, max(150, 36 * (len(visible) + 1))))
