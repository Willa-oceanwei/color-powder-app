"""Streamlit workflow for registering and reviewing shipment returns."""

import logging
from datetime import date
from decimal import Decimal
from uuid import uuid4

import streamlit as st

from .sales_return_repository import (list_sales_returns, returned_quantities, save_sales_return,
                                      void_sales_return)
from .shipment_codes import printed_code
from .shipment_page_data import clear_reads
from .shipment_repository import ShipmentError, get_shipment, list_shipments


def _after_write(message):
    clear_reads(st.session_state)
    for key in ("receivable_pages", "receivable_exports", "ranking_statements"):
        st.session_state.pop(key, None)
    st.session_state.sales_return_notice = message
    st.rerun()


def _render_entry(config, shipment, available, last_active):
    shipment_id = shipment["id"]
    version = shipment["version"]
    form_key = f"sales_return_entry_{shipment_id}_{version}"
    token_key = "sales_return_token"
    state = st.session_state
    if state.get(token_key, (None,))[0] != form_key:
        state[token_key] = (form_key, str(uuid4()))
    min_date = date.fromisoformat(last_active["return_date"] if last_active else shipment["shipment_date"])
    st.subheader("登錄退回")
    with st.form(form_key):
        date_col, reason_col = st.columns([1, 3])
        return_date = date_col.date_input("退回日期", value=max(date.today(), min_date), min_value=min_date)
        reason = reason_col.text_input("退回原因")
        quantities = {}
        for number, item in enumerate(shipment["items"], 1):
            if available[number] <= 0:
                continue
            label = f"{number} · {printed_code(item)} {item['name']}（可退 {available[number]:f} {item['unit']}）"
            quantities[number] = st.number_input(
                label, min_value=0.0, max_value=float(available[number]), value=0.0, step=0.001,
                format="%.3f", key=f"{form_key}_{number}",
            )
        submitted = st.form_submit_button("儲存退回單", type="primary")
    if submitted:
        try:
            record = save_sales_return(
                config, return_id=state[token_key][1], shipment_id=shipment_id, shipment_version=version,
                return_date=return_date, reason=reason,
                quantities={number: format(value, ".3f") for number, value in quantities.items()},
            )
        except ShipmentError as error:
            st.error(str(error))
        except Exception:
            logging.getLogger(__name__).exception("Sales return save failed")
            st.error("退回單儲存失敗，請重試或重新查詢確認。")
        else:
            _after_write(f"已儲存退回單 {record['return_number']}，含稅退回金額 {int(record['total_amount']):,} 元。")


def _render_history(config, shipment, returns, last_active):
    st.subheader("退回紀錄")
    if not returns:
        st.caption("這張出貨單尚無退回紀錄。")
        return
    for record in returns:
        status = "有效" if record["status"] == "active" else "已作廢"
        with st.expander(
            f"{record['return_number']} · {record['return_date']} · {int(record['total_amount']):,} 元 · {status}"
        ):
            st.text(f"原出貨單 {record['shipment_number']}")
            st.text(f"退回原因 {record['reason']}")
            st.caption(f"未稅 {int(record['net_amount']):,} 元　稅額 {int(record['tax_amount']):,} 元")
            st.dataframe([
                {"貨品編號": printed_code(item), "品名": item["name"], "數量": Decimal(item["quantity"]),
                 "單位": item["unit"], "原單價": item["price"], "退回金額": item["amount"]}
                for item in record["items"]
            ], hide_index=True, use_container_width=True)
            if record["void_reason"]:
                st.text(f"作廢原因 {record['void_reason']}")
            if record is last_active:
                with st.form(f"sales_return_void_{record['id']}_{shipment['version']}"):
                    reason = st.text_input("作廢原因")
                    confirmed = st.toggle("確認作廢此退回單")
                    submitted = st.form_submit_button("作廢退回單")
                if submitted and not confirmed:
                    st.warning("請先勾選確認作廢。")
                elif submitted:
                    try:
                        void_sales_return(config, record["id"], shipment["version"], reason)
                    except ShipmentError as error:
                        st.error(str(error))
                    except Exception:
                        logging.getLogger(__name__).exception("Sales return void failed")
                        st.error("退回單作廢失敗，請重試或重新查詢確認。")
                    else:
                        _after_write(f"已作廢退回單 {record['return_number']}。")


def render_sales_returns(config):
    st.header("銷貨退回")
    notice = st.session_state.pop("sales_return_notice", "")
    if notice:
        st.success(notice)
    st.caption("退回沿用原出貨單價與課稅方式，並依退回日期列入帳款明細。實際退款與庫存入庫需另行處理。")
    query = st.text_input("搜尋原出貨單", placeholder="出貨單號、客戶編號或客戶名稱").strip()
    matches = list_shipments(config, query=query, include_void=True, summary=True, newest_first=True)
    if not matches:
        st.info("找不到符合條件的出貨單。")
        return
    documents = {row["id"]: row for row in matches}
    shipment_id = st.selectbox(
        "原出貨單", documents, index=None, placeholder="選擇出貨單",
        format_func=lambda key: " · ".join(documents[key][field]
                                           for field in ("shipment_number", "shipment_date", "customer_name")),
    )
    if shipment_id is None:
        return
    shipment = get_shipment(config, shipment_id)
    returns = list_sales_returns(config, shipment_id)
    last_active = next((record for record in returns if record["status"] == "active"), None)
    quantities = returned_quantities(returns)
    available = {number: Decimal(item["quantity"]) - quantities[number]
                 for number, item in enumerate(shipment["items"], 1)}
    if shipment["status"] != "draft":
        st.info("原出貨單已作廢。")
    elif any(amount > 0 for amount in available.values()):
        _render_entry(config, shipment, available, last_active)
    else:
        st.info("這張出貨單的品項已全數退回。")
    _render_history(config, shipment, returns, last_active)
