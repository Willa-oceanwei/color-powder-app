import streamlit as st
import gspread
import pandas as pd
import json
from google.oauth2 import service_account

# --- Google Sheet 連線設定 ---
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
credentials = service_account.Credentials.from_service_account_info(
    gcp_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["gcp"]["sheet_url"]
spreadsheet = gc.open_by_url(SHEET_URL)

# --- 工具函式 ---
def load_sheet(sheet_name, columns):
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=len(columns))
        ws.append_row(columns)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=columns)
    return ws, df

def save_sheet(ws, df):
    if df.empty:
        ws.clear()
        ws.append_row(list(df.columns))
    else:
        values = [df.columns.tolist()] + df.fillna("").values.tolist()
        ws.update(values)

# --- 色粉管理模組 ---
def color_module():
    st.header("🎨 色粉管理")

    # 載入色粉資料
    ws_color, df_color = load_sheet("色粉管理", ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])

    # --- 搜尋 ---
    color_search_input = st.text_input("🔍 搜尋 (編號/名稱):", value=st.session_state.get("color_search_input", ""), key="color_search_input")
    if color_search_input:
        df_color_display = df_color[
            df_color.apply(lambda row: color_search_input in str(row.to_dict()), axis=1)
        ]
        if df_color_display.empty:
            st.warning("找不到符合條件的色粉。")
    else:
        df_color_display = df_color

    # --- 新增 / 修改 ---
    st.subheader("➕ 新增 / 修改 色粉")
    with st.form("color_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        色粉編號 = col1.text_input("色粉編號", value=st.session_state.get("form_color_色粉編號", ""))
        國際色號 = col2.text_input("國際色號", value=st.session_state.get("form_color_色國際色號", ""))
        col3, col4 = st.columns(2)
        名稱 = col3.text_input("名稱", value=st.session_state.get("form_color_名稱", ""))
        色粉類別 = col4.selectbox("色粉類別", ["色粉", "色母", "添加劑"], index=[
            "色粉", "色母", "添加劑"
        ].index(st.session_state.get("form_color_色粉類別", "色粉")))
        col5, col6 = st.columns(2)
        包裝 = col5.selectbox("包裝", ["袋裝", "桶裝", "箱裝"], index=[
            "袋裝", "桶裝", "箱裝"
        ].index(st.session_state.get("form_color_包裝", "袋裝")))
        備註 = col6.text_input("備註", value=st.session_state.get("form_color_色備註", ""))
        
        submitted = st.form_submit_button("💾 儲存")
        if submitted:
            if not 色粉編號:
                st.warning("【色粉編號】必填！")
            else:
                new_row = {
                    "色粉編號": 色粉編號,
                    "國際色號": 國際色號,
                    "名稱": 名稱,
                    "色粉類別": 色粉類別,
                    "包裝": 包裝,
                    "備註": 備註,
                }
                if "edit_color_index" in st.session_state and st.session_state.edit_color_index is not None:
                    # 編輯
                    try:
                        df_color.iloc[st.session_state.edit_color_index] = new_row
                        st.success("修改完成！")
                    except IndexError:
                        st.warning("修改失敗，找不到資料。")
                else:
                    # 新增
                    if 色粉編號 in df_color["色粉編號"].values:
                        st.warning(f"色粉編號【{色粉編號}】已存在，請改用修改功能！")
                    else:
                        df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("新增完成！")
                save_sheet(ws_color, df_color)
                st.session_state.edit_color_index = None
                st.experimental_rerun()

    # --- 列表 ---
    st.subheader("📋 色粉列表")
    for idx, row in df_color_display.iterrows():
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2,2,2,2,2,2,1,1])
        col1.write(row["色粉編號"])
        col2.write(row["國際色號"])
        col3.write(row["名稱"])
        col4.write(row["色粉類別"])
        col5.write(row["包裝"])
        col6.write(row["備註"])
        if col7.button("✏️ 修改", key=f"edit_color_{idx}"):
            for col_name in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col_name}"] = row[col_name]
            st.session_state.edit_color_index = idx
            st.experimental_rerun()
        if col8.button("🗑️ 刪除", key=f"del_color_{idx}"):
            if st.confirm(f"確定要刪除色粉編號【{row['色粉編號']}】嗎？"):
                df_color = df_color.drop(idx).reset_index(drop=True)
                save_sheet(ws_color, df_color)
                st.success(f"已刪除色粉編號【{row['色粉編號']}】")
                st.experimental_rerun()

# --- 客戶名單模組 ---
def customer_module():
    st.header("👥 客戶名單")

    ws_customer, df_customer = load_sheet("客戶名單", ["客戶編號", "客戶簡稱", "備註"])

    # --- 搜尋 ---
    customer_search_input = st.text_input("🔍 搜尋 (客戶編號/簡稱):", value=st.session_state.get("customer_search_input", ""), key="customer_search_input")
    if customer_search_input:
        df_customer_display = df_customer[
            df_customer.apply(lambda row: customer_search_input in str(row.to_dict()), axis=1)
        ]
        if df_customer_display.empty:
            st.warning("找不到符合條件的客戶。")
    else:
        df_customer_display = df_customer

    # --- 新增 / 修改 ---
    st.subheader("➕ 新增 / 修改 客戶")
    with st.form("customer_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        客戶編號 = col1.text_input("客戶編號", value=st.session_state.get("form_customer_客戶編號", ""))
        客戶簡稱 = col2.text_input("客戶簡稱", value=st.session_state.get("form_customer_客戶簡稱", ""))
        備註 = st.text_input("備註", value=st.session_state.get("form_customer_備註", ""))
        submitted = st.form_submit_button("💾 儲存")
        if submitted:
            if not 客戶編號:
                st.warning("【客戶編號】必填！")
            else:
                new_row = {
                    "客戶編號": 客戶編號,
                    "客戶簡稱": 客戶簡稱,
                    "備註": 備註,
                }
                if "edit_customer_index" in st.session_state and st.session_state.edit_customer_index is not None:
                    try:
                        df_customer.iloc[st.session_state.edit_customer_index] = new_row
                        st.success("修改完成！")
                    except IndexError:
                        st.warning("修改失敗，找不到資料。")
                else:
                    if 客戶編號 in df_customer["客戶編號"].values:
                        st.warning(f"客戶編號【{客戶編號}】已存在，請改用修改功能！")
                    else:
                        df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("新增完成！")
                save_sheet(ws_customer, df_customer)
                st.session_state.edit_customer_index = None
                st.experimental_rerun()

    # --- 列表 ---
    st.subheader("📋 客戶列表")
    for idx, row in df_customer_display.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2,2,2,1,1])
        col1.write(row["客戶編號"])
        col2.write(row["客戶簡稱"])
        col3.write(row["備註"])
        if col4.button("✏️ 修改", key=f"edit_customer_{idx}"):
            for col_name in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col_name}"] = row[col_name]
            st.session_state.edit_customer_index = idx
            st.experimental_rerun()
        if col5.button("🗑️ 刪除", key=f"del_customer_{idx}"):
            if st.confirm(f"確定要刪除客戶編號【{row['客戶編號']}】嗎？"):
                df_customer = df_customer.drop(idx).reset_index(drop=True)
                save_sheet(ws_customer, df_customer)
                st.success(f"已刪除客戶編號【{row['客戶編號']}】")
                st.experimental_rerun()

# --- 選單 ---
st.sidebar.title("選擇模組")
module_choice = st.sidebar.radio("請選擇模組：", ["色粉管理", "客戶名單"])
if module_choice == "色粉管理":
    color_module()
elif module_choice == "客戶名單":
    customer_module()
