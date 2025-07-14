import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os

# ========== Debug print ==========
st.write("✅ Debug Info: 執行的 app.py 路徑:", os.path.abspath(__file__))

# ========== Sidebar with expander ==========
with st.sidebar:
    st.title("🎨 管理選單")
    with st.expander("👉 點此展開 / 收合模組選擇", expanded=True):
        st.write("✅ Sidebar 區塊已修改，支援收合。")
        module_choice = st.radio(
            "請選擇模組",
            ["色粉管理", "客戶名單"],
            key="module_choice"
        )

# ========= 模擬 Gspread 初始化 (略) =========

# 以下省略色粉管理模組程式

# ========== 客戶名單 模組 ==========
if module_choice == "客戶名單":

    st.header("📋 客戶名單")

    # 測試用資料
    df_customer = pd.DataFrame(
        [
            {"客戶編號": "C001", "客戶簡稱": "ABC", "備註": "測試"},
            {"客戶編號": "C002", "客戶簡稱": "XYZ", "備註": "Hello"},
        ]
    )

    # ========== 客戶清單列表 ==========
    for i, row in df_customer.iterrows():
        cols = st.columns([3, 3, 3, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])

        with cols[3]:
            st.write("✅ 橫排測試區 (客戶名單按鈕)")

            # 修正：在同一橫列放兩個按鈕
            col_edit, col_delete = st.columns(2, gap="small")
            
            with col_edit:
                if st.button("✏️ 修改", key=f"edit_cust_{i}"):
                    st.write(f"✅ 點擊修改：{row.to_dict()}")
            
            with col_delete:
                if st.button("🗑️ 刪除", key=f"del_cust_{i}"):
                    st.write(f"✅ 點擊刪除：{row.to_dict()}")

    st.write("✅ Debug Info: 客戶名單模組已渲染完畢。")

