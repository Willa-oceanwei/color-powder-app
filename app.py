# ==============================
# 1~9 匯入與驗證
# ==============================

import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# 定義 Google Sheets 權限範圍
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 讀取 Secrets 中 JSON
gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])

# 建立憑證
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)

# 授權
gc = gspread.authorize(credentials)

# ==============================
# 10~19 開啟 Sheet
# ==============================

sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"

try:
    sh = gc.open_by_key(sheet_key)
    st.success("✅ 成功開啟 Google Sheets!")
    worksheet = sh.worksheet("工作表1")
    st.success("✅ 成功開啟 Worksheet!")

# ==============================
# 20 標題 + CSS
# ==============================

    st.markdown("""
        <style>
        .main-title { color: #0081A7; font-size: 40px; font-weight: bold;}
        .btn-modify { background-color: #00AFB9; color: white;}
        .btn-delete { background-color: #F07167; color: white;}
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='main-title'>🎨 色粉管理系統</div>", unsafe_allow_html=True)

# ==============================
# 22~28 搜尋框
# ==============================

    records = worksheet.get_all_records()

    search_code = st.text_input("🔍 請輸入色粉編號進行搜尋")

    if search_code:
        filtered = [rec for rec in records if rec["色粉編號"] == search_code]
        st.write("搜尋結果：")
        st.dataframe(filtered)

# ==============================
# 30~50 新增色粉表單
# ==============================

    with st.form("color_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            color_code = st.text_input("色粉編號")
            intl_code = st.text_input("國際色號")
            origin = st.text_input("產地")
        with col2:
            color_type = st.selectbox("色粉類別", ["A", "B", "C"])
            spec = st.text_input("品名規格")
            storage = st.text_input("存放倉庫")
        note = st.text_area("備註")

        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("新增色粉資料")
        with c2:
            cancel = st.form_submit_button("取消")

    if cancel:
        st.experimental_rerun()

    if submitted:
        existing_codes = [rec["色粉編號"] for rec in records]
        if color_code in existing_codes:
            st.warning("⚠️ 編號重複！請改用其他編號。")
        else:
            worksheet.append_row([color_code, intl_code, origin, color_type, spec, storage, note])
            st.success("✅ 資料已新增！")
            st.experimental_rerun()

# ==============================
# 52~70 顯示色粉清單 + 編輯/刪除
# ==============================

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

    st.markdown("### 📋 色粉總表")

    # 顯示橫式 DataFrame
st.markdown("### 📋 色粉總表")

if not df.empty:
    st.dataframe(
        df.style.set_properties(**{
            'text-align': 'left'
        }),
        use_container_width=True
    )
else:
    st.info("目前無任何色粉資料。")

# 顯示編輯 / 刪除按鈕
for idx, row in df.iterrows():
    col1, col2 = st.columns([8, 2])
    with col1:
        st.write(f"➡️ 色粉編號：{row['色粉編號']} ｜ 國際色號：{row['國際色號']} ｜ 產地：{row['產地']} ｜ 類別：{row['色粉類別']}")
    with col2:
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("✏️ 修改", key=f"edit_{idx}"):
                st.session_state["edit_row"] = idx
        with btn2:
            if st.button("🗑️ 刪除", key=f"delete_{idx}"):
                worksheet.delete_rows(idx + 2)
                st.success("✅ 已刪除資料")
                st.experimental_rerun()

# ==============================
# 72~90 編輯表單
# ==============================

    if "edit_row" in st.session_state:
        row_idx = st.session_state["edit_row"]
        row_data = df.iloc[row_idx]

        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            with col1:
                color_code = st.text_input("色粉編號", value=row_data["色粉編號"])
                intl_code = st.text_input("國際色號", value=row_data["國際色號"])
                origin = st.text_input("產地", value=row_data["產地"])
            with col2:
                color_type = st.selectbox("色粉類別", ["A", "B", "C"], index=["A", "B", "C"].index(row_data["色粉類別"]))
                spec = st.text_input("品名規格", value=row_data["品名規格"])
                storage = st.text_input("存放倉庫", value=row_data["存放倉庫"])
            note = st.text_area("備註", value=row_data["備註"])

            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("確認修改"):
                    worksheet.update(
                        f"A{row_idx + 2}",
                        [[color_code, intl_code, origin, color_type, spec, storage, note]]
                    )
                    del st.session_state["edit_row"]
                    st.success("✅ 資料已修改！")
                    st.experimental_rerun()
            with c2:
                if st.form_submit_button("取消修改"):
                    del st.session_state["edit_row"]
                    st.experimental_rerun()

except Exception as e:
    st.error(f"發生錯誤: {e}")

