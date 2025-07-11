import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ========== GCP SERVICE ACCOUNT ==========
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

# 固定工作表名稱
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ========== INITIALIZATION ==========
color_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

customer_columns = [
    "客戶編號",
    "客戶簡稱",
    "備註",
]

def load_sheet(ws, columns):
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=columns)
    # 強制所有欄位轉字串
    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df.columns = df.columns.str.strip()
    return df

df_color = load_sheet(ws_color, color_columns)
df_customer = load_sheet(ws_customer, customer_columns)

# ========== SESSION STATE ==========
# 色粉
if "form_color" not in st.session_state:
    st.session_state.form_color = {col: "" for col in color_columns}
if "edit_mode_color" not in st.session_state:
    st.session_state.edit_mode_color = False
if "edit_index_color" not in st.session_state:
    st.session_state.edit_index_color = None
if "delete_index_color" not in st.session_state:
    st.session_state.delete_index_color = None
if "show_delete_confirm_color" not in st.session_state:
    st.session_state.show_delete_confirm_color = False
if "search_input_color" not in st.session_state:
    st.session_state.search_input_color = ""

# 客戶
if "form_customer" not in st.session_state:
    st.session_state.form_customer = {col: "" for col in customer_columns}
if "edit_mode_customer" not in st.session_state:
    st.session_state.edit_mode_customer = False
if "edit_index_customer" not in st.session_state:
    st.session_state.edit_index_customer = None
if "delete_index_customer" not in st.session_state:
    st.session_state.delete_index_customer = None
if "show_delete_confirm_customer" not in st.session_state:
    st.session_state.show_delete_confirm_customer = False
if "search_input_customer" not in st.session_state:
    st.session_state.search_input_customer = ""

# ========== SIDEBAR ==========
module = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"]
)

# ========== COLOR MODULE ==========
if module == "色粉管理":
    st.title("🎨 色粉管理系統")

    # 搜尋
    st.subheader("🔎 搜尋色粉")
    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        st.session_state.search_input_color,
        placeholder="直接按 Enter 搜尋"
    )
    if search_input != st.session_state.search_input_color:
        st.session_state.search_input_color = search_input

    if st.session_state.search_input_color.strip():
        df_color_filtered = df_color[
            df_color["色粉編號"].str.contains(st.session_state.search_input_color, case=False, na=False) |
            df_color["國際色號"].str.contains(st.session_state.search_input_color, case=False, na=False)
        ]
        if df_color_filtered.empty:
            st.info("🔍 查無此色粉資料")
    else:
        df_color_filtered = df_color

    # 新增 / 修改表單
    st.subheader("➕ 新增 / 修改 色粉")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state.form_color["色粉編號"]
        )
        st.session_state.form_color["國際色號"] = st.text_input(
            "國際色號",
            st.session_state.form_color["國際色號"]
        )
        st.session_state.form_color["名稱"] = st.text_input(
            "名稱",
            st.session_state.form_color["名稱"]
        )
    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.form_color["色粉類別"]
            ) if st.session_state.form_color["色粉類別"] in ["色粉", "色母", "添加劑"] else 0
        )
        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.form_color["包裝"]
            ) if st.session_state.form_color["包裝"] in ["袋", "箱", "kg"] else 0
        )
        st.session_state.form_color["備註"] = st.text_input(
            "備註",
            st.session_state.form_color["備註"]
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_color.copy()
        if new_data["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_mode_color:
                df_color.iloc[st.session_state.edit_index_color] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.clear()
                ws_color.update("A1", values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.form_color = {col: "" for col in color_columns}
            st.session_state.edit_mode_color = False
            st.session_state.edit_index_color = None
            st.experimental_rerun()

    # 刪除確認
    if st.session_state.show_delete_confirm_color:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_index_color
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.clear()
                ws_color.update("A1", values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_color = False
            st.session_state.delete_index_color = None
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.show_delete_confirm_color = False
            st.session_state.delete_index_color = None
            st.experimental_rerun()

    # 清單
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
                st.session_state.edit_mode_color = True
                st.session_state.edit_index_color = i
                st.session_state.form_color = row.to_dict()
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_index_color = i
                st.session_state.show_delete_confirm_color = True
                st.experimental_rerun()

# ========== CUSTOMER MODULE ==========
elif module == "客戶名單":
    st.title("👥 客戶名單")

    # 搜尋
    st.subheader("🔎 搜尋客戶")
    search_input = st.text_input(
        "請輸入客戶編號或客戶簡稱",
        st.session_state.search_input_customer,
        placeholder="直接按 Enter 搜尋"
    )
    if search_input != st.session_state.search_input_customer:
        st.session_state.search_input_customer = search_input

    if st.session_state.search_input_customer.strip():
        df_customer_filtered = df_customer[
            df_customer["客戶編號"].str.contains(st.session_state.search_input_customer, case=False, na=False) |
            df_customer["客戶簡稱"].str.contains(st.session_state.search_input_customer, case=False, na=False)
        ]
        if df_customer_filtered.empty:
            st.info("🔍 查無此客戶資料")
    else:
        df_customer_filtered = df_customer

    # 新增 / 修改表單
    st.subheader("➕ 新增 / 修改 客戶")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state.form_customer["客戶編號"]
        )
    with col2:
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state.form_customer["客戶簡稱"]
        )
    st.session_state.form_customer["備註"] = st.text_input(
        "備註",
        st.session_state.form_customer["備註"]
    )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_customer.copy()
        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_mode_customer:
                df_customer.iloc[st.session_state.edit_index_customer] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.clear()
                ws_customer.update("A1", values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.form_customer = {col: "" for col in customer_columns}
            st.session_state.edit_mode_customer = False
            st.session_state.edit_index_customer = None
            st.experimental_rerun()

    # 刪除確認
    if st.session_state.show_delete_confirm_customer:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_index_customer
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.clear()
                ws_customer.update("A1", values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_customer = False
            st.session_state.delete_index_customer = None
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.show_delete_confirm_customer = False
            st.session_state.delete_index_customer = None
            st.experimental_rerun()

    # 清單
    st.subheader("📋 客戶清單")
    for i, row in df_customer_filtered.iterrows():
        cols = st.columns([2, 2, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        with cols[2]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_mode_customer = True
                st.session_state.edit_index_customer = i
                st.session_state.form_customer = row.to_dict()
                st.experimental_rerun()
            if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_index_customer = i
                st.session_state.show_delete_confirm_customer = True
                st.experimental_rerun()
