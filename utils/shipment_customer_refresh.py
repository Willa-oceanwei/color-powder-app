"""Explicit, field-selective refresh of a shipment's customer snapshot."""

import streamlit as st

from .accounting_widgets import widget_default
from .customer_repository import CONTACT_FIELDS, CustomerError, get_customer


REFRESH_FIELDS = {"customer_name": "客戶名稱", "recipient_name": "指送對象名稱", **CONTACT_FIELDS, "address": "送貨地址"}


def customer_refresh_values(config, customer_id, recipient_id):
    """Read current masters directly, without changing any saved document."""
    customer = get_customer(config, customer_id)
    values = {"customer_name": customer["name"]}
    recipient = customer
    if recipient_id and recipient_id != customer_id:
        recipient = get_customer(config, recipient_id)
    if recipient_id:
        values["recipient_name"] = recipient["name"]
    values.update({field: recipient.get(field) or "" for field in CONTACT_FIELDS})
    return values


def render_customer_refresh(config, document, prefix):
    """Render before delivery/contact widgets so selected values appear at once."""
    state = st.session_state
    recipient_id = str(state.get(prefix + "recipient_id", document.get("recipient_id", "")) or "").strip()
    scope = (repr(config), state.get("shipment_epoch", 0), document.get("id", ""),
             document.get("customer_id", ""), recipient_id)
    preview = state.get("shipment_customer_refresh_preview")
    if preview and preview["scope"] != scope:
        state.pop("shipment_customer_refresh_preview", None)
        preview = None
    with st.popover("更新客戶資料", use_container_width=True):
        st.caption("讀取最新資料、選擇欄位後套用；最後按出貨單的「儲存」才會更新原單。")
        if st.button("讀取最新客戶資料", key="shipment_read_customer_refresh", disabled=not document.get("customer_id")):
            state.pop("shipment_customer_refresh_preview", None)
            preview = None
            try:
                values = customer_refresh_values(config, document["customer_id"], recipient_id)
            except CustomerError as error:
                st.error(str(error))
            except Exception:
                st.error("無法讀取最新客戶資料，請稍後重試；單據內容已保留。")
            else:
                revision = state.get("shipment_customer_refresh_revision", 0) + 1
                state.shipment_customer_refresh_revision = revision
                preview = {"scope": scope, "values": values, "revision": revision}
                state.shipment_customer_refresh_preview = preview
        if not preview:
            return
        current = {field: str(state.get(prefix + field, document.get(field, "")) or "")
                   for field in preview["values"]}
        changes = {field: value for field, value in preview["values"].items() if current[field] != value}
        if not changes:
            st.info("單據資料與這次讀取的客戶資料相同。")
            return
        st.caption(f"客戶：{document['customer_id']}；聯絡／送貨資料來源：{recipient_id or document['customer_id']}")
        st.dataframe([{"欄位": REFRESH_FIELDS[field], "目前單據": current[field] or "（空白）",
                       "最新客戶資料": value or "（空白）"} for field, value in changes.items()],
                     hide_index=True, use_container_width=True)
        selection_key = prefix + f"customer_refresh_fields_{preview['revision']}"
        # Edits made after previewing may eliminate some differences.
        if selection_key in state:
            state[selection_key] = [field for field in state[selection_key] if field in changes]
        selected = st.multiselect("選擇要更新的欄位", list(changes),
            default=widget_default(selection_key, [field for field in changes if field in ("customer_name", "recipient_name")]),
            format_func=lambda field: REFRESH_FIELDS[field], key=selection_key)
        if st.button("套用選取欄位", key="shipment_apply_customer_refresh", disabled=not selected):
            for field in selected:
                document[field] = changes[field]
                if field != "customer_name":
                    state[prefix + field] = changes[field]
            st.success("已套用至目前出貨單草稿，請按「儲存」完成更新。")
