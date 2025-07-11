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

# 固定使用你指定的 sheet 名稱
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ======== COLOR POWDER MODULE =========

# 初始化顏色模組 session_state
if "form_color" not in st.session_state:
    st.session_state.form_color = {
        "色粉編號": "",
        "國際色號": "",
        "名稱": "",
        "色粉類別": "",
        "包裝": "",
        "備註": "",
    }
if "edit_color_mode" not in st.session_state:
    st.session_state.edit_color_mode = False
if "edit_color_index" not in st.session_state:
    st.session_state.edit_color_index = None
if "delete_color_index" not in st.session_state:
    st.session_state.delete_color_index = None
if "show_delete_color_confirm" not in st.session_state:
    st.session_state.show_delete_color_confirm = False
if "search_color" not in st.session_state:
    st.session_state.search_color = ""

data_color = ws_color.get_all_records()
df_color = pd.DataFrame(data_color).astype(str)

st.header("🎨 色粉管理系統")

# ===== 搜尋區塊 =====
search_input_color = st.text_input("請輸入色粉編號或國際色號", st.session_state.search_color)

if search_input_color != st.session_state.search_color:
    st.session_state.search_color = search_input_color

if st.session_state.search_color.strip():
    df_color_filtered = df_color[
        df_color["色粉編號"].str.contains(st.session_state.search_color, case=False, na=False)
        | df_color["國際色號"].str.contains(st.session_state.search_color, case=False, na=False)
    ]
    if df_color_filtered.empty:
        st.info("🔍 查無此色粉資料")
else:
    df_color_filtered = df_color

# ===== 新增/修改表單 =====
st.subheader("➕ 新增 / 修改 色粉")

col1, col2 = st.columns(2)
with col1:
    st.session_state.form_color["色粉編號"] = st.text_input(
        "色粉編號",
        st.session_state.form_color["色粉編號"],
    )
    st.session_state.form_color["國際色號"] = st.text_input(
        "國際色號",
        st.session_state.form_color["國際色號"],
    )
    st.session_state.form_color["名稱"] = st.text_input(
        "名稱",
        st.session_state.form_color["名稱"],
    )
with col2:
    st.session_state.form_color["色粉類別"] = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(
            st.session_state.form_color.get("色粉類別", "色粉")
        ) if st.session_state.form_color.get("色粉類別", "") else 0,
    )
    st.session_state.form_color["包裝"] = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=["袋", "箱", "kg"].index(
            st.session_state.form_color.get("包裝", "袋")
        ) if st.session_state.form_color.get("包裝", "") else 0,
    )
    st.session_state.form_color["備註"] = st.text_input(
        "備註",
        st.session_state.form_color["備註"],
    )

if st.button("💾 儲存"):
    new_data = st.session_state.form_color.copy()

    if new_data["色粉編號"].strip() == "":
        st.warning("⚠️ 請輸入色粉編號！")
    else:
        if st.session_state.edit_color_mode:
            df_color.iloc[st.session_state.edit_color_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            if new_data["色粉編號"] in df_color["色粉編號"].values:
                st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
            else:
                df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增色粉成功！")

        values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
        ws_color.clear()
        ws_color.update("A1", values)

        st.session_state.form_color = {k: "" for k in st.session_state.form_color}
        st.session_state.edit_color_mode = False
        st.session_state.edit_color_index = None
        st.experimental_rerun()

# ===== Delete Confirm =====
if st.session_state.show_delete_color_confirm:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state.delete_color_index
        df_color.drop(index=idx, inplace=True)
        df_color.reset_index(drop=True, inplace=True)
        values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
        ws_color.clear()
        ws_color.update("A1", values)
        st.success("✅ 色粉已刪除！")

        st.session_state.show_delete_color_confirm = False
        st.session_state.delete_color_index = None
        st.experimental_rerun()
    if col_no.button("否，取消"):
        st.session_state.show_delete_color_confirm = False
        st.session_state.delete_color_index = None

# ===== 顯示清單 =====
st.subheader("📋 色粉清單")

for i, row in df_color_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2, 2, 3])
    cols[0].write(row["色粉編號"])
    cols[1].write(row["國際色號"])
    cols[2].write(row["名稱"])
    cols[3].write(row["色粉類別"])
    cols[4].write(row["包裝"])
    with cols[5]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state.edit_color_mode = True
            st.session_state.edit_color_index = i
            st.session_state.form_color = row.to_dict()
        if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
            st.session_state.delete_color_index = i
            st.session_state.show_delete_color_confirm = True

# ======== CUSTOMER MODULE =========

# 初始化客戶模組 session_state
if "form_customer" not in st.session_state:
    st.session_state.form_customer = {
        "客戶編號": "",
        "客戶簡稱": "",
        "備註": "",
    }
if "edit_customer_mode" not in st.session_state:
    st.session_state.edit_customer_mode = False
if "edit_customer_index" not in st.session_state:
    st.session_state.edit_customer_index = None
if "delete_customer_index" not in st.session_state:
    st.session_state.delete_customer_index = None
if "show_delete_customer_confirm" not in st.session_state:
    st.session_state.show_delete_customer_confirm = False
if "search_customer" not in st.session_state:
    st.session_state.search_customer = ""

data_customer = ws_customer.get_all_records()
df_customer = pd.DataFrame(data_customer).astype(str)

st.header("🗂 客戶名單管理")

search_input_customer = st.text_input("請輸入客戶編號或客戶簡稱", st.session_state.search_customer)

if search_input_customer != st.session_state.search_customer:
    st.session_state.search_customer = search_input_customer

if st.session_state.search_customer.strip():
    df_customer_filtered = df_customer[
        df_customer["客戶編號"].str.contains(st.session_state.search_customer, case=False, na=False)
        | df_customer["客戶簡稱"].str.contains(st.session_state.search_customer, case=False, na=False)
    ]
    if df_customer_filtered.empty:
        st.info("🔍 查無此客戶資料")
else:
    df_customer_filtered = df_customer

st.subheader("➕ 新增 / 修改 客戶")

st.session_state.form_customer["客戶編號"] = st.text_input(
    "客戶編號",
    st.session_state.form_customer["客戶編號"],
)
st.session_state.form_customer["客戶簡稱"] = st.text_input(
    "客戶簡稱",
    st.session_state.form_customer["客戶簡稱"],
)
st.session_state.form_customer["備註"] = st.text_input(
    "備註",
    st.session_state.form_customer["備註"],
)

if st.button("💾 儲存", key="save_customer"):
    new_data = st.session_state.form_customer.copy()

    if new_data["客戶編號"].strip() == "":
        st.warning("⚠️ 請輸入客戶編號！")
    else:
        if st.session_state.edit_customer_mode:
            df_customer.iloc[st.session_state.edit_customer_index] = new_data
            st.success("✅ 客戶已更新！")
        else:
            if new_data["客戶編號"] in df_customer["客戶編號"].values:
                st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
            else:
                df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增客戶成功！")

        values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
        ws_customer.clear()
        ws_customer.update("A1", values)

        st.session_state.form_customer = {k: "" for k in st.session_state.form_customer}
        st.session_state.edit_customer_mode = False
        st.session_state.edit_customer_index = None
        st.experimental_rerun()

if st.session_state.show_delete_customer_confirm:
    st.warning("⚠️ 確定要刪除此筆客戶嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state.delete_customer_index
        df_customer.drop(index=idx, inplace=True)
        df_customer.reset_index(drop=True, inplace=True)
        values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
        ws_customer.clear()
        ws_customer.update("A1", values)
        st.success("✅ 客戶已刪除！")

        st.session_state.show_delete_customer_confirm = False
        st.session_state.delete_customer_index = None
        st.experimental_rerun()
    if col_no.button("否，取消"):
        st.session_state.show_delete_customer_confirm = False
        st.session_state.delete_customer_index = None

st.subheader("📋 客戶清單")

for i, row in df_customer_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2])
    cols[0].write(row["客戶編號"])
    cols[1].write(row["客戶簡稱"])
    cols[2].write(row["備註"])
    with cols[3]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state.edit_customer_mode = True
            st.session_state.edit_customer_index = i
            st.session_state.form_customer = row.to_dict()
        if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
            st.session_state.delete_customer_index = i
            st.session_state.show_delete_customer_confirm = True
