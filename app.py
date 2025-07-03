import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Color Powder Management")

st.title("🌈 Color Powder Management")

# 1️⃣ 讀取 Secrets
if "gcp_credentials" in st.secrets:
    gcp_json = st.secrets["gcp_credentials"]
    gcp_info = json.loads(gcp_json)

    # 2️⃣ 建立 Google Sheets 連線
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        gcp_info, scope
    )
    gc = gspread.authorize(credentials)

    # 3️⃣ 開啟 Google Sheets
    spreadsheet_key = st.text_input("輸入 Google Sheets Key")
    if spreadsheet_key:
        try:
            sh = gc.open_by_key(spreadsheet_key)
            worksheet = sh.sheet1

            # 4️⃣ 抓資料
            data = worksheet.get_all_values()

            # 顯示資料
            st.write("✅ 抓到的資料：", data)

        except Exception as e:
            st.error(f"讀取 Google Sheets 錯誤：{e}")
else:
    st.warning("⚠️ Secrets 裡沒有 gcp_credentials！")

