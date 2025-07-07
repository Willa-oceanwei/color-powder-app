import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# ======== GOOGLE SHEETS AUTH ========

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 從 secrets 抓 service account JSON
gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])

# 認證
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)
gc = gspread.authorize(credentials)

# Google Sheets Key
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"

# ======== LOAD SHEET ========

try:
    sh = gc.open_by_key(sheet_key)
    worksheet = sh.worksheet("工作表1")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    st.success("✅ 成功讀取 Google Sheets!")

except Exception as e:
    st.error(f"發生錯誤: {e}")
    st.stop()

# 如果表格是空的，建立欄位
if df.empty:
    df = pd.DataFrame(columns=[
        "色粉編號", "國際色號", "色粉名稱",
        "色粉類別", "規格", "產地", "備註"
    ])

# ======== 搜尋 ========

st.markdown("## 🔍 搜尋色粉")

keyword = st.text_input("請輸入色粉編號")

if keyword:
    filtered_df = df[
        df["色粉編號"].astype(str).str.contains(keyword, na=False)
    ]
else:
    filtered_df = df

# ======== 新增 ========

st.markdown("---")
st.markdown("## ➕ 新增色粉")

# 建立欄位
color_code = st.text_input("色粉編號")
pantone_code = st.text_input("國際色號")
color_name = st.text_input("色粉名稱")
color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"])
spec = st.text_input("規格")
origin = st.text_input("產地")
remark = st.text_input("備註")

# 檢查重複編號
existing_codes = df["色粉編號"].astype(str).tolist()

if st.button("確定新增"):
    if color_code in existing_codes:
        st.warning("⚠️ 色粉編號重複，請重新輸入！")
    else:
        new_row = [color_code, pantone_code, color_name, color_type, spec, origin, remark]
        worksheet.append_row(new_row)
        st.success("✅ 新增完成！請重新執行程式查看更新。")

# ======== 顯示序列 ========

st.markdown("---")
st.markdown("## 📋 色粉總表")

# 重新用最新 DataFrame
if keyword:
    display_df = filtered_df
else:
    display_df = df

for i, row in display_df.iterrows():
    # 用 st.columns 排版
    cols = st.columns([10, 1, 1])
    
    # 資料
    with cols[0]:
        st.markdown(
            f"""
            <div style='
                font-size: 14px;
                text-align: center;
                background-color: {"#FED9B7" if i % 2 == 0 else "#FDFCDC"};
                padding: 6px;
                border-radius: 5px;
            '>
            ➡️ 色粉編號：{row.get("色粉編號", "")} ｜ 名稱：{row.get("色粉名稱", "")} ｜ 國際色號：{row.get("國際色號", "")} ｜ 
            類別：{row.get("色粉類別", "")} ｜ 規格：{row.get("規格", "")} ｜ 產地：{row.get("產地", "")} ｜ 備註：{row.get("備註", "")}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # 修改按鈕
    with cols[1]:
        if st.button("修改", key=f"edit_{i}"):
            st.info(f"🔧 準備修改：色粉編號 {row.get('色粉編號','')}")
    
    # 刪除按鈕
    with cols[2]:
        delete_clicked = st.button("刪除", key=f"delete_{i}")
        if delete_clicked:
            worksheet.delete_rows(i + 2)  # GSpread 第 2 列是第一筆資料
            st.warning("🗑️ 已刪除！請重新執行程式查看更新。")
            st.stop()

