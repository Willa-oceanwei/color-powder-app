import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ========== GOOGLE SHEET 設定 ==========

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
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ========== 初始化 session_state ==========

# 色粉
if "form_color" not in st.session_state:
    st.session_state.form_color = {
        "色粉編號": "",
        "國際色號": "",
        "名稱": "",
        "色粉類別": "色粉",
        "包裝": "袋",
        "備註": ""
    }
if "edit_color_mode" not in st.session_state:
    st.session_state.edit_color_mode = False
if "edit_color_index" not in st.session_state:
    st.session_state.edit_color_index = None
if "delete_color_index" not in st.session_state:
    st.session_state.delete_color_index = None
if "show_color_delete_confirm" not in st.session_state:
    st.session_state.show_color_delete_confirm = False
if "search_color_input" not in st.session_state:
    st.session_state.search_color_input = ""

# 客戶
if "form_customer" not in st.session_state:
    st.session_state.form_customer = {
        "客戶編號": "",
        "客戶簡稱": "",
        "備註": ""
    }
if "edit_customer_mode" not in st.session_state:
    st.session_state.edit_customer_mode = False
if "edit_customer_index" not in st.session_state:
    st.session_state.edit_customer_index = None
if "delete_customer_index" not in st.session_state:
    st.session_state.delete_customer_index = None
if "show_customer_delete_confirm" not in st.session_state:
    st.session_state.show_customer_delete_confirm = False
if "search_customer_input" not in st.session_state:
    st.session_state.search_customer_input = ""

# ========== 載入資料 ==========

def load_sheet(ws, required_cols):
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=required_cols)
    df = df.astype(str)
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    return df

df_color = load_sheet(ws_color, ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])
df_customer = load_sheet(ws_customer, ["客戶編號", "客戶簡稱", "備註"])

# ========== UI 切換 ==========

tabs = st.tabs(["🎨 色粉管理", "👥 客戶名單"])

# ==========================
# 色粉模組
# ==========================
with tabs[0]:
    st.subheader("🔎 搜尋色粉")

    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        st.session_state.search_color_input,
        key="search_color_input_box"
    )
    if search_input != st.session_state.search_color_input:
        st.session_state.search_color_input = search_input

    if st.session_state.search_color_input.strip():
        df_filtered = df_color[
            df_color["色粉編號"].str.contains(st.session_state.search_color_input, case=False, na=False) |
            df_color["國際色號"].str.contains(st.session_state.search_color_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("查無色粉資料")
    else:
        df_filtered = df_color

    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input("色粉編號", st.session_state.form_color["色粉編號"], key="color_色粉編號")
        st.session_state.form_color["國際色號"] = st.text_input("國際色號", st.session_state.form_color["國際色號"], key="color_國際色號")
        st.session_state.form_color["名稱"] = st.text_input("名稱", st.session_state.form_color["名稱"], key="color_名稱")
    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(st.session_state.form_color["色粉類別"]) if st.session_state.form_color["色粉類別"] else 0,
            key="color_色粉類別"
        )
        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(st.session_state.form_color["包裝"]) if st.session_state.form_color["包裝"] else 0,
            key="color_包裝"
        )
        st.session_state.form_color["備註"] = st.text_input("備註", st.session_state.form_color["備註"], key="color_備註")

    if st.button("💾 儲存", key="save_color"):
        new_row = st.session_state.form_color.copy()
        if new_row["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_color_mode:
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.success("✅ 色粉已更新！")
            else:
                if new_row["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ 新增成功！")
            ws_color.clear()
            ws_color.update([df_color.columns.tolist()] + df_color.values.tolist())
            st.session_state.form_color = {col: "" for col in st.session_state.form_color}
            st.session_state.edit_color_mode = False
            st.session_state.edit_color_index = None
            st.experimental_rerun()

    if st.session_state.show_color_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="yes_delete_color"):
            idx = st.session_state.delete_color_index
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            ws_color.clear()
            ws_color.update([df_color.columns.tolist()] + df_color.values.tolist())
            st.session_state.show_color_delete_confirm = False
            st.session_state.delete_color_index = None
            st.experimental_rerun()
        if col_no.button("否，取消", key="no_delete_color"):
            st.session_state.show_color_delete_confirm = False
            st.session_state.delete_color_index = None
            st.experimental_rerun()

    st.subheader("📋 色粉清單")
    for i, row in df_filtered.iterrows():
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
                for col in st.session_state.form_color:
                    st.session_state.form_color[col] = row[col]
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_color_index = i
                st.session_state.show_color_delete_confirm = True
                st.experimental_rerun()

# ==========================
# 客戶模組
# ==========================
with tabs[1]:
    st.subheader("🔎 搜尋客戶")

    search_input = st.text_input(
        "請輸入客戶編號或簡稱",
        st.session_state.search_customer_input,
        key="search_customer_input_box"
    )
    if search_input != st.session_state.search_customer_input:
        st.session_state.search_customer_input = search_input

    if st.session_state.search_customer_input.strip():
        df_filtered = df_customer[
            df_customer["客戶編號"].str.contains(st.session_state.search_customer_input, case=False, na=False) |
            df_customer["客戶簡稱"].str.contains(st.session_state.search_customer_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("查無客戶資料")
    else:
        df_filtered = df_customer

    st.subheader("➕ 新增 / 修改 客戶")

    st.session_state.form_customer["客戶編號"] = st.text_input("客戶編號", st.session_state.form_customer["客戶編號"], key="customer_客戶編號")
    st.session_state.form_customer["客戶簡稱"] = st.text_input("客戶簡稱", st.session_state.form_customer["客戶簡稱"], key="customer_客戶簡稱")
    st.session_state.form_customer["備註"] = st.text_input("備註", st.session_state.form_customer["備註"], key="customer_備註")

    if st.button("💾 儲存", key="save_customer"):
        new_row = st.session_state.form_customer.copy()
        if new_row["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_mode:
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.success("✅ 客戶已更新！")
            else:
                if new_row["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ 新增成功！")
            ws_customer.clear()
            ws_customer.update([df_customer.columns.tolist()] + df_customer.values.tolist())
            st.session_state.form_customer = {col: "" for col in st.session_state.form_customer}
            st.session_state.edit_customer_mode = False
            st.session_state.edit_customer_index = None
            st.experimental_rerun()

    if st.session_state.show_customer_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="yes_delete_customer"):
            idx = st.session_state.delete_customer_index
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            ws_customer.clear()
            ws_customer.update([df_customer.columns.tolist()] + df_customer.values.tolist())
            st.session_state.show_customer_delete_confirm = False
            st.session_state.delete_customer_index = None
            st.experimental_rerun()
        if col_no.button("否，取消", key="no_delete_customer"):
            st.session_state.show_customer_delete_confirm = False
            st.session_state.delete_customer_index = None
            st.experimental_rerun()

    st.subheader("📋 客戶清單")
    for i, row in df_filtered.iterrows():
        cols = st.columns([3, 3, 3, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        with cols[3]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_customer_mode = True
                st.session_state.edit_customer_index = i
                for col in st.session_state.form_customer:
                    st.session_state.form_customer[col] = row[col]
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_customer_index = i
                st.session_state.show_customer_delete_confirm = True
                st.experimental_rerun()
