"""Compact Streamlit adapter for shipment documents."""

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape
import json
from time import monotonic

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit.runtime.scriptrunner import get_script_run_ctx

from .shipment_catalog import shipment_choices, complete_items, recent_item_defaults, editing_product_matcher
from .shipment_print import display_amount, display_price
from .paper_preview import theme_preview
from .shipment_page_data import (
    cached_read, clear_reads, discard_catalog, edit_read_is_fresh, preload_edit_reads, shipment_timing, timed_read,
)
from .shipment_history_ui import render_purchase_history
from .scheduled_quote_ui import render_shipment_quote_notices
from .shipment_search_print import render_search_print
from .shipment_codes import display_code_options, printed_code
from .accounting_widgets import widget_default, widget_index
from .accounting_navigation import is_accounting_action
from .customer_display import CustomerDisplay
from .list_ui import render_selection_table
from .customer_repository import (
    CONTACT_FIELDS, CustomerError, CustomerNotFound, customer_display_name, get_customer, list_customers,
)
from .shipment_repository import (
    TAX_MODES, ShipmentError, blank_shipment, calculate, copy_shipment, get_shipment,
    list_shipments, printable_shipment, save_shipment, void_shipment, update_shipment_item_notes, update_shipment_notes,
    is_blank_price, recent_shipment_price, shipment_price_history,
)

COLUMNS = {"code": "貨品編號", "name": "品名", "quantity": "數量", "unit": "單位",
           "price": "單價", "amount": "金額", "tax_exempt": "免稅", "order_number": "採購單號", "notes": "附註說明", "display_code": "顯示編號"}

# Scope overrides to this page, including the existing ERP's global CSS.
COMPACT_STYLE = """
<span id="shipment-page"></span><style>
:is(.stMain, section.main):has(#shipment-page) .block-container {padding-top:60px!important;padding-bottom:10px!important;}
:is(.stMain, section.main):has(#shipment-page) .stHeading [data-testid="stMarkdownContainer"] {margin-bottom:0!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stVerticalBlock"] {gap:6px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"] {gap:8px!important;}
:is(.stMain, section.main):has(#shipment-page) h3 {font-size:18px!important;margin:0!important;padding:0!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stWidgetLabel"] p {font-size:12px!important;margin-bottom:0!important;}
.shipment-read-field {display:grid;gap:3px;font-size:12px;min-width:0;}
.shipment-read-value {display:flex;align-items:center;min-height:32px;padding:4px 8px;
  border:1px solid #527086;border-radius:4px;font-size:13px;overflow-wrap:anywhere;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stTextInput"] input,
:is(.stMain, section.main):has(#shipment-page) [data-testid="stDateInput"] input,
:is(.stMain, section.main):has(#shipment-page) [data-testid="stNumberInput"] input {font-size:13px!important;min-height:28px!important;padding-top:2px!important;padding-bottom:2px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-baseweb="input"],
:is(.stMain, section.main):has(#shipment-page) [data-baseweb="select"]>div {min-height:30px!important;height:32px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stSelectbox"] [data-baseweb="select"]>div {font-size:13px!important;padding-top:0!important;padding-bottom:0!important;}
:is(.stMain, section.main):has(#shipment-page) button {min-height:29px!important;padding:2px 7px!important;border-radius:4px!important;}
:is(.stMain, section.main):has(#shipment-page) button p {font-size:12px!important;white-space:nowrap;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stTextArea"] textarea {min-height:64px!important;font-size:13px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stExpander"] details summary {padding:4px 8px!important;min-height:30px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stTabs"] [role="tablist"] {gap:12px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stTabs"] [role="tab"] {height:30px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stTabs"] [role="tabpanel"] {padding-top:5px!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stCaptionContainer"] p {margin:0!important;}
:is(.stMain, section.main):has(#shipment-page) .shipment-total {display:grid;grid-template-columns:minmax(0,1fr) max-content;align-items:baseline;gap:8px;padding:3px 0;font-size:13px;font-variant-numeric:tabular-nums;}
:is(.stMain, section.main):has(#shipment-page) .shipment-total>span:last-child {text-align:right;white-space:nowrap;}
:is(.stMain, section.main):has(#shipment-page) .shipment-total:last-child {border-top:1px solid #84919d;font-weight:600;font-size:16px;margin-top:4px;padding-top:6px;}
/* Streamlit 1.38's Markdown wrapper has a negative bottom margin. Custom
   HTML blocks must reserve their full height before the next control. */
:is(.stMain, section.main):has(#shipment-page) [data-testid="stMarkdownContainer"]:has(> :is(.shipment-section, .shipment-read-field, .shipment-edit-status, .shipment-totals-card, .shipment-lines, .shipment-number-help, #shipment-toolbar)) {display:flow-root;margin:0!important;}
:is(.stMain, section.main):has(#shipment-page) .shipment-section {font-size:13px;line-height:1.6;font-weight:700;letter-spacing:.04em;padding:5px 10px;margin:0;border-left:4px solid #59baff;border-radius:4px;background:#10293b;color:#c5e7ff;}
:is(.stMain, section.main):has(#shipment-page) .shipment-section.delivery {border-color:#57d6b1;background:#102e2a;color:#b3f2dd;}
:is(.stMain, section.main):has(#shipment-page) .shipment-section.items {border-color:#b8a1ff;background:#28213a;color:#e1d5ff;}
:is(.stMain, section.main):has(#shipment-page) .shipment-section.amounts {border-color:#ffd084;background:#382c18;color:#ffe1ad;}
:is(.stMain, section.main):has(#shipment-page) .shipment-edit-status {display:inline-block;border:1px solid #8e6832;border-radius:5px;padding:3px 9px;background:#352918;color:#ffda9a;font-size:12px;font-weight:600;}
:is(.stMain, section.main):has(#shipment-page) .shipment-totals-card {background:#142b29;border:1px solid #387d6d;border-radius:8px;padding:8px 12px;margin-top:8px;}
:is(.stMain, section.main):has(#shipment-page) .shipment-totals-card .shipment-total {color:#d7eee8!important;}
:is(.stMain, section.main):has(#shipment-page) .shipment-totals-card .shipment-total:last-child {color:#8ff0cb!important;border-color:#387d6d;font-size:20px;}
:is(.stMain, section.main):has(#shipment-page) button[kind="primary"] {background:#166b55!important;border-color:#49b99c!important;color:#fff!important;}
:is(.stMain, section.main):has(#shipment-page) .shipment-lines {font-size:12px;white-space:nowrap;overflow-x:auto;max-width:100%;}
:is(.stMain, section.main):has(#shipment-page) .shipment-number-help {font-size:10px;line-height:1.3;margin:0;overflow-wrap:anywhere;}
:is(.stMain, section.main):has(#shipment-page) label[data-baseweb="radio"]>div:first-child {background:transparent!important;border:1.5px solid #527086!important;box-sizing:border-box;}
:is(.stMain, section.main):has(#shipment-page) label[data-baseweb="radio"]:has(input:checked)>div:first-child {background:#3487b6!important;border-color:#3487b6!important;}
:is(.stMain, section.main):has(#shipment-page) label[data-baseweb="radio"]:has(input:checked)>div:first-child>div {background:#fff!important;}
:is(.stMain, section.main):has(#shipment-page) label[data-baseweb="radio"]:not(:has(input:checked))>div:first-child>div {background:transparent!important;}
:is(.stMain, section.main):has(#shipment-page) label[data-baseweb="radio"]:has(input:focus-visible)>div:first-child {outline:2px solid #8cc8ea;outline-offset:3px;}
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stRadio"] p,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stMetricLabel"],
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stMetricLabel"] p,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stMetricValue"] {color:#d5e1ec!important;}
body:has(#shipment-page) [data-testid="stPopoverBody"] {width:min(960px,calc(100vw - 40px))!important;max-width:calc(100vw - 40px)!important;}
body:has(#shipment-page) [data-testid="stPopoverBody"]:has(iframe) {max-height:calc(100vh - 32px)!important;overflow-y:auto;}
body:has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
body:has(#shipment-page) [data-testid="stPopoverBody"] .element-container {width:100%!important;max-width:100%!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] {background:#101820!important;color:#d5e1ec!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"]>div {background:#101820!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p,
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] p {color:#d5e1ec!important;}
body:has(.erp-title):has(#shipment-page) [data-testid="stPopoverBody"] button {background:#193042!important;color:#fff!important;border-color:#527086!important;}
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) .block-container {padding-top:72px!important;}
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) h3,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stWidgetLabel"] p,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stCaptionContainer"] p,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stExpander"] summary p,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) [data-testid="stCheckbox"] label span,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) .shipment-total,
.stApp:has(.erp-title) :is(.stMain, section.main):has(#shipment-page) #shipment-toolbar {color:#d5e1ec!important;}
#shipment-toolbar .shipment-action-wait {display:none;}
[data-shipment-action-pending] #shipment-toolbar .shipment-action-wait {display:inline;}
[data-shipment-action-pending] #shipment-toolbar .shipment-position {display:none;}
/* Keep item actions beside their heading, including when global mobile
   styles would otherwise stack every column at full width. */
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(.shipment-item-heading) {flex-wrap:nowrap!important;align-items:center;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(.shipment-item-heading)>:is([data-testid="column"],[data-testid="stColumn"]) {min-width:0!important;width:auto!important;}
@media(max-width:520px){
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(.shipment-item-heading) {flex-wrap:wrap!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(.shipment-item-heading)>:is([data-testid="column"],[data-testid="stColumn"]):first-child {flex-basis:100%!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(.shipment-item-heading)>:is([data-testid="column"],[data-testid="stColumn"]):not(:first-child) {flex:1 1 calc(50% - 4px)!important;}
}
@media(min-width:1000px){
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(#shipment-toolbar) {flex-wrap:nowrap!important;}
:is(.stMain, section.main):has(#shipment-page) [data-testid="stHorizontalBlock"]:has(#shipment-toolbar)>:is([data-testid="column"],[data-testid="stColumn"]) {min-width:0!important;}
}
</style>
"""

# Streamlit 1.45 reports a rerun through the app root, including fragment runs.
SHIPMENT_BROWSER_CONTROLS = """
<script>
(() => {
    const appWindow = window.parent;
    const page = appWindow.document;
    if (page.documentElement.dataset.shipmentControlsBound) return;
    page.documentElement.dataset.shipmentControlsBound = "true";
    const chromium = /(?:Chrome|Chromium|Edg)\\//.test(appWindow.navigator.userAgent);
    const scopePrefix = "st-key-shipment_save_scope_";
    const saveButton = ".st-key-shipment_save button";
    const savedClicks = new Set();
    const actionControls = [
        ".st-key-shipment_new", ".st-key-shipment_edit", ".st-key-shipment_copy",
        ".st-key-shipment_cancel", ".st-key-shipment_save", '[class*="st-key-shipment_nav_"]',
        ".st-key-shipment_print_preview", ".st-key-shipment_hide_prices",
        ".st-key-shipment_edit_items", ".st-key-shipment_add_recipe",
        '[class*="_show_product_search"]', '[class*="_show_customer_search"]',
        '[class*="_detail_section"]', '[class*="_edit_item_notes"]',
        ".st-key-shipment_confirm_blank_prices", ".st-key-shipment_cancel_blank_prices",
    ].join(",");
    let pendingAction = null;

    function getAction(target, includeLabel = false) {
        if (!page.getElementById("shipment-page")) return null;
        const element = target.closest?.(includeLabel ? "button,input,label" : "button,input");
        const control = element?.matches("label") ? element.querySelector("input") : element;
        return control && !control.disabled && control.closest(actionControls) ? control : null;
    }

    function release() {
        if (!pendingAction) return;
        const {app, watcher, timer} = pendingAction;
        watcher.disconnect();
        appWindow.clearTimeout(timer);
        delete app.dataset.shipmentActionPending;
        pendingAction = null;
    }

    function activeAction() {
        if (pendingAction && (!pendingAction.app.isConnected || !page.getElementById("shipment-page"))) release();
        return pendingAction;
    }

    function afterIdle() {
        const action = activeAction();
        if (!action || action.readyAfter === null) return;
        const remaining = action.readyAfter - appWindow.performance.now();
        if (remaining > 0) {
            appWindow.clearTimeout(action.timer);
            action.timer = appWindow.setTimeout(afterIdle, remaining);
            return;
        }
        const state = action.app.dataset.testScriptState;
        if (!["running", "rerunRequested", "stopRequested"].includes(state)) release();
    }

    function beginAction(control) {
        const app = control.closest('[data-testid="stApp"]');
        if (!app) return;
        const watcher = new appWindow.MutationObserver(afterIdle);
        pendingAction = {app, watcher, readyAfter: null, timer: null};
        app.dataset.shipmentActionPending = "true";
        watcher.observe(app, {attributes: true, attributeFilter: ["data-test-script-state"]});
    }

    function dispatched() {
        if (!pendingAction) return;
        // A short window also covers reruns that finish before React paints.
        pendingAction.readyAfter = appWindow.performance.now() + 450;
        afterIdle();
    }

    if (chromium) page.addEventListener("pointerdown", (event) => {
        if (event.isTrusted && activeAction() && getAction(event.target, true)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    page.addEventListener("click", (event) => {
        if (!event.isTrusted) return;
        const action = chromium && getAction(event.target);
        if (action) {
            if (activeAction()) {
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            beginAction(action);
        }
        const button = event.target.closest?.(saveButton);
        const scope = button?.closest('[class*="' + scopePrefix + '"]');
        const draft = scope && Array.from(scope.classList).find(name => name.startsWith(scopePrefix));
        const epoch = draft && draft.slice(scopePrefix.length);
        if (!draft || button.disabled || !page.querySelector('[class*="st-key-shipment_' + epoch + '_items"]')) {
            if (action) dispatched();
            return;
        }
        // The data editor debounces its final cell update before a save.
        event.preventDefault();
        event.stopImmediatePropagation();
        if (savedClicks.has(draft)) return;
        savedClicks.add(draft);
        appWindow.setTimeout(() => {
            savedClicks.delete(draft);
            const current = page.querySelector("." + draft + " " + saveButton);
            if (current && !current.disabled) {
                if (action) dispatched();
                current.click();
            } else if (action) {
                release();
            }
        }, 250);
    }, true);
})();
</script>
"""


def _readonly_field(label, value):
    st.markdown(
        f'<div class="shipment-read-field"><span>{escape(label)}</span>'
        f'<span class="shipment-read-value">{escape(str(value) if value not in (None, "") else "—")}</span></div>',
        unsafe_allow_html=True,
    )


def _rerun_shipment():
    context = get_script_run_ctx()
    if context is not None and context.fragment_ids_this_run:
        st.rerun(scope="fragment")
    else:
        st.rerun()


def _request_shipment_save():
    """Retain the click until a complete render can validate and save the draft."""
    st.session_state.shipment_pending_save = True


def _return_to_item_prices(confirmation_key, editor_key):
    st.session_state.pop(confirmation_key, None)
    st.session_state[editor_key] = True


def _missing_prices(document):
    return tuple((index, item["code"]) for index, item in enumerate(document["items"], 1)
                 if is_blank_price(item.get("price")))


def _edit_field_key(prefix, field):
    if field == "address":
        revision = st.session_state.get(prefix + "delivery_address_revision", 0)
        if revision:
            return f"{prefix}address_{revision}"
    return prefix + field


def _sync_edit_details(document, prefix):
    state = st.session_state
    for field in ("notes", "payment_terms", "paid_in_full", *CONTACT_FIELDS):
        key = _edit_field_key(prefix, field)
        if key not in state:
            continue
        value = state[key]
        if field in CONTACT_FIELDS and value != str(document.get(field) or ""):
            document.setdefault("_cleared_contacts", {})[field] = not value.strip()
        document[field] = value
    invoice = document["invoice"]
    for target, field, widget in ((document, "account_date", "account_date"),
                                  (invoice, "date", "invoice_date")):
        if prefix + widget in state:
            value = state[prefix + widget]
            target[field] = value.isoformat() if value else ""
    for field in ("number", "method", "type", "amount"):
        widget = prefix + "invoice_" + field
        if widget in state:
            invoice[field] = state[widget]
    if not document.get("id"):
        for field, default in (("method", "隨單開立"), ("type", "收銀機")):
            if prefix + "invoice_" + field not in state and not invoice.get(field):
                invoice[field] = default


def _prepare_invoice_amount(document, prefix):
    state = st.session_state
    invoice = document["invoice"]
    manual_key = prefix + "invoice_amount_manual"
    if manual_key not in state:
        state[manual_key] = bool(invoice.get("amount"))
    if not state[manual_key]:
        try:
            tax = calculate(document["items"], document["tax_mode"],
                            state.get(prefix + "tax_rate", document["tax_rate"]))["tax_amount"]
        except ShipmentError:
            return
        invoice["amount"] = state[prefix + "invoice_amount"] = str(tax)


def _commit_shipment_draft(config, document, customers, matcher, *, sync_products, rerun):
    if any(len(matcher.match(item.get("code"))) > 1 for item in document["items"]):
        raise ShipmentError("有多筆相符貨品，請先選擇並採用完整編號。")
    cleared = document.get("_cleared_contacts", {})
    missing_contacts = tuple(field for field in CONTACT_FIELDS
                             if not cleared.get(field) and not str(document.get(field) or "").strip())
    with shipment_timing("shipment_save", item_count=len(document["items"])):
        saved = save_shipment(config, document, sync_products=sync_products, fill_missing_contacts=missing_contacts)
    st.session_state.shipment_selected = saved["id"]
    st.session_state.shipment_preview_preference = False
    st.session_state.update(shipment_query="", shipment_start=None, shipment_end=None, shipment_include_void=False,
                            shipment_customer_start="", shipment_customer_end="", shipment_search_epoch=0)
    customer = next((row for row in customers if row["customer_id"] == saved["customer_id"]), {})
    _finish("已儲存出貨單 " + saved["shipment_number"], rerun=rerun, invalidate_reports=True,
            keep_catalog=not sync_products,
            saved_view={"config": repr(config), "document": saved,
                        "customer_label": customer_display_name(customer) or saved["customer_name"]})


def _save_before_render(config, draft, prefix):
    state = st.session_state
    checkpoint = state.get("shipment_save_checkpoint")
    if not checkpoint or checkpoint[0] != (repr(config), prefix, state.get("shipment_grid_epoch", 0)):
        return False
    values, customers, matcher = checkpoint[1:]
    # A fresh grid edit, date, customer or tax change must run through the
    # editor's normal matching, pricing and validation before writing.
    if any(state.get(key) != value for key, value in values.items()):
        return False
    adopting_item = any(key.startswith(prefix) and is_accounting_action(key) and state[key] for key in state)
    if (_missing_prices(draft) or state.get("shipment_add_recipe") or adopting_item
            or state.get("FormSubmitter:shipment_search-查詢")):
        return False
    document = deepcopy(draft)
    for field in ("shipment_number", "recipient_id", "recipient_name"):
        if prefix + field in state:
            document[field] = state[prefix + field]
    _sync_edit_details(document, prefix)
    if prefix + "number_mode" in state:
        document["number_mode"] = "date" if state[prefix + "number_mode"] == "依日期生成" else "manual"
    state.pop("shipment_pending_save", None)
    try:
        _commit_shipment_draft(config, document, customers, matcher,
                               sync_products=state.get(prefix + "sync_products", False), rerun=False)
    except ShipmentError as error:
        state.shipment_action_error = str(error)
    except Exception:
        state.shipment_action_error = "儲存失敗，請確認單號沒有重複及資料庫連線正常；修改內容已保留"
    return True


def _navigate_shipment(target_id, direction):
    if "shipment_draft" in st.session_state:
        return
    if target_id is None:
        st.session_state.shipment_saved_nav_direction = direction
    else:
        st.session_state.shipment_selected = target_id


def _cached_print(config, document, **options):
    signature = (repr(config), json.dumps(document, sort_keys=True, ensure_ascii=False, default=str),
                 tuple(sorted((key, option) for key, option in options.items() if key != "show_prices")))
    cached = st.session_state.get("shipment_print_cache")
    if cached is None or cached[0] != signature:
        cached = (signature, {})
        st.session_state.shipment_print_cache = cached
    show_prices = options["show_prices"]
    if show_prices not in cached[1]:
        cached[1][show_prices] = printable_shipment(document, **options)
    return cached[1][show_prices]


def _begin(document, *, rerun=True):
    for key in ("shipment_pending_save", "shipment_pending_export", "shipment_draft_export", "shipment_action_error",
                "shipment_blank_price_confirmation", "shipment_blank_price_toast"):
        st.session_state.pop(key, None)
    saved_view = st.session_state.pop("shipment_saved_view", None)
    reopening_saved = bool(saved_view and saved_view["document"].get("id") == document.get("id"))
    st.session_state.shipment_cancel_view = saved_view if reopening_saved else None
    if not reopening_saved:
        discard_catalog(st.session_state)
    st.session_state.pop("shipment_saved_nav_direction", None)
    st.session_state.pop("shipment_read_cache", None)
    st.session_state.shipment_draft = deepcopy(document)
    if document.get("id") in st.session_state.get("shipment_note_drafts", {}):
        st.session_state.shipment_draft["notes"] = st.session_state.shipment_note_drafts[document["id"]]
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
    for key in ("shipment_draft", "shipment_original", "shipment_editor_base", "shipment_save_checkpoint"):
        st.session_state.pop(key, None)


def _resume_search_draft():
    drafts = st.session_state.get("shipment_suspended_drafts", [])
    if drafts:
        _begin(drafts.pop(), rerun=False)


def _new_shipment():
    return dict(blank_shipment(), number_mode="manual")


def _cancel(config):
    """Discard edits while retaining the original browsing snapshot."""
    saved_view = st.session_state.get("shipment_cancel_view")
    cache = st.session_state.get("shipment_page_cache", {})
    now = monotonic()
    for identity, entry in list(cache.items()):
        database, key = identity
        if database == repr(config) and isinstance(key, tuple) and key[0] in (
                "records", "number-navigation", "document", "customer-label"):
            cache[identity] = (now, entry[1])
    _finish("已取消修改", rerun=False, saved_view=saved_view, clear_cache=False)


def _finish(message="", *, rerun=True, invalidate_reports=False, saved_view=None, clear_cache=True,
            keep_catalog=False):
    for key in ("shipment_pending_save", "shipment_pending_export", "shipment_draft_export", "shipment_action_error",
                "shipment_blank_price_confirmation", "shipment_blank_price_toast"):
        st.session_state.pop(key, None)
    st.session_state.pop("shipment_cancel_view", None)
    if clear_cache:
        clear_reads(st.session_state, keep_catalog=keep_catalog)
    else:
        st.session_state.pop("shipment_read_cache", None)
    if invalidate_reports:
        st.session_state.pop("receivable_pages", None)
        st.session_state.pop("ranking_statements", None)
    st.session_state.pop("shipment_purchase_history_result", None)
    st.session_state.pop("shipment_search_print_snapshot", None)
    st.session_state.pop("shipment_draft", None)
    st.session_state.pop("shipment_original", None)
    st.session_state.pop("shipment_editor_base", None)
    st.session_state.pop("shipment_save_checkpoint", None)
    st.session_state.pop("shipment_saved_nav_direction", None)
    if saved_view is not None and message.startswith("已儲存出貨單"):
        st.session_state.get("shipment_note_drafts", {}).pop(saved_view["document"]["id"], None)
    if saved_view is None:
        st.session_state.pop("shipment_saved_view", None)
    else:
        st.session_state.shipment_saved_view = deepcopy(saved_view)
    st.session_state.shipment_notice = message
    if rerun:
        _rerun_shipment()




def _note_write_version(config, document):
    # A queued blur event can still carry the snapshot from before our last save.
    versions = st.session_state.get("shipment_note_versions", {})
    version = document["version"]
    while (repr(config), document["id"], version) in versions:
        version = versions[(repr(config), document["id"], version)]
    return version


def _remember_note_write(config, document, version, saved_version):
    if saved_version == version:
        return
    versions = st.session_state.setdefault("shipment_note_versions", {})
    versions[(repr(config), document["id"], version)] = saved_version
    while len(versions) > 64:
        versions.pop(next(iter(versions)))


def _save_notes(config, document, key):
    pending_notes = st.session_state.setdefault("shipment_note_drafts", {})
    pending_notes[document["id"]] = st.session_state[key]
    draft = st.session_state.get("shipment_draft")
    if draft is not None and draft.get("id") == document["id"]:
        # A click on Modify can arrive with the textarea blur in one event.
        # Keep that edit and its new note together for the normal Save action.
        draft["notes"] = st.session_state[key]
        return
    try:
        version = _note_write_version(config, document)
        saved_version = update_shipment_notes(config, document["id"], version, st.session_state[key])
    except ShipmentError as error:
        st.session_state.shipment_notes_error = (document["id"], "備註未儲存：" + str(error))
    except Exception:
        st.session_state.shipment_notes_error = (
            document["id"], "備註未儲存：請確認資料庫連線後重試；輸入內容已保留。")
    else:
        _remember_note_write(config, document, version, saved_version)
        st.session_state.pop("shipment_notes_error", None)
        pending_notes.pop(document["id"], None)
        if draft is None:
            _finish("備註已儲存", rerun=False)
        else:
            # Saving the previous note must not cancel a simultaneous New/Copy.
            clear_reads(st.session_state)
            st.session_state.pop("shipment_saved_view", None)
            st.session_state.shipment_notice = "備註已儲存"


def _save_item_notes(config, document, key):
    changes = st.session_state.get(key, {}).get("edited_rows", {})
    notes = {int(index): row["附註說明"] or "" for index, row in changes.items() if "附註說明" in row}
    if not notes:
        return
    try:
        version = _note_write_version(config, document)
        saved_version = update_shipment_item_notes(config, document["id"], version, notes)
    except ShipmentError as error:
        st.session_state.shipment_item_notes_error = (
            document["id"], "附註未儲存：" + str(error))
    except Exception:
        st.session_state.shipment_item_notes_error = (
            document["id"], "附註未儲存：請確認資料庫連線後重試；輸入內容已保留。")
    else:
        _remember_note_write(config, document, version, saved_version)
        st.session_state.pop("shipment_item_notes_error", None)
        _finish("附註說明已儲存", rerun=False)


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


def _show_print_preview():
    return st.toggle(
        "預覽／列印", key="shipment_print_preview",
        value=widget_default("shipment_print_preview", st.session_state.get("shipment_preview_preference", False)),
        on_change=_remember_print_settings, args=("shipment_print_preview",),
    )


@st.fragment
def _render_shipment_output(config, document, *, workspace_id, preview, prepare_export, options, preview_slot):
    # Draft preview can open without rebuilding the editor. In saved view the
    # outer toggle still switches between the paper and the document details.
    editing = preview is None
    context = get_script_run_ctx()
    if context.fragment_ids_this_run and workspace_id not in context.fragment_ids_this_run:
        prepare_export = False
    if editing:
        preview_control, price_control = st.columns(2)
        with preview_control:
            preview = _show_print_preview()
    else:
        price_control = st.container()
    with price_control:
        hide_prices = st.toggle(
            "隱藏單價與金額", key="shipment_hide_prices",
            value=widget_default("shipment_hide_prices", st.session_state.get("shipment_hide_preference", False)),
            on_change=_remember_print_settings, args=("shipment_hide_prices",),
        )
    options = dict(options, show_prices=not hide_prices)
    if not preview:
        preview_slot.empty()

    if editing:
        prepared = st.session_state.get("shipment_draft_export")
        if prepared or prepare_export:
            signature = (repr(config), json.dumps(document, sort_keys=True, ensure_ascii=False, default=str),
                         tuple(options.items()))
            if prepared and prepared["signature"] != signature:
                st.session_state.pop("shipment_draft_export", None)
                prepared = None
        if preview or prepare_export:
            try:
                snapshot = _draft_print_document(document)
                print_html = _cached_print(config, snapshot, **options)
            except ShipmentError as error:
                if preview:
                    preview_slot.info(str(error))
            else:
                if prepare_export:
                    prepared = {"signature": signature, "html": print_html,
                                "filename": (snapshot["shipment_number"] or "未儲存出貨單") + ".html"}
                    st.session_state.shipment_draft_export = prepared
                if preview:
                    with preview_slot:
                        components.html(theme_preview(print_html), height=550, scrolling=True)
        if prepared:
            st.download_button("下載列印版", prepared["html"], file_name=prepared["filename"],
                               mime="text/html", on_click="ignore", use_container_width=True)
        return context.current_fragment_id

    export_key = (repr(config), document["id"], document["version"], tuple(options.items()))
    if prepare_export:
        st.session_state.shipment_prepared_saved_export = export_key
    elif st.session_state.get("shipment_prepared_saved_export") != export_key:
        st.session_state.pop("shipment_prepared_saved_export", None)
    if preview or st.session_state.get("shipment_prepared_saved_export") == export_key:
        print_html = _cached_print(config, document, **options)
        st.download_button("下載列印版", data=print_html, file_name=document["shipment_number"] + ".html",
                           mime="text/html", on_click="ignore", use_container_width=True)
        if preview:
            with preview_slot:
                components.html(theme_preview(print_html), height=550, scrolling=True)
    return context.current_fragment_id


def _place_shipment_output(config, document, **kwargs):
    context = get_script_run_ctx()
    parent_id = context.current_fragment_id
    output_id = _render_shipment_output(config, document, workspace_id=parent_id, **kwargs)
    render_only_output = context.fragment_storage.get(output_id)

    def render_unless_workspace_is_queued():
        # Streamlit 1.45 may batch events from both fragments. The workspace
        # already renders this output with the current document and widget
        # state, so skip the duplicate before it registers the same widgets.
        running = get_script_run_ctx()
        if parent_id not in running.fragment_ids_this_run:
            render_only_output()

    context.fragment_storage.set(output_id, render_unless_workspace_is_queued)


def _editor_rebase_needed(raw_items, completed_items):
    """Rebuild the grid only when automatic completion changes visible values."""
    if len(raw_items) != len(completed_items):
        return True
    for raw, completed in zip(raw_items, completed_items):
        for field in COLUMNS:
            if field in ("amount", "display_code"):
                continue
            before, after = raw.get(field, ""), completed.get(field, "")
            if before == after:
                continue
            if field in ("quantity", "price"):
                try:
                    if Decimal(str(before)) == Decimal(str(after)):
                        continue
                except InvalidOperation:
                    pass
            return True
    return False


@st.fragment
@shipment_timing("shipment_render")
def render_shipment_management(config, *, start_new_on_entry=False):
    draft = st.session_state.get("shipment_draft")
    save_attempted = bool(draft is not None and st.session_state.get("shipment_pending_save") and
                          _save_before_render(config, draft, f"shipment_{st.session_state.get('shipment_epoch', 0)}_"))
    for key, preference in (("shipment_print_preview", "shipment_preview_preference"), ("shipment_hide_prices", "shipment_hide_preference")):
        if preference in st.session_state:
            st.session_state[key] = st.session_state[preference]
    if start_new_on_entry and not st.session_state.get("shipment_entry_ready"):
        st.session_state.shipment_entry_ready = True
        if "shipment_draft" not in st.session_state:
            _begin(_new_shipment(), rerun=False)
    st.html(COMPACT_STYLE)
    notice = st.session_state.pop("shipment_notice", "")
    if notice:
        st.toast(notice, icon="✅" if "已儲存" in notice or "已取消" in notice else "ℹ️")
    # Fill this slot after validation so feedback stays above the toolbar.
    action_feedback = st.empty()
    price_confirmation = st.empty()
    action_error = st.session_state.pop("shipment_action_error", "")
    if action_error:
        action_feedback.error(action_error)
    draft = st.session_state.get("shipment_draft")
    editing = draft is not None
    if editing:
        draft_prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_"
        # Early search reruns must not clean up editor widgets not rendered yet.
        for key in list(st.session_state):
            if key.startswith(draft_prefix) and not key.startswith(draft_prefix + "items") and not is_accounting_action(key):
                st.session_state[key] = st.session_state[key]
    def read(key, loader):
        if not editing:
            return cached_read(config, st.session_state, key, loader)
        cache = st.session_state.setdefault("shipment_read_cache", {})
        cache_key = (repr(config), key)
        if cache_key not in cache:
            # New editing snapshots must see current customer details and prices.
            cache[cache_key] = (timed_read(key, loader) if edit_read_is_fresh(key)
                                else cached_read(config, st.session_state, key, loader, ttl=60))
        return cache[cache_key]

    with st.expander("查詢", expanded=False):
        if st.button("重讀資料", key="shipment_reload_data"):
            clear_reads(st.session_state)
            st.session_state.pop("shipment_cancel_view", None)
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
    search_active = bool(st.session_state.get("shipment_search_epoch"))
    record_filters = tuple(st.session_state.get(key) for key in (
        "shipment_query", "shipment_start", "shipment_end",
        "shipment_include_void", "shipment_customer_start", "shipment_customer_end",
    ))
    record_key = ("records", *record_filters, search_active)
    saved_view = st.session_state.get("shipment_saved_view", {})
    saved_document = saved_view.get("document") if saved_view.get("config") == repr(config) else None
    saved_direction = st.session_state.get("shipment_saved_nav_direction", 0)
    showing_saved = bool(not editing and saved_document and not saved_direction
                         and not st.session_state.get("shipment_search_epoch")
                         and st.session_state.get("shipment_selected") == saved_document["id"])
    # The committed document is already available. Load the full list only on
    # an explicit search, refresh, or previous/next action.
    if editing:
        # Query results cannot be opened while editing. Avoid re-reading and
        # rebuilding the list on every field change, even after its TTL expires.
        records = []
    elif showing_saved:
        records = [saved_document]
    else:
        records = cached_read(config, st.session_state, record_key, lambda: list_shipments(
            config, query=st.session_state.get("shipment_query", ""),
            start=st.session_state.get("shipment_start"), end=st.session_state.get("shipment_end"),
            include_void=st.session_state.get("shipment_include_void", False),
            customer_start=st.session_state.get("shipment_customer_start", ""),
            customer_end=st.session_state.get("shipment_customer_end", ""), summary=True, newest_first=search_active))
    if search_active:
        with st.expander("查詢結果（編輯中暫停更新）" if editing else f"查詢結果 · {len(records)} 筆", expanded=True):
            if editing:
                st.caption("草稿已保留；儲存或取消後可開啟查詢結果。")
            elif records:
                display = CustomerDisplay(config)
                result = pd.DataFrame([{"出貨日期": r["shipment_date"], "出貨單號": r["shipment_number"],
                          "客戶編號": r["customer_id"], "客戶名稱": display.name(r["customer_name"], r["customer_id"]), "總計（未稅）": int(r["net_amount"]),
                          "狀態": "作廢" if r["status"] == "void" else "有效",
                          "收款註記": "已付清" if r.get("paid_in_full") else ""} for r in records])
                if len(records) == 1:
                    st.table(result)
                    chosen = records[0]
                else:
                    chosen = render_selection_table(result, records, key="shipment_results_" + str(st.session_state["shipment_search_epoch"]),
                                                    id_field="id", height=min(400, 38 * (len(records) + 1)))
                if chosen is not None:
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
        navigation_key = ("number-navigation", *record_filters[1:])
        navigation_records = cached_read(config, st.session_state, navigation_key, lambda: sorted(
            list_shipments(config, start=st.session_state.get("shipment_start"), end=st.session_state.get("shipment_end"),
                           include_void=st.session_state.get("shipment_include_void", False),
                           customer_start=st.session_state.get("shipment_customer_start", ""),
                           customer_end=st.session_state.get("shipment_customer_end", ""), summary=True),
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
        note_error = st.session_state.get("shipment_notes_error")
        if note_error and note_error[0] == document["id"]:
            action_feedback.error(note_error[1])
    tools = st.columns([1, 1, 1, 1, 1.1, 1, 1, .6, 1.6])
    with tools[0]:
        st.button("新增", key="shipment_new", disabled=editing, use_container_width=True,
                  on_click=_begin, args=(_new_shipment(),), kwargs={"rerun": False})
    tools[1].button("修改", key="shipment_edit", disabled=editing or not document or document.get("status") == "void", use_container_width=True,
                    on_click=_begin, args=(document,), kwargs={"rerun": False})
    tools[2].button("複製", key="shipment_copy", disabled=editing or not document, use_container_width=True,
                    on_click=_copy_for_edit, args=(document,))
    tools[3].button("取消", key="shipment_cancel", disabled=not editing, use_container_width=True,
                    on_click=_cancel, args=(config,))
    with tools[4], st.container(key=f"shipment_save_scope_{st.session_state.get('shipment_epoch', 0)}"):
        save_pressed = st.button("儲存", key="shipment_save", type="primary", disabled=not editing,
                                 on_click=_request_shipment_save, use_container_width=True)
    # Honor the button event itself as well as a request retained across reruns.
    # A missing callback flag must never silently discard an explicit save click.
    save_clicked = editing and not save_attempted and (save_pressed or st.session_state.get("shipment_pending_save", False))
    if save_clicked:
        st.session_state.shipment_pending_save = True
    for col, label, direction in ((tools[5], "上一筆", -1), (tools[6], "下一筆", 1)):
        target = index + direction
        target_id = ids[target] if not showing_saved and 0 <= target < len(ids) else None
        col.button(label, key="shipment_nav_" + label, disabled=editing or (not showing_saved and target_id is None),
                   use_container_width=True, on_click=_navigate_shipment, args=(target_id, direction))
    position = "已儲存" if showing_saved else f"{index + 1 if ids else 0} / {len(ids)}"
    tools[7].markdown(f'<span id="shipment-toolbar" role="status" style="font-size:12px">'
                      f'<span class="shipment-position">{position}</span>'
                      '<span class="shipment-action-wait">處理中</span></span>', unsafe_allow_html=True)
    with tools[8].popover("列印／匯出", use_container_width=True), st.container():
        output = st.selectbox("列印用途", ("實體列印", "另存 PDF（置中）"), key="shipment_output_mode")
        output_mode = "pdf" if output.startswith("另存 PDF") else "print"
        stock = st.selectbox("紙張尺寸", ("A4", "三聯紙 240 × 140 mm", "A5"), key="shipment_paper_stock")
        paper_stock = "a4_driver" if stock == "A4" else "triplicate" if stock.startswith("三聯紙") else "standard"
        layout = st.selectbox("列印方向", ("橫式", "直式"), key="shipment_print_orientation",
                              format_func=lambda value: "列印：" + ("橫放進紙" if paper_stock == "a4_driver" and value == "橫式" else value), label_visibility="collapsed", disabled=paper_stock != "standard")
        feed_rotation = st.selectbox("紙張進紙", (0, 90), format_func=lambda v: ("240 mm 長邊先進（橫放）" if v == 0 else "140 mm 短邊先進（直放）") if paper_stock != "standard" else ("原方向" if v == 0 else "旋轉90度進紙"), key="shipment_feed_rotation", disabled=paper_stock == "a4_driver")
        hole_margin = st.number_input("左右打洞留白（mm）", min_value=0.0, max_value=25.0, value=12.5, step=0.5, key="shipment_hole_margin")
        prepare_saved_export = bool(document and not editing and st.button(
            "產生列印檔", key="shipment_prepare_saved_export", use_container_width=True,
        ))
        prepare_draft_export = st.button("產生列印檔", key="shipment_prepare_draft_export", use_container_width=True,
                                         disabled=not document.get("items")) if editing else False
        pending_export = st.session_state.pop("shipment_pending_export", False)
        prepare_draft_export = prepare_draft_export or pending_export
    orientation = "portrait" if layout == "直式" else "landscape"
    print_options = dict(orientation=orientation, feed_rotation=feed_rotation, hole_margin=hole_margin,
                         paper_stock=paper_stock, output_mode=output_mode)
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
            return customer_display_name(customer) if customer else document["customer_name"]
        return read(("customer-label", document["customer_id"], document["customer_name"]),
                    lambda: display.name(document["customer_name"], document["customer_id"]))
    if document.get("status") == "void":
        st.warning("已作廢：" + document.get("void_reason", ""))
    prefix = f"shipment_{st.session_state.get('shipment_epoch', 0)}_" if editing else f"shipment_view_{document['id']}_{document['version']}_"
    print_controls = st.columns([2, 2, 1])
    sync_products = print_controls[1].toggle("同步建立缺少貨品", key=prefix + "sync_products", disabled=not editing,
                                            help="成交價依客戶、貨品與單位保存於出貨紀錄，不覆蓋共用標準售價")
    preview_slot = st.empty()
    if not editing:
        with print_controls[0]:
            preview_control, price_control = st.columns(2)
        with preview_control:
            preview = _show_print_preview()
        with price_control:
            _place_shipment_output(config, document, preview=preview, prepare_export=prepare_saved_export,
                                   options=print_options, preview_slot=preview_slot)
        if preview:
            with print_controls[2]:
                render_purchase_history(config, document["customer_id"], current_customer_label())
            return

    if editing:
        document["tax_mode"] = st.session_state.get(prefix + "tax_mode", document["tax_mode"])
        document["tax_rate"] = str(st.session_state.get(prefix + "tax_rate", document["tax_rate"]))

    def text(label, key, *, target=None):
        data = document if target is None else target
        previous = str(data.get(key) or "")
        if not editing:
            _readonly_field(label, previous)
            return
        widget_key = prefix + "invoice_" + key if target is not None else _edit_field_key(prefix, key)
        value = st.text_input(label, value=widget_default(widget_key, previous), key=widget_key)
        if target is None and key in CONTACT_FIELDS and value != previous:
            document.setdefault("_cleared_contacts", {})[key] = not value.strip()
        data[key] = value

    def date_field(label, key, *, target=None, optional=False):
        data = document if target is None else target
        value = date.fromisoformat(data[key]) if data.get(key) else None if optional else date.today()
        if not editing:
            _readonly_field(label, value.strftime("%Y/%m/%d") if value else "")
            return
        widget_key = prefix + ("invoice_" if target is not None else "") + key
        value = st.date_input(label, value=widget_default(widget_key, value), key=widget_key)
        data[key] = value.isoformat() if value else ""
        if value is None and not optional:
            st.error(f"請輸入{label}")

    def invoice_choice(label, field, options):
        invoice = document["invoice"]
        if not editing:
            _readonly_field(label, invoice.get(field))
            return
        current = invoice.get(field) or (options[0] if not document.get("id") else "")
        choices = [""] + list(options)
        if current and current not in choices:
            choices.append(current)
        widget_key = prefix + "invoice_" + field
        invoice[field] = st.selectbox(label, choices, index=widget_index(widget_key, current),
                                     format_func=lambda value: value or "請選擇", key=widget_key)

    section = '<div class="shipment-section">出貨與客戶</div>'
    search_customers = False
    if editing:
        title_col, search_col = st.columns([4, 1], vertical_alignment="center")
        title_col.markdown(section, unsafe_allow_html=True)
        search_key = prefix + "show_customer_search"
        search_customers = search_col.toggle(
            "搜尋／更換客戶", value=widget_default(search_key, not document["customer_id"]), key=search_key,
        )
    else:
        st.markdown(section, unsafe_allow_html=True)

    customers = []
    if editing:
        customer_id = document["customer_id"]
        loaders = {}
        if search_customers:
            customer_key = "customers"
            loaders[customer_key] = lambda: list_customers(config, include_inactive=True)
        elif customer_id:
            customer_key = ("selected-customer", customer_id)

            def selected_customer_record():
                try:
                    return [get_customer(config, customer_id)]
                except CustomerNotFound:
                    return []

            loaders[customer_key] = selected_customer_record
        if customer_id:
            history_key = ("history", customer_id, document["shipment_date"], document.get("id", ""))
            loaders[history_key] = lambda: shipment_price_history(
                config, customer_id, document["shipment_date"], document.get("id", ""))
            loaders["all_choices"] = lambda: shipment_choices(config, customer_id, all_recipes=True)
        preload_edit_reads(config, st.session_state, loaders)
        if search_customers or customer_id:
            customers = read(customer_key, loaders[customer_key])
        if st.session_state.pop("shipment_contacts_pending", False):
            customer = next((row for row in customers if row["customer_id"] == customer_id), {})
            same_recipient = document.get("recipient_id") in (None, "", customer_id)
            for field in CONTACT_FIELDS:
                if (not str(document.get(field) or "").strip()
                        and not document.get("_cleared_contacts", {}).get(field)
                        and (field != "address" or same_recipient)):
                    document[field] = customer.get(field) or ""

    header = st.columns([1.1, 1.2, 1.35, 1.55, 2.15] if search_customers else [1.25, 1.35, 1.55, 2.8])
    with header[0]:
        date_field("出貨日期", "shipment_date")
    with header[1]:
        current_mode = "依日期生成" if document.get("number_mode") == "date" else "自行輸入"
        if editing:
            mode = st.selectbox("單號方式", ("依日期生成", "自行輸入"),
                                index=widget_index(prefix + "number_mode", current_mode), key=prefix + "number_mode")
            document["number_mode"] = "date" if mode == "依日期生成" else "manual"
        else:
            _readonly_field("單號方式", current_mode)
    with header[2]:
        text("出貨單號", "shipment_number")
        if editing and document["number_mode"] == "date":
            st.markdown('<p class="shipment-number-help">留白自動編號；填入用指定單號。</p>', unsafe_allow_html=True)
    if search_customers:
        query = header[3].text_input(
            "客戶編號／全名／簡稱", key=prefix + "customer_search_query",
            help="搜尋結果最多顯示 50 筆，請輸入關鍵字縮小範圍。",
        ).strip().casefold()
        available = {}
        for row in customers:
            if row["lifecycle_status"] != "active":
                continue
            if query and not any(query in str(row.get(key) or "").casefold()
                                 for key in ("customer_id", "name", "short_name")):
                continue
            if len(available) == 50:
                break
            available[row["customer_id"]] = customer_display_name(row)
        original = st.session_state.get("shipment_original", document)
        if original.get("customer_id"):
            available.setdefault(original["customer_id"], original["customer_name"])
        if document["customer_id"]:
            available.setdefault(document["customer_id"], current_customer_label())
        options = [""] + list(available)
        # Keep widget identity stable while the selected customer changes.
        selected_customer = header[4].selectbox(
            "客戶", options, index=widget_index(prefix + "customer_picker", document["customer_id"]),
            format_func=lambda value: f"{value} · {available[value]}" if value else "請選擇客戶",
            key=prefix + "customer_picker",
        )
        if selected_customer != document["customer_id"]:
            try:
                customer = get_customer(config, selected_customer) if selected_customer else {}
            except CustomerNotFound as error:
                st.error(str(error))
                st.stop()
            except CustomerError as error:
                # A temporarily unavailable detail lookup can still use
                # the customer snapshot loaded for this draft.
                customer = next((row for row in customers if row["customer_id"] == selected_customer), None)
                if customer is None:
                    st.error(str(error))
                    st.stop()
            name = customer.get("name", "")
            document.pop("_cleared_contacts", None)
            document.update(customer_id=selected_customer, customer_name=name,
                            recipient_id=selected_customer, recipient_name=name)
            for field in CONTACT_FIELDS:
                document[field] = customer.get(field) or ""
            # A rerun already sent by the browser can still contain the old
            # address. Give the new delivery address its own widget identity.
            state = st.session_state
            state.pop(_edit_field_key(prefix, "address"), None)
            revision_key = prefix + "delivery_address_revision"
            state[revision_key] = state.get(revision_key, 0) + 1
            # Update delivery widgets before they are rendered in this run.
            for field in ("recipient_id", "recipient_name", *CONTACT_FIELDS):
                state[_edit_field_key(prefix, field)] = document[field]
    else:
        with header[3]:
            _readonly_field("客戶", f"{document['customer_id']} · {current_customer_label()}"
                            if document["customer_id"] else "請選擇客戶")
    st.markdown('<div class="shipment-section delivery">送貨資訊</div>', unsafe_allow_html=True)
    receiver = st.columns([1.2, 1.8, 4])
    for col, label, field in zip(receiver, ("指送對象編號", "指送對象名稱", "送貨地址"), ("recipient_id", "recipient_name", "address")):
        with col:
            text(label, field)
    with print_controls[2]:
        render_purchase_history(config, document["customer_id"], current_customer_label())
    if editing:
        item_header = st.columns([3, 1.2, 1.2], vertical_alignment="center")
        with item_header[0]:
            st.markdown('<div class="shipment-section items shipment-item-heading">貨品明細</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="shipment-section items">貨品明細</div>', unsafe_allow_html=True)
    product_search_panel = st.container()
    requested_item = None
    editor_rebased = False
    editing_items = False
    if editing:
        item_tools = item_header[1:]
        history_key = ("history", document["customer_id"], document["shipment_date"], document.get("id", ""))
        history = read(history_key, lambda: shipment_price_history(config, document["customer_id"],
                       document["shipment_date"], document.get("id", ""))) if document["customer_id"] else []
        all_choices = read("all_choices",
                           lambda: shipment_choices(config, document["customer_id"], all_recipes=True)) if document["customer_id"] else {}
        matcher = editing_product_matcher(st.session_state, all_choices)
        search_open = item_tools[0].toggle("搜尋貨品", key=prefix + "show_product_search")
        item_editor_key = prefix + "item_editor_open"
        if search_open:
            st.session_state[item_editor_key] = True
        editing_items = not document.get("id") or st.session_state.get(item_editor_key, False)
        if not editing_items:
            item_tools[1].button("修改品項", key="shipment_edit_items", use_container_width=True,
                                 on_click=st.session_state.update, kwargs={item_editor_key: True})
        if search_open:
            with product_search_panel:
                query = st.text_input("貨品編號／品名", key=prefix + "product_search_query").strip().casefold()
                choices = {}
                for code, item in all_choices.items():
                    if item.get("_recipe_customer", "") not in ("", document["customer_id"]):
                        continue
                    if query and query not in code.casefold() and query not in item["name"].casefold():
                        continue
                    if len(choices) == 50:
                        st.caption("只顯示前 50 筆，輸入貨品編號或品名縮小範圍。")
                        break
                    choices[code] = item
                picker, unit_col, quantity_col, add_col = st.columns([3, 1, 1, 1])
                picker_key = prefix + "recipe_picker_" + document["customer_id"]
                if st.session_state.get(picker_key) and st.session_state[picker_key] not in choices:
                    st.session_state[picker_key] = ""
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
                        st.caption("無相符單位或課稅方式的單價，可清空後補")
                if add_col.button("加入", key="shipment_add_recipe", disabled=not code or not unit, use_container_width=True):
                    requested_item = dict(code=code, name=defaults.get("name") or chosen["name"], quantity=str(quantity), unit=unit,
                                          price=price, tax_exempt=bool(defaults.get("tax_exempt", False)), order_number="", notes="")
    source_items = (st.session_state.get("shipment_editor_base", document["items"])
                    if editing_items else document["items"])
    frame = pd.DataFrame(source_items, columns=list(COLUMNS)).rename(columns=COLUMNS)
    # Pandas 3 infers Arrow large_string; older Streamlit editors make it read-only.
    for column in ("貨品編號", "品名", "單位", "採購單號", "附註說明", "顯示編號"):
        frame[column] = frame[column].fillna("").astype(object)
    frame["免稅"] = frame["免稅"].fillna(False).astype(bool)
    for column in ("數量", "單價"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if editing_items:
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
        document["items"] = complete_items(config, document, raw_items, document["items"], choices=all_choices, history=history, matcher=matcher)
        if _editor_rebase_needed(raw_items, document["items"]):
            editor_rebased = True
            if save_clicked:
                st.session_state.shipment_pending_save = True
            if prepare_draft_export:
                st.session_state.shipment_pending_export = True
            st.session_state.shipment_editor_base = deepcopy(document["items"])
            st.session_state.shipment_grid_epoch = st.session_state.get("shipment_grid_epoch", 0) + 1
            # Saving/exporting can use the completed values in this run. Do not
            # interrupt before later header, invoice and note widgets are read.
            if not save_clicked and not prepare_draft_export:
                _rerun_shipment()
        for row_index, item in enumerate(document["items"]):
            candidates = matcher.match(item.get("code")) if item.get("code") else matcher.match(item.get("name"), by_name=True, history=history)
            if len(candidates) > 1:
                left, right = st.columns([4, 1], vertical_alignment="bottom")
                choice = left.selectbox(f"第 {row_index + 1} 項相符貨品", candidates, format_func=lambda c: f"{c} · {all_choices[c]['name']}", key=prefix + f"match_{row_index}")
                if right.button("採用", key=prefix + f"apply_{row_index}"):
                    before = deepcopy(document["items"])
                    document["items"][row_index]["code"] = choice
                    document["items"] = complete_items(config, document, document["items"], before, choices=all_choices, history=history, matcher=matcher)
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
        edit_item_notes = not editing and document["status"] != "void" and st.toggle(
            "編輯品項附註", key=f"shipment_view_{document['id']}_edit_item_notes",
        )
        if not edit_item_notes:
            # Viewing an order and editing only its header use the same static table.
            for column in ("數量", "單價"):
                frame[column] = frame[column].map(display_price, na_action="ignore").fillna("")
            frame["金額"] = frame["金額"].map(display_amount)
            frame["免稅"] = frame["免稅"].map({True: "是", False: ""})
            with st.container(height=185, border=False):
                st.table(frame)
        else:
            note_error = st.session_state.get("shipment_item_notes_error")
            if note_error and note_error[0] == document["id"]:
                st.error(note_error[1])
            notes_key = prefix + "item_notes"
            st.data_editor(frame, key=notes_key, height=185, hide_index=True, use_container_width=True,
                           num_rows="fixed", disabled=[name for name in frame.columns if name != "附註說明"],
                           on_change=_save_item_notes, args=(config, deepcopy(document), notes_key),
                           column_config={"附註說明": st.column_config.TextColumn("附註說明", help="可直接修改，離開儲存格後自動儲存。"), "採購單號": st.column_config.TextColumn("採購單號", width="medium"), "數量": st.column_config.NumberColumn(format="%.15g"), "單價": st.column_config.NumberColumn(format="%.15g")})
            if note_error and note_error[0] == document["id"]:
                st.button("重試儲存附註", key=notes_key + "_retry", on_click=_save_item_notes,
                          args=(config, deepcopy(document), notes_key))
    if editing:
        render_shipment_quote_notices(config, document)
    summary, details = st.columns([1, 3])
    if editing:
        _sync_edit_details(document, prefix)
        _prepare_invoice_amount(document, prefix)
    with details:
        sections = ("交易明細", "發票資料", "帳款資料", "相關資料")
        if editing:
            selected_section = st.radio("明細分頁", sections, key=prefix + "detail_section",
                                        horizontal=True, label_visibility="collapsed")
            transaction = invoice_tab = account = related = st.container()
        else:
            selected_section = None
            transaction, invoice_tab, account, related = st.tabs(sections)
        if selected_section in (None, "交易明細"):
            with transaction:
                notes_col, paid_col = st.columns([4, 1], vertical_alignment="center")
                notes_options = {} if editing or document.get("status") == "void" else {
                    "on_change": _save_notes, "args": (config, deepcopy(document), prefix + "notes"),
                    "help": "可直接修改，離開欄位後自動儲存。"}
                note_default = document.get("notes", "") if editing else st.session_state.get("shipment_note_drafts", {}).get(document["id"], document.get("notes", ""))
                notes = notes_col.text_area("備註", value=widget_default(prefix + "notes", note_default), height=68,
                                           key=prefix + "notes", disabled=document.get("status") == "void", **notes_options)
                note_error = st.session_state.get("shipment_notes_error")
                if not editing and note_error and note_error[0] == document["id"]:
                    notes_col.button("重試儲存備註", key=prefix + "retry_notes", on_click=_save_notes,
                                     args=(config, deepcopy(document), prefix + "notes"))
                paid_in_full = paid_col.toggle("已付清", value=widget_default(prefix + "paid_in_full", bool(document.get("paid_in_full", False))),
                                               key=prefix + "paid_in_full", disabled=not editing,
                                               help="供應收帳款明細表與單筆收款篩選；不會自動登錄收款或更動金額。")
                if editing:
                    document["notes"] = notes
                    document["paid_in_full"] = paid_in_full
        if selected_section in (None, "發票資料"):
            with invoice_tab:
                invoice = document["invoice"]
                row = st.columns(3)
                with row[0]:
                    if editing:
                        document["tax_mode"] = st.selectbox(
                            "課稅類別", TAX_MODES, index=widget_index(prefix + "tax_mode", document["tax_mode"]),
                            key=prefix + "tax_mode", on_change=_tax_changed, args=(prefix, "mode"),
                        )
                    else:
                        _readonly_field("課稅類別", document["tax_mode"])
                    invoice_choice("開立方式", "method", ("隨單開立", "月結開立"))
                with row[1]:
                    date_field("發票日期", "date", target=invoice, optional=True)
                    invoice_choice("發票聯式", "type", ("收銀機", "三聯式"))
                with row[2]:
                    text("發票編號", "number", target=invoice)
                    amount_key = prefix + "invoice_amount"
                    if editing:
                        invoice["amount"] = st.text_input("發票金額", value=widget_default(amount_key, invoice.get("amount", "")),
                                                          key=amount_key, on_change=_invoice_amount_changed, args=(prefix,))
                    else:
                        _readonly_field("發票金額", invoice.get("amount"))
        if selected_section in (None, "帳款資料"):
            with account:
                left, right = st.columns(2)
                with left:
                    date_field("帳款日期", "account_date")
                with right:
                    text("付款條件", "payment_terms")
        if selected_section in (None, "相關資料"):
            with related:
                for row_fields in ((("聯絡人", "contact"), ("統一編號", "tax_id")), (("聯絡電話", "phone"), ("傳真號碼", "fax"))):
                    for col, (label, field) in zip(st.columns(2), row_fields):
                        with col:
                            text(label, field)
                if document.get("id"):
                    st.caption(f"建立：{document['created_at']}　更新：{document['updated_at']}")
                    st.caption("已作廢" if document.get("status") == "void" else "草稿")
    missing_prices = _missing_prices(document)
    with summary:
        st.markdown('<div class="shipment-section amounts">金額摘要</div>', unsafe_allow_html=True)
        if editing:
            rate = st.selectbox("稅率", (0, 5), index=widget_index(prefix + "tax_rate", 0 if document["tax_mode"] in ("免稅", "零稅率") or float(document["tax_rate"]) == 0 else 5),
                                format_func=lambda value: "0%（免稅）" if value == 0 else "5%",
                                key=prefix + "tax_rate", on_change=_tax_changed, args=(prefix, "rate"))
            document["tax_rate"] = str(rate)
        else:
            _readonly_field("稅率", f"{float(document['tax_rate']):g}%")
        if missing_prices:
            st.caption("有品項待報價；合計僅包含已填單價的品項。")
        try:
            totals = calculate(document["items"], document["tax_mode"], document["tax_rate"]) if editing else document
            st.markdown('<div class="shipment-totals-card">' + ''.join(f'<div class="shipment-total"><span>{label}</span><span>{int(totals[key]):,}</span></div>'
                               for label, key in (("未稅合計", "net_amount"), ("稅額", "tax_amount"), ("總計 TWD", "total_amount"))) + '</div>', unsafe_allow_html=True)
        except ShipmentError as error:
            totals = None
            st.error(str(error))
    if editing and totals and document["items"]:
        lines = '　·　'.join(f'{escape(str(item.get("code", "")))}：{display_amount(amount) or "待報價"}' for item, amount in zip(document["items"], totals["line_amounts"]))
        st.markdown(f'<div class="shipment-lines">{lines}</div>', unsafe_allow_html=True)
    if editing:
        with print_controls[0]:
            _place_shipment_output(config, document, preview=None, prepare_export=prepare_draft_export,
                                   options=print_options, preview_slot=preview_slot)
    save_error = ""
    if editing:
        # Consume the toolbar request after reading the whole draft. A second
        # click is required to write a document with unpriced items.
        st.session_state.pop("shipment_pending_save", None)
        confirmation_key = "shipment_blank_price_confirmation"
        if st.session_state.get(confirmation_key) != missing_prices:
            st.session_state.pop(confirmation_key, None)
        if save_clicked and missing_prices:
            st.session_state[confirmation_key] = missing_prices
            save_clicked = False
            st.session_state.shipment_blank_price_toast = True
        if not editor_rebased and st.session_state.pop("shipment_blank_price_toast", False) and st.session_state.get(confirmation_key):
            st.toast(f"有 {len(missing_prices)} 筆品項未填單價，請確認是否留白儲存。", icon="⚠️")
        if st.session_state.get(confirmation_key):
            with price_confirmation.container():
                st.warning("未填的單價會保留空白，可在出貨單儲存後補價。")
                confirm, cancel = st.columns(2)
                save_clicked = confirm.button("確認留白並儲存", key="shipment_confirm_blank_prices", type="primary")
                if cancel.button("返回填寫單價", key="shipment_cancel_blank_prices",
                                 on_click=_return_to_item_prices, args=(confirmation_key, item_editor_key)):
                    save_clicked = False
                if save_clicked:
                    st.session_state.pop(confirmation_key, None)
                    price_confirmation.empty()
    if save_clicked:
        try:
            _commit_shipment_draft(config, document, customers, matcher, sync_products=sync_products, rerun=True)
        except ShipmentError as error:
            save_error = str(error)
            action_feedback.error(save_error)
            st.session_state.shipment_action_error = save_error
        except Exception:
            save_error = "儲存失敗，請確認單號沒有重複及資料庫連線正常；修改內容已保留"
            action_feedback.error(save_error)
            st.session_state.shipment_action_error = save_error
    if editing and editor_rebased:
        # If export or a failed save leaves the draft open, mount the completed
        # grid before accepting another edit under its new widget key.
        if save_error:
            st.session_state.shipment_action_error = save_error
        _rerun_shipment()
    if editing:
        grid_suffix = st.session_state.get("shipment_grid_epoch", 0)
        grid_key = prefix + "items" + (f"_{grid_suffix}" if grid_suffix else "")
        watched = (grid_key, item_editor_key,
                   *(prefix + key for key in ("shipment_date", "customer_picker", "tax_mode", "tax_rate")))
        st.session_state.shipment_save_checkpoint = (
            (repr(config), prefix, grid_suffix),
            {key: deepcopy(st.session_state.get(key)) for key in watched},
            customers,
            matcher,
        )
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


