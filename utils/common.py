# utils/common.py
import streamlit as st
import gspread
import json
import pandas as pd
from google.oauth2.service_account import Credentials


# ============================================================
#   1️⃣ 初始化 Google Sheet 連線
# ============================================================

def get_spreadsheet():
    """
    取得 Google Spreadsheet 物件（自動快取於 session_state）。
    若 st.secrets 缺少設定，會回傳 None，但不會讓整個 APP 崩潰。
    """
    # 已快取 → 直接回傳
    if "spreadsheet" in st.session_state:
        return st.session_state["spreadsheet"]

    # secrets 缺東西 → 回傳 None（模組層會 fallback）
    if "gcp" not in st.secrets or "sheet_url" not in st.secrets:
        st.warning("⚠️ st.secrets 缺少 gcp 或 sheet_url 設定，進入離線模式")
        st.session_state["spreadsheet"] = None
        return None

    try:
        # 建立 GCP 憑證
        service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)

        # 連線目標 Google Sheet
        sheet_url = st.secrets["sheet_url"]
        spreadsheet = client.open_by_url(sheet_url)

        # 快取
        st.session_state["spreadsheet"] = spreadsheet
        return spreadsheet

    except Exception as e:
        st.error(f"❌ 無法開啟 Google Sheet：{e}")
        st.session_state["spreadsheet"] = None
        return None


# ============================================================
#   2️⃣ 儲存 DataFrame -> Google Sheet
# ============================================================

def save_df_to_sheet(worksheet, df: pd.DataFrame):
    """將 DataFrame 儲存回 Google 工作表."""
    if worksheet is None:
        st.warning("⚠️ 無法存檔：未連線 Google Sheet")
        return

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    worksheet.clear()
    worksheet.update("A1", values)


# ============================================================
#   3️⃣ 統一初始化 Session State List or Dict
# ============================================================

def ensure_session_keys(defaults: dict):
    """
    確保 session_state 中有指定的 key。
    defaults = { key: default_value }
    """
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
