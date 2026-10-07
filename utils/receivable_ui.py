"""Compact filter form and paginated customer statement preview."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

from .customer_repository import list_customers
from .receivable_report import build_statements, render_statement_print, statement_pages
from .shipment_repository import ShipmentError, get_shipment, list_shipments
from .receipt_repository import list_receipts, save_receipt, void_receipt
from .shipment_ui import COMPACT_STYLE
from .accounting_export import statement_excel, statement_pdf, ranking_excel, ranking_pdf, ranking_rows


def render_receivable_statement(config):
    st.markdown(COMPACT_STYLE.replace("shipment-page", "receivable-page"), unsafe_allow_html=True)
    st.markdown("### 應收帳款明細表")
    report_tab, receipt_tab = st.tabs(["明細表預覽", "收款登錄"])
    with receipt_tab:
        render_receipt_entry(config)
    with report_tab:
        render_report(config)


def render_report(config):
    customers = list_customers(config, include_inactive=True)
    names = {c["customer_id"]: c["name"] for c in customers}
    codes = [""] + list(names)
    today = date.today()
    with st.form("receivable_filters"):
        cols = st.columns(4)
        lower = cols[0].selectbox("起始客戶編號", codes, format_func=lambda c: c + " · " + names[c] if c else "不限")
        upper = cols[1].selectbox("結束客戶編號", codes, format_func=lambda c: c + " · " + names[c] if c else "不限")
        start = cols[2].date_input("起始帳款日期", value=today.replace(day=1))
        end = cols[3].date_input("結束帳款日期", value=today)
        hide_empty = st.toggle("本期未交易者不顯示", value=True)
        submitted = st.form_submit_button("預覽", type="primary")
    if submitted:
        try:
            pages = statement_pages(build_statements(config, start, end, lower, upper, hide_empty))
        except ShipmentError as error:
            st.error(str(error))
            st.session_state.pop("receivable_pages", None)
        else:
            st.session_state.receivable_pages = pages
            st.session_state.receivable_page = 0
    pages = st.session_state.get("receivable_pages")
    if pages is None:
        return
    if not pages:
        st.info("此區間沒有符合條件的出貨資料")
        return
    index = min(st.session_state.get("receivable_page", 0), len(pages) - 1)
    def move(target):
        st.session_state.receivable_page = target
    controls = st.columns([1, 1, 1, 1, 2, 2])
    for col, label, target in zip(controls, ("首頁", "上一頁", "下一頁", "末頁"), (0, index - 1, index + 1, len(pages) - 1)):
        col.button(label, key="receivable_" + label, on_click=move, args=(target,),
                   disabled=target < 0 or target >= len(pages) or target == index, use_container_width=True)
    controls[4].write(f"{index + 1} / {len(pages)} · {pages[index]['statement']['customer_id']}")
    html = render_statement_print(pages, selected=index)
    controls[5].download_button("下載列印版", html, file_name="應收帳款明細表.html", mime="text/html", use_container_width=True)
    statements = list({p["statement"]["customer_id"]: p["statement"] for p in pages}.values())
    exports = st.columns([1, 1, 4])
    exports[0].download_button("另存 PDF", statement_pdf(pages), file_name="應收帳款明細表.pdf", mime="application/pdf")
    exports[1].download_button("匯出 Excel", statement_excel(statements), file_name="應收帳款明細表.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    components.html(render_statement_print(pages, selected=index, embedded=True), height=530, scrolling=True)


def render_customer_ranking(config):
    st.subheader("客戶交易排行")
    with st.form("ranking_filters"):
        cols = st.columns(4)
        lower = cols[0].text_input("起始客戶編號")
        upper = cols[1].text_input("結束客戶編號")
        start = cols[2].date_input("起始帳款日期", value=date.today().replace(day=1))
        end = cols[3].date_input("結束帳款日期", value=date.today())
        if st.form_submit_button("查詢"):
            try:
                st.session_state.ranking_statements = build_statements(config, start, end, lower.strip(), upper.strip())
            except ShipmentError as exc:
                st.error(str(exc))
                st.session_state.pop("ranking_statements", None)
    statements = st.session_state.get("ranking_statements")
    if statements is None:
        return
    if not statements:
        st.info("此區間沒有交易")
        return
    rows = ranking_rows(statements)
    st.dataframe([dict(zip(rows[0], row)) for row in rows[1:]], hide_index=True, use_container_width=True)
    left, right, _ = st.columns([1, 1, 4])
    left.download_button("另存 PDF", ranking_pdf(statements), file_name="客戶交易排行.pdf", mime="application/pdf")
    right.download_button("匯出 Excel", ranking_excel(statements), file_name="客戶交易排行.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def render_receipt_entry(config):
    records = list_shipments(config)
    if not records:
        st.info("目前沒有可登錄收款的出貨單")
        return
    customers = {r["customer_id"]: r["customer_name"] for r in records}
    customer = st.selectbox("收款客戶", sorted(customers), format_func=lambda c: c + " · " + customers[c], key="receipt_customer")
    documents = {r["id"]: r for r in records if r["customer_id"] == customer}
    shipment_id = st.selectbox("收款出貨單", list(documents), format_func=lambda i: documents[i]["shipment_number"] + " · " + documents[i]["shipment_date"], key="receipt_shipment")
    document = get_shipment(config, shipment_id)
    receipts = list_receipts(config, shipment_id)
    paid = sum((Decimal(r["amount"]) for r in receipts if r["status"] == "active"), Decimal(0))
    balance = Decimal(document["total_amount"]) - paid
    st.caption(f"出貨總額 {int(Decimal(document['total_amount'])):,}　已登錄收款 {int(paid):,}　帳面未收餘額 {int(balance):,}")
    token_key = "receipt_token_" + shipment_id
    if token_key not in st.session_state:
        st.session_state[token_key] = str(uuid4())
    token = st.session_state[token_key]
    notice = st.session_state.pop("receipt_notice", "")
    if notice:
        st.success(notice)
    with st.form("receipt_entry_" + token, clear_on_submit=False):
        cols = st.columns(3)
        receipt_date = cols[0].date_input("收款日期", value=date.today())
        amount = cols[1].number_input("本次收款金額", min_value=0, max_value=1000000000000, value=0, step=1)
        method = cols[2].selectbox("收款方式", ["匯款", "現金", "支票", "其他"])
        cols = st.columns(2)
        reference = cols[0].text_input("收款憑據／銀行末碼")
        notes = cols[1].text_input("收款備註")
        submitted = st.form_submit_button("登錄收款", disabled=balance <= 0)
    if submitted:
        try:
            save_receipt(config, receipt_id=token, shipment_id=shipment_id, shipment_version=document["version"],
                         receipt_date=receipt_date, amount=amount, method=method, reference=reference, notes=notes)
        except ShipmentError as error:
            st.error(str(error))
        else:
            st.session_state.pop(token_key, None)
            st.session_state.pop("receivable_pages", None)
            st.session_state.receipt_notice = "收款已登錄"
            st.rerun()
    if receipts:
        st.dataframe([{"收款日期": r["receipt_date"], "金額": int(r["amount"]), "方式": r["method"],
                       "憑據": r["reference"], "備註": r["notes"], "狀態": "有效" if r["status"] == "active" else "作廢",
                       "作廢原因": r["void_reason"] or ""} for r in receipts], use_container_width=True, hide_index=True, height=170)
        active = {r["id"]: r for r in receipts if r["status"] == "active"}
        if active:
            with st.expander("作廢收款紀錄"):
                with st.form("receipt_void_" + shipment_id):
                    receipt_id = st.selectbox("收款紀錄", list(active), format_func=lambda i: active[i]["receipt_date"] + " · " + active[i]["amount"] + " · " + active[i]["method"] + " · " + i[:8])
                    reason = st.text_input("作廢收款原因")
                    confirmed = st.toggle("確認作廢此收款")
                    if st.form_submit_button("作廢收款"):
                        if not confirmed:
                            st.error("請確認作廢")
                        else:
                            try:
                                void_receipt(config, receipt_id, reason)
                            except ShipmentError as error:
                                st.error(str(error))
                            else:
                                st.session_state.pop("receivable_pages", None)
                                st.session_state.receipt_notice = "收款已作廢"
                                st.rerun()
