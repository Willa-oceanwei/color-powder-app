"""Explicit, preview-first naming consolidation for wash-facility inventory."""
import hashlib
import json
import pandas as pd
import streamlit as st

from .carwash_inventory_repository import CarwashInventoryError, carwash_sheet_payload
from .carwash_product_repository import canonical_name, preview_carwash_merge, merge_carwash_names, carwash_merge_history
from .carwash_query import carwash_query_rows


def movement_frame(records):
    columns = ["類型", "初始庫存日期", "初始數量", "貨品編號", "入庫日期", "出庫日期", "數量", "單位", "登記人", "備註", "_sync_id"]
    return pd.DataFrame([carwash_sheet_payload(row) for row in records], columns=columns).fillna("")


def render_carwash_merge(config, movements, aliases):
    identity = hashlib.sha256(repr(config).encode()).hexdigest()
    st.caption("只建立編號對應與合併檢視；原始編號、數量、日期及各自的初始庫存計算都保留。")
    names = sorted({canonical_name(row["product_id"], aliases) for row in movements})
    if len(names) >= 2:
        left, right = st.columns(2)
        source = left.selectbox("要合併的編號", names, key="cw_merge_source")
        target = right.selectbox("保留的正式編號", names, index=1, key="cw_merge_target")
        if st.button("預覽合併", key="cw_merge_preview_button"):
            try:
                preview = preview_carwash_merge(config, source, target)
            except CarwashInventoryError as error:
                st.error(str(error))
            except Exception:
                st.error("合併預覽讀取失敗，請稍後重試；原資料未更動。")
            else:
                st.session_state["cw_merge_preview"] = dict(preview, config=identity)
        preview = st.session_state.get("cw_merge_preview")
        if preview and (preview.get("config") != identity or (preview["source"], preview["target"]) != (source, target)):
            preview = None
            st.session_state.pop("cw_merge_preview", None)
        if preview:
            frame = carwash_query_rows(movement_frame(preview["records"]))
            counts = pd.Series([str(row["product_id"]).strip() for row in preview["records"]]).value_counts()
            display = frame[["產品編號", "期初庫存", "區間入庫", "區間出庫", "目前庫存", "單位"]].copy()
            display["紀錄筆數"] = display["產品編號"].map(counts).fillna(0).astype(int)
            st.dataframe(display, hide_index=True, use_container_width=True)
            total = frame["_目前庫存數值"].sum()
            st.metric("合併顯示後目前庫存", f"{total:g} {frame.iloc[0]['單位']}")
            st.caption("合併只加總上方原有結果。今後初始庫存仍依各原編號的基準計算，不會互相覆蓋。")
            initial_ok = True
            if preview["needs_initial_confirmation"]:
                st.warning("兩邊都有初始庫存。如果是同一批重複登錄，請先到資料修改查核；這裡不會自動刪除或抵銷。")
                initial_ok = st.toggle("我確認兩邊是不同批庫存，要保留並加總原有餘額",
                                       key="cw_merge_initial_" + preview["token"])
            actor = st.selectbox("登記人", ["德", "Q"], key="cw_merge_actor")
            confirmed = st.toggle("確認是同一貨品，並保留所有原始紀錄", key="cw_merge_confirm_" + preview["token"])
            if st.button("確認合併編號", type="primary", key="cw_merge_commit", disabled=not (confirmed and initial_ok)):
                try:
                    merge_carwash_names(config, source, target, preview["token"], actor=actor, confirm_initials=initial_ok)
                except CarwashInventoryError as error:
                    st.error(str(error))
                except Exception:
                    st.error("合併未完成，請重新預覽後再試；原始庫存紀錄未改動。")
                else:
                    for key in ("cw_merge_preview", "cw_inventory_result_df", "cw_inventory_result_message", "cw_alias_signature"):
                        st.session_state.pop(key, None)
                    st.session_state["carwash_toast"] = {"msg": f"已將 {source} 歸戶至 {target}，原始紀錄保留", "icon": "✅"}
                    st.rerun()
    else:
        st.info("至少需要兩個有庫存紀錄的編號，才能預覽合併。")
    with st.expander("編號對應與合併紀錄", expanded=False):
        if aliases:
            st.dataframe(pd.DataFrame([{"舊編號": row["alias_name"], "正式編號": row["canonical_name"]} for row in aliases]),
                         hide_index=True, use_container_width=True)
        history = carwash_merge_history(config)
        if history:
            history_frame = pd.DataFrame(history)
            history_frame["members_json"] = history_frame["members_json"].map(lambda value: "、".join(json.loads(value)))
            history_frame["created_at"] = pd.to_datetime(history_frame["created_at"], utc=True).dt.tz_convert("Asia/Taipei").dt.strftime("%Y/%m/%d %H:%M:%S")
            st.dataframe(history_frame.rename(columns={"source_name": "原群組", "target_name": "正式編號",
                         "actor": "登記人", "created_at": "合併時間", "members_json": "涉及編號"}).drop(columns=["merge_id"]),
                         hide_index=True, use_container_width=True)
