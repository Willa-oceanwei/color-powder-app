"""Compact Streamlit adapter for shipment documents."""

from copy import deepcopy
from datetime import date
from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from .shipment_catalog import shipment_choices, complete_items
from .shipment_print import display_price
from .accounting_widgets import widget_default
from .customer_repository import list_customers
from .shipment_repository import (
    TAX_MODES, ShipmentError, blank_shipment, calculate, copy_shipment, get_shipment,
    list_shipments, printable_shipment, save_shipment, void_shipment,
    recent_shipment_price,
)

COLUMNS = {"code": "貨品編號", "name": "品名", "quantity": "數量", "unit": "單位",
           "price": "單價", "amount": "金額", "order_number": "採購單號", "notes": "附註說明"}

# Scope overrides to this page, including the existing ERP's global CSS.
COMPACT_STYLE = """
<span id="shipment-page"></span><style>
.main:has(#shipment-page) .block-container {padding-top:60px!important;padding-bottom:10px!important;}
.main:has(#shipment-page) .stHeading [data-testid="stMarkdownContainer"] {margin-bottom:0!important;}
.main:has(#shipment-page) [data-testid="stVerticalBlock"] {gap:6px!important;}
.main:has(#shipment-page) [data-testid="stHorizontalBlock"] {gap:8px!important;}
.main:has(#shipment-page) h3 {font-size:18px!important;margin:0!important;padding:0!important;}
.main:has(#shipment-page) [data-testid="stWidgetLabel"] p {font-size:12px!important;margin-bottom:0!important;}
.main:has(#shipment-page) [data-testid="stTextInput"] input,
.main:has(#shipment-page) [data-testid="stDateInput"] input,
.main:has(#shipment-page) [data-testid="stNumberInput"] input {font-size:13px!important;min-height:28px!important;padding-top:2px!important;padding-bottom:2px!important;}
.main:has(#shipment-page) [data-baseweb="input"],
.main:has(#shipment-page) [data-baseweb="select"]>div {min-height:30px!important;height:32px!important;}
.main:has(#shipment-page) [data-testid="stSelectbox"] [data-baseweb="select"]>div {font-size:13px!important;padding-top:0!important;padding-bottom:0!important;}
.main:has(#shipment-page) button {min-height:29px!important;padding:2px 7px!important;border-radius:4px!important;}
.main:has(#shipment-page) button p {font-size:12px!important;white-space:nowrap;}
.main:has(#shipment-page) [data-testid="stTextArea"] textarea {min-height:64px!important;font-size:13px!important;}
.main:has(#shipment-page) [data-testid="stExpander"] details summary {padding:4px 8px!important;min-height:30px!important;}
.main:has(#shipment-page) [data-testid="stTabs"] [role="tablist"] {gap:12px!important;}
.main:has(#shipment-page) [data-testid="stTabs"] [role="tab"] {height:30px!important;}
.main:has(#shipment-page) [data-testid="stTabs"] [role="tabpanel"] {padding-top:5px!important;}
.main:has(#shipment-page) [data-testid="stCaptionContainer"] p {margin:0!important;}
.main:has(#shipment-page) .shipment-total {display:flex;justify-content:space-between;gap:8px;padding:3px 0;font-size:13px;font-variant-numeric:tabular-nums;}
.main:has(#shipment-page) .shipment-total:last-child {border-top:1px solid #84919d;font-weight:600;font-size:16px;margin-top:4px;padding-top:6px;}
.main:has(#shipment-page) .shipment-lines {font-size:12px;white-space:nowrap;overflow-x:auto;max-width:100%;}
.stApp:has(.erp-title) .main:has(#shipment-page) .block-container {padding-top:72px!important;}
.stApp:has(.erp-title) .main:has(#shipment-page) h3,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stWidgetLabel"] p,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stCaptionContainer"] p,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stExpander"] summary p,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stCheckbox"] label span,
.stApp:has(.erp-title) .main:has(#shipment-page) .shipment-total,
.stApp:has(.erp-title) .main:has(#shipment-page) #shipment-toolbar {color:#d5e1ec!important;}
@media(min-width:1000px){
.main:has(#shipment-page) [data-testid="stHorizontalBlock"]:has(#shipment-toolbar) {flex-wrap:nowrap!important;}
.main:has(#shipment-page) [data-testid="stHorizontalBlock"]:has(#shipment-toolbar)>[data-testid="column"] {min-width:0!important;}
}
</style>
"""


def _begin(document):
    st.session_state.shipment_draft = deepcopy(document)
    st.session_state.shipment_original = deepcopy(document)
    st.session_state.shipment_editor_base = deepcopy(document["items"])
    st.session_state.shipment_grid_epoch = 0
    st.session_state.shipment_epoch = st.session_state.get("shipment_epoch", 0) + 1
    st.rerun()


def _finish(message=""):
    st.session_state.pop("shipment_draft", None)
    st.session_state.pop("shipment_original", None)
    st.session_state.pop("shipment_editor_base", None)
    st.session_state.shipment_notice = message
    st.rerun()


def _remember_print_settings():
    st.session_state.shipment_preview_preference = st.session_state.get("shipment_print_preview", False)
    st.session_state.shipment_hide_preference = st.session_state.get("shipment_hide_prices", False)


def _fill_product_unit(prefix, products, picker_key):
    selected = st.session_state.get(picker_key, "")
    if selected in products:
        st.session_state[prefix + "sale_unit"] = products[selected]["sales_unit"]


def _tax_changed(prefix, source):
    state = st.session_state
    if source == "rate":
        if state[prefix + "tax_rate"] == 0:
            state[prefix + "tax_mode"] = "免稅"
        elif state.get(prefix + "tax_mode") in ("免稅", "零稅率"):
            state[prefix + "tax_mode"] = "外加"
    else:
        state[prefix + "tax_rate"] = 0 if state[prefix + "tax_mode"] in ("免稅", "零稅率") else 5


def render_shipment_management(config):
    st.markdown(COMPACT_STYLE, unsafe_allow_html=True)
    st.subheader("出貨單")
    notice = st.session_state.pop("shipment_notice", "")
    if notice:
        st.caption(notice)
    draft = st.session_state.get("shipment_draft")
    editing = draft is not None
    with st.expander("查詢", expanded=False):
        with st.form("shipment_search"):
            search = st.columns([3, 1])
            query = search[0].text_input("出貨單號 / 客戶 / 貨品編號", value=st.session_state.get("shipment_query", ""), disabled=editing)
            include_void = search[1].toggle("包含作廢單", value=st.session_state.get("shipment_include_void", False), disabled=editing)
            ranges = st.columns(4)
            customer_start = ranges[0].text_input("起始客戶編號", value=st.session_state.get("shipment_customer_start", ""), disabled=editing).strip()
            customer_end = ranges[1].text_input("結束客戶編號", value=st.session_state.get("shipment_customer_end", ""), disabled=editing).strip()
            start = ranges[2].date_input("起始日期", value=st.session_state.get("shipment_start"), disabled=editing)
            end = ranges[3].date_input("結束日期", value=st.session_state.get("shipment_end"), disabled=editing)
            if st.form_submit_button("查詢", disabled=editing):
                if start and end and start > end:
                    st.error("起始日期不可晚於結束日期")
                elif customer_start and customer_end and customer_start > customer_end:
                    st.error("起始客戶編號不可大於結束編號")
                else:
                    st.session_state.update(shipment_query=query, shipment_start=start, shipment_end=end,
                                            shipment_include_void=include_void, shipment_customer_start=customer_start,
                                            shipment_customer_end=customer_end,
                                            shipment_search_epoch=st.session_state.get("shipment_search_epoch", 0) + 1)
                    st.session_state.pop("shipment_selected", None)
                    st.rerun()
    records = list_shipments(config, query=st.session_state.get("shipment_query", ""),
                             start=st.session_state.get("shipment_start"), end=st.session_state.get("shipment_end"),
                             include_void=st.session_state.get("shipment_include_void", False),
                             customer_start=st.session_state.get("shipment_customer_start", ""),
                             customer_end=st.session_state.get("shipment_customer_end", ""))
    if st.session_state.get("shipment_search_epoch"):
        with st.expander(f"查詢結果 · {len(records)} 筆", expanded=False):
            if records:
                result = pd.DataFrame([{"出貨日期": r["shipment_date"], "出貨單號": r["shipment_number"],
                          "客戶編號": r["customer_id"], "客戶名稱": r["customer_name"], "總計": int(r["total_amount"]),
                          "狀態": "作廢" if r["status"] == "void" else "有效"} for r in records])
                if editing:
                    st.dataframe(result, height=160, hide_index=True, use_container_width=True)
                else:
                    epoch = st.session_state["shipment_search_epoch"]
                    selection = st.dataframe(result, height=160, hide_index=True, use_container_width=True,
                                             on_select="rerun", selection_mode="single-row", key=f"shipment_results_{epoch}")
                    rows = selection.selection.rows
                    event = (epoch, tuple(rows))
                    if event != st.session_state.get("shipment_result_event"):
                        st.session_state.shipment_result_event = event
                        if rows and rows[0] < len(records):
                            st.session_state.shipment_selected = records[rows[0]]["id"]
            else:
                st.info("沒有符合條件的出貨單")
    ids = [row["id"] for row in records]
    selected = st.session_state.get("shipment_selected")
    index = ids.index(selected) if selected in ids else 0
    document = draft or (get_shipment(config, ids[index]) if ids else None)
    if not editing and document:
        st.session_state.shipment_selected = document["id"]
    tools = st.columns([1, 1, 1, 1, 1.1, 1, 1, 1, 1, .85])
    with tools[0]:
        if st.button("新增", key="shipment_new", disabled=editing, use_container_width=True):
            _begin(blank_shipment())
    if tools[1].button("修改", key="shipment_edit", disabled=editing or not document or document.get("status") == "void", use_container_width=True):
        _begin(document)
    if tools[2].button("複製", key="shipment_copy", disabled=editing or not document, use_container_width=True):
        _begin(copy_shipment(document))
    if tools[3].button("取消", key="shipment_cancel", disabled=not editing, use_container_width=True):
        _finish("已取消修改")
    save_clicked = tools[4].button("儲存", key="shipment_save", type="primary", disabled=not editing, use_container_width=True)
    for col, label, target in ((tools[5], "首筆", 0), (tools[6], "上一筆", index - 1),
                               (tools[7], "下一筆", index + 1), (tools[8], "尾筆", len(ids) - 1)):
        if col.button(label, key="shipment_nav_" + label,
                      disabled=editing or not ids or target < 0 or target >= len(ids) or target == index, use_container_width=True):
            st.session_state.shipment_selected = ids[target]
            st.rerun()
    tools[9].markdown(f'<span id="shipment-toolbar" style="font-size:12px">{index + 1 if ids else 0} / {len(ids)}</span>', unsafe_allow_html=True)
    if editing:
        st.caption("編輯中 · 尚未儲存")
    if not document:
        st.info("目前沒有出貨單")
        return
    if document.get("status") == "void":
        st.warning("已作廢：" + document.get("void_reason", ""))
    prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_" if editing else f"shipment_view_{document['id']}_{document['version']}_"
    print_controls = st.columns([1, 1, 3])
    preview = print_controls[0].toggle("預覽／列印", value=widget_default("shipment_print_preview", st.session_state.get("shipment_preview_preference", False)), key="shipment_print_preview", disabled=editing, on_change=_remember_print_settings)
    hide_prices = print_controls[1].toggle("隱藏單價與金額", value=widget_default("shipment_hide_prices", st.session_state.get("shipment_hide_preference", False)), key="shipment_hide_prices", disabled=editing, on_change=_remember_print_settings)
    sync_products = print_controls[2].toggle("同步建立缺少貨品", key=prefix + "sync_products", disabled=not editing,
                                            help="成交價依客戶、貨品與單位保存於出貨紀錄，不覆蓋共用標準售價")
    if preview and not editing:
        print_html = printable_shipment(document, show_prices=not hide_prices)
        print_controls[2].download_button("下載 A5 列印版", data=print_html,
                                          file_name=document["shipment_number"] + ("-無金額" if hide_prices else "") + ".html", mime="text/html")
        components.html(print_html, height=550, scrolling=True)
        return
    prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_" if editing else f"shipment_view_{document['id']}_{document['version']}_"

    def text(label, key, *, target=None):
        data = document if target is None else target
        widget_key = prefix + ("invoice_" if target is not None else "") + key
        value = st.text_input(label, value=widget_default(widget_key, str(data.get(key) or "")), key=widget_key, disabled=not editing)
        if editing:
            data[key] = value

    def date_field(label, key, *, target=None, optional=False):
        data = document if target is None else target
        value = date.fromisoformat(data[key]) if data.get(key) else None if optional else date.today()
        widget_key = prefix + ("invoice_" if target is not None else "") + key
        value = st.date_input(label, value=widget_default(widget_key, value), key=widget_key, disabled=not editing)
        if editing:
            data[key] = value.isoformat() if value else ""

    customers = list_customers(config, include_inactive=True)
    header = st.columns([1.25, 1.35, 1.55, 2.8])
    with header[0]:
        date_field("出貨日期", "shipment_date")
    with header[1]:
        mode = st.selectbox("單號方式", ("依日期生成", "自行輸入"),
                            index=widget_default(prefix + "number_mode", "依日期生成" if document.get("number_mode") == "date" else "自行輸入"),
                            key=prefix + "number_mode", disabled=not editing)
        if editing:
            document["number_mode"] = "date" if mode == "依日期生成" else "manual"
    with header[2]:
        if editing and document["number_mode"] == "manual":
            text("出貨單號", "shipment_number")
        else:
            retained = document.get("shipment_number", "")
            original = st.session_state.get("shipment_original", {})
            if editing and (not document.get("id") or original.get("number_mode") != "date" or document["shipment_date"] != original.get("shipment_date")):
                retained = ""
            preview = retained or date.fromisoformat(document["shipment_date"]).strftime("%y%m%d") + "####"
            st.text_input("出貨單號", value=preview, disabled=True)
    with header[3]:
        if editing:
            available = {row["customer_id"]: row["name"] for row in customers if row["lifecycle_status"] == "active"}
            original = st.session_state.get("shipment_original", document)
            if original.get("customer_id"):
                available.setdefault(original["customer_id"], original["customer_name"])
            options = [""] + list(available)
            # Keep widget identity stable while the selected customer changes.
            chosen = st.selectbox("客戶", options, index=widget_default(prefix + "customer_picker", original.get("customer_id", "")),
                                  format_func=lambda value: f"{value} · {available[value]}" if value else "請選擇客戶", key=prefix + "customer_picker")
            if chosen != document["customer_id"]:
                document.update(customer_id=chosen, customer_name=available.get(chosen, ""), recipient_id=chosen, recipient_name=available.get(chosen, ""))
                customer = next((row for row in customers if row["customer_id"] == chosen), {})
                for field in ("address", "phone", "fax", "contact", "tax_id"):
                    document[field] = customer.get(field) or ""
                for field in ("recipient_id", "recipient_name", "address", "phone", "fax", "contact", "tax_id"):
                    st.session_state[prefix + field] = document[field]
        else:
            st.text_input("客戶", value=f"{document['customer_id']} · {document['customer_name']}", disabled=True)
    receiver = st.columns([1.2, 1.8, 4])
    for col, label, field in zip(receiver, ("指送對象編號", "指送對象名稱", "送貨地址"), ("recipient_id", "recipient_name", "address")):
        with col:
            text(label, field)
    source_items = st.session_state.get("shipment_editor_base", document["items"]) if editing else document["items"]
    requested_item = None
    if editing:
        with st.expander("加入貨品／配方", expanded=False):
            choices = shipment_choices(config, document["customer_id"])
            picker, unit_col, quantity_col, add_col = st.columns([3, 1, 1, 1])
            picker_key = prefix + "recipe_picker_" + document["customer_id"]
            code = picker.selectbox("貨品／配方", [""] + list(choices),
                                    index=widget_default(picker_key, ""),
                                    format_func=lambda key: f"{key} · {choices[key]['name']}" if key else "請選擇貨品或配方",
                                    key=picker_key, on_change=_fill_product_unit, args=(prefix, choices, picker_key))
            unit = unit_col.text_input("銷售單位", value=widget_default(prefix + "sale_unit", "KG"), key=prefix + "sale_unit").strip()
            quantity = quantity_col.number_input("加入數量", min_value=0.001, value=widget_default(prefix + "add_quantity", 1.0), step=1.0, key=prefix + "add_quantity")
            previous = recent_shipment_price(config, document["customer_id"], code, unit,
                                             shipment_date=document["shipment_date"], tax_mode=document["tax_mode"],
                                             exclude_id=document.get("id", ""))
            chosen = choices.get(code)
            price = "0"
            if previous:
                price = str(previous["price"])
                st.caption(f"前次單價：{display_price(price)} / {unit} · {previous['shipment_date']} · {previous['shipment_number']}")
            elif code in choices:
                if chosen["sales_unit"].upper() == unit.upper() and chosen["tax_mode"] == document["tax_mode"]:
                    price = chosen["standard_price"]
                    st.caption(f"標準售價：{display_price(price)} / {unit}")
                else:
                    st.caption("無相符單位或課稅方式的單價，加入後請自行填價")
            if add_col.button("加入", key="shipment_add_recipe", disabled=not code or not unit, use_container_width=True):
                requested_item = dict(code=code, name=chosen["name"], quantity=str(quantity), unit=unit,
                                      price=price, order_number="", notes=chosen["specification"])
    frame = pd.DataFrame(source_items, columns=list(COLUMNS)).rename(columns=COLUMNS)
    for column in ("數量", "單價"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if editing:
        grid_suffix = st.session_state.get("shipment_grid_epoch", 0)
        frame = st.data_editor(frame.drop(columns="金額"), key=prefix + "items" + (f"_{grid_suffix}" if grid_suffix else ""), num_rows="dynamic", height=185,
                               use_container_width=True, hide_index=True, column_config={
                                   "採購單號": st.column_config.TextColumn("採購單號", width="medium"),
                                   "數量": st.column_config.NumberColumn("數量", min_value=0.001, step=0.001, required=True),
                                   "單價": st.column_config.NumberColumn("單價", min_value=0, step=0.001, format="%.15g", required=True)})
        raw_items = frame.rename(columns={value: key for key, value in COLUMNS.items()}).fillna("").to_dict("records")
        document["items"] = complete_items(config, document, raw_items, document["items"], choices=choices)
        if document["items"] != raw_items:
            st.session_state.shipment_editor_base = deepcopy(document["items"])
            st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
            st.rerun()
        if requested_item:
            # Preserve current grid edits before rebasing on the newly added item.
            document["items"].append(requested_item)
            st.session_state.shipment_editor_base = deepcopy(document["items"])
            st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
            st.rerun()
    else:
        st.dataframe(frame, height=185, hide_index=True, use_container_width=True,
                     column_config={"採購單號": st.column_config.TextColumn("採購單號", width="medium"), "單價": st.column_config.NumberColumn(format="%.15g")})
    details, summary, clearance = st.columns([3.7, 1.3, 1])
    with details:
        transaction, invoice_tab, account, related = st.tabs(["交易明細", "發票資料", "帳款資料", "相關資料"])
        with transaction:
            notes = st.text_area("備註", value=widget_default(prefix + "notes", document.get("notes", "")), height=68, key=prefix + "notes", disabled=not editing)
            if editing:
                document["notes"] = notes
        with invoice_tab:
            invoice = document["invoice"]
            row = st.columns(3)
            with row[0]:
                mode = st.selectbox("課稅類別", TAX_MODES, index=widget_default(prefix + "tax_mode", document["tax_mode"]), key=prefix + "tax_mode", disabled=not editing,
                                    on_change=_tax_changed, args=(prefix, "mode"))
                if editing:
                    document["tax_mode"] = mode
                text("開立方式", "method", target=invoice)
            with row[1]:
                date_field("發票日期", "date", target=invoice, optional=True)
                text("發票聯式", "type", target=invoice)
            with row[2]:
                text("發票編號", "number", target=invoice)
                text("發票金額", "amount", target=invoice)
        with account:
            left, right = st.columns(2)
            with left:
                date_field("帳款日期", "account_date")
            with right:
                text("付款條件", "payment_terms")
        with related:
            for row_fields in ((("聯絡人", "contact"), ("統一編號", "tax_id")), (("聯絡電話", "phone"), ("傳真號碼", "fax"))):
                for col, (label, field) in zip(st.columns(2), row_fields):
                    with col:
                        text(label, field)
            if document.get("id"):
                st.caption(f"建立：{document['created_at']}　更新：{document['updated_at']}")
                st.caption("已作廢" if document["status"] == "void" else "草稿")
    with summary:
        if editing:
            rate = st.selectbox("稅率", (0, 5), index=widget_default(prefix + "tax_rate", 0 if document["tax_mode"] in ("免稅", "零稅率") or float(document["tax_rate"]) == 0 else 5),
                                format_func=lambda value: "0%（免稅）" if value == 0 else "5%",
                                key=prefix + "tax_rate", on_change=_tax_changed, args=(prefix, "rate"))
            document["tax_rate"] = str(rate)
        else:
            st.text_input("稅率", value=f"{float(document['tax_rate']):g}%", disabled=True)
        try:
            totals = calculate(document["items"], document["tax_mode"], document["tax_rate"]) if editing else document
            st.markdown(''.join(f'<div class="shipment-total"><span>{label}</span><span>{int(totals[key]):,}</span></div>'
                               for label, key in (("未稅合計", "net_amount"), ("稅額", "tax_amount"), ("總計 TWD", "total_amount"))), unsafe_allow_html=True)
        except ShipmentError as error:
            totals = None
            st.error(str(error))
    if editing and totals and document["items"]:
        lines = '　·　'.join(f'{escape(str(item.get("code", "")))}：{int(amount):,}' for item, amount in zip(document["items"], totals["line_amounts"]))
        st.markdown(f'<div class="shipment-lines">{lines}</div>', unsafe_allow_html=True)
    if save_clicked:
        try:
            saved = save_shipment(config, document, sync_products=sync_products)
        except ShipmentError as error:
            st.error(str(error))
        except Exception:
            st.error("儲存失敗，請確認單號沒有重複及資料庫連線正常；修改內容已保留")
        else:
            st.session_state.shipment_selected = saved["id"]
            st.session_state.update(shipment_query="", shipment_start=None, shipment_end=None, shipment_include_void=False,
                                    shipment_customer_start="", shipment_customer_end="", shipment_search_epoch=0)
            _finish("已儲存出貨單 " + saved["shipment_number"])
    if not editing:
        download, lifecycle = st.columns([1, 3])
        download.download_button("下載列印版", data=printable_shipment(document, show_prices=not hide_prices), file_name=document["shipment_number"] + ".html", mime="text/html")
        if document["status"] == "draft":
            with lifecycle.expander("作廢出貨單"):
                with st.form("shipment_void_" + document["id"]):
                    reason = st.text_input("作廢原因")
                    confirm = st.toggle("確認作廢此出貨單")
                    if st.form_submit_button("作廢"):
                        if not confirm:
                            st.error("請確認作廢")
                        else:
                            try:
                                void_shipment(config, document["id"], document["version"], reason)
                            except ShipmentError as error:
                                st.error(str(error))
                            else:
                                _finish("出貨單已作廢，歷史資料保留")
