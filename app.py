import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Color Powder Management")

st.title("🌈 Color Powder Management")

# 1️⃣ 檢查 Secrets
if "gcp_credentials" not in st.secrets:
    st.warning("❗尚未設定 gcp_credentials Secrets。請到 Settings → Secrets 設定")
    st.stop()

# 2️⃣ Google Sheets 授權
gcp_info = st.secrets["gcp_credentials"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scope
)
gc = gspread.authorize(credentials)

# 3️⃣ UI - 讓使用者輸入試算表 ID
spreadsheet_key = st.text_input("請輸入 Google Sheets 的 Key（網址中的那一段）")

if spreadsheet_key:
    try:
        sh = gc.open_by_key(spreadsheet_key)
        worksheet = sh.sheet1
        data = worksheet.get_all_values()

        st.success("✅ 成功讀取資料")
        st.write("📄 表單內容如下：")
        st.dataframe(data)

    except Exception as e:
        st.error(f"讀取失敗：{e}")
