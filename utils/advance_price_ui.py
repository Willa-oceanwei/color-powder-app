"""Advance price workspace and persistent navigation reminders."""

from datetime import date
import pandas as pd
import streamlit as st

from .accounting_widgets import widget_default
from .advance_price_repository import (
    AdvancePriceError, business_today, cancel_advance_price,
    item_quote, list_advance_prices, reminder_status, save_advance_price,
    same_price, unchanged_price_context,
)
from .customer_repository import customer_display_name, list_customers
from .shipment_catalog import shipment_choices
from .shipment_repository import TAX_MODES


def render_advance_price_reminders(config):
    quotes = list_advance_prices(config)
    states = [reminder_status(q, quotes) for q in quotes]
    waiting, due = states.count("待生效"), states.count("已生效未出貨")
    if waiting or due:
        st.caption(f"🟡 預告待生效 {waiting} 筆　🔴 已生效未出貨 {due} 筆")


def _new_quote():
    st.session_state.pop("advance_price_edit", None)
    st.session_state.advance_price_epoch = st.session_state.get("advance_price_epoch", 0) + 1


def render_advance_price_management(config):
    st.subheader("預告報價")
    st.caption("依出貨日期套用。單位與課稅方式必須相同；舊出貨單保留當時成交價。")
    flash = st.session_state.pop("advance_price_flash", "")
    if flash:
        st.success(flash)
    quotes = list_advance_prices(config)
    waiting = sum(reminder_status(q, quotes) == "待生效" for q in quotes)
    due = sum(reminder_status(q, quotes) == "已生效未出貨" for q in quotes)
    if due:
        st.warning(f"{due} 筆預告報價已生效，尚未使用適用價格出貨；提醒會持續保留。")
    st.caption(f"待生效 {waiting} 筆 · 已生效未出貨 {due} 筆")
    if st.button("重新整理", key="advance_price_refresh"):
        from .read_cache import invalidate_read_cache
        invalidate_read_cache(config)
        st.rerun()
    status = st.selectbox("顯示狀態", ["需要提醒", "全部", "待生效", "已生效未出貨", "已套用", "已被後續報價取代", "已取消"])
    visible = [q for q in quotes if status == "全部" or reminder_status(q, quotes) == status
               or status == "需要提醒" and reminder_status(q, quotes) in ("待生效", "已生效未出貨")]
    if visible:
        st.dataframe(pd.DataFrame([{
            "客戶": f"{q['customer_id']} · {q['customer_label'] or ''}", "貨品編號": q["code"], "品名": q["name"],
            "預告單價": q["price"], "單位": q["unit"], "課稅方式": q["tax_mode"], "生效日期": q["effective_date"],
            "狀態": reminder_status(q, quotes), "備註": q["notes"], "取消原因": q["cancel_reason"],
        } for q in visible]), use_container_width=True, hide_index=True)
        ids = [q["id"] for q in visible]
        lookup = {q["id"]: q for q in visible}
        selected = st.selectbox("管理報價", ids, format_func=lambda key: f"{lookup[key]['customer_label']} · {lookup[key]['code']} · {lookup[key]['effective_date']}")
        quote = lookup[selected]
        if quote["status"] == "active":
            if st.button("修改此報價", disabled=bool(quote["referenced"])):
                _new_quote()
                st.session_state.advance_price_edit = quote
                st.rerun()
            if quote["referenced"]:
                st.caption("已有出貨引用此報價，後續調價請新增另一生效日。")
            with st.expander("取消此預告報價"):
                st.caption("保留報價與出貨歷史。取消後停止優先帶入此報價；一般歷史帶價仍照常運作。")
                with st.form("advance_cancel_" + quote["id"]):
                    reason = st.text_input("取消原因")
                    if st.form_submit_button("確認取消報價"):
                        try:
                            cancel_advance_price(config, quote["id"], quote["version"], reason)
                        except AdvancePriceError as exc:
                            st.error(str(exc))
                        else:
                            _new_quote()
                            st.session_state.advance_price_flash = "預告報價已取消，歷史紀錄保留"
                            st.rerun()
    else:
        st.info("目前沒有符合狀態的預告報價")

    st.button("＋ 新增預告報價", on_click=_new_quote)
    edit = st.session_state.get("advance_price_edit", {})
    prefix = f"advance_{st.session_state.get('advance_price_epoch', 0)}_"
    st.markdown("### " + ("修改預告報價" if edit else "新增預告報價"))
    customers = {c["customer_id"]: customer_display_name(c) for c in list_customers(config) if c["lifecycle_status"] == "active"}
    customer = st.selectbox("客戶", [""] + list(customers), index=([""] + list(customers)).index(edit.get("customer_id", "")) if edit.get("customer_id", "") in [""] + list(customers) else 0,
                            format_func=lambda key: f"{key} · {customers[key]}" if key else "請選擇客戶", key=prefix + "customer")
    choices = shipment_choices(config, customer) if customer else {}
    codes = [""] + list(choices)
    code = st.selectbox("貨品／配方", codes, index=codes.index(edit.get("code")) if edit.get("code") in codes else 0,
                       format_func=lambda key: f"{key} · {choices[key]['name']}" if key else "請選擇貨品", key=prefix + "code_" + customer)
    product = choices.get(code, {})
    # Form names include the selected scope so changing customer/product cannot retain an unrelated unit.
    with st.form(prefix + "form_" + customer + "_" + code):
        unit = st.text_input("銷售單位", value=edit.get("unit", product.get("sales_unit", "KG")))
        tax = st.selectbox("課稅方式", TAX_MODES, index=TAX_MODES.index(edit.get("tax_mode", product.get("tax_mode", "外加"))))
        price = st.text_input("預告單價", value=edit.get("price", ""), help="最多三位小數；含稅／未稅依上方課稅方式")
        effective = st.date_input("生效日期", value=date.fromisoformat(edit["effective_date"]) if edit else business_today())
        notes = st.text_area("備註／客戶確認紀錄", value=edit.get("notes", ""))
        if st.form_submit_button("確認儲存預告報價", type="primary"):
            try:
                save_advance_price(config, dict(edit, customer_id=customer, code=code, name=product.get("name", ""),
                                               unit=unit, tax_mode=tax, price=price, effective_date=effective, notes=notes))
            except AdvancePriceError as exc:
                st.error(str(exc))
            else:
                _new_quote()
                st.session_state.advance_price_flash = "預告報價已儲存；生效前仍沿用原價"
                st.rerun()


def render_customer_price_notice(quotes, document):
    active = [q for q in quotes if q["status"] == "active" and
              reminder_status(q, quotes, document["shipment_date"]) != "已被後續報價取代"]
    if active:
        with st.expander(f"預告報價提醒 · 此客戶 {len(active)} 筆", expanded=True):
            for q in active:
                label = "本次出貨日期已生效" if q["effective_date"] <= document["shipment_date"] else "尚未生效"
                st.caption(f"{q['code']} · {q['name']}｜{q['price']} / {q['unit']} · {q['tax_mode']}｜{q['effective_date']} 起 · {label}")


def render_shipment_price_checks(quotes, document, original, prefix):
    for index, item in enumerate(document["items"]):
        quote = item_quote(quotes, document, item)
        old = original.get("items", [])
        if not quote or original.get("id") and index < len(old) and unchanged_price_context(document, item, original, old[index]):
            continue
        if same_price(item.get("price"), quote["price"]):
            st.caption(f"第 {index + 1} 項：已帶入預告報價 {quote['price']} / {quote['unit']}（{quote['effective_date']} 生效）")
        else:
            st.warning(f"第 {index + 1} 項 {item.get('code')}：適用預告單價 {quote['price']} / {quote['unit']}，目前為 {item.get('price')}。")
            if st.button(f"第 {index + 1} 項改用適用價格", key="advance_apply_" + prefix + str(index)):
                from copy import deepcopy
                item["price"] = quote["price"]
                item.pop("advance_price_override_reason", None)
                st.session_state.shipment_editor_base = deepcopy(document["items"])
                st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
                st.rerun()
            reason_key = prefix + f"quote_reason_{index}_{quote['id']}"
            item["advance_price_override_reason"] = st.text_input(
                f"第 {index + 1} 項特殊議價原因（保留目前單價時必填）", key=reason_key,
                value=widget_default(reason_key, item.get("advance_price_override_reason", "")))
