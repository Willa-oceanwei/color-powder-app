import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Color Powder Management")

st.title("🌈 Color Powder Management")

# 檢查 Secrets
if "gcp" not in st.secrets:
    st.warning("❗ 尚未設定 gcp Secrets。請到 Settings → Secrets 設定")
    st.stop()

try:
    gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])
except json.JSONDecodeError as e:
    st.error(f"❌ JSON 格式錯誤：{e}")
    st.stop()

scope = [
    "https://spreadsheets.google/feeds",
    "https://www.googleapis.com/auth/drive",
]

credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scope
)

gc = gspread.authorize(credentials)

st.success("✅ Google Sheets 已連線成功！")

spreadsheet_key = st.text_input("請輸入 Google Sheets Key")

if spreadsheet_key:
    try:
        sh = gc.open_by_key(spreadsheet_key)
        worksheet = sh.worksheet("ColorPowder")
        data = worksheet.get_all_values()
        st.write("🎯 讀取到以下資料：")
        st.dataframe(data)
    except Exception as e:
        st.error(f"讀取失敗：{e}")

