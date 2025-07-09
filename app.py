import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
import json

st.set_page_config(page_title="色粉管理", page_icon="🎨", layout="wide")

# ========= GCP SERVICE ACCOUNT 設定 =========
# 讀取 secrets
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]
)

client = gspread.authorize(credentials)
SHEET_NAME = "色粉管理"
worksheet = client.open(SHEET_NAME).sheet1

# ========= 讀取資料 =========
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()  # 去掉欄位名稱空白

# ========= 處理 Query Params =========
query_params = st.query_params.to_dict()
edit_id = query_params.get("edit", [None])[0]
delete_id = query_params.get("delete", [None])[0]

# ========= 新增 / 修改 表單 =========
with st.form("add_edit_form"):
    st.subheader("🔧 新增 / 修改 色粉")

    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        色粉編號 = st.text_input("色粉編號")
    with col2:
        名稱 = st.text_input("名稱")
    with col3:
        國際色號 = st.text_input("國際色號")

    # 若是編輯狀態，帶入資料
    if edit_id:
        row = df[df["色粉編號"] == edit_id]
        if not row.empty:
            row = row.iloc[0]
            色粉編號 = row["色粉編號"]
            名稱 = row["名稱"]
            國際色號 = row["國際色號"]

    submit = st.form_submit_button("✅ 新增 / 修改")

# ========= 新增 / 修改邏輯 =========
if submit:
    if 色粉編號 == "":
        st.error("請輸入色粉編號！")
    else:
        # 檢查是否存在相同色粉編號
        exists = df[df["色粉編號"] == 色粉編號]
        if exists.empty or edit_id == 色粉編號:
            # 如果是修改，就先刪除原本的紀錄
            if edit_id and edit_id != 色粉編號:
                df = df[df["色粉編號"] != edit_id]

            # 新增或更新
            new_row = {
                "色粉編號": 色粉編號,
                "名稱": 名稱,
                "國際色號": 國際色號
            }
            df = df[df["色粉編號"] != 色粉編號]
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            # 更新工作表
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())

            st.success(f"✅ 已成功新增 / 修改色粉【{色粉編號}】！")
            st.experimental_rerun()
        else:
            st.warning(f"⚠️ 色粉編號【{色粉編號}】已存在！無法重複新增。")

# ========= 刪除邏輯 =========
if delete_id:
    row = df[df["色粉編號"] == delete_id]
    if not row.empty:
        row = row.iloc[0]
        if st.confirm(f"⚠️ 確定要刪除【{row['名稱']}】嗎？"):
            df = df[df["色粉編號"] != delete_id]
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            st.success(f"✅ 已刪除【{row['名稱']}】")
            st.experimental_rerun()

# ========= 顯示總表 =========
st.subheader("🎨 色粉總表")

if not df.empty:
    for i, row in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([1, 2, 3, 2, 2])

        col1.write(i + 1)  # 序列
        col2.write(row["色粉編號"])
        col3.write(row["名稱"])
        col4.write(row["國際色號"])

        # 同一行顯示修改、刪除按鈕
        with col5:
            edit_url = f"?edit={row['色粉編號']}"
            delete_url = f"?delete={row['色粉編號']}"
            edit_clicked = st.button("修改", key=f"edit_{i}")
            delete_clicked = st.button("刪除", key=f"del_{i}")

            if edit_clicked:
                st.query_params.update({"edit": row["色粉編號"]})
                st.experimental_rerun()

            if delete_clicked:
                st.query_params.update({"delete": row["色粉編號"]})
                st.experimental_rerun()
else:
    st.info("目前沒有任何色粉資料。")
