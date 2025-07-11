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
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit"

spreadsheet = client.open_by_url(SHEET_URL)

# 固定 sheet name
SHEET_COLOR = "色粉管理"
SHEET_CUSTOMER = "客戶名單"

# ====== 確保 Worksheet 存在 ======
def get_or_create_worksheet(name, cols):
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows="1000", cols=str(len(cols)))
        ws.update("A1", [cols])
    return ws

# ========= UTILS =========
def load_data(ws, required_columns):
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df = df.astype(str)
    return df

def save_data(ws, df):
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update("A1", values)

# ========== APP START ==========
st.set_page_config(page_title="色粉管理系統", layout="wide")
st.title("🎨 色粉管理系統")

menu = st.sidebar.radio(
    "請選擇功能模組",
    ["色粉管理", "客戶名單"],
)

# ========= 色粉管理模組 =========
if menu == "色粉管理":
    required_columns = [
        "色粉編號",
        "國際色號",
        "名稱",
        "色粉類別",
        "包裝",
        "備註",
    ]

    ws_color = get_or_create_worksheet(SHEET_COLOR, required_columns)
    df_color = load_data(ws_color, required_columns)

    # 初始化 Session State
    if "form_color" not in st.session_state:
        st.session_state.form_color = {col: "" for col in required_columns}
    if "edit_index_color" not in st.session_state:
        st.session_state.edit_index_color = None
    if "delete_index_color" not in st.session_state:
        st.session_state.delete_index_color = None
    if "show_delete_confirm_color" not in st.session_state:
        st.session_state.show_delete_confirm_color = False
    if "search_input_color" not in st.session_state:
        st.session_state.search_input_color = ""

    # 如果在修改模式 → 填入表單
    if st.session_state.edit_index_color is not None:
        row = df_color.iloc[st.session_state.edit_index_color]
        st.session_state.form_color = row.to_dict()

    # --------- Search ---------
    st.subheader("🔎 搜尋色粉")
    with st.form("search_form_color"):
        search_input = st.text_input(
            "請輸入色粉編號或國際色號",
            value=st.session_state.search_input_color,
            placeholder="直接按 Enter 搜尋"
        )
        search_submitted = st.form_submit_button("搜尋")

    if search_submitted:
        st.session_state.search_input_color = search_input

    if st.session_state.search_input_color.strip():
        df_filtered = df_color[
            df_color["色粉編號"].str.contains(st.session_state.search_input_color, case=False, na=False) |
            df_color["國際色號"].str.contains(st.session_state.search_input_color, case=False, na=False)
        ]
    else:
        df_filtered = df_color

    # --------- Form ---------
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state.form_color.get("色粉編號", "")
        )
        st.session_state.form_color["國際色號"] = st.text_input(
            "國際色號",
            st.session_state.form_color.get("國際色號", "")
        )
        st.session_state.form_color["名稱"] = st.text_input(
            "名稱",
            st.session_state.form_color.get("名稱", "")
        )

    with col2:
        val = st.session_state.form_color.get("色粉類別", "")
        if val not in ["色粉", "色母", "添加劑"]:
            val = "色粉"
        st.session_state.form_color["色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(val)
        )

        packaging_options = ["袋", "箱", "kg"]
        selected_packaging = st.session_state.form_color.get("包裝", "袋")
        if selected_packaging not in packaging_options:
            selected_packaging = "袋"

        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝",
            packaging_options,
            index=packaging_options.index(selected_packaging)
        )

        st.session_state.form_color["備註"] = st.text_input(
            "備註",
            st.session_state.form_color.get("備註", "")
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_color.copy()

        if new_data["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_index_color is not None:
                df_color.iloc[st.session_state.edit_index_color] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            save_data(ws_color, df_color)

            st.session_state.form_color = {col: "" for col in required_columns}
            st.session_state.edit_index_color = None
            st.experimental_rerun()

    if st.session_state.show_delete_confirm_color:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_index_color
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            save_data(ws_color, df_color)
            st.session_state.show_delete_confirm_color = False
            st.session_state.delete_index_color = None
            st.success("✅ 已刪除！")
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.show_delete_confirm_color = False
            st.session_state.delete_index_color = None
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
                st.session_state.edit_index_color = i
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_index_color = i
                st.session_state.show_delete_confirm_color = True
                st.experimental_rerun()

# ========= 客戶名單模組 =========
elif menu == "客戶名單":
    required_columns = ["客戶編號", "客戶簡稱", "備註"]
    ws_customer = get_or_create_worksheet(SHEET_CUSTOMER, required_columns)
    df_customer = load_data(ws_customer, required_columns)

    if "form_customer" not in st.session_state:
        st.session_state.form_customer = {col: "" for col in required_columns}
    if "edit_index_customer" not in st.session_state:
        st.session_state.edit_index_customer = None
    if "delete_index_customer" not in st.session_state:
        st.session_state.delete_index_customer = None
    if "show_delete_confirm_customer" not in st.session_state:
        st.session_state.show_delete_confirm_customer = False
    if "search_input_customer" not in st.session_state:
        st.session_state.search_input_customer = ""

    if st.session_state.edit_index_customer is not None:
        row = df_customer.iloc[st.session_state.edit_index_customer]
        st.session_state.form_customer = row.to_dict()

    st.subheader("🔎 搜尋客戶")
    with st.form("search_form_customer"):
        search_input = st.text_input(
            "請輸入客戶編號或簡稱",
            value=st.session_state.search_input_customer,
            placeholder="直接按 Enter 搜尋"
        )
        search_submitted = st.form_submit_button("搜尋")

    if search_submitted:
        st.session_state.search_input_customer = search_input

    if st.session_state.search_input_customer.strip():
        df_filtered = df_customer[
            df_customer["客戶編號"].str.contains(st.session_state.search_input_customer, case=False, na=False) |
            df_customer["客戶簡稱"].str.contains(st.session_state.search_input_customer, case=False, na=False)
        ]
    else:
        df_filtered = df_customer

    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state.form_customer.get("客戶編號", "")
        )
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state.form_customer.get("客戶簡稱", "")
        )

    with col2:
        st.session_state.form_customer["備註"] = st.text_input(
            "備註",
            st.session_state.form_customer.get("備註", "")
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_customer.copy()

        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_index_customer is not None:
                df_customer.iloc[st.session_state.edit_index_customer] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            save_data(ws_customer, df_customer)
            st.session_state.form_customer = {col: "" for col in required_columns}
            st.session_state.edit_index_customer = None
            st.experimental_rerun()

    if st.session_state.show_delete_confirm_customer:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_index_customer
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            save_data(ws_customer, df_customer)
            st.session_state.show_delete_confirm_customer = False
            st.session_state.delete_index_customer = None
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.show_delete_confirm_customer = False
            st.session_state.delete_index_customer = None
            st.experimental_rerun()

    st.subheader("📋 客戶清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        with cols[2]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_index_customer = i
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_index_customer = i
                st.session_state.show_delete_confirm_customer = True
                st.experimental_rerun()
