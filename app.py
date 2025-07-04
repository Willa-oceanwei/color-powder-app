import streamlit as st
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ========== 1. 讀取 secrets.toml 中的 base64 json ==========
b64_key = st.secrets["gcp"]["gcp_json_base64"]

# decode base64 → json string
json_str = base64.b64decode(b64_key).decode("utf-8")

# load json
gcp_info = json.loads(json_str)

# ========== 2. 建立憑證 ==========
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info,
    scopes=scope
)

# ========== 3. 連線 Google Sheet ==========
gc = gspread.authorize(credentials)

# 從 secrets 拿 spreadsheet url
sheet_url = st.secrets["gcp"]["spreadsheet_url"]

# 開啟 spreadsheet
sh = gc.open_by_url="https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit?gid=0#gid=0"

# 假設第一個工作表
worksheet = sh.worksheet("工作表1")

# ========== 4. 測試讀寫 ==========
# 讀第 1 列
data = worksheet.row_values(1)

st.write("第 1 列資料：", data)

# 寫一筆資料（例如寫到 A10, B10）
worksheet.update("A10", [["Hello", "Streamlit"]])

st.success("已更新 Google Sheet！")
