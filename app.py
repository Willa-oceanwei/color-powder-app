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

# ========= SHEETS =========
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ========= CONFIG =========
required_color_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

required_customer_columns = [
    "客戶編號",
    "客戶簡稱",
    "備註",
]

# ========== LOAD SHEETS ==========
def load_sheet(ws, columns):
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=columns)

    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df.columns = df.columns.str.strip()

    return df

df_color = load_sheet(ws_color, required_color_columns)
df_customer = load_sheet(ws_customer, required_customer_columns)

# ========= INIT STATE ==========
if "form_color" not in st.session_state:
    st.session_state.form_color = {col: "" for col in required_color_columns}
if "form_customer" not in st.session_state:
    st.session_state.form_customer = {col: "" for col in required_customer_columns}

if "edit_color_mode" not in st.session_state:
    st.session_state.edit_color_mode = False
if "edit_color_index" not in st.session_state:
    st.session_state.edit_color_index = None

if "edit_customer_mode" not in st.session_state:
    st.session_state.edit_customer_mode = False
if "edit_customer_index" not in st.session_state:
    st.session_state.edit_customer_index = None

if "search_color_input" not in st.session_state:
    st.session_state.search_color_input = ""
if "search_customer_input" not in st.session_state:
    st.session_state.search_customer_input = ""

# ========= MODULE CHOICE ==========
st.title("🎨 色粉與客戶管理系統")
module = st.radio("請選擇模組", ["色粉管理", "客戶名單"])

# ==================================
#        COLOR MODULE
# ==================================
if module == "色粉管理":

    st.subheader("🔎 搜尋色粉")
    search_color_input = st.text_input(
        "請輸入色粉編號或國際色號",
        value=st.session_state.search_color_input,
        placeholder="直接按 Enter 搜尋",
    )

    if search_color_input != st.session_state.search_color_input:
        st.session_state.search_color_input = search_color_input

    if st.session_state.search_color_input.strip():
        df_filtered = df_color[
            df_color["色粉編號"].str.contains(st.session_state.search_color_input, case=False, na=False) |
            df_color["國際色號"].str.contains(st.session_state.search_color_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("🔍 查無此色粉資料")
    else:
        df_filtered = df_color

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
                st.session_state.form_color["色粉類別"]
            ) if st.session_state.form_color["色粉類別"] in ["色粉", "色母", "添加劑"] else 0,
        )
        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.form_color["包裝"]
            ) if st.session_state.form_color["包裝"] in ["袋", "箱", "kg"] else 0,
        )
        st.session_state.form_color["備註"] = st.text_input(
            "備註",
            st.session_state.form_color["備註"],
        )

    if st.button("💾 儲存"):
        new_row = st.session_state.form_color.copy()

        if new_row["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_color_mode:
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.success("✅ 色粉已更新！")
            else:
                if new_row["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            # 儲存到 Sheet
            values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
            ws_color.clear()
            ws_color.update("A1", values)

            st.session_state.form_color = {col: "" for col in required_color_columns}
            st.session_state.edit_color_mode = False
            st.session_state.edit_color_index = None
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
                st.session_state.form_color = row.to_dict()
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
                df_color.drop(index=i, inplace=True)
                df_color.reset_index(drop=True, inplace=True)
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.clear()
                ws_color.update("A1", values)
                st.success("✅ 已刪除色粉！")
                st.experimental_rerun()

# ==================================
#       CUSTOMER MODULE
# ==================================
if module == "客戶名單":

    st.subheader("🔎 搜尋客戶")
    search_customer_input = st.text_input(
        "請輸入客戶編號或客戶簡稱",
        value=st.session_state.search_customer_input,
        placeholder="直接按 Enter 搜尋",
    )

    if search_customer_input != st.session_state.search_customer_input:
        st.session_state.search_customer_input = search_customer_input

    if st.session_state.search_customer_input.strip():
        df_filtered = df_customer[
            df_customer["客戶編號"].str.contains(st.session_state.search_customer_input, case=False, na=False) |
            df_customer["客戶簡稱"].str.contains(st.session_state.search_customer_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("🔍 查無此客戶資料")
    else:
        df_filtered = df_customer

    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state.form_customer["客戶編號"],
        )
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state.form_customer["客戶簡稱"],
        )
    with col2:
        st.session_state.form_customer["備註"] = st.text_input(
            "備註",
            st.session_state.form_customer["備註"],
        )

    if st.button("💾 儲存"):
        new_row = st.session_state.form_customer.copy()

        if new_row["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_mode:
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.success("✅ 客戶已更新！")
            else:
                if new_row["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
            ws_customer.clear()
            ws_customer.update("A1", values)

            st.session_state.form_customer = {col: "" for col in required_customer_columns}
            st.session_state.edit_customer_mode = False
            st.session_state.edit_customer_index = None
            st.experimental_rerun()

    st.subheader("📋 客戶清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        with cols[2]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_customer_mode = True
                st.session_state.edit_customer_index = i
                st.session_state.form_customer = row.to_dict()
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                df_customer.drop(index=i, inplace=True)
                df_customer.reset_index(drop=True, inplace=True)
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.clear()
                ws_customer.update("A1", values)
                st.success("✅ 已刪除客戶！")
                st.experimental_rerun()
