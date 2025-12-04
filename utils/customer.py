# utils/customer.py
import streamlit as st
import pandas as pd
from .common import get_spreadsheet, save_df_to_sheet, init_states

def show_customer_page():
    """客戶名單主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 讀取或建立 Google Sheet
    try:
        spreadsheet = get_spreadsheet()
        ws_customer = spreadsheet.worksheet("客戶名單")
    except:
        spreadsheet = get_spreadsheet()
        ws_customer = spreadsheet.add_worksheet("客戶名單", rows=100, cols=10)
    
    columns = ["客戶編號", "客戶簡稱", "備註"]
    
    # 安全初始化 form_customer
    if "form_customer" not in st.session_state or not isinstance(st.session_state.form_customer, dict):
        st.session_state.form_customer = {}
    
    # 初始化其他 session_state 變數
    init_states(["edit_customer_index", "delete_customer_index", "show_delete_customer_confirm", "search_customer"])
    
    # 確保所有欄位都有 key
    for col in columns:
        st.session_state.form_customer.setdefault(col, "")
    
    # 載入 Google Sheet 資料
    try:
        df = pd.DataFrame(ws_customer.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)
    
    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    
    # ===== 新增客戶 =====
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🤖新增客戶</h2>',
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號", 
            st.session_state.form_customer["客戶編號"],
            key="input_customer_id"
        )
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱", 
            st.session_state.form_customer["客戶簡稱"],
            key="input_customer_name"
        )
    with col2:
        st.session_state.form_customer["備註"] = st.text_input(
            "備註", 
            st.session_state.form_customer["備註"],
            key="input_customer_note"
        )
    
    if st.button("💾 儲存", key="btn_save_customer"):
        new_data = st.session_state.form_customer.copy()
        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_index is not None:
                df.iloc[st.session_state.edit_customer_index] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增成功！")
            
            save_df_to_sheet(ws_customer, df)
            st.session_state.form_customer = {col: "" for col in columns}
            st.session_state.edit_customer_index = None
            st.rerun()
    
    # 刪除確認
    if st.session_state.show_delete_customer_confirm:
        target_row = df.iloc[st.session_state.delete_customer_index]
        target_text = f'{target_row["客戶編號"]} {target_row["客戶簡稱"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("刪除", key="confirm_delete_customer_yes"):
            df.drop(index=st.session_state.delete_customer_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_customer, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_customer_confirm = False
            st.rerun()
        if c2.button("取消", key="confirm_delete_customer_no"):
            st.session_state.show_delete_customer_confirm = False
            st.rerun()
    
    st.markdown("---")
    
    # ===== 客戶清單（搜尋後顯示表格與操作） =====
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🛠️ 客戶修改/刪除</h2>', unsafe_allow_html=True)
    
    df_filtered = pd.DataFrame()
    
    keyword = st.text_input("請輸入客戶編號或簡稱", st.session_state.get("search_customer_keyword", ""))
    st.session_state.search_customer_keyword = keyword.strip()
    
    if keyword:
        df_filtered = df[
            df["客戶編號"].str.contains(keyword, case=False, na=False) |
            df["客戶簡稱"].str.contains(keyword, case=False, na=False)
        ]
        
        if df_filtered.empty:
            st.warning("● 查無符合的資料")
    
    if not df_filtered.empty:
        st.dataframe(df_filtered[columns], use_container_width=True, hide_index=True)
        
        st.markdown("<hr style='margin-top:10px;margin-bottom:10px;'>", unsafe_allow_html=True)
        
        st.markdown(
            """
            <p style="font-size:14px; font-family:Arial; color:gray; margin-top:-8px;">
                🛈 請於新增欄位修改
            </p>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown("""
            <style>
            div.stButton > button {
                font-size:16px !important;
                padding:2px 8px !important;
                border-radius:8px;
                background-color:#333333 !important;
                color:white !important;
                border:1px solid #555555;
            }
            div.stButton > button:hover {
                background-color:#555555 !important;
                border-color:#dbd818 !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        for i, row in df_filtered.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(
                    f"<div style='font-family:Arial;color:#FFFFFF;'>📹 {row['客戶編號']}　{row['客戶簡稱']}</div>",
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
