"""Compact filter form and paginated customer statement preview."""

from datetime import date
from decimal import Decimal
from uuid import uuid4
from hashlib import sha256
from calendar import monthrange
import json
import logging

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from .customer_display import CustomerDisplay
from .customer_repository import list_customers, customer_display_name
from .receivable_report import build_statements, render_statement_print, statement_pages, monthly_receipt_summary
from .paper_preview import theme_preview, dismiss_export_on_preview_click
from .shipment_repository import ShipmentError, get_shipment, list_shipments
from .receipt_repository import (list_receipts, save_receipt, void_receipt, outstanding_shipments,
                                 save_receipt_batch, list_receipt_batches, receipt_batch_details,
                                 apply_prepaid_batch, void_receipt_batch, receipt_tracking_start,
                                 update_receipt_amount, update_receipt_batch_amounts, receipt_changes)
from .shipment_page_data import clear_reads
from .shipment_ui import COMPACT_STYLE
from .accounting_export import statement_excel, statement_pdf, ranking_excel, ranking_pdf, ranking_rows
from .shipment_print import COMPANY


def render_receivable_statement(config, *, title="應收帳款明細表"):
    st.markdown(COMPACT_STYLE.replace("shipment-page", "receivable-page"), unsafe_allow_html=True)
    tabs = st.tabs(["明細表預覽", "收款登錄"] + (["每月收款總覽"] if title == "應收帳款明細表" else []))
    report_tab, receipt_tab = tabs[:2]
    with receipt_tab:
        render_receipt_entry(config)
    with report_tab:
        render_report(config, title=title)
    if len(tabs) == 3:
        with tabs[2]:
            render_monthly_receipt_summary(config)


def render_monthly_receipt_summary(config):
    st.markdown("""<style>
    .receivable-summary {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:8px 0 24px}
    .receivable-card {border:1px solid #64748b55;border-radius:14px;padding:20px 22px;min-width:0;background:color-mix(in srgb,currentColor 3%,transparent)}
    .receivable-card-label {font-size:14px;opacity:.75;margin-bottom:8px}
    .receivable-card-value {font-size:clamp(23px,2.6vw,36px);font-weight:700;line-height:1.3;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
    .receivable-card-note {font-size:12px;opacity:.65;margin-top:8px}
    .receivable-card.balance {border-top:3px solid #f59e0b}
    .receivable-card.received {border-top:3px solid #38bdf8}
    .receivable-card.total {border-top:3px solid #94a3b8}
    .stApp:has(.erp-title) .receivable-summary {color:#d5e1ec}
    .stApp:has(.erp-title) .main:has(#receivable-page) [data-testid="stMarkdownContainer"] {color:#d5e1ec}
    @media(max-width:640px){.receivable-summary{grid-template-columns:1fr;gap:10px}.receivable-card{padding:14px 18px}.receivable-card-value{font-size:28px}}
    </style>""", unsafe_allow_html=True)
    st.subheader('每月收款總覽')
    st.caption('選擇帳款月份，查看各客戶的應收、已收與未收款項。')
    today = date.today()
    with st.container(border=True):
        year_col, month_col, closing_col, date_col = st.columns([1, 1, 1.6, 1.8])
        year = year_col.number_input('年度', min_value=2000, max_value=2100, value=today.year, step=1, key='receipt_summary_year')
        month = month_col.selectbox('月份', list(range(1, 13)), index=today.month-1,
                                   format_func=lambda m: f'{m} 月', key='receipt_summary_month')
        closing = closing_col.radio('結帳日', ['25 號', '31 號／月底'], index=1, horizontal=True, key='receipt_summary_closing')
        as_of = date_col.date_input('收款截至日期', value=today, key='receipt_summary_as_of')
        start, end = month_receipt_period(year, month, 25 if closing == '25 號' else 31)
        st.caption(f'帳款期間　{start:%Y/%m/%d} ～ {end:%Y/%m/%d}　｜　收款截至　{as_of:%Y/%m/%d}')
    rows = monthly_receipt_summary(config, start.isoformat(), end.isoformat(), as_of.isoformat())
    display = CustomerDisplay(config)
    cards = []
    for label, field, kind, note in [('本期應收總額', 'total', 'total', '所選帳款期間合計'),
                                     ('已收金額', 'received', 'received', '截至指定日期已登錄收款'),
                                     ('未收金額', 'balance', 'balance', '本期尚待收取款項')]:
        amount = sum(r[field] for r in rows)
        cards.append(f'<div class="receivable-card {kind}"><div class="receivable-card-label">{label}</div>'
                     f'<div class="receivable-card-value">{amount:,}</div><div class="receivable-card-note">{note}</div></div>')
    st.markdown('<div class="receivable-summary">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('**客戶收款清單**')
        controls = st.columns([3, 1])
        query = controls[0].text_input('搜尋客戶', placeholder='輸入編號、簡稱或完整名稱', key='receipt_summary_query').strip().casefold()
        with controls[1]:
            st.caption('顯示範圍')
            unpaid_only = st.toggle('只顯示未收', key='receipt_summary_unpaid')
        filtered = [r for r in rows if (not query or any(query in str(value).casefold() for value in
                    (r['customer_id'], r['customer_name'], display.name(r['customer_name'], r['customer_id']))))
                    and (not unpaid_only or r['balance'] > 0)]
        st.caption(f'顯示 {len(filtered)} / {len(rows)} 位客戶 · 上方金額為全部客戶合計')
        if not filtered:
            st.info('沒有符合條件的客戶，請調整搜尋或顯示範圍。')
            return
        st.dataframe(pd.DataFrame([{'客戶編號': r['customer_id'], '客戶簡稱': display.name(r['customer_name'], r['customer_id']),
                                    '未收金額': r['balance'], '收款狀態': r['status'], '本期應收': r['total'],
                                    '已收金額': r['received'], '最後收款日期': r['last_receipt'] or '—',
                                    '收款起算日': r['tracking_start'] or '尚未開始'} for r in filtered]),
                     hide_index=True, use_container_width=True, height=min(500, 38 * (len(filtered) + 1)),
                     column_config={field: st.column_config.NumberColumn(field, format='%d')
                                    for field in ['本期應收', '已收金額', '未收金額']})


@st.fragment
def render_report(config, *, title="應收帳款明細表"):
    customers = list_customers(config, include_inactive=True)
    names = {c["customer_id"]: customer_display_name(c) for c in customers}
    codes = [""] + list(names)
    today = date.today()
    filter_col, export_col, scope_col = st.columns([1.2, 1.3, 5.5], vertical_alignment="center")
    with filter_col.popover("查詢條件", use_container_width=True):
        components.html('''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
        <style>body{margin:0;text-align:right}button{font:14px "Microsoft JhengHei",sans-serif;
        background:#0b2f4a;color:#fff;border:1px solid #527086;border-radius:5px;
        padding:5px 12px;cursor:pointer}button:hover{background:#124466}
        button:focus-visible{outline:2px solid #8cc8ea;outline-offset:1px}</style></head>
        <body><button type="button" id="close-filters" aria-label="收合查詢條件">收合條件 ×</button>
        <script>function closeFilters(){try{
        const trigger=Array.from(window.parent.document.querySelectorAll('[data-testid="stPopover"] button'))
        .find(button=>button.textContent.trim()==='查詢條件');
        if(trigger){trigger.click();trigger.focus();}
        }catch(error){}}
        document.getElementById('close-filters').addEventListener('click',closeFilters);
        document.addEventListener('keydown',event=>{if(event.key==='Escape')closeFilters();});
        </script></body></html>''', height=34, scrolling=False)
        # Keep query controls independent of Streamlit's nested form lifecycle.
        # Only the preview button below replaces the saved report.
        with st.container():
            cols = st.columns(2)
            lower = cols[0].selectbox("起始客戶編號", codes, format_func=lambda c: c + " · " + names[c] if c else "不限")
            upper = cols[1].selectbox("結束客戶編號", codes, format_func=lambda c: c + " · " + names[c] if c else "不限")
            dates = st.columns(2)
            start = dates[0].date_input("起始帳款日期", value=today.replace(day=1))
            end = dates[1].date_input("結束帳款日期", value=today)
            paper_col, hide_col, paid_col = st.columns([1, 1.5, 1.5], vertical_alignment="center")
            paper = paper_col.selectbox("紙張尺寸", ("A4", "三聯紙 240 × 140 mm", "依內容自動選擇", "A5"))
            hide_empty = hide_col.toggle("本期未交易者不顯示", value=True)
            hide_paid = paid_col.toggle("已付清者不顯示", value=True, key="receivable_hide_paid",
                                       help="排除出貨單已勾選「已付清」的單據；同一客戶仍有其他單據時會繼續顯示。") if title == "應收帳款明細表" else False
            submitted = st.button("預覽", key="receivable_preview", type="primary", use_container_width=True)
    if submitted:
        st.session_state.pop("receivable_exports", None)
        try:
            pages = statement_pages(build_statements(config, start, end, lower, upper, hide_empty, hide_paid=hide_paid),
                                    paper_size="A5" if paper.startswith("三聯紙") else "auto" if paper == "依內容自動選擇" else paper,
                                    name_width=14 if title == "應收帳款明細表" else 10)
        except ShipmentError as error:
            st.error(str(error))
            st.session_state.pop("receivable_pages", None)
            st.session_state.pop("receivable_report_scope", None)
        else:
            st.session_state.receivable_report_scope = f"{lower or '不限'} ～ {upper or '不限'} · {start:%Y/%m/%d} ～ {end:%Y/%m/%d} · {paper}" + (" · 排除已付清" if hide_paid else "")
            st.session_state.receivable_pages = pages
            st.session_state.receivable_page = 0
            st.session_state.receivable_paper_stock = "a4_driver" if paper == "A4" else "triplicate" if paper.startswith("三聯紙") else "standard"
    scope_col.caption(st.session_state.get("receivable_report_scope", "請開啟查詢條件，選好範圍後按預覽。"))
    pages = st.session_state.get("receivable_pages")
    if not pages:
        export_col.button("列印／匯出", disabled=True, use_container_width=True)
    if pages is None:
        return
    if not pages:
        st.info("此區間沒有符合條件的出貨資料")
        return
    paper_stock = st.session_state.get("receivable_paper_stock", "standard")
    st.markdown('''<style>
    [data-testid="stPopoverBody"]:has(#receivable-export-panel){
        width:min(620px,calc(100vw - 32px))!important;
        max-width:calc(100vw - 32px)!important}
    </style>''', unsafe_allow_html=True)
    with export_col.popover("列印／匯出", use_container_width=True), st.container():
        st.markdown('<span id="receivable-export-panel"></span>', unsafe_allow_html=True)
        heading_col, receipt_col = st.columns(2)
        company_name = COMPANY["name"]
        if title == "應收帳款明細表" and heading_col.toggle("抬頭改為加舜企業有限公司", key="receivable_alternate_company", value=False):
            company_name = "加舜企業有限公司"
        show_receipts = receipt_col.toggle("顯示收款資訊", key="receivable_show_receipts", value=False)
        feed_col, margin_col = st.columns([2, 1])
        feed_rotation = feed_col.selectbox("紙張進紙", (0, 90), key="receivable_feed_rotation",
                                    format_func=lambda v: "240 mm 長邊先進（橫放）" if v == 0 or paper_stock == "a4_driver" else "140 mm 短邊先進（直放）", disabled=paper_stock != "triplicate")
        hole_margin = margin_col.number_input("打洞留白（mm）", min_value=0.0, max_value=25.0, value=12.5, step=0.5,
                                      key="receivable_hole_margin", disabled=paper_stock == "standard")
        print_settings = dict(paper_stock=paper_stock, feed_rotation=feed_rotation, hole_margin=hole_margin, company_name=company_name)
        html = render_statement_print(pages, show_receipts=show_receipts, title=title, **print_settings)
        html_col, pdf_col, excel_col = st.columns(3)
        html_col.download_button("下載列印版", html, file_name=title + ".html", mime="text/html", use_container_width=True)
        # Keep generated files private to this session and the current report/settings.
        signature = (title, company_name, show_receipts)
        exports = st.session_state.get("receivable_exports")
        if exports is None or exports["signature"] != signature:
            exports = {"signature": signature}
            st.session_state.receivable_exports = exports
        if pdf_col.button("產生 PDF", key="receivable_prepare_pdf", use_container_width=True):
            exports["pdf"] = statement_pdf(pages, show_receipts=show_receipts, title=title, company_name=company_name)
        if "pdf" in exports:
            pdf_col.download_button("另存 PDF", exports["pdf"], file_name=title + ".pdf", mime="application/pdf", use_container_width=True)
        if excel_col.button("產生 Excel", key="receivable_prepare_excel", use_container_width=True):
            statements = list({p["statement"]["customer_id"]: p["statement"] for p in pages}.values())
            exports["xlsx"] = statement_excel(statements, show_receipts=show_receipts, title=title, company_name=company_name)
        if "xlsx" in exports:
            excel_col.download_button("匯出 Excel", exports["xlsx"], file_name=title + ".xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    # Navigation runs inside the iframe: no Streamlit rerun or report regeneration.
    components.html(dismiss_export_on_preview_click(theme_preview(html)), height=480, scrolling=True)


def render_customer_ranking(config):
    st.markdown(COMPACT_STYLE.replace("shipment-page", "ranking-page"), unsafe_allow_html=True)
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
            except Exception as exc:
                logging.getLogger(__name__).exception("Customer ranking read failed: error_type=%s", type(exc).__name__)
                st.error("客戶排行資料讀取失敗，請稍後重新查詢。未變更任何資料。")
                st.session_state.pop("ranking_statements", None)
    statements = st.session_state.get("ranking_statements")
    if statements is None:
        return
    if not statements:
        st.info("此區間沒有交易")
        return
    rows = ranking_rows(statements)
    st.dataframe(CustomerDisplay(config).frame([dict(zip(rows[0], row)) for row in rows[1:]]), hide_index=True, use_container_width=True)
    st.metric("未稅金額總計", f"{int(sum((Decimal(s['net']) for s in statements), Decimal(0))):,}")
    left, right, _ = st.columns([1, 1, 4])
    left.download_button("另存 PDF", ranking_pdf(statements), file_name="客戶交易排行.pdf", mime="application/pdf")
    right.download_button("匯出 Excel", ranking_excel(statements), file_name="客戶交易排行.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _batch_receipt_saved(token_key, message):
    st.session_state.pop(token_key, None)
    st.session_state.pop("receivable_pages", None)
    clear_reads(st.session_state)
    st.session_state.receipt_notice = message
    st.rerun()


def _receipt_change_history(config, entity_id):
    changes = receipt_changes(config, entity_id)
    if changes:
        with st.expander('收款修改紀錄'):
            st.dataframe([{'修改時間': r['created_at'], '原收款金額': int(json.loads(r['before_json'])['amount']),
                           '新收款金額': int(json.loads(r['after_json'])['amount']), '修改原因': r['reason']}
                          for r in changes], hide_index=True, use_container_width=True)


def month_receipt_period(year, month, closing_day):
    last = min(closing_day, monthrange(year, month)[1])
    return date(year, month, 1), date(year, month, last)


def _receipt_period_controls(prefix, amount_key):
    mode = st.radio('帳款期間', ['月份', '自訂日期'], horizontal=True, key=prefix + 'period_mode',
                    on_change=_set_batch_amount, args=(amount_key, 0))
    if mode == '月份':
        cols = st.columns([1, 1, 2])
        year = cols[0].number_input('年度', min_value=2000, max_value=2100, value=date.today().year, step=1, key=prefix + 'year',
                                    on_change=_set_batch_amount, args=(amount_key, 0))
        month = cols[1].selectbox('月份', list(range(1, 13)), index=date.today().month-1,
                                  format_func=lambda m: f'{m} 月', key=prefix + 'month',
                                  on_change=_set_batch_amount, args=(amount_key, 0))
        closing = cols[2].radio('結帳日', ['25 號', '31 號／月底'], index=1, horizontal=True, key=prefix + 'closing',
                                on_change=_set_batch_amount, args=(amount_key, 0))
        start, end = month_receipt_period(year, month, 25 if closing == '25 號' else 31)
        st.caption(f'帳款期間：{start:%Y/%m/%d} ～ {end:%Y/%m/%d}')
    else:
        cols = st.columns(2)
        start = cols[0].date_input('帳款起日', value=date.today().replace(day=1), key=prefix + 'start',
                                   on_change=_set_batch_amount, args=(amount_key, 0))
        end = cols[1].date_input('帳款迄日', value=date.today(), key=prefix + 'end',
                                 on_change=_set_batch_amount, args=(amount_key, 0))
    return start, end


def _set_batch_amount(key, amount):
    st.session_state[key] = amount


def render_batch_receipt(config, customer, records, *, prepaid=False):
    notice = st.session_state.pop('receipt_notice', '')
    if notice:
        st.success(notice)
    batches = list_receipt_batches(config, customer)
    token_key = 'batch_receipt_token_' + customer + ('_prepaid' if prepaid else '')
    token = st.session_state.setdefault(token_key, str(uuid4()))
    prefix = 'batch_' + token + '_'
    credit = None
    if prepaid:
        credits = {b['id']: b for b in batches if b['status'] == 'active' and int(b['amount']) > b['allocated']}
        if credits:
            credit_id = st.selectbox('預收款', list(credits), key=prefix + 'credit',
                                    format_func=lambda i: f"{credits[i]['receipt_date']} · {credits[i]['reference']} · 餘額 {int(credits[i]['amount'])-credits[i]['allocated']:,}")
            credit = credits[credit_id]
        else:
            st.info('此客戶目前沒有預收餘額')
    if not prepaid or credit:
        start, end = _receipt_period_controls('batch_period_' + customer + '_', prefix + 'amount')
        include_prior = st.toggle('包含前期未收', value=False, key='batch_period_' + customer + '_prior_opt_in',
                                     on_change=_set_batch_amount, args=(prefix + 'amount', 0))
        valid_period = start <= end
        if not valid_period:
            st.error('帳款起日不可晚於迄日')
        tracking_start = receipt_tracking_start(config, customer) or start.isoformat()
        st.caption('收款起算日：' + tracking_start.replace('-', '/'))
        outstanding = [d for d in outstanding_shipments(config, customer) if d['shipment_date'] >= tracking_start]
        in_period = lambda d: max(start.isoformat(), tracking_start) <= d['shipment_date'] <= end.isoformat()
        billed = sum(int(d['total_amount']) for d in records if d['customer_id'] == customer and in_period(d)) if valid_period else 0
        unpaid = sum(d['balance'] for d in outstanding if in_period(d)) if valid_period else 0
        prior_unpaid = sum(d['balance'] for d in outstanding if d['shipment_date'] < start.isoformat()) if valid_period and include_prior else 0
        totals = st.columns(3)
        totals[0].metric('本期應收總額', f'{billed:,}')
        totals[1].metric('本期未收金額', f'{unpaid:,}')
        totals[2].metric('前期未收金額', f'{prior_unpaid:,}' if include_prior else '未納入')
        cols = st.columns(3)
        received_date = cols[0].date_input('沖帳日期' if prepaid else '收款日期', value=date.today(), key=prefix + 'date')
        documents = [d for d in outstanding
                     if d['shipment_date'] <= min(end, received_date).isoformat()
                     and (include_prior or d['shipment_date'] >= start.isoformat())] if valid_period else []
        maximum = int(credit['amount'])-credit['allocated'] if credit else 1000000000000
        st.session_state.setdefault(prefix + 'amount', 0)
        if st.session_state[prefix + 'amount'] > maximum:
            st.session_state[prefix + 'amount'] = 0
        amount = cols[1].number_input('本次沖抵金額' if prepaid else '本次收款金額', min_value=0,
                                     max_value=maximum, value=None, step=1, key=prefix + 'amount') or 0
        methods = ['匯款', '現金', '支票', '其他']
        method = cols[2].selectbox('收款方式', methods, index=methods.index(credit['method']) if credit and credit['method'] in methods else 0,
                                  key=prefix + 'method' + (credit['id'] if credit else ''), disabled=prepaid)
        cols = st.columns(2)
        reference = cols[0].text_input('收款憑據／銀行末碼', value=credit['reference'] if credit else '',
                                       key=prefix + 'reference' + (credit['id'] if credit else ''), disabled=prepaid)
        notes = cols[1].text_input('收款備註', value=credit['notes'] if credit else '',
                                   key=prefix + 'notes' + (credit['id'] if credit else ''), disabled=prepaid)
        full_amount = sum(d['balance'] for d in documents)
        if credit:
            full_amount = min(full_amount, int(credit['amount'])-credit['allocated'])
        st.button('全額沖抵' if prepaid else '全額收款', disabled=not full_amount, key=prefix + 'full',
                  on_click=_set_batch_amount, args=(prefix + 'amount', full_amount))
        remaining, rows = amount, []
        for d in documents:
            allocated = min(remaining, d['balance'])
            remaining -= allocated
            rows.append({'出貨日期': d['shipment_date'], '出貨單號': d['shipment_number'],
                         '出貨總額': int(d['total_amount']), '未收金額': d['balance'], '本次沖抵': allocated})
        allocations = []
        if rows:
            fingerprint = sha256(repr((amount, [(d['id'], d['version'], d['balance']) for d in documents])).encode()).hexdigest()[:16]
            edited = st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                                    disabled=['出貨日期', '出貨單號', '出貨總額', '未收金額'],
                                    column_config={'本次沖抵': st.column_config.NumberColumn('本次沖抵', min_value=0, step=1, required=True)},
                                    key=prefix + 'allocations_' + fingerprint)
            allocations = [dict(shipment_id=d['id'], shipment_version=d['version'], amount=edited.iloc[i]['本次沖抵'])
                           for i, d in enumerate(documents)]
        else:
            st.info('所選期間沒有未收出貨單')
        try:
            total = sum(Decimal(str(a['amount'])) for a in allocations)
            valid = total <= amount and all(0 <= Decimal(str(a['amount'])) <= d['balance'] and
                                           Decimal(str(a['amount'])) == Decimal(str(a['amount'])).to_integral_value()
                                           for a, d in zip(allocations, documents))
        except Exception:
            total, valid = Decimal(0), False
        cols = st.columns(3)
        cols[0].metric('本次沖抵合計', f'{total:,.0f}')
        cols[1].metric('清單剩餘未收', f"{sum(d['balance'] for d in documents)-total:,.0f}")
        cols[2].metric('預收剩餘' if prepaid else '轉入預收', f"{(int(credit['amount'])-credit['allocated'] if credit else amount)-total:,.0f}")
        if not valid:
            st.error('沖抵須為整數，且不得超過單據未收金額或本次金額')
        if st.button('確認沖抵預收款' if prepaid else '登錄批次收款', type='primary',
                     disabled=not valid or not valid_period or amount <= 0 or (prepaid and total <= 0), key=prefix + 'save'):
            try:
                if prepaid:
                    apply_prepaid_batch(config, batch_id=credit['id'], batch_version=credit['version'], request_id=token,
                                        allocation_date=received_date.isoformat(), allocations=allocations)
                else:
                    save_receipt_batch(config, batch_id=token, customer_id=customer, receipt_date=received_date.isoformat(),
                                       amount=amount, allocations=allocations, method=method, reference=reference, notes=notes,
                                       tracking_start=start.isoformat())
            except ShipmentError as error:
                st.error(str(error))
            else:
                _batch_receipt_saved(token_key, '預收款已沖抵' if prepaid else '批次收款已登錄')
    if batches:
        st.dataframe([{'收款日期': b['receipt_date'], '收款總額': int(b['amount']), '已沖抵': b['allocated'],
                       '預收餘額': int(b['amount'])-b['allocated'] if b['status'] == 'active' else 0,
                       '方式': b['method'], '憑據': b['reference'], '備註': b['notes'],
                       '狀態': '有效' if b['status'] == 'active' else '作廢', '作廢原因': b['void_reason'] or ''}
                      for b in batches], hide_index=True, use_container_width=True)
        by_id = {b['id']: b for b in batches}
        selected = st.selectbox('批次收款紀錄', list(by_id), key='batch_history_' + customer,
                                format_func=lambda i: f"{by_id[i]['receipt_date']} · {int(by_id[i]['amount']):,} · {by_id[i]['reference']} · {i[:8]}")
        details = receipt_batch_details(config, selected)
        if details:
            st.dataframe([{'出貨日期': r['shipment_date'], '出貨單號': r['shipment_number'],
                           '沖帳日期': r['receipt_date'], '沖抵金額': int(r['amount'])} for r in details],
                          hide_index=True, use_container_width=True)
        if by_id[selected]['status'] == 'active':
            batch = by_id[selected]
            with st.expander('修改批次收款'):
                with st.form(f"batch_edit_{selected}_{batch['version']}"):
                    amount_col, reason_col = st.columns([1, 2])
                    corrected = amount_col.number_input('修改收款總額', min_value=1, max_value=1000000000000, value=int(batch['amount']), step=1)
                    reason = reason_col.text_input('修改原因')
                    allocation_rows = [{'出貨單號': r['shipment_number'], '沖帳日期': r['receipt_date'], '沖抵金額': int(r['amount'])} for r in details]
                    revised = st.data_editor(pd.DataFrame(allocation_rows), hide_index=True, use_container_width=True,
                                             disabled=['出貨單號', '沖帳日期'],
                                             column_config={'沖抵金額': st.column_config.NumberColumn('沖抵金額', min_value=0, step=1, required=True)}) if details else None
                    if st.form_submit_button('儲存收款修改'):
                        try:
                            allocations = [dict(receipt_id=r['id'], shipment_version=r['shipment_version'], amount=revised.iloc[i]['沖抵金額'])
                                           for i, r in enumerate(details)]
                            update_receipt_batch_amounts(config, batch_id=selected, batch_version=batch['version'], amount=corrected,
                                                         allocations=allocations, reason=reason)
                        except ShipmentError as error:
                            st.error(str(error))
                        else:
                            _batch_receipt_saved(token_key, '批次收款已修改')
            with st.expander('作廢整批收款'):
                with st.form('batch_void_' + selected):
                    reason_col, confirm_col = st.columns([2, 1])
                    reason = reason_col.text_input('收款作廢原因')
                    confirmed = confirm_col.toggle('確認作廢整批收款及所有沖抵')
                    if st.form_submit_button('作廢整批收款'):
                        if not confirmed:
                            st.error('請確認作廢')
                        else:
                            try:
                                void_receipt_batch(config, selected, reason)
                            except ShipmentError as error:
                                st.error(str(error))
                            else:
                                _batch_receipt_saved(token_key, '整批收款已作廢')
        _receipt_change_history(config, selected)


def render_receipt_entry(config):
    mode_col, paid_filter_col = st.columns([3, 1.3], vertical_alignment="center")
    mode = mode_col.radio('收款模式', ['單筆收款', '月結／批次收款', '預收款沖帳'], horizontal=True, key='receipt_mode')
    records = list_shipments(config)
    if mode == '單筆收款' and paid_filter_col.toggle('已付清者不顯示', value=True, key='receipt_hide_paid',
                                      help='排除出貨單的已付清註記；關閉後可查看或修改既有收款紀錄。'):
        records = [row for row in records if not row.get('paid_in_full')]
    names = {r['customer_id']: customer_display_name(r) for r in list_customers(config, include_inactive=True)}
    customers = names if mode != '單筆收款' else {r['customer_id']: names.get(r['customer_id'], r['customer_name']) for r in records}
    if not customers:
        st.info("目前沒有可登錄收款的出貨單")
        return
    customer_col, shipment_col = st.columns(2)
    customer = customer_col.selectbox("收款客戶", sorted(customers), format_func=lambda c: c + " · " + customers[c], key="receipt_customer")
    if mode != '單筆收款':
        render_batch_receipt(config, customer, records, prepaid=mode == '預收款沖帳')
        return
    documents = {r["id"]: r for r in records if r["customer_id"] == customer}
    shipment_id = shipment_col.selectbox("收款出貨單", list(documents), format_func=lambda i: documents[i]["shipment_number"] + " · " + documents[i]["shipment_date"], key="receipt_shipment")
    document = get_shipment(config, shipment_id)
    if document.get("paid_in_full"):
        st.caption("已付清註記 · 僅供篩選，以下金額仍依實際收款紀錄計算。")
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
            editable = {i: r for i, r in active.items() if not r.get('batch_id')}
            if editable:
                with st.expander('修改收款紀錄'):
                    selected = st.selectbox('修改哪筆收款', list(editable), key='receipt_edit_' + shipment_id,
                                             format_func=lambda i: editable[i]['receipt_date'] + ' · ' + editable[i]['amount'] + ' · ' + i[:8])
                    with st.form(f"receipt_edit_{selected}_{document['version']}"):
                        amount_col, reason_col = st.columns([1, 2])
                        corrected = amount_col.number_input('修改收款金額', min_value=1, max_value=1000000000000,
                                                     value=int(editable[selected]['amount']), step=1)
                        reason = reason_col.text_input('修改原因')
                        if st.form_submit_button('儲存收款修改'):
                            try:
                                update_receipt_amount(config, receipt_id=selected, shipment_version=document['version'],
                                                      amount=corrected, reason=reason)
                            except ShipmentError as error:
                                st.error(str(error))
                            else:
                                _batch_receipt_saved(token_key, '收款已修改')
                _receipt_change_history(config, selected)
            with st.expander("作廢收款紀錄"):
                with st.form("receipt_void_" + shipment_id):
                    receipt_col, reason_col = st.columns([3, 2])
                    receipt_id = receipt_col.selectbox("收款紀錄", list(active), format_func=lambda i: active[i]["receipt_date"] + " · " + active[i]["amount"] + " · " + active[i]["method"] + " · " + i[:8])
                    reason = reason_col.text_input("作廢收款原因")
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
