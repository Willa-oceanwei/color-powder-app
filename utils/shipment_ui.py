"""Compact Streamlit adapter for shipment documents."""

from copy import deepcopy
from datetime import date
from html import escape
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from .shipment_catalog import shipment_choices, complete_items, recent_item_defaults, matching_products
from .shipment_print import display_price
from .paper_preview import theme_preview
from .shipment_page_data import cached_read, clear_reads, shipment_timing, timed_read
from .shipment_history_ui import render_purchase_history
from .shipment_search_print import render_search_print
from .shipment_codes import display_code_options, printed_code
from .accounting_widgets import widget_default, widget_index
from .customer_display import CustomerDisplay
from .list_ui import render_selection_table
from .customer_repository import customer_display_name, CONTACT_FIELDS, CustomerError, get_customer, list_customers
from .shipment_repository import (
    TAX_MODES, ShipmentError, blank_shipment, calculate, copy_shipment, get_shipment,
    list_shipments, printable_shipment, save_shipment, void_shipment,
    recent_shipment_price, shipment_price_history,
)

COLUMNS = {"code": "貨品編號", "name": "品名", "quantity": "數量", "unit": "單位",
           "price": "單價", "amount": "金額", "tax_exempt": "免稅", "order_number": "採購單號", "notes": "附註說明", "display_code": "顯示編號"}

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
.main:has(#shipment-page) .shipment-section {font-size:13px;font-weight:700;letter-spacing:.04em;padding:5px 10px;margin:5px 0 3px;border-left:4px solid #59baff;border-radius:4px;background:#10293b;color:#c5e7ff;}
.main:has(#shipment-page) .shipment-section.delivery {border-color:#57d6b1;background:#102e2a;color:#b3f2dd;}
.main:has(#shipment-page) .shipment-section.items {border-color:#b8a1ff;background:#28213a;color:#e1d5ff;}
.main:has(#shipment-page) .shipment-section.amounts {border-color:#ffd084;background:#382c18;color:#ffe1ad;}
.main:has(#shipment-page) .shipment-edit-status {display:inline-block;border:1px solid #8e6832;border-radius:5px;padding:3px 9px;background:#352918;color:#ffda9a;font-size:12px;font-weight:600;}
.main:has(#shipment-page) .shipment-totals-card {background:#142b29;border:1px solid #387d6d;border-radius:8px;padding:8px 12px;margin-top:8px;}
.main:has(#shipment-page) .shipment-totals-card .shipment-total {color:#d7eee8!important;}
.main:has(#shipment-page) .shipment-totals-card .shipment-total:last-child {color:#8ff0cb!important;border-color:#387d6d;font-size:20px;}
.main:has(#shipment-page) button[kind="primary"] {background:#166b55!important;border-color:#49b99c!important;color:#fff!important;}
.main:has(#shipment-page) .shipment-lines {font-size:12px;white-space:nowrap;overflow-x:auto;max-width:100%;}
.main:has(#shipment-page) .shipment-number-help {font-size:10px;line-height:1.3;margin:0;overflow-wrap:anywhere;}
.main:has(#shipment-page) label[data-baseweb="radio"]>div:first-child {background:transparent!important;border:1.5px solid #527086!important;box-sizing:border-box;}
.main:has(#shipment-page) label[data-baseweb="radio"]:has(input:checked)>div:first-child {background:#3487b6!important;border-color:#3487b6!important;}
.main:has(#shipment-page) label[data-baseweb="radio"]:has(input:checked)>div:first-child>div {background:#fff!important;}
.main:has(#shipment-page) label[data-baseweb="radio"]:not(:has(input:checked))>div:first-child>div {background:transparent!important;}
.main:has(#shipment-page) label[data-baseweb="radio"]:has(input:focus-visible)>div:first-child {outline:2px solid #8cc8ea;outline-offset:3px;}
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stRadio"] p,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stMetricLabel"],
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stMetricLabel"] p,
.stApp:has(.erp-title) .main:has(#shipment-page) [data-testid="stMetricValue"] {color:#d5e1ec!important;}
body:has(#shipment-page) [data-testid="stPopoverBody"] {width:min(960px,calc(100vw - 40px))!important;max-width:calc(100vw - 40px)!important;}
body:has(#shipment-page) [data-testid="stPopoverBody"]:has(iframe) {max-height:calc(100vh - 32px)!important;overflow-y:auto;}
body:has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
body:has(#shipment-page) [data-testid="stPopoverBody"] .element-container {width:100%!important;max-width:100%!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] {background:#101820!important;color:#d5e1ec!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"]>div {background:#101820!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p,
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] p {color:#d5e1ec!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] button {background:#193042!important;color:#fff!important;border-color:#527086!important;}
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


def _rerun_shipment():
    st.rerun()


def _cached_print(config, document, **options):
    signature = (repr(config), json.dumps(document, sort_keys=True, ensure_ascii=False, default=str),
                 tuple(sorted(options.items())))
    cached = st.session_state.get("shipment_print_cache")
    if cached is None or cached[0] != signature:
        cached = (signature, printable_shipment(document, **options))
        st.session_state.shipment_print_cache = cached
    return cached[1]


def _begin(document, *, rerun=True):
    st.session_state.pop("shipment_saved_view", None)
    st.session_state.pop("shipment_saved_nav_direction", None)
    st.session_state.pop("shipment_read_cache", None)
    st.session_state.shipment_draft = deepcopy(document)
    st.session_state.shipment_original = deepcopy(document)
    st.session_state.shipment_editor_base = deepcopy(document["items"])
    st.session_state.shipment_grid_epoch = 0
    st.session_state.shipment_contacts_pending = True
    st.session_state.shipment_epoch = st.session_state.get("shipment_epoch", 0) + 1
    if rerun:
        _rerun_shipment()


def _copy_for_edit(document):
    copied = copy_shipment(document)
    copied["number_mode"] = "manual"
    _begin(copied, rerun=False)


def _suspend_for_search():
    draft = st.session_state.get("shipment_draft")
    original = st.session_state.get("shipment_original", {})
    fields = ("items", "customer_id", "shipment_number", "notes", "recipient_id", "recipient_name", "address", "payment_terms", "order_number")
    has_content = draft and (any(draft.get(key) for key in fields)
                            or any(draft.get(key) != original.get(key) for key in ("shipment_date", "account_date", "tax_mode", "tax_rate"))
                            or draft.get("invoice", {}).get("number")
                            or st.session_state.get(f"shipment_{st.session_state.get('shipment_epoch', 0)}_invoice_amount_manual"))
    if has_content and draft != original:
        st.session_state.setdefault("shipment_suspended_drafts", []).append(deepcopy(draft))
    for key in ("shipment_draft", "shipment_original", "shipment_editor_base"):
        st.session_state.pop(key, None)


def _resume_search_draft():
    drafts = st.session_state.get("shipment_suspended_drafts", [])
    if drafts:
        _begin(drafts.pop(), rerun=False)


def _new_shipment():
    return dict(blank_shipment(), number_mode="manual")


def _finish(message="", *, rerun=True, invalidate_reports=False, saved_view=None):
    clear_reads(st.session_state)
    if invalidate_reports:
        st.session_state.pop("receivable_pages", None)
        st.session_state.pop("ranking_statements", None)
    st.session_state.pop("shipment_purchase_history_result", None)
    st.session_state.pop("shipment_search_print_snapshot", None)
    st.session_state.pop("shipment_draft", None)
    st.session_state.pop("shipment_original", None)
    st.session_state.pop("shipment_editor_base", None)
    st.session_state.pop("shipment_saved_nav_direction", None)
    if saved_view is None:
        st.session_state.pop("shipment_saved_view", None)
    else:
        st.session_state.shipment_saved_view = deepcopy(saved_view)
    st.session_state.shipment_notice = message
    if rerun:
        _rerun_shipment()


def _remember_print_settings(key):
    preference = "shipment_preview_preference" if key == "shipment_print_preview" else "shipment_hide_preference"
    st.session_state[preference] = st.session_state.get(key, False)


def _fill_product_unit(prefix, products, picker_key, history):
    selected = st.session_state.get(picker_key, "")
    if selected in products:
        recent = recent_item_defaults(history, selected) or {}
        st.session_state[prefix + "sale_unit"] = recent.get("unit") or products[selected]["sales_unit"]


def _tax_changed(prefix, source):
    state = st.session_state
    if source == "rate":
        if state[prefix + "tax_rate"] == 0:
            state[prefix + "tax_mode"] = "免稅"
        elif state.get(prefix + "tax_mode") in ("免稅", "零稅率"):
            state[prefix + "tax_mode"] = "外加"
    else:
        state[prefix + "tax_rate"] = 0 if state[prefix + "tax_mode"] in ("免稅", "零稅率") else 5


def _invoice_amount_changed(prefix):
    st.session_state[prefix + "invoice_amount_manual"] = True


def _select_customer(config, prefix):
    """Apply customer defaults before the page emits any editor widgets."""
    document = st.session_state.get("shipment_draft")
    if document is None:
        return
    chosen = st.session_state.get(prefix + "customer_picker", "")
    if chosen == document["customer_id"]:
        return
    try:
        customer = get_customer(config, chosen) if chosen else {}
    except CustomerError as error:
        st.session_state[prefix + "customer_picker"] = document["customer_id"]
        st.session_state.shipment_customer_error = str(error)
        return
    name = customer.get("name", "")
    document.update(customer_id=chosen, customer_name=name, recipient_id=chosen, recipient_name=name)
    for field in ("address", "phone", "fax", "contact", "tax_id"):
        document[field] = customer.get(field) or ""
    for field in ("recipient_id", "recipient_name", "address", "phone", "fax", "contact", "tax_id"):
        st.session_state[prefix + field] = document[field]


def _set_code_display(index, code, key):
    document = st.session_state.get("shipment_draft")
    if not document or index >= len(document["items"]) or document["items"][index]["code"] != code:
        return
    selected = st.session_state[key]
    document["items"][index]["display_code"] = "" if selected == code else selected
    st.session_state.shipment_editor_base = deepcopy(document["items"])
    st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1


def _draft_print_document(document):
    if not document.get("items"):
        raise ShipmentError("請先輸入出貨品項")
    if not document.get("shipment_date"):
        raise ShipmentError("請先輸入出貨日期")
    snapshot = deepcopy(document)
    totals = calculate(snapshot["items"], snapshot["tax_mode"], snapshot["tax_rate"])
    snapshot.update(totals)
    for item, amount in zip(snapshot["items"], totals["line_amounts"]):
        item["amount"] = str(amount)
    return snapshot


# Streamlit 1.38 can leave editor/tab nodes blank on fragment updates.
# Render this page in the normal app run; session read/print caches stay in use.
@shipment_timing("shipment_render")
def render_shipment_management(config, *, start_new_on_entry=False):
    for key, preference in (("shipment_print_preview", "shipment_preview_preference"), ("shipment_hide_prices", "shipment_hide_preference")):
        if preference in st.session_state:
            st.session_state[key] = st.session_state[preference]
    if start_new_on_entry and not st.session_state.get("shipment_entry_ready"):
        st.session_state.shipment_entry_ready = True
        if "shipment_draft" not in st.session_state:
            _begin(_new_shipment(), rerun=False)
    st.markdown(COMPACT_STYLE, unsafe_allow_html=True)
    notice = st.session_state.pop("shipment_notice", "")
    if notice:
        st.caption(notice)
    customer_error = st.session_state.pop("shipment_customer_error", "")
    if customer_error:
        st.error(customer_error)
    draft = st.session_state.get("shipment_draft")
    editing = draft is not None
    if editing:
        draft_prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_"
        # Early search reruns must not clean up editor widgets not rendered yet.
        for key in list(st.session_state):
            if key.startswith(draft_prefix) and not key.startswith(draft_prefix + "items"):
                st.session_state[key] = st.session_state[key]
    def read(key, loader):
        if not editing:
            return cached_read(config, st.session_state, key, loader)
        cache = st.session_state.setdefault("shipment_read_cache", {})
        cache_key = (repr(config), key)
        if cache_key not in cache:
            # New editing snapshots must see current customer details and prices.
            cache[cache_key] = timed_read(key, loader) if key == "customers" or isinstance(key, tuple) and key[0] == "history" else cached_read(config, st.session_state, key, loader, ttl=60)
        return cache[cache_key]

    with st.expander("查詢", expanded=False):
        if st.button("重讀資料", key="shipment_reload_data"):
            clear_reads(st.session_state)
            st.session_state.pop("shipment_saved_view", None)
            st.session_state.pop("shipment_purchase_history_result", None)
            st.session_state.pop("shipment_search_print_snapshot", None)
            _rerun_shipment()
        with st.form("shipment_search"):
            search = st.columns([3, 1])
            query = search[0].text_input("出貨單號 / 客戶 / 貨品編號", value=st.session_state.get("shipment_query", ""))
            include_void = search[1].toggle("包含作廢單", value=st.session_state.get("shipment_include_void", False))
            ranges = st.columns(4)
            customer_start = ranges[0].text_input("起始客戶編號", value=st.session_state.get("shipment_customer_start", "")).strip()
            customer_end = ranges[1].text_input("結束客戶編號", value=st.session_state.get("shipment_customer_end", "")).strip()
            start = ranges[2].date_input("起始日期", value=st.session_state.get("shipment_start"))
            end = ranges[3].date_input("結束日期", value=st.session_state.get("shipment_end"))
            if st.form_submit_button("查詢"):
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
                    st.session_state.pop("shipment_saved_view", None)
                    st.session_state.pop("shipment_search_print_snapshot", None)
                    clear_reads(st.session_state)
                    if editing:
                        _suspend_for_search()
                    _rerun_shipment()
    suspended = st.session_state.get("shipment_suspended_drafts", [])
    if suspended:
        resume = st.columns([3, 1])
        resume[0].caption(f"暫存草稿 {len(suspended)} 筆")
        resume[1].button("繼續草稿", key="shipment_resume_draft", disabled=editing, on_click=_resume_search_draft, use_container_width=True)
    record_key = ("records", *(st.session_state.get(key) for key in ("shipment_query", "shipment_start", "shipment_end",
                  "shipment_include_void", "shipment_customer_start", "shipment_customer_end")))
    saved_view = st.session_state.get("shipment_saved_view", {})
    saved_document = saved_view.get("document") if saved_view.get("config") == repr(config) else None
    saved_direction = st.session_state.get("shipment_saved_nav_direction", 0)
    showing_saved = bool(not editing and saved_document and not saved_direction
                         and not st.session_state.get("shipment_search_epoch")
                         and st.session_state.get("shipment_selected") == saved_document["id"])
    # The committed document is already available. Load the full list only on
    # an explicit search, refresh, or previous/next action.
    if showing_saved:
        records = [saved_document]
    elif editing and not st.session_state.get("shipment_search_epoch"):
        records = []
    else:
        records = cached_read(config, st.session_state, record_key, lambda: list_shipments(
            config, query=st.session_state.get("shipment_query", ""),
            start=st.session_state.get("shipment_start"), end=st.session_state.get("shipment_end"),
            include_void=st.session_state.get("shipment_include_void", False),
            customer_start=st.session_state.get("shipment_customer_start", ""),
            customer_end=st.session_state.get("shipment_customer_end", "")))
    if st.session_state.get("shipment_search_epoch"):
        with st.expander(f"查詢結果 · {len(records)} 筆", expanded=True):
            if records:
                display = CustomerDisplay(config)
                result = pd.DataFrame([{"出貨日期": r["shipment_date"], "出貨單號": r["shipment_number"],
                          "客戶編號": r["customer_id"], "客戶名稱": display.name(r["customer_name"], r["customer_id"]), "總計（未稅）": int(r["net_amount"]),
                          "狀態": "作廢" if r["status"] == "void" else "有效"} for r in records])
                chosen = render_selection_table(result, records, key="shipment_results_" + str(st.session_state["shipment_search_epoch"]),
                                                id_field="id", height=min(400, 38 * (len(records) + 1)), disabled=editing)
                if editing:
                    st.caption("草稿已保留；儲存或取消後可開啟查詢結果。")
                elif chosen is not None:
                    event = (st.session_state["shipment_search_epoch"], chosen["id"])
                    if event != st.session_state.get("shipment_result_event"):
                        st.session_state.shipment_result_event = event
                        st.session_state.shipment_selected = chosen["id"]
                    summary, actions = st.columns([3, 1.4], vertical_alignment="center")
                    summary.caption("已選取 · " + chosen["shipment_number"])
                    with actions:
                        render_search_print(config, [chosen], st.session_state["shipment_search_epoch"])
                else:
                    st.caption("勾選表格左側的資料列，即可查看內容或列印。")
            else:
                st.info("沒有符合條件的出貨單")
    query_number = st.session_state.get("shipment_query", "").strip()
    exact_match = next((row for row in records if row["shipment_number"] == query_number), None)
    navigation_records = records
    if exact_match and not showing_saved:
        # A full number locates a document; it must not limit sequential browsing.
        navigation_key = ("number-navigation", *record_key[2:])
        navigation_records = cached_read(config, st.session_state, navigation_key, lambda: sorted(
            list_shipments(config, start=st.session_state.get("shipment_start"), end=st.session_state.get("shipment_end"),
                           include_void=st.session_state.get("shipment_include_void", False),
                           customer_start=st.session_state.get("shipment_customer_start", ""),
                           customer_end=st.session_state.get("shipment_customer_end", "")),
            key=lambda row: (row["shipment_number"], row["id"])))
    ids = [row["id"] for row in navigation_records]
    selected = st.session_state.get("shipment_selected")
    if selected not in ids and exact_match:
        selected = exact_match["id"]
    index = ids.index(selected) if selected in ids else 0
    if saved_direction:
        if selected in ids:
            index = min(max(index + saved_direction, 0), len(ids) - 1)
        st.session_state.pop("shipment_saved_nav_direction", None)
        st.session_state.pop("shipment_saved_view", None)
    if editing:
        document = draft
    elif showing_saved:
        document = deepcopy(saved_document)
    else:
        document = read(("document", ids[index]), lambda: get_shipment(config, ids[index])) if ids else None
    if not editing and document:
        st.session_state.shipment_selected = document["id"]
    tools = st.columns([1, 1, 1, 1, 1.1, 1, 1, .6, 1.6])
    with tools[0]:
        st.button("新增", key="shipment_new", disabled=editing, use_container_width=True,
                  on_click=_begin, args=(_new_shipment(),), kwargs={"rerun": False})
    tools[1].button("修改", key="shipment_edit", disabled=editing or not document or document.get("status") == "void", use_container_width=True,
                    on_click=_begin, args=(document,), kwargs={"rerun": False})
    tools[2].button("複製", key="shipment_copy", disabled=editing or not document, use_container_width=True,
                    on_click=_copy_for_edit, args=(document,))
    tools[3].button("取消", key="shipment_cancel", disabled=not editing, use_container_width=True,
                    on_click=_finish, args=("已取消修改",), kwargs={"rerun": False})
    save_clicked = tools[4].button("儲存", key="shipment_save", type="primary", disabled=not editing, use_container_width=True)
    for col, label, target in ((tools[5], "上一筆", index - 1), (tools[6], "下一筆", index + 1)):
        if col.button(label, key="shipment_nav_" + label,
                      disabled=editing or (not showing_saved and (not ids or target < 0 or target >= len(ids) or target == index)), use_container_width=True):
            if showing_saved:
                st.session_state.shipment_saved_nav_direction = -1 if label == "上一筆" else 1
            else:
                st.session_state.shipment_selected = ids[target]
            _rerun_shipment()
    position = "已儲存" if showing_saved else f"{index + 1 if ids else 0} / {len(ids)}"
    tools[7].markdown(f'<span id="shipment-toolbar" style="font-size:12px">{position}</span>', unsafe_allow_html=True)
    hide_prices = st.session_state.get("shipment_hide_prices", st.session_state.get("shipment_hide_preference", False))
    export_panel = tools[8].popover("列印／匯出", use_container_width=True)
    with export_panel, st.container():
        output = st.selectbox("列印用途", ("實體列印", "另存 PDF（置中）"), key="shipment_output_mode")
        output_mode = "pdf" if output.startswith("另存 PDF") else "print"
        stock = st.selectbox("紙張尺寸", ("A4", "三聯紙 240 × 140 mm", "A5"), key="shipment_paper_stock")
        paper_stock = "a4_driver" if stock == "A4" else "triplicate" if stock.startswith("三聯紙") else "standard"
        layout = st.selectbox("列印方向", ("橫式", "直式"), key="shipment_print_orientation",
                              format_func=lambda value: "列印：" + ("橫放進紙" if paper_stock == "a4_driver" else value), label_visibility="collapsed", disabled=paper_stock != "standard")
        feed_rotation = st.selectbox("紙張進紙", (0, 90), format_func=lambda v: ("240 mm 長邊先進（橫放）" if v == 0 or paper_stock == "a4_driver" else "140 mm 短邊先進（直放）") if paper_stock != "standard" else ("原方向" if v == 0 else "旋轉90度進紙"), key="shipment_feed_rotation", disabled=paper_stock == "a4_driver")
        hole_margin = st.number_input("左右打洞留白（mm）", min_value=0.0, max_value=25.0, value=12.5, step=0.5, key="shipment_hole_margin")
        orientation = "portrait" if layout == "直式" else "landscape"
        print_html = _cached_print(config, document, show_prices=not hide_prices, orientation=orientation, feed_rotation=feed_rotation, hole_margin=hole_margin, paper_stock=paper_stock, output_mode=output_mode) if document and not editing else None
        if print_html:
            st.download_button("下載列印版", data=print_html, file_name=document["shipment_number"] + ".html", mime="text/html", use_container_width=True)
    orientation = "portrait" if layout == "直式" else "landscape"
    if editing:
        st.markdown('<span class="shipment-edit-status">編輯中 · 尚未儲存</span>', unsafe_allow_html=True)
    if not document:
        st.info("目前沒有出貨單")
        return
    display = CustomerDisplay(config)
    def current_customer_label():
        if showing_saved:
            return saved_view["customer_label"]
        if editing:
            customer = next((row for row in customers if row["customer_id"] == document["customer_id"]), None)
            if customer is not None:
                return customer_display_name(customer)
        return read(("customer-label", document["customer_id"], document["customer_name"]),
                    lambda: display.name(document["customer_name"], document["customer_id"]))
    if document.get("status") == "void":
        st.warning("已作廢：" + document.get("void_reason", ""))
    prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_" if editing else f"shipment_view_{document['id']}_{document['version']}_"
    print_controls = st.columns([1, 1, 2, 1])
    preview = print_controls[0].toggle("預覽／列印", value=widget_default("shipment_print_preview", st.session_state.get("shipment_preview_preference", False)), key="shipment_print_preview", on_change=_remember_print_settings, args=("shipment_print_preview",))
    hide_prices = print_controls[1].toggle("隱藏單價與金額", value=widget_default("shipment_hide_prices", st.session_state.get("shipment_hide_preference", False)), key="shipment_hide_prices", on_change=_remember_print_settings, args=("shipment_hide_prices",))
    sync_products = print_controls[2].toggle("同步建立缺少貨品", key=prefix + "sync_products", disabled=not editing,
                                            help="成交價依客戶、貨品與單位保存於出貨紀錄，不覆蓋共用標準售價")
    if preview and not editing:
        with print_controls[3]:
            render_purchase_history(config, document["customer_id"], current_customer_label())
        components.html(theme_preview(print_html), height=550, scrolling=True)
        return
    draft_preview = st.empty() if editing and preview else None
    prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_" if editing else f"shipment_view_{document['id']}_{document['version']}_"

    if editing:
        document["tax_mode"] = st.session_state.get(prefix + "tax_mode", document["tax_mode"])
        document["tax_rate"] = str(st.session_state.get(prefix + "tax_rate", document["tax_rate"]))

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
            if value is None and not optional:
                st.error(f"請輸入{label}")

    def invoice_choice(label, field, options):
        invoice = document["invoice"]
        current = invoice.get(field) or (options[0] if editing and not document.get("id") else "")
        choices = [""] + list(options)
        if current and current not in choices:
            choices.append(current)
        widget_key = prefix + "invoice_" + field
        selected = st.selectbox(label, choices, index=widget_index(widget_key, current),
                                format_func=lambda value: value or "請選擇", key=widget_key, disabled=not editing)
        if editing:
            invoice[field] = selected

    customers = read("customers", lambda: list_customers(config, include_inactive=True)) if editing else []
    if editing and st.session_state.pop("shipment_contacts_pending", False):
        customer = next((row for row in customers if row["customer_id"] == document["customer_id"]), {})
        for field in CONTACT_FIELDS:
            if not str(document.get(field) or "").strip():
                document[field] = customer.get(field) or ""
    st.markdown('<div class="shipment-section">出貨與客戶</div>', unsafe_allow_html=True)
    header = st.columns([1.25, 1.35, 1.55, 2.8])
    with header[0]:
        date_field("出貨日期", "shipment_date")
    with header[1]:
        mode = st.selectbox("單號方式", ("依日期生成", "自行輸入"),
                            index=widget_index(prefix + "number_mode", "依日期生成" if document.get("number_mode") == "date" else "自行輸入"),
                            key=prefix + "number_mode", disabled=not editing)
        if editing:
            document["number_mode"] = "date" if mode == "依日期生成" else "manual"
    with header[2]:
        if editing:
            text("出貨單號", "shipment_number")
            if document["number_mode"] == "date":
                st.markdown('<p class="shipment-number-help">留白自動編號；填入用指定單號。</p>', unsafe_allow_html=True)
        else:
            retained = document.get("shipment_number", "")
            original = st.session_state.get("shipment_original", {})
            if editing and (not document.get("id") or original.get("number_mode") != "date" or document["shipment_date"] != original.get("shipment_date")):
                retained = ""
            preview = retained or (date.fromisoformat(document["shipment_date"]).strftime("%y%m%d") + "####" if document["shipment_date"] else "請先選擇出貨日期")
            st.text_input("出貨單號", value=preview, disabled=True)
    with header[3]:
        if editing:
            available = {row["customer_id"]: customer_display_name(row) for row in customers if row["lifecycle_status"] == "active"}
            original = st.session_state.get("shipment_original", document)
            if original.get("customer_id"):
                available.setdefault(original["customer_id"], original["customer_name"])
            options = [""] + list(available)
            # Keep widget identity stable while the selected customer changes.
            st.selectbox("客戶", options, index=widget_index(prefix + "customer_picker", original.get("customer_id", "")),
                         format_func=lambda value: f"{value} · {available[value]}" if value else "請選擇客戶", key=prefix + "customer_picker",
                         on_change=_select_customer, args=(config, prefix))
        else:
            st.text_input("客戶", value=f"{document['customer_id']} · {current_customer_label()}", disabled=True)
    st.markdown('<div class="shipment-section delivery">送貨資訊</div>', unsafe_allow_html=True)
    receiver = st.columns([1.2, 1.8, 4])
    for col, label, field in zip(receiver, ("指送對象編號", "指送對象名稱", "送貨地址"), ("recipient_id", "recipient_name", "address")):
        with col:
            text(label, field)
    with print_controls[3]:
        render_purchase_history(config, document["customer_id"], current_customer_label())
    source_items = st.session_state.get("shipment_editor_base", document["items"]) if editing else document["items"]
    st.markdown('<div class="shipment-section items">貨品明細</div>', unsafe_allow_html=True)
    requested_item = None
    if editing:
        item_tools = st.columns([1, 1, 2])
        history_key = ("history", document["customer_id"], document["shipment_date"], document.get("id", ""))
        history = read(history_key, lambda: shipment_price_history(config, document["customer_id"],
                       document["shipment_date"], document.get("id", ""))) if document["customer_id"] else []
        all_choices = read("all_choices",
                           lambda: shipment_choices(config, document["customer_id"], all_recipes=True)) if document["customer_id"] else {}
        with item_tools[0].popover("搜尋貨品", use_container_width=True):
            choices = {code: item for code, item in all_choices.items()
                       if item.get("_recipe_customer", "") in ("", document["customer_id"])}
            picker, unit_col, quantity_col, add_col = st.columns([3, 1, 1, 1])
            picker_key = prefix + "recipe_picker_" + document["customer_id"]
            code = picker.selectbox("貨品／配方", [""] + list(choices),
                                    index=widget_index(picker_key, ""),
                                    format_func=lambda key: f"{key} · {choices[key]['name']}" if key else "請選擇貨品或配方",
                                    key=picker_key, on_change=_fill_product_unit, args=(prefix, choices, picker_key, history))
            unit = unit_col.text_input("銷售單位", value=widget_default(prefix + "sale_unit", "KG"), key=prefix + "sale_unit").strip()
            quantity = quantity_col.number_input("加入數量", min_value=0.001, value=widget_default(prefix + "add_quantity", 1.0), step=1.0, format="%.15g", key=prefix + "add_quantity")
            defaults = recent_item_defaults(history, code) or {}
            previous = recent_shipment_price(config, document["customer_id"], code, unit,
                                             shipment_date=document["shipment_date"], tax_mode="免稅" if defaults.get("tax_exempt") else document["tax_mode"],
                                             exclude_id=document.get("id", ""), history=history)
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
                requested_item = dict(code=code, name=defaults.get("name") or chosen["name"], quantity=str(quantity), unit=unit,
                                      price=price, tax_exempt=bool(defaults.get("tax_exempt", False)), order_number="", notes="")
    frame = pd.DataFrame(source_items, columns=list(COLUMNS)).rename(columns=COLUMNS)
    # Pandas 3 infers Arrow large_string; older Streamlit editors make it read-only.
    for column in ("貨品編號", "品名", "單位", "採購單號", "附註說明", "顯示編號"):
        frame[column] = frame[column].fillna("").astype(object)
    frame["免稅"] = frame["免稅"].fillna(False).astype(bool)
    for column in ("數量", "單價"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if editing:
        grid_suffix = st.session_state.get("shipment_grid_epoch", 0)
        frame = st.data_editor(frame.drop(columns="金額"), key=prefix + "items" + (f"_{grid_suffix}" if grid_suffix else ""), num_rows="dynamic", height=185,
                               use_container_width=True, hide_index=True, column_config={
                                   "貨品編號": st.column_config.TextColumn("貨品編號"),
                                   "顯示編號": None,
                                   "品名": st.column_config.TextColumn("品名"),
                                   "單位": st.column_config.TextColumn("單位"),
                                   "附註說明": st.column_config.TextColumn("附註說明"),
                                   "免稅": st.column_config.CheckboxColumn("免稅", default=False, width="small"),
                                   "採購單號": st.column_config.TextColumn("採購單號", width="medium"),
                                   "數量": st.column_config.NumberColumn("數量", min_value=0.001, step=0.001, format="%.15g"),
                                   "單價": st.column_config.NumberColumn("單價", min_value=0, step=0.001, format="%.15g")})
        frame["免稅"] = frame["免稅"].fillna(False).astype(bool)
        raw_items = frame.rename(columns={value: key for key, value in COLUMNS.items()}).fillna("").to_dict("records")
        document["items"] = complete_items(config, document, raw_items, document["items"], choices=all_choices, history=history)
        if document["items"] != raw_items:
            st.session_state.shipment_editor_base = deepcopy(document["items"])
            st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
            _rerun_shipment()
        for row_index, item in enumerate(document["items"]):
            candidates = matching_products(all_choices, item.get("code")) if item.get("code") else matching_products(all_choices, item.get("name"), by_name=True, history=history)
            if len(candidates) > 1:
                left, right = st.columns([4, 1])
                choice = left.selectbox(f"第 {row_index + 1} 項相符貨品", candidates, format_func=lambda c: f"{c} · {all_choices[c]['name']}", key=prefix + f"match_{row_index}")
                if right.button("採用", key=prefix + f"apply_{row_index}"):
                    before = deepcopy(document["items"])
                    document["items"][row_index]["code"] = choice
                    document["items"] = complete_items(config, document, document["items"], before, choices=all_choices, history=history)
                    st.session_state.shipment_editor_base = deepcopy(document["items"])
                    st.session_state.shipment_grid_epoch += 1
                    _rerun_shipment()
        if requested_item:
            # Preserve current grid edits before rebasing on the newly added item.
            document["items"].append(requested_item)
            st.session_state.shipment_editor_base = deepcopy(document["items"])
            st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
            _rerun_shipment()
        eligible = [(i, item) for i, item in enumerate(document["items"]) if len(display_code_options(item["code"])) > 1]
        if eligible:
            with item_tools[1].popover("編號顯示", use_container_width=True):
                for i, item in eligible:
                    code = item["code"]
                    key = prefix + f"display_{st.session_state.get('shipment_grid_epoch', 0)}_{i}_{code}"
                    st.selectbox(f"第 {i + 1} 項 · {item['name']}", display_code_options(code),
                                 index=widget_index(key, printed_code(item)), key=key,
                                 on_change=_set_code_display, args=(i, code, key))
    else:
        frame["貨品編號"] = [printed_code(item) for item in document["items"]]
        frame = frame.drop(columns="顯示編號")
        st.dataframe(frame, height=185, hide_index=True, use_container_width=True,
                     column_config={"採購單號": st.column_config.TextColumn("採購單號", width="medium"), "數量": st.column_config.NumberColumn(format="%.15g"), "單價": st.column_config.NumberColumn(format="%.15g")})
    details, summary = st.columns([3, 1])
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
                mode = st.selectbox("課稅類別", TAX_MODES, index=widget_index(prefix + "tax_mode", document["tax_mode"]), key=prefix + "tax_mode", disabled=not editing,
                                    on_change=_tax_changed, args=(prefix, "mode"))
                if editing:
                    document["tax_mode"] = mode
                invoice_choice("開立方式", "method", ("隨單開立", "月結開立"))
            with row[1]:
                date_field("發票日期", "date", target=invoice, optional=True)
                invoice_choice("發票聯式", "type", ("收銀機", "三聯式"))
            with row[2]:
                text("發票編號", "number", target=invoice)
                amount_key = prefix + "invoice_amount"
                manual_key = prefix + "invoice_amount_manual"
                if editing:
                    if manual_key not in st.session_state:
                        st.session_state[manual_key] = bool(invoice.get("amount"))
                    if not st.session_state[manual_key]:
                        try:
                            tax = calculate(document["items"], document["tax_mode"],
                                            st.session_state.get(prefix + "tax_rate", document["tax_rate"]))["tax_amount"]
                        except ShipmentError:
                            pass
                        else:
                            st.session_state[amount_key] = str(tax)
                amount = st.text_input("發票金額", value=widget_default(amount_key, invoice.get("amount", "")),
                                       key=amount_key, disabled=not editing,
                                       on_change=_invoice_amount_changed, args=(prefix,))
                if editing:
                    invoice["amount"] = amount
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
        st.markdown('<div class="shipment-section amounts">金額摘要</div>', unsafe_allow_html=True)
        if editing:
            rate = st.selectbox("稅率", (0, 5), index=widget_index(prefix + "tax_rate", 0 if document["tax_mode"] in ("免稅", "零稅率") or float(document["tax_rate"]) == 0 else 5),
                                format_func=lambda value: "0%（免稅）" if value == 0 else "5%",
                                key=prefix + "tax_rate", on_change=_tax_changed, args=(prefix, "rate"))
            document["tax_rate"] = str(rate)
        else:
            st.text_input("稅率", value=f"{float(document['tax_rate']):g}%", disabled=True)
        try:
            totals = calculate(document["items"], document["tax_mode"], document["tax_rate"]) if editing else document
            st.markdown('<div class="shipment-totals-card">' + ''.join(f'<div class="shipment-total"><span>{label}</span><span>{int(totals[key]):,}</span></div>'
                               for label, key in (("未稅合計", "net_amount"), ("稅額", "tax_amount"), ("總計 TWD", "total_amount"))) + '</div>', unsafe_allow_html=True)
        except ShipmentError as error:
            totals = None
            st.error(str(error))
    if editing and totals and document["items"]:
        lines = '　·　'.join(f'{escape(str(item.get("code", "")))}：{int(amount):,}' for item, amount in zip(document["items"], totals["line_amounts"]))
        st.markdown(f'<div class="shipment-lines">{lines}</div>', unsafe_allow_html=True)
    if editing:
        try:
            snapshot = _draft_print_document(document)
            draft_html = _cached_print(config, snapshot, show_prices=not hide_prices, orientation=orientation,
                                             feed_rotation=feed_rotation, hole_margin=hole_margin,
                                             paper_stock=paper_stock, output_mode=output_mode)
        except ShipmentError as error:
            if draft_preview is not None:
                draft_preview.info(str(error))
        else:
            with export_panel:
                st.download_button("下載列印版", draft_html, file_name=(snapshot["shipment_number"] or "未儲存出貨單") + ".html",
                                   mime="text/html", use_container_width=True)
            if draft_preview is not None:
                with draft_preview.container():
                    components.html(theme_preview(draft_html), height=550, scrolling=True)
    if save_clicked:
        try:
            if any(len(matching_products(all_choices, item.get("code"))) > 1 for item in document["items"]):
                raise ShipmentError("有多筆相符貨品，請先選擇並採用完整編號。")
            with shipment_timing("shipment_save", item_count=len(document["items"])):
                saved = save_shipment(config, document, sync_products=sync_products)
        except ShipmentError as error:
            st.error(str(error))
        except Exception:
            st.error("儲存失敗，請確認單號沒有重複及資料庫連線正常；修改內容已保留")
        else:
            st.session_state.shipment_selected = saved["id"]
            st.session_state.update(shipment_query="", shipment_start=None, shipment_end=None, shipment_include_void=False,
                                    shipment_customer_start="", shipment_customer_end="", shipment_search_epoch=0)
            customer = next((row for row in customers if row["customer_id"] == saved["customer_id"]), {})
            _finish("已儲存出貨單 " + saved["shipment_number"], invalidate_reports=True,
                    saved_view={"config": repr(config), "document": saved,
                                "customer_label": customer_display_name(customer) or saved["customer_name"]})
    if not editing:
        lifecycle = st.container()
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
                                _finish("出貨單已作廢，歷史資料保留", invalidate_reports=True)
