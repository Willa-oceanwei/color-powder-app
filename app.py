import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# =========== GCP SERVICE ACCOUNT ============
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

# =========== INITIALIZATION ============

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

# 確保欄位存在
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

# 清理欄位名稱
df.columns = df.columns.str.strip()

# =========== SESSION STATE DEFAULTS ============

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

# =========== UI START ============

st.title("🎨 色粉管理系統")

# -------- Search bar --------

st.subheader("🔎 搜尋色粉")

search_input = st.text_input(
    "請輸入色粉編號或國際色號", 
    st.session_state.search_input,
    placeholder="例如：1234 或 PANTONE 485C"
)

st.session_state.search_input = search_input.strip()

# -------- New/Edit Form --------

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
        index=[
            "色粉", "色母", "添加劑"
        ].index(st.session_state.form_data["色粉類別"]) 
        if st.session_state.form_data["色粉類別"] in ["色粉", "色母", "添加劑"]
        else 0
    )
    st.session_state.form_data["包裝"] = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=[
            "袋", "箱", "kg"
        ].index(st.session_state.form_data["包裝"])
        if st.session_state.form_data["包裝"] in ["袋", "箱", "kg"]
        else 0
    )
    st.session_state.form_data["備註"] = st.text_input(
        "備註",
        st.session_state.form_data["備註"]
    )

save_btn = st.button("💾 儲存")

if save_btn:
    new_data = st.session_state.form_data.copy()

    if st.session_state.edit_mode:
        # 更新
        df.iloc[st.session_state.edit_index] = new_data
        st.success("✅ 色粉已更新！")
    else:
        # 檢查重複
        if new_data["色粉編號"] in df["色粉編號"].astype(str).values:
            st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
        else:
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            st.success("✅ 新增色粉成功！")

    # 更新 Google Sheet
    try:
        values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        worksheet.update("A1", values)
    except Exception as e:
        st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

    # 重置表單
    st.session_state.form_data = {col: "" for col in required_columns}
    st.session_state.edit_mode = False
    st.session_state.edit_index = None

# -------- Delete Confirmation --------

if st.session_state.show_delete_confirm:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state.delete_index
        df.drop(index=idx, inplace=True)
        df.reset_index(drop=True, inplace=True)
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.update("A1", values)
            st.success("✅ 色粉已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
    if col_no.button("否，取消"):
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None

# -------- Filter Search --------

if st.session_state.search_input:
    df_filtered = df[
        df["色粉編號"].astype(str).str.contains(st.session_state.search_input, case=False, na=False)
        | df["國際色號"].astype(str).str.contains(st.session_state.search_input, case=False, na=False)
    ]
    if df_filtered.empty:
        st.warning(f"⚠️ 沒有找到符合「{st.session_state.search_input}」的色粉資料。")
else:
    df_filtered = df

# -------- Powder List --------

st.subheader("📋 色粉清單")

if not df_filtered.empty:
    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(str(row["色粉編號"]))
        cols[1].write(str(row["國際色號"]))
        cols[2].write(str(row["名稱"]))
        cols[3].write(str(row["色粉類別"]))
        cols[4].write(str(row["包裝"]))
        if cols[5].button("✏️ 修改", key=f"edit_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i
            st.session_state.form_data = row.to_dict()
        if cols[6].button("🗑️ 刪除", key=f"delete_{i}"):
            st.session_state.delete_index = i
            st.session_state.show_delete_confirm = True

# =========== 功能模組（示範） ============
st.sidebar.header("🔧 功能模組")
st.sidebar.write("- 配方管理（未實作）")
