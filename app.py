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

# ======== MODULE SELECTION =========
module = st.sidebar.selectbox("請選擇模組", ["色粉管理", "客戶名單"])

# ======== CONFIG FOR TWO MODULES =========
module_config = {
    "色粉管理": {
        "sheet_name": "色粉管理",
        "required_columns": ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
        "category_field": "色粉類別",
        "category_options": ["色粉", "色母", "添加劑"],
        "package_field": "包裝",
        "package_options": ["袋", "箱", "kg"],
        "code_field": "色粉編號",
        "search_fields": ["色粉編號", "國際色號"],
        "title": "🎨 色粉管理系統",
        "search_placeholder": "請輸入色粉編號或國際色號",
        "form_title": "➕ 新增 / 修改 色粉",
        "list_title": "📋 色粉清單",
    },
    "客戶名單": {
        "sheet_name": "客戶名單",
        "required_columns": ["客戶編號", "客戶簡稱", "備註"],
        "category_field": None,
        "category_options": None,
        "package_field": None,
        "package_options": None,
        "code_field": "客戶編號",
        "search_fields": ["客戶編號", "客戶簡稱"],
        "title": "🧑‍💼 客戶名單系統",
        "search_placeholder": "請輸入客戶編號或簡稱",
        "form_title": "➕ 新增 / 修改 客戶",
        "list_title": "📋 客戶清單",
    },
}

conf = module_config[module]

# ======== LOAD SHEET =========
try:
    worksheet = spreadsheet.worksheet(conf["sheet_name"])
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except Exception:
    df = pd.DataFrame(columns=conf["required_columns"])

df = df.astype(str)

for col in conf["required_columns"]:
    if col not in df.columns:
        df[col] = ""

df.columns = df.columns.str.strip()

# ======== SESSION STATE INITIALIZATION =========
prefix = module  # to isolate session states

if f"{prefix}_form_data" not in st.session_state:
    st.session_state[f"{prefix}_form_data"] = {col: "" for col in conf["required_columns"]}
if f"{prefix}_edit_mode" not in st.session_state:
    st.session_state[f"{prefix}_edit_mode"] = False
if f"{prefix}_edit_index" not in st.session_state:
    st.session_state[f"{prefix}_edit_index"] = None
if f"{prefix}_delete_index" not in st.session_state:
    st.session_state[f"{prefix}_delete_index"] = None
if f"{prefix}_show_delete_confirm" not in st.session_state:
    st.session_state[f"{prefix}_show_delete_confirm"] = False
if f"{prefix}_search_input" not in st.session_state:
    st.session_state[f"{prefix}_search_input"] = ""
if f"{prefix}_rerun_flag" not in st.session_state:
    st.session_state[f"{prefix}_rerun_flag"] = False

# ======== RERUN HANDLING =========
if st.session_state[f"{prefix}_rerun_flag"]:
    st.session_state[f"{prefix}_rerun_flag"] = False
    st.experimental_rerun()

# ======== UI START =========
st.title(conf["title"])

# ---------- Search ----------
st.subheader("🔎 搜尋")

search_input = st.text_input(
    conf["search_placeholder"],
    st.session_state[f"{prefix}_search_input"],
    placeholder="直接按 Enter 搜尋",
)

if search_input != st.session_state[f"{prefix}_search_input"]:
    st.session_state[f"{prefix}_search_input"] = search_input

if st.session_state[f"{prefix}_search_input"].strip():
    conditions = [df[field].str.contains(st.session_state[f"{prefix}_search_input"], case=False, na=False)
                  for field in conf["search_fields"]]
    combined_condition = conditions[0]
    for cond in conditions[1:]:
        combined_condition = combined_condition | cond
    df_filtered = df[combined_condition]
    if df_filtered.empty:
        st.info("🔍 查無資料")
else:
    df_filtered = df

# ---------- New/Edit Form ----------
st.subheader(conf["form_title"])

cols1, cols2 = st.columns(2)

with cols1:
    for col in conf["required_columns"][:3]:
        st.session_state[f"{prefix}_form_data"][col] = st.text_input(
            col,
            st.session_state[f"{prefix}_form_data"][col],
        )

with cols2:
    if conf["category_field"]:
        st.session_state[f"{prefix}_form_data"][conf["category_field"]] = st.selectbox(
            conf["category_field"],
            conf["category_options"],
            index=conf["category_options"].index(
                st.session_state[f"{prefix}_form_data"][conf["category_field"]]
            ) if st.session_state[f"{prefix}_form_data"][conf["category_field"]] in conf["category_options"] else 0
        )
    if conf["package_field"]:
        st.session_state[f"{prefix}_form_data"][conf["package_field"]] = st.selectbox(
            conf["package_field"],
            conf["package_options"],
            index=conf["package_options"].index(
                st.session_state[f"{prefix}_form_data"][conf["package_field"]]
            ) if st.session_state[f"{prefix}_form_data"][conf["package_field"]] in conf["package_options"] else 0
        )
    if len(conf["required_columns"]) > 3:
        for col in conf["required_columns"][3:]:
            if col not in [conf["category_field"], conf["package_field"]]:
                st.session_state[f"{prefix}_form_data"][col] = st.text_input(
                    col,
                    st.session_state[f"{prefix}_form_data"][col],
                )

save_btn = st.button("💾 儲存")

if save_btn:
    new_data = st.session_state[f"{prefix}_form_data"].copy()

    if new_data[conf["code_field"]].strip() == "":
        st.warning(f"⚠️ 請輸入 {conf['code_field']}！")
    else:
        if st.session_state[f"{prefix}_edit_mode"]:
            df.iloc[st.session_state[f"{prefix}_edit_index"]] = new_data
            st.success("✅ 資料已更新！")
        else:
            if new_data[conf["code_field"]] in df[conf["code_field"]].values:
                st.warning(f"⚠️ 此 {conf['code_field']} 已存在，請勿重複新增！")
            else:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增成功！")

        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        st.session_state[f"{prefix}_form_data"] = {col: "" for col in conf["required_columns"]}
        st.session_state[f"{prefix}_edit_mode"] = False
        st.session_state[f"{prefix}_edit_index"] = None
        st.session_state[f"{prefix}_rerun_flag"] = True

# ---------- Delete Confirm ----------
if st.session_state[f"{prefix}_show_delete_confirm"]:
    st.warning("⚠️ 確定要刪除這筆資料嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state[f"{prefix}_delete_index"]
        df.drop(index=idx, inplace=True)
        df.reset_index(drop=True, inplace=True)
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
            st.success("✅ 資料已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state[f"{prefix}_show_delete_confirm"] = False
        st.session_state[f"{prefix}_delete_index"] = None
        st.session_state[f"{prefix}_rerun_flag"] = True
    if col_no.button("否，取消"):
        st.session_state[f"{prefix}_show_delete_confirm"] = False
        st.session_state[f"{prefix}_delete_index"] = None
        st.session_state[f"{prefix}_rerun_flag"] = True

# ---------- List ----------
st.subheader(conf["list_title"])

for i, row in df_filtered.iterrows():
    cols = st.columns([2] * (len(conf["required_columns"])) + [3])
    for j, field in enumerate(conf["required_columns"]):
        cols[j].write(row[field])

    with cols[-1]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"{prefix}_edit_{i}"):
            st.session_state[f"{prefix}_edit_mode"] = True
            st.session_state[f"{prefix}_edit_index"] = i
            st.session_state[f"{prefix}_form_data"] = row.to_dict()
            st.session_state[f"{prefix}_rerun_flag"] = True
        if col_delete.button("🗑️ 刪除", key=f"{prefix}_delete_{i}"):
            st.session_state[f"{prefix}_delete_index"] = i
            st.session_state[f"{prefix}_show_delete_confirm"] = True
            st.session_state[f"{prefix}_rerun_flag"] = True
