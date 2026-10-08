"""Compact Streamlit product master editor."""

from copy import deepcopy

import streamlit as st

from .product_repository import (
    ProductError, blank_product, list_products, product_references, product_from_recipe, save_product, set_product_active,
)
from .shipment_repository import TAX_MODES
from .shipment_ui import COMPACT_STYLE
from .accounting_widgets import widget_default


def _begin(document):
    st.session_state.product_draft = deepcopy(document)
    if document.get("version"):
        st.session_state.product_draft["original_id"] = document["product_id"]
    st.session_state.product_epoch = st.session_state.get("product_epoch", 0) + 1
    st.session_state.pop("product_delete_open", None)


def _cancel(message="已取消修改"):
    st.session_state.pop("product_draft", None)
    st.session_state.pop("product_delete_open", None)
    st.session_state.product_notice = message


def _finish(message=""):
    _cancel(message)
    st.rerun()


def _fill_recipe(prefix, recipes):
    draft = st.session_state.product_draft
    code = st.session_state.get(prefix + "recipe_id", "")
    if not draft.get("version") and code:
        if not st.session_state.get(prefix + "product_id", ""):
            st.session_state[prefix + "product_id"] = code
        if not st.session_state.get(prefix + "name", ""):
            st.session_state[prefix + "name"] = recipes[code]["color"] or code
        defaults = product_from_recipe(recipes[code])
        for field in ("specification", "base_unit", "sales_unit"):
            st.session_state[prefix + field] = defaults[field]


def _open_recipe(config, recipe):
    existing = next((p for p in list_products(config, include_inactive=True)
                     if p["product_id"] == recipe["recipe_id"].upper()), None)
    if existing:
        st.session_state.product_selected = existing["product_id"]
        st.session_state.product_search = ""
        st.session_state.product_show_inactive = existing["lifecycle_status"] != "active"
        if existing["lifecycle_status"] == "active":
            _begin(existing)
    else:
        _begin(product_from_recipe(recipe))


def render_product_management(config):
    st.markdown(COMPACT_STYLE.replace("shipment-page", "product-page").replace("shipment-toolbar", "product-toolbar"), unsafe_allow_html=True)
    st.subheader("貨品")
    notice = st.session_state.pop("product_notice", "")
    if notice:
        st.caption(notice)
    draft = st.session_state.get("product_draft")
    editing = draft is not None
    recipes, suppliers = product_references(config)
    with st.expander("查詢／配方定價", expanded=True):
        search, status = st.columns([4, 1])
        query = search.text_input("貨品編號 / 名稱 / 配方 / 規格", key="product_search", disabled=editing)
        include_inactive = status.toggle("包含已刪除", key="product_show_inactive", disabled=editing)
        active_recipes = {r["recipe_id"]: r for r in recipes if r["lifecycle_status"] == "active"}
        picker, open_col = st.columns([4, 1])
        code = picker.selectbox("查找現有配方編號", [""] + list(active_recipes),
                                format_func=lambda c: f"{c} · {active_recipes[c]['color']}" if c else "選擇配方",
                                key="product_recipe_search", disabled=editing)
        open_col.button("補上定價", key="product_recipe_open", disabled=editing or not code,
                        on_click=_open_recipe, args=(config, active_recipes.get(code)))
    records = list_products(config, query=query, include_inactive=include_inactive)
    ids = [row["product_id"] for row in records]
    selected = st.session_state.get("product_selected")
    index = ids.index(selected) if selected in ids else 0
    document = draft if editing else records[index] if records else None
    if not editing and document:
        st.session_state.product_selected = document["product_id"]
    active = bool(document and document.get("lifecycle_status", "active") == "active")
    tools = st.columns([1, 1, 1, 1, 1.1, 1, 1, 1, 1, .85])
    tools[0].button("新增", key="product_new", disabled=editing, use_container_width=True, on_click=_begin, args=(blank_product(),))
    tools[1].button("修改", key="product_edit", disabled=editing or not active, use_container_width=True, on_click=_begin, args=(document,))
    if tools[2].button("刪除", key="product_delete", disabled=editing or not active, use_container_width=True):
        st.session_state.product_delete_open = document["product_id"]
    tools[3].button("取消", key="product_cancel", disabled=not editing, use_container_width=True, on_click=_cancel)
    save_clicked = tools[4].button("儲存", key="product_save", type="primary", disabled=not editing, use_container_width=True)
    for col, label, target in ((tools[5], "首筆", 0), (tools[6], "上一筆", index - 1),
                               (tools[7], "下一筆", index + 1), (tools[8], "尾筆", len(ids) - 1)):
        if col.button(label, key="product_nav_" + label, use_container_width=True,
                      disabled=editing or not ids or target < 0 or target >= len(ids) or target == index):
            st.session_state.product_selected = ids[target]
            st.session_state.pop("product_delete_open", None)
            st.rerun()
    tools[9].markdown(f'<span id="product-toolbar" style="font-size:12px">{index + 1 if ids else 0} / {len(ids)}</span>', unsafe_allow_html=True)
    if not document:
        st.info("目前沒有貨品")
        return
    if editing:
        st.caption("編輯中 · 尚未儲存")
    elif not active:
        st.warning("已刪除：" + document.get("delete_reason", ""))
        if st.button("恢復貨品", key="product_restore"):
            try:
                set_product_active(config, document["product_id"], document["version"], active=True)
                _finish("已恢復貨品")
            except ProductError as exc:
                st.error(str(exc))
    if not editing and st.session_state.get("product_delete_open") == document["product_id"]:
        with st.form("product_delete_confirm"):
            reason = st.text_input("刪除原因")
            confirm = st.toggle("確認刪除此貨品，保留歷史單據")
            if st.form_submit_button("確認刪除"):
                try:
                    if not confirm:
                        raise ProductError("請勾選確認刪除")
                    set_product_active(config, document["product_id"], document["version"], active=False, reason=reason)
                    _finish("已刪除貨品，歷史單據保留")
                except ProductError as exc:
                    st.error(str(exc))
    prefix = f"product_{st.session_state.get('product_epoch', 0)}_" if editing else f"product_view_{document['product_id']}_{document['version']}_"

    def text(col, label, field, *, disabled=False):
        value = col.text_input(label, value=widget_default(prefix + field, str(document.get(field) or "")), key=prefix + field, disabled=not editing or disabled)
        if editing:
            document[field] = value

    def number(col, label, field):
        value = col.number_input(label, min_value=0.0, max_value=1e12, value=widget_default(prefix + field, float(document.get(field) or 0)),
                                 step=1.0, format="%.15g", key=prefix + field, disabled=not editing)
        if editing:
            document[field] = str(value)

    by_recipe = {row["recipe_id"]: row for row in recipes if row["lifecycle_status"] == "active" or row["recipe_id"] == document["recipe_id"]}
    by_supplier = {row["supplier_id"]: row for row in suppliers if row["lifecycle_status"] == "active" or row["supplier_id"] == document["supplier_id"]}
    header = st.columns([1.4, 2.5, 2])
    text(header[0], "貨品編號", "product_id", disabled=bool(document.get("version")))
    text(header[1], "貨品名稱", "name")
    recipe_id = header[2].selectbox("關聯配方", [""] + list(by_recipe),
                                    index=widget_default(prefix + "recipe_id", document["recipe_id"]),
                                    format_func=lambda key: f"{key} · {by_recipe[key]['color']}" if key else "無關聯配方",
                                    key=prefix + "recipe_id", disabled=not editing, on_change=_fill_recipe, args=(prefix, by_recipe))
    if editing:
        document["recipe_id"] = recipe_id
    basic, pricing = st.tabs(["基本資料與規格", "成本與定價"])
    with basic:
        row = st.columns(3)
        text(row[0], "類別編號 / 名稱", "category")
        supplier_options = [""] + list(by_supplier)
        supplier_id = row[1].selectbox("供應商", supplier_options, index=widget_default(prefix + "supplier_id", document["supplier_id"]),
                                       format_func=lambda key: f"{key} · {by_supplier[key]['name']}" if key else "未指定",
                                       key=prefix + "supplier_id", disabled=not editing)
        if editing:
            document["supplier_id"] = supplier_id
        text(row[2], "基本單位", "base_unit")
        row = st.columns([2, 1, 1])
        text(row[0], "規格", "specification")
        text(row[1], "內包裝單位", "inner_unit")
        number(row[2], "內包裝容量（基本單位）", "inner_quantity")
        row = st.columns([1, 2, 2])
        text(row[0], "銷售單位", "sales_unit")
        text(row[1], "備註", "notes")
        if not editing:
            row[2].caption(f"建立：{document['created_at']}\n\n更新：{document['updated_at']}")
    with pricing:
        row = st.columns(3)
        for col, label, field in zip(row, ("標準成本", "期初成本", "現行成本"), ("standard_cost", "opening_cost", "current_cost")):
            number(col, label, field)
        for labels, fields in ((('標準售價', '售價 A', '售價 B'), ('standard_price', 'price_a', 'price_b')),):
            row = st.columns(3)
            for col, label, field in zip(row, labels, fields):
                number(col, label, field)
        row = st.columns([1, 1, 2])
        mode = row[0].selectbox("定價課稅方式", TAX_MODES, index=widget_default(prefix + "tax_mode", document["tax_mode"]), key=prefix + "tax_mode", disabled=not editing)
        if editing:
            document["tax_mode"] = mode
        row[1].text_input("幣別", value="TWD", disabled=True)
        row[2].text_input("售價計價單位", value=document["sales_unit"], disabled=True)
    if save_clicked:
        try:
            saved = save_product(config, document)
            st.session_state.product_selected = saved["product_id"]
            _finish("貨品已儲存")
        except ProductError as exc:
            st.error(str(exc))
