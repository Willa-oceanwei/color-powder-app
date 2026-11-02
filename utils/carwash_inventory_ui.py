"""Save confirmation for the wash-facility inventory ledger."""

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from .carwash_inventory_repository import calculate_carwash_inventory_balances


@st.dialog("入／出庫儲存成功")
def show_carwash_save_notice(notice, movements, *, aliases=None):
    """Show committed, current balances without submitting the entry again."""
    product_id = notice["product_id"]
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    balances = calculate_carwash_inventory_balances(movements, as_of=today)
    quantity, unit = balances.get(product_id.strip().casefold(), (0, notice["unit"]))
    st.success(f"已登錄{notice['movement_type']}：{product_id} "
               f"{notice['quantity']:g} {notice['unit']}")
    st.metric("目前洗車廠庫存", f"{quantity:,.2f} {unit}")
    st.caption(f"貨品編號：{product_id}｜截至 {today:%Y/%m/%d}")
    if aliases:
        from .carwash_product_repository import canonical_name, name_key
        canonical = canonical_name(product_id, aliases)
        member_keys = {name_key(row["product_id"]) for row in movements
                       if name_key(canonical_name(row["product_id"], aliases)) == name_key(canonical)}
        units = {str(row["unit"] or "").strip().upper() for row in movements
                 if name_key(row["product_id"]) in member_keys}
        if len(member_keys) > 1 and len(units) == 1:
            total = sum(balances.get(key, (0, unit))[0] for key in member_keys)
            st.metric(f"合併顯示庫存 · {canonical}", f"{total:,.2f} {unit}")
            st.caption("上方原編號結果保持不變；合併顯示只加總各原編號庫存。")

    if notice.get("movement_date", "") > today.isoformat():
        st.info("這筆是未來日期的登錄，目前庫存尚未計入。")
    if notice.get("transfer_note"):
        st.caption(notice["transfer_note"].lstrip("，"))
    if st.button("確定", key="cw_save_notice_close", use_container_width=True):
        st.rerun()
