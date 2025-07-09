import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.get_worksheet(0)

# ======== INITIALIZATION =========
required_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

# 載入資料
try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame(columns=required_columns)

# 強制所有欄位都轉成字串
df = df.astype(str)

# 確保欄位存在
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

df.columns = df.columns.str.strip()

# ======== SESSION STATE =========
if "form_data" not in st.session_state:
    st.session_state.form_data = {col: "" for col in required_columns}
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "delete_index" not in st.session_state:
    st.session_state.delete_index = None
if "show_delete_confirm" not in st.session_state:
    st.session_state.show_delete_confirm = False
if "search_input" not in st.session_state:
    st.session_state.search_input = ""

# ======== UI START =========
st.title("🎨 色粉管理系統")

# ---------- Search ----------
st.subheader("🔎 搜尋色粉")
search_input = st.text_input(
    "請輸入色粉編號或國際色號",
    st.session_state.search_input,
    placeholder="直接按 Enter 搜尋"
)

# 更新搜尋
if search_input != st.session_state.search_input:
    st.session_state.search_input = search_input

# ======= Search Filter =======
if st.session_state.search_input.strip():
    df_filtered = df[
        df["色粉編號"].str.contains(st.session_state.search_input, case=False, na=False) |
        df["國際色號"].str.contains(st.session_state.search_input, case=False, na=False)
    ]
    if df_filtered.empty:
        st.info("🔍 查無此色粉資料")
else:
    df_filtered = df

# ---------- New/Edit Form ----------
st.subheader("➕ 新增 / 修改 色粉")

col1, col2 = st.columns(2)

with col1:
    st.session_state.form_data["色粉編號"] = st.text_input(
        "色粉編號",
        st.session_state.form_data["色粉編號"]
    )
    st.session_state.form_data["國際色號"] = st.text_input(
        "國際色號",
        st.session_state.form_data["國際色號"]
    )
    st.session_state.form_data["名稱"] = st.text_input(
        "名稱",
        st.session_state.form_data["名稱"]
    )

with col2:
    st.session_state.form_data["色粉類別"] = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(
            st.session_state.form_data["色粉類別"]
        ) if st.session_state.form_data["色粉類別"] in ["色粉", "色母", "添加劑"] else 0
    )
    st.session_state.form_data["包裝"] = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=["袋", "箱", "kg"].index(
            st.session_state.form_data["包裝"]
        ) if st.session_state.form_data["包裝"] in ["袋", "箱", "kg"] else 0
    )
    st.session_state.form_data["備註"] = st.text_input(
        "備註",
        st.session_state.form_data["備註"]
    )

save_btn = st.button("💾 儲存")

# ======== SAVE / UPDATE LOGIC =========
if save_btn:
    new_data = st.session_state.form_data.copy()

    if new_data["色粉編號"].strip() == "":
        st.warning("⚠️ 請輸入色粉編號！")
    else:
        if st.session_state.edit_mode:
            df.iloc[st.session_state.edit_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            if new_data["色粉編號"] in df["色粉編號"].values:
                st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
            else:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增色粉成功！")

        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        st.session_state.form_data = {col: "" for col in required_columns}
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
        st.rerun()

# ======== DELETE CONFIRM =========
if st.session_state.show_delete_confirm:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state.delete_index
        df.drop(index=idx, inplace=True)
        df.reset_index(drop=True, inplace=True)
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
            st.success("✅ 色粉已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
        st.rerun()
    if col_no.button("否，取消"):
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
        st.rerun()

# ======== Powder List =========
st.subheader("📋 色粉清單")

for i, row in df_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2, 2, 3])
    cols[0].write(row["色粉編號"])
    cols[1].write(row["國際色號"])
    cols[2].write(row["名稱"])
    cols[3].write(row["色粉類別"])
    cols[4].write(row["包裝"])

    # 橫排放兩顆按鈕
    with cols[5]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"edit_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i
            st.session_state.form_data = row.to_dict()
            st.rerun()
        if col_delete.button("🗑️ 刪除", key=f"delete_{i}"):
            st.session_state.delete_index = i
            st.session_state.show_delete_confirm = True
            st.rerun()
