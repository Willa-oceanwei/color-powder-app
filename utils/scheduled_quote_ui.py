"""Schedule customer price notices and surface due quotes in shipment drafts."""

from datetime import date

import pandas as pd
import streamlit as st

from .customer_repository import customer_display_name, list_customers
from .read_cache import invalidate_read_cache
from .scheduled_quote_repository import (
    QuoteError, effective_quote_notices, list_scheduled_quotes, quote_today, save_scheduled_quote,
)
from .shipment_repository import TAX_MODES


def render_scheduled_quotes(config):
    st.subheader("預告報價")
    st.caption("生效日到達後，相同客戶的出貨單輸入相同貨號會提醒新報價；單價由你確認填入。")
    if st.button("重讀報價", key="scheduled_quote_reload"):
        invalidate_read_cache(config)
    if st.session_state.pop("scheduled_quote_saved", False):
        st.success("預告報價已儲存")
    try:
        customers = list_customers(config, include_inactive=True)
        quotes = list_scheduled_quotes(config, include_inactive=True)
    except Exception:
        st.error("報價資料讀取失敗，請稍後重讀")
        return
    names = {c["customer_id"]: customer_display_name(c) for c in customers}
    by_id = {q["quote_id"]: q for q in quotes}
    selected = st.selectbox("新增／修改", [""] + list(by_id), key="scheduled_quote_selected",
        format_func=lambda key: "新增預告報價" if not key else
        f"{by_id[key]['customer_id']} · {by_id[key]['product_code']} · {by_id[key]['effective_date']}" +
        ("（停用）" if not by_id[key]['active'] else ""))
    current = by_id.get(selected, {})
    prefix = f"quote_{selected}_{current.get('version', 0)}_"
    options = [""] + [c["customer_id"] for c in customers if c["lifecycle_status"] == "active"]
    if current.get("customer_id") and current["customer_id"] not in options:
        options.append(current["customer_id"])
    with st.form("scheduled_quote_form"):
        cols = st.columns(2)
        customer_id = cols[0].selectbox("客戶", options,
            index=options.index(current.get("customer_id", "")), key=prefix + "customer",
            format_func=lambda value: f"{value} · {names.get(value, value)}" if value else "請選擇客戶")
        code = cols[1].text_input("貨品編號", value=current.get("product_code", ""), key=prefix + "code")
        cols = st.columns(3)
        price = cols[0].text_input("新單價", value=current.get("price", ""), key=prefix + "price")
        unit = cols[1].text_input("單位", value=current.get("unit", "KG"), key=prefix + "unit")
        tax_mode = cols[2].selectbox("課稅方式", TAX_MODES,
            index=TAX_MODES.index(current.get("tax_mode", "外加")), key=prefix + "tax")
        effective_date = st.date_input("生效日期", value=date.fromisoformat(current["effective_date"]) if current else quote_today(), key=prefix + "date")
        notes = st.text_area("備註", value=current.get("notes", ""), key=prefix + "notes")
        active = st.checkbox("啟用此報價提醒", value=bool(current.get("active", True)), key=prefix + "active")
        submitted = st.form_submit_button("儲存預告報價", type="primary")
    if submitted:
        try:
            save_scheduled_quote(config, dict(current, customer_id=customer_id, product_code=code,
                price=price, unit=unit, tax_mode=tax_mode, effective_date=effective_date.isoformat(), notes=notes, active=active))
        except QuoteError as error:
            st.error(str(error))
        except Exception:
            st.error("儲存失敗，請確認資料庫連線後重試")
        else:
            st.session_state.scheduled_quote_saved = True
            st.rerun()
    if quotes:
        st.dataframe(pd.DataFrame([{
            "客戶": f"{q['customer_id']} · {names.get(q['customer_id'], q['customer_name'])}",
            "貨品編號": q["product_code"], "新單價": q["price"], "單位": q["unit"],
            "課稅方式": q["tax_mode"], "生效日期": q["effective_date"],
            "狀態": "停用" if not q["active"] else "已生效" if q["effective_date"] <= quote_today().isoformat() else "待生效",
            "備註": q["notes"],
        } for q in quotes]), hide_index=True, use_container_width=True)
    else:
        st.info("尚未設定預告報價")


def render_shipment_quote_notices(config, document):
    try:
        quotes = effective_quote_notices(config, document.get("customer_id"), document.get("items", []))
    except Exception:
        st.warning("預告報價提醒暫時無法讀取，請重試或至「預告報價」確認。")
        return
    seen = set(st.session_state.get("shipment_quote_notices_seen", ()))
    current = set()
    for quote in quotes:
        identity = (repr(config), st.session_state.get("shipment_epoch", 0),
                    document.get("customer_id"), quote["quote_id"], quote["version"])
        current.add(identity)
        text = (f"已有新報價｜客戶 {quote['customer_id']}｜貨號 {quote['product_code']}｜"
                f"新單價 {quote['price']} / {quote['unit']}（{quote['tax_mode']}）｜"
                f"生效日 {quote['effective_date']}")
        st.warning(text + (f"｜{quote['notes']}" if quote["notes"] else "") + "。請確認出貨單單價。")
        if identity not in seen:
            st.toast(text, icon="🔔")
    st.session_state.shipment_quote_notices_seen = current
