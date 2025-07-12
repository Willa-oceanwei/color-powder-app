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

# 模組對應工作表
ws_map = {
    "色粉管理": "色粉管理",
    "客戶名單": "客戶名單",
}

# ======== SESSION FLAGS (核心修正) =========
# 全部 flag 預設為 False
flags = [
    "run_save",
    "run_delete",
]
for f in flags:
    if f not in st.session_state:
        st.session_state[f] = False

# ======== SIDEBAR 模組切換 =========
module = st.sidebar.selectbox("請選擇模組", ["色粉管理", "客戶名單"])
sheet_name = ws_map[module]
try:
    worksheet = spreadsheet.worksheet(sheet_name)
except:
    # 如果工作表不存在就創建
    spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    worksheet = spreadsheet.worksheet(sheet_name)

# ======== MODULE CONFIG =========

if module == "色粉管理":
    required_columns = [
        "色粉編號",
        "國際色號",
        "名稱",
        "色粉類別",
        "包裝",
        "備註",
    ]
else:
    required_columns = [
        "客戶編號",
        "客戶簡稱",
        "備註",
    ]

# 載入資料
try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame(columns=required_columns)

df = df.astype(str)

for col in required_columns:
    if col not in df.columns:
        df[col] = ""

df.columns = df.columns.str.strip()

# ======== SESSION INIT =========

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

# ======== FLAG CHECK & EXECUTE =========

# ---------------- SAVE ----------------
if st.session_state.run_save:
    new_data = st.session_state.form_data.copy()

    if module == "色粉管理":
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

    else:  # 客戶名單
        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_mode:
                df.iloc[st.session_state.edit_index] = new_data
                st.success("✅ 客戶資料已更新！")
            else:
                if new_data["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

    try:
        values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        worksheet.clear()
        worksheet.update("A1", values)
    except Exception as e:
        st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

    # reset
    st.session_state.form_data = {col: "" for col in required_columns}
    st.session_state.edit_mode = False
    st.session_state.edit_index = None
    st.session_state.run_save = False
    st.experimental_rerun()

# ---------------- DELETE ----------------
if st.session_state.run_delete:
    idx = st.session_state.delete_index
    df.drop(index=idx, inplace=True)
    df.reset_index(drop=True, inplace=True)

    try:
        values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        worksheet.clear()
        worksheet.update("A1", values)
        st.success("✅ 資料已刪除！")
    except Exception as e:
        st.error(f"❌ 刪除失敗: {e}")

    st.session_state.run_delete = False
    st.session_state.show_delete_confirm = False
    st.session_state.delete_index = None
    st.experimental_rerun()

# ======== UI START =========

st.title(f"🎨 {module} 系統")

# ---------- Search ----------
st.subheader(f"🔎 搜尋 {module}")
search_input = st.text_input(
    f"請輸入 {required_columns[0]} 或 {required_columns[1]}",
    st.session_state.search_input,
    placeholder="直接按 Enter 搜尋"
)

if search_input != st.session_state.search_input:
    st.session_state.search_input = search_input

if st.session_state.search_input.strip():
    df_filtered = df[
        df[required_columns[0]].str.contains(st.session_state.search_input, case=False, na=False) |
        df[required_columns[1]].str.contains(st.session_state.search_input, case=False, na=False)
    ]
    if df_filtered.empty:
        st.info("🔍 查無資料")
else:
    df_filtered = df

# ---------- Form ----------
st.subheader(f"➕ 新增 / 修改 {module}")

col1, col2 = st.columns(2)

for i, col in enumerate(required_columns):
    if module == "色粉管理":
        if col in ["色粉編號", "國際色號", "名稱"] and i < 3:
            with col1:
                st.session_state.form_data[col] = st.text_input(
                    col,
                    st.session_state.form_data[col],
                    key=f"{col}_input"
                )
        elif col in ["色粉類別", "包裝"] and i < 5:
            with col2:
                options = (
                    ["色粉", "色母", "添加劑"]
                    if col == "色粉類別"
                    else ["袋", "箱", "kg"]
                )
                index = (
                    options.index(st.session_state.form_data[col])
                    if st.session_state.form_data[col] in options
                    else 0
                )
                st.session_state.form_data[col] = st.selectbox(
                    col,
                    options,
                    index=index,
                    key=f"{col}_select"
                )
        elif col == "備註":
            with col2:
                st.session_state.form_data[col] = st.text_input(
                    col,
                    st.session_state.form_data[col],
                    key=f"{col}_input"
                )
    else:
        # 客戶名單
        with (col1 if i < 2 else col2):
            st.session_state.form_data[col] = st.text_input(
                col,
                st.session_state.form_data[col],
                key=f"{col}_input"
            )

save_btn = st.button("💾 儲存")

if save_btn:
    st.session_state.run_save = True
    st.experimental_rerun()

# ======== DELETE CONFIRM =========
if st.session_state.show_delete_confirm:
    st.warning(f"⚠️ 確定要刪除此筆 {module} 嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        st.session_state.run_delete = True
        st.experimental_rerun()
    if col_no.button("否，取消"):
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
        st.experimental_rerun()

# ======== LIST =========
st.subheader(f"📋 {module} 清單")

for i, row in df_filtered.iterrows():
    cols = st.columns([2] * (len(required_columns)) + [3])
    for j, col_name in enumerate(required_columns):
        cols[j].write(row[col_name])

    with cols[-1]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"edit_{module}_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i
            st.session_state.form_data = row.to_dict()
            st.experimental_rerun()
        if col_delete.button("🗑️ 刪除", key=f"delete_{module}_{i}"):
            st.session_state.show_delete_confirm = True
            st.session_state.delete_index = i
            st.experimental_rerun()
