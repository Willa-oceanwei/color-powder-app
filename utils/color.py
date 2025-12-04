# utils/color.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from .common import get_spreadsheet, save_df_to_sheet, init_states

def show_color_page():
    """色粉管理主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 讀取工作表
    try:
        spreadsheet = get_spreadsheet()
        worksheet = spreadsheet.worksheet("色粉管理")
    except Exception as e:
        st.error(f"無法連線 Google Sheet：{e}")
        return
    
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    
    # 初始化 session_state
    if "form_color" not in st.session_state:
        st.session_state.form_color = {col: "" for col in required_columns}
    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None
    if "delete_color_index" not in st.session_state:
        st.session_state.delete_color_index = None
    if "show_delete_color_confirm" not in st.session_state:
        st.session_state.show_delete_color_confirm = False
    if "search_color" not in st.session_state:
        st.session_state.search_color = ""
    
    # 讀取資料
    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except:
        df = pd.DataFrame(columns=required_columns)
    
    df = df.astype(str)
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    
    # ===== 新增色粉 =====
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818; margin:0 0 10px 0;">🪅新增色粉</h2>',
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input(
            "色粉編號", 
            st.session_state.form_color["色粉編號"],
            key="input_color_id"
        )
        st.session_state.form_color["國際色號"] = st.text_input(
            "國際色號", 
            st.session_state.form_color["國際色號"],
            key="input_intl_code"
        )
        st.session_state.form_color["名稱"] = st.text_input(
            "名稱", 
            st.session_state.form_color["名稱"],
            key="input_name"
        )
    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox(
            "色粉類別", 
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(st.session_state.form_color["色粉類別"]) 
                if st.session_state.form_color["色粉類別"] in ["色粉", "色母", "添加劑"] else 0,
            key="select_type"
        )
        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝", 
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(st.session_state.form_color["包裝"]) 
                if st.session_state.form_color["包裝"] in ["袋", "箱", "kg"] else 0,
            key="select_pack"
        )
        st.session_state.form_color["備註"] = st.text_input(
            "備註", 
            st.session_state.form_color["備註"],
            key="input_note"
        )
    
    if st.button("💾 儲存", key="btn_save_color"):
        new_data = st.session_state.form_color.copy()
        if new_data["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_color_index is not None:
                idx = st.session_state.edit_color_index
                for col in df.columns:
                    df.at[idx, col] = new_data.get(col, "")
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data], columns=df.columns)], ignore_index=True)
                    st.success("✅ 新增成功！")
            
            save_df_to_sheet(worksheet, df)
            st.session_state.form_color = {col: "" for col in required_columns}
            st.session_state.edit_color_index = None
            st.rerun()
    
    # 刪除確認
    if st.session_state.show_delete_color_confirm:
        target_row = df.iloc[st.session_state.delete_color_index]
        target_text = f'{target_row["色粉編號"]} {target_row["名稱"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("刪除", key="confirm_delete_yes"):
            df.drop(index=st.session_state.delete_color_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(worksheet, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_color_confirm = False
            st.rerun()
        if c2.button("取消", key="confirm_delete_no"):
            st.session_state.show_delete_color_confirm = False
            st.rerun()
    
    st.markdown("---")
    
    # ===== 色粉清單（搜尋後顯示表格與操作） =====
    st.markdown(
        """
        <h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🛠️ 色粉修改 / 刪除</h2>
        """,
        unsafe_allow_html=True
    )
    
    # 搜尋輸入框
    keyword = st.text_input(
        "輸入色粉編號或名稱搜尋", 
        value=st.session_state.search_color,
        key="search_color_input"
    )
    st.session_state.search_color = keyword.strip()
    
    df_filtered = pd.DataFrame()
    
    if keyword:
        df_filtered = df[
            df["色粉編號"].str.contains(keyword, case=False, na=False) |
            df["名稱"].str.contains(keyword, case=False, na=False) |
            df["國際色號"].str.contains(keyword, case=False, na=False)
        ]
        
        if df_filtered.empty:
            st.warning("● 查無符合的資料")
        else:
            display_cols = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝"]
            existing_cols = [c for c in display_cols if c in df_filtered.columns]
            df_display = df_filtered[existing_cols].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            st.markdown(
                """
                <p style="font-size:14px; font-family:Arial; color:gray; margin-top:-8px;">
                    🛈 請於新增欄位修改
                </p>
                """,
                unsafe_allow_html=True
            )
            
            # 按鈕樣式
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
                        f"<div style='font-family:Arial; color:#FFFFFF;'>📸 {row['色粉編號']}　{row['名稱']}</div>",
                        unsafe_allow_html=True
                    )
                
                with c2:
                    if st.button("✏️ 改", key=f"edit_color_{i}"):
                        st.session_state.edit_color_index = i
                        st.session_state.form_color = row.to_dict()
                        st.rerun()
                
                with c3:
                    if st.button("🗑️ 刪", key=f"delete_color_{i}"):
                        st.session_state.delete_color_index = i
                        st.session_state.show_delete_color_confirm = True
                        st.rerun()
