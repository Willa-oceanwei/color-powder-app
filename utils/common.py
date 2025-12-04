# utils/common.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ================================
# 1️⃣ 建立 Google Sheet 連線
# ================================
def get_spreadsheet():
    """取得已連線的 Google Spreadsheet，若不存在則建立。"""

    # 如果 app.py 已經建立就直接使用
    if "spreadsheet" in st.session_state:
        return st.session_state["spreadsheet"]

    # 若沒有，這裡重新建立（保險做法）
    try:
        service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
    except Exception as e:
        st.error(f"❗ Google 授權失敗：{e}")
        st.stop()

    # Sheet URL
    if "sheet_url" not in st.secrets:
        st.error("❗ st.secrets 缺少 sheet_url，請加入：\nsheet_url='你的 Google Sheet URL'")
        st.stop()

    try:
        spreadsheet = client.open_by_url(st.secrets["sheet_url"])
        st.session_state["spreadsheet"] = spreadsheet
        return spreadsheet
    except Exception as e:
        st.error(f"❗ 無法開啟 Google Sheet：{e}")
        st.stop()

# ================================
# 2️⃣ 將 DataFrame 寫回 Google Sheet
# ================================
def save_df_to_sheet(worksheet, df: pd.DataFrame):
    """將 DataFrame 全面覆蓋寫回 Google Sheet 工作表"""
    worksheet.clear()
    if df.empty:
        return
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# ================================
# 3️⃣ 初始化 session_state 中的變數
# ================================
def init_states(keys):
    """安全初始化 session_state 中的多個 key"""
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = None
