import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
import json

st.set_page_config(page_title="色粉管理", page_icon="🎨", layout="wide")

# ========= GCP SERVICE ACCOUNT 設定 =========
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(credentials)
SHEET_NAME = "色粉管理"
worksheet = client.open(SHEET_NAME).sheet1

# ========= 讀取資料 =========
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()

# 保證 DataFrame 至少有所有欄位
needed_cols = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "kg",
    "備註"
]
for col in needed_cols:
    if col not in df.columns:
        df[col] = ""

# 強制所有欄位轉成字串，避免搜尋錯誤
for col in ["色粉編號", "名稱"]:
    df[col] = df[col].astype(str)

# ========= Tab 模組切換 =========
tab = st.radio(
    "模組選擇",
    ["色粉管理", "配方管理"],
    horizontal=True
)

if tab == "配方管理":
    st.warning("配方管理尚未開發。")
    st.stop()

# ========= 搜尋區塊 =========
st.subheader("🔎 搜尋色粉")

col_search, col_clear = st.columns([5, 1])
with col_search:
    search_term = st.text_input("請輸入色粉編號或名稱後按 Enter", value="", key="search_input")

with col_clear:
    if st.button("清空畫面"):
        st.query_params.clear()
        st.rerun()

# 進行搜尋
filtered_df = df.copy()
if search_term:
    filtered_df = df[
        df["色粉編號"].str.contains(str(search_term), case=False, na=False) |
        df["名稱"].str.contains(str(search_term), case=False, na=False)
    ]

if search_term and filtered_df.empty:
    st.warning("⚠️ 查無此色粉。")

# ========= Query Params 處理 =========
query_params = st.query_params.to_dict()
edit_id = query_params.get("edit", [None])[0]
delete_id = query_params.get("delete", [None])[0]

# ========= 新增 / 修改 表單 =========
st.subheader("➕ 新增 / 修改 色粉")

# 預設空值
default_data = {
    "色粉編號": "",
    "國際色號": "",
    "名稱": "",
    "色粉類別": "",
    "包裝": "",
    "kg": 0,
    "備註": ""
}

# 若進入修改模式
if edit_id:
    row = df[df["色粉編號"] == edit_id]
    if not row.empty:
        row = row.iloc[0]
        default_data.update(row.to_dict())

# 建立 2列 * 4欄 UI
row1 = st.columns(4)
row2 = st.columns(4)

色粉編號 = row1[0].text_input("色粉編號", value=default_data["色粉編號"])
國際色號 = row1[1].text_input("國際色號", value=default_data["國際色號"])
名稱 = row1[2].text_input("名稱", value=default_data["名稱"])
色粉類別 = row1[3].selectbox(
    "色粉類別",
    ["", "色粉", "色母", "添加劑"],
    index=0 if default_data["色粉類別"] == "" else ["", "色粉", "色母", "添加劑"].index(default_data["色粉類別"])
)

包裝 = row2[0].selectbox(
    "包裝",
    ["", "袋", "箱", "kg"],
    index=0 if default_data["包裝"] == "" else ["", "袋", "箱", "kg"].index(default_data["包裝"])
)
kg = row2[1].number_input("kg", min_value=0.0, step=0.1, value=float(default_data["kg"]) if default_data["kg"] else 0.0)
備註 = row2[3].text_input("備註", value=default_data["備註"])

submitted = st.button("✅ 新增 / 修改")

if submitted:
    if 色粉編號 == "":
        st.error("請輸入色粉編號！")
    else:
        exists = df[(df["色粉編號"] == 色粉編號)]
        if (edit_id and edit_id != 色粉編號 and not exists.empty) or (not edit_id and not exists.empty):
            st.warning(f"⚠️ 色粉編號【{色粉編號}】已存在，無法重複新增。")
        else:
            # 若修改，就先刪除舊的
            if edit_id:
                df = df[df["色粉編號"] != edit_id]
            # 新增
            new_row = {
                "色粉編號": 色粉編號,
                "國際色號": 國際色號,
                "名稱": 名稱,
                "色粉類別": 色粉類別,
                "包裝": 包裝,
                "kg": kg,
                "備註": 備註
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            worksheet.clear()
            worksheet.update([df.columns.tolist()] + df.values.tolist())

            st.success(f"✅ 色粉【{色粉編號}】已成功新增 / 修改！")
            st.query_params.clear()
            st.rerun()

# ========= 刪除邏輯 =========
if delete_id:
    row = df[df["色粉編號"] == delete_id]
    if not row.empty:
        row = row.iloc[0]
        if st.button(f"⚠️ 確定要刪除【{row['名稱']}】嗎？"):
            df = df[df["色粉編號"] != delete_id]
            worksheet.clear()
            worksheet.update([df.columns.tolist()] + df.values.tolist())
            st.success(f"✅ 已刪除【{row['名稱']}】")
            st.query_params.clear()
            st.rerun()

# ========= 顯示總表 =========
st.subheader("📋 色粉總表")

if not filtered_df.empty:
    for i, row in filtered_df.iterrows():
        bg_color = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        col1, col2, col3 = st.columns([10, 1, 1])

        with col1:
            st.markdown(
                f"""
                <div style='background-color: {bg_color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;'>
                    <b>{i+1}</b> |
                    色粉編號: {row['色粉編號']} |
                    名稱: {row['名稱']} |
                    國際色號: {row['國際色號']} |
                    色粉類別: {row['色粉類別']} |
                    包裝: {row['包裝']} |
                    kg: {row['kg']} |
                    備註: {row['備註']}
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            if st.button("修改", key=f"edit_{i}"):
                st.query_params.update({"edit": row["色粉編號"]})
                st.rerun()

        with col3:
            if st.button("刪除", key=f"del_{i}"):
                st.query_params.update({"delete": row["色粉編號"]})
                st.rerun()

else:
    st.info("目前沒有任何色粉資料。")
