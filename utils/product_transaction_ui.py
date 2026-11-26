"""Compact product history filters and optional customer checkboxes."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape

import pandas as pd
import streamlit as st

from .product_transaction_report import product_transactions, product_price_changes, product_price_notices
from .shipment_print import display_price
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


def _query_help():
    with st.popover("查詢說明", use_container_width=True):
        st.write("以出貨明細查詢；同主編號有不同字母尾碼時，可選單一編號或全部列出，作廢單不列入。")
        st.write("勾選「包含相關配方」，會納入已登記原始配方的關聯，以及字母和 -1 等尾碼。"
                 "五位數的主編號按後四碼找相關配方，例如 52814 會查到 82814M-1。"
                 "有字首的主編號會保留字首，例如 C10499、B00886、A1434。")
        st.write("日期留白會查全部期間；登錄時間顯示台灣時間。")
        st.write("右側客戶可複選，未勾選時顯示全部客戶。")
        st.write("售價異動依同一編號、客戶、單位、課稅方式比較成交單價；保留初始售價，相同價格不重複列出。")
        st.write("日期範圍只篩選顯示結果，比價仍會參照較早的交易；這不是舊單修改前後的稽核紀錄。")
        st.write("價格提示採「預告報價」的生效日。沒有已生效報價時，顯示該客戶最早有單價的出貨紀錄。")


def _price_notice_text(notice):
    day = date.fromisoformat(notice["date"])
    unit = "kg" if notice["unit"] == "KG" else notice["unit"]
    suffix = f"元/{unit}" if unit else "元"
    price = f"{display_price(notice['price'])} {suffix}"
    if notice["previous_price"] is not None:
        price = f"從 {display_price(notice['previous_price'])} {suffix} 調為 {price}"
    return (f"{day.year - 1911}/{day:%m/%d} {notice['kind']} · "
            f"{notice['code']} · {notice['customer_id']} {notice['customer_name']} · {price}（{notice['tax_mode']}）")


def _render_price_notices(notices, chosen_code, customers=()):
    if notices is None:
        st.warning("價格提示暫時無法讀取，可繼續查閱交易明細。")
        return
    notices = [notice for notice in notices if (chosen_code == "__all__" or notice["code"] == chosen_code)
               and (not customers or notice["customer_id"] in customers)]
    if notices:
        st.info(_price_notice_text(notices[0]))
    if len(notices) > 1:
        with st.expander(f"其他價格紀錄（{len(notices) - 1} 筆）"):
            for notice in notices[1:]:
                st.write(_price_notice_text(notice))


def render_product_transactions(config):
    st.html(COMPACT_STYLE.replace("shipment-page", "product-history-page"))
    st.html('''<style>
    .main:has(#product-history-page) .block-container,
    .stApp:has(.erp-title) .main:has(#product-history-page) .block-container {margin-top:0!important;padding-top:28px!important;}
    .main:has(#product-history-page) :is([data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"]) {margin:0!important;display:flow-root;}
    .history-tags {display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
    .history-tag {background:#152c3d;border:1px solid #36576d;border-radius:6px;padding:5px 10px;font-size:13px;line-height:1.4;color:#d7ebf8;}
    .history-tag strong {color:#fff;margin-left:6px;}
    .history-stats {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-width:34rem;margin:2px 0 8px;}
    .history-stat {padding:5px 10px;border:1px solid #36576d;border-radius:7px;background:#132b3b;}
    .history-stat:nth-child(2) {background:#15322c;border-color:#387564;}
    .history-stat:nth-child(3) {background:#2a2440;border-color:#655483;}
    .history-stat strong {display:block;font-size:20px;line-height:1.2;color:#fff;}
    .history-stat span {font-size:12px;line-height:1.4;color:#bed1df;}
    </style>''')
    st.subheader("貨品交易明細")
    with st.form("product_history_filters"):
        code_col, start_col, end_col, submit_col = st.columns([2, 1, 1, 0.7], vertical_alignment="bottom")
        code = code_col.text_input("貨品／配方編號", key="product_history_code").strip()
        start = start_col.date_input("起始出貨日期（選填）", value=None, key="product_history_start")
        end = end_col.date_input("結束出貨日期（選填）", value=None, key="product_history_end")
        submitted = submit_col.form_submit_button("查詢", use_container_width=True)
    expand_family = st.toggle("包含相關配方", key="product_history_expand_family")
    previous = st.session_state.get("product_history_result")
    scope_changed = (previous and previous["config"] == repr(config)
                     and expand_family != previous.get("expand_family", False))
    if submitted or scope_changed:
        if not submitted:
            code, start, end = previous["code"], previous["start"], previous["end"]
        try:
            all_rows = product_transactions(config, code, start, end, include_prior=True,
                                            include_related=True, expand_family=expand_family)
            in_period = lambda row: (not start or row["shipment_date"] >= start.isoformat()) and (
                not end or row["shipment_date"] <= end.isoformat())
            rows = [row for row in all_rows if in_period(row)]
            prices = [row for row in product_price_changes(all_rows) if in_period(row)]
        except ShipmentError as error:
            st.session_state.pop("product_history_result", None)
            st.error(str(error))
        except Exception:
            st.session_state.pop("product_history_result", None)
            st.error("交易明細讀取失敗，請稍後重新查詢")
        else:
            try:
                notices = product_price_notices(config, code, all_rows, expand_family=expand_family)
            except Exception:
                notices = None
            epoch = st.session_state.get("product_history_epoch", 0) + 1
            st.session_state.product_history_epoch = epoch
            st.session_state.product_history_result = {
                "config": repr(config), "code": code.upper(), "start": start, "end": end, "expand_family": expand_family,
                "rows": rows, "all_rows": all_rows, "price_changes": prices, "price_notices": notices, "epoch": epoch}
    result = st.session_state.get("product_history_result")
    if not result or result["config"] != repr(config):
        _, help_col = st.columns([5, 1])
        with help_col:
            _query_help()
        return
    family_rows = result["rows"]
    rows = family_rows
    latest_by_code = {}
    for row in result.get("all_rows", family_rows):
        latest_by_code.setdefault(str(row["code"]).strip().upper(), row)
    price_notices = result.get("price_notices", [])
    matching_codes = list(dict.fromkeys([*latest_by_code, *(notice["code"] for notice in price_notices or [])]))
    chosen_code = result["code"] if result["code"] in matching_codes or not matching_codes else matching_codes[0]
    if len(matching_codes) > 1:
        notice_col, choice_col = st.columns([3, 2], vertical_alignment="center")
        latest = next(iter(latest_by_code.values()), None)
        caption = f"找到 {len(matching_codes)} 個相近編號"
        if latest:
            caption += f"；最近出貨：{latest['code']} · {latest['shipment_date']}（全部期間）"
        notice_col.info(caption)
        options = ["__all__"] + matching_codes
        default = 0 if result.get("expand_family") or result["code"] not in options else options.index(result["code"])
        chosen_code = choice_col.selectbox(
            "選擇查詢編號", options, index=default, key=f"product_history_variant_{result['epoch']}",
            format_func=lambda value: "全部相近編號" if value == "__all__" else
                f"{value} · 最近 {latest_by_code[value]['shipment_date']}" if value in latest_by_code else f"{value} · 有價格紀錄")
        rows = [row for row in family_rows if chosen_code == "__all__"
                or str(row["code"]).strip().upper() == chosen_code]
    elif chosen_code != result["code"]:
        latest = latest_by_code.get(chosen_code)
        hint = f"最近出貨：{latest['shipment_date']}" if latest else "有價格紀錄"
        st.info(f"查無 {result['code']} 的交易；相近編號 {chosen_code} {hint}")
    scope_label = f"{result['code']} 等 {len(matching_codes)} 個編號" if chosen_code == "__all__" else chosen_code
    if result["start"] and result["end"]:
        period = f"{result['start']} ～ {result['end']}"
    elif result["start"]:
        period = f"{result['start']} 起"
    elif result["end"]:
        period = f"截至 {result['end']}"
    else:
        period = "全部期間"
    scope_col, help_col = st.columns([5, 1], vertical_alignment="center")
    with scope_col:
        st.markdown(f'<div class="history-tags"><span class="history-tag">編號<strong>{escape(scope_label)}</strong></span>'
                    f'<span class="history-tag">{escape(period)}</span></div>', unsafe_allow_html=True)
    with help_col:
        _query_help()
    if not family_rows:
        _render_price_notices(price_notices, chosen_code)
        st.info("沒有符合條件的出貨記錄")
        return
    customers = {}
    for row in family_rows:
        customers.setdefault(row["customer_id"], row["customer_name"])
    selected = []
    if len(customers) > 1:
        table_col, customer_col = st.columns([3, 1])
        with customer_col:
            st.markdown("**客戶篩選**")
            st.caption("可複選；未勾選顯示全部客戶" + ("（筆數含相近編號）" if len(latest_by_code) > 1 else ""))
            counts = Counter(row["customer_id"] for row in family_rows)
            with st.container(height=min(360, max(160, 56 * len(customers) + 24)), border=True):
                for index, customer_id in enumerate(sorted(customers)):
                    if st.toggle(f"{customer_id} · {customers[customer_id]}（{counts[customer_id]} 筆）",
                                 key=f"product_history_customer_{result['epoch']}_{index}"):
                        selected.append(customer_id)
    else:
        table_col = st.container()
    visible = [row for row in rows if not selected or row["customer_id"] in selected]
    with table_col:
        _render_price_notices(price_notices, chosen_code, selected)
        if selected and len(latest_by_code) > 1:
            latest_customer = next((row for row in result.get("all_rows", family_rows) if row["customer_id"] in selected), None)
            if latest_customer:
                st.caption(f"所選客戶最近一筆出貨：{latest_customer['customer_id']} · {latest_customer['code']} · {latest_customer['shipment_date']}（全部期間）")
        stats = ((len(visible), "筆明細"), (len({r['shipment_id'] for r in visible}), "張出貨單"),
                 (len({r['customer_id'] for r in visible}), "位客戶"))
        st.markdown('<div class="history-stats">' + ''.join(
            f'<div class="history-stat"><strong>{count}</strong><span>{label}</span></div>'
            for count, label in stats) + '</div>', unsafe_allow_html=True)
        labels = {"shipment_date": "出貨日期", "created_at": "登錄時間（台灣）", "shipment_number": "出貨單號",
                  "customer_id": "客戶編號", "customer_name": "客戶名稱", "code": "貨品／配方編號", "name": "品名",
                  "quantity": "數量", "unit": "單位", "price": "單價", "amount": "明細金額", "tax_mode": "課稅方式",
                  "order_number": "採購單號", "notes": "明細備註"}
        detail_tab, price_tab = st.tabs(["交易明細", "售價異動"])
        with detail_tab:
            frame = pd.DataFrame(visible, columns=list(labels))
            frame["created_at"] = frame["created_at"].map(taiwan_timestamp)
            st.dataframe(frame.rename(columns=labels), hide_index=True, use_container_width=True,
                         height=min(550, max(150, 36 * (len(visible) + 1))))
        with price_tab:
            st.caption("同一編號、客戶、單位及課稅方式分別比較；第一筆註記初始售價，後續僅列變價記錄。")
            changes = [row for row in result.get("price_changes", [])
                       if (not selected or row["customer_id"] in selected)
                       and (chosen_code == "__all__" or str(row["code"]).strip().upper() == chosen_code)]
            if not changes:
                st.info("此期間沒有初始售價或售價異動記錄。")
            else:
                price_labels = {"shipment_date": "日期", "code": "貨品／配方編號", "price_event": "異動類型",
                                "customer_id": "客戶編號", "customer_name": "客戶名稱",
                                "previous_price": "原單價", "price": "新單價", "price_change": "漲跌",
                                "unit": "單位", "tax_mode": "課稅方式", "shipment_number": "出貨單號"}
                st.dataframe(pd.DataFrame(changes, columns=list(price_labels)).rename(columns=price_labels),
                             hide_index=True, use_container_width=True,
                             height=min(550, max(150, 36 * (len(changes) + 1))))
