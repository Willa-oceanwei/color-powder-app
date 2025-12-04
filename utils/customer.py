# utils/customer.py
import streamlit as st
import pandas as pd
from .common import get_spreadsheet, save_df_to_sheet, ensure_session_keys


def show_customer_page():
    """客戶名單【主功能頁】"""

    # ===== CSS：縮小上邊界 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===== 初始化 session_state =====
    ensure_session_keys({
        "form_customer": {"客戶編號": "", "客戶簡稱": "", "備註": ""},
        "edit_customer_index": None,
        "delete_customer_index": None,
        "show_delete_customer_confirm": False,
        "search_customer_keyword": "",
    })

    # ===== 讀取 Google Sheet =====
    spreadsheet = get_spreadsheet()
    if spreadsheet:
        # 能正常連線
        try:
            ws_customer = spreadsheet.worksheet("客戶名單")
        except:
            ws_customer = spreadsheet.add_worksheet("客戶名單", rows=200, cols=10)

        try:
            df = pd.DataFrame(ws_customer.get_all_records())
        except:
            df = pd.DataFrame(columns=["客戶編號", "客戶簡稱", "備註"])
    else:
        # 無法連線 → 建立空的本地 DataFrame（避免整頁爆炸）
        st.warning("⚠️ 無法連線 Google Sheet，已改用本地暫存資料（不會儲存）")
        df = pd.DataFrame(columns=["客戶編號", "客戶簡稱", "備註"])

    df = df.astype(str)
    for col in ["客戶編號", "客戶簡稱", "備註"]:
        if col not in df.columns:
            df[col] = ""

    # ============================================================
    #                     🟦 新增客戶
    # ============================================================

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🤖 新增客戶</h2>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state.form_customer["客戶編號"],
            key="cust_id"
        )
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state.form_customer["客戶簡稱"],
            key="cust_name"
        )
    with col2:
        st.session_state.form_customer["備註"] = st.text_input(
            "備註",
            st.session_state.form_customer["備註"],
            key="cust_note"
        )

    if st.button("💾 儲存", key="save_customer"):
        new = st.session_state.form_customer.copy()
        if new["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_index is not None:
                # 修改現有
                df.iloc[st.session_state.edit_customer_index] = new
                st.success("✅ 客戶資料已更新")
            else:
                # 新增
                if new["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                    st.success("✅ 新增成功！")

            # 存回 Google Sheet（若連得上）
            if spreadsheet:
                save_df_to_sheet(ws_customer, df)

            # 清空欄位
            st.session_state.form_customer = {"客戶編號": "", "客戶簡稱": "", "備註": ""}
            st.session_state.edit_customer_index = None
            st.rerun()

    # ============================================================
    #                     🟥 刪除確認
    # ============================================================
    if st.session_state.show_delete_customer_confirm:
        idx = st.session_state.delete_customer_index
        target = df.iloc[idx]

        st.warning(f"⚠️ 確定要刪除 {target['客戶編號']} {target['客戶簡稱']}？")

        c1, c2 = st.columns(2)
        if c1.button("刪除", key="confirm_delete_yes"):
            df.drop(index=idx, inplace=True)
            df.reset_index(drop=True, inplace=True)

            if spreadsheet:
                save_df_to_sheet(ws_customer, df)

            st.success("✅ 刪除完成")
            st.session_state.show_delete_customer_confirm = False
            st.rerun()

        if c2.button("取消", key="confirm_delete_no"):
            st.session_state.show_delete_customer_confirm = False
            st.rerun()

    st.markdown("---")

    # ============================================================
    #                 🟧 客戶清單（搜尋 + 修改/刪除）
    # ============================================================

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🛠️ 客戶修改 / 刪除</h2>',
        unsafe_allow_html=True
    )

    keyword = st.text_input(
        "請輸入客戶編號或簡稱",
        st.session_state.search_customer_keyword,
        key="search_customer_input"
    )
    st.session_state.search_customer_keyword = keyword.strip()

    if keyword.strip():
        df_filtered = df[
            df["客戶編號"].str.contains(keyword, case=False, na=False) |
            df["客戶簡稱"].str.contains(keyword, case=False, na=False)
        ]
    else:
        df_filtered = pd.DataFrame()

    if df_filtered.empty:
        st.info("🔍 輸入關鍵字以開始搜尋")
        return

    # 顯示表格
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # 操作列
    for i, row in df_filtered.iterrows():
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(
                f"<div style='font-family:Arial; color:white;'>📁 {row['客戶編號']}　{row['客戶簡稱']}</div>",
                unsafe_allow_html=True
            )
        with c2:
            if st.button("✏️ 改", key=f"edit_customer_{i}"):
                st.session_state.edit_customer_index = i
                st.session_state.form_customer = row.to_dict()
                st.rerun()
        with c3:
            if st.button("🗑️ 刪", key=f"delete_customer_{i}"):
                st.session_state.delete_customer_index = i
                st.session_state.show_delete_customer_confirm = True
                st.rerun()
