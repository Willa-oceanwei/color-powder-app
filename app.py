import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# 定義 Google Sheets 權限範圍
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 讀取 Secrets 中的 JSON 字串
gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])

# 建立憑證
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)

# 授權
gc = gspread.authorize(credentials)

# 用 spreadsheet key 開啟
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"

try:
    sh = gc.open_by_key(sheet_key)
    st.success("✅ 成功開啟 Google Sheets!")
    st.write(sh)

    # 若分頁名稱叫「工作表1」
    worksheet = sh.worksheet("工作表1")
    st.success("✅ 成功開啟 Worksheet!")
    st.write(worksheet)

    # 讀取資料（改用漂亮的 DataFrame 顯示）
    import pandas as pd
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    st.dataframe(df)


except Exception as e:
    st.error("發生錯誤：")
    st.write("Exception string：", str(e))
    st.write("Exception repr：", repr(e))
    import traceback
    st.code(traceback.format_exc())
