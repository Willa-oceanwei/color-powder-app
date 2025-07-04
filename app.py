# 行 1 - 9：匯入與 Google Sheets 驗證
import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scopes=scope)
gc = gspread.authorize(credentials)

# 行 11 - 18：開啟 Sheet 與分頁
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
try:
    sh = gc.open_by_key(sheet_key)
    st.success("✅ 成功開啟 Google Sheets!")
    worksheet = sh.worksheet("工作表1")
    st.success("✅ 成功開啟 Worksheet!")

    # 行 20：顯示標題與樣式
    st.markdown("<h1 style='color:#0081A7;'>🎨 色粉管理系統</h1>", unsafe_allow_html=True)

    # 行 22 - 40：新增色粉資料輸入表單
    with st.form("color_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            color_code = st.text_input("色粉編號")
            intl_code = st.text_input("國際色號")
            origin = st.text_input("產地")
        with col2:
            color_type = st.selectbox("色粉類別", ["A 色粉", "B 色母", "C 添加劑"])
            spec = st.selectbox("規格", ["A 箱", "B 袋", "C 桶"])
            storage = st.text_input("存放倉庫")
        note = st.text_area("備註")

        submitted = st.form_submit_button("新增色粉資料", use_container_width=True)
        if submitted:
            worksheet.append_row([color_code, intl_code, origin, color_type, spec, storage, note])
            st.success("✅ 資料已新增！")

    # 行 42 - 45：顯示資料表格
    st.markdown("### 📋 色粉總表")
    records = worksheet.get_all_records()
    st.dataframe(records)

except Exception as e:
    st.error(f"發生錯誤: {e}")
