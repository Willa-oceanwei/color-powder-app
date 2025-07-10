import streamlit as st
import gspread
import pandas as pd
import json
from google.oauth2 import service_account

# --- Google Sheets setup ---
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
credentials = service_account.Credentials.from_service_account_info(
    gcp_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
SHEET_URL = st.secrets["gcp"]["sheet_url"]
spreadsheet = gc.open_by_url(SHEET_URL)

# --- Helpers ---
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

# --- 色粉管理 ---
def color_module():
    st.header("🎨 色粉管理")

    ws_color, df_color = load_sheet("色粉管理", ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])

    # --- 搜尋 ---
    search_val = st.text_input("🔍 搜尋 (編號/名稱)：", st.session_state.get("color_search_input", ""))
    st.session_state.color_search_input = search_val

    if search_val:
        df_disp = df_color[
            df_color.apply(lambda row: search_val in str(row.to_dict()), axis=1)
        ]
        if df_disp.empty:
            st.warning("找不到符合的色粉！")
    else:
        df_disp = df_color

    # --- 新增 / 修改 ---
    st.subheader("➕ 新增 / 修改 色粉")

    with st.form("color_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        色粉編號 = col1.text_input("色粉編號", value=st.session_state.get("form_color_色粉編號", ""))
        國際色號 = col2.text_input("國際色號", value=st.session_state.get("form_color_色國際色號", ""))

        col3, col4 = st.columns(2)
        名稱 = col3.text_input("名稱", value=st.session_state.get("form_color_名稱", ""))
        色粉類別 = col4.selectbox("色粉類別", ["色粉", "色母", "添加劑"],
            index=(["色粉", "色母", "添加劑"].index(st.session_state.get("form_color_色粉類別", "色粉"))
                   if st.session_state.get("form_color_色粉類別", "色粉") in ["色粉", "色母", "添加劑"] else 0)
        )

        col5, col6 = st.columns(2)
        包裝 = st.session_state.get("form_color_包裝", "袋裝")
        index = ["袋裝", "桶裝", "箱裝"].index(包裝) if 包裝 in ["袋裝", "桶裝", "箱裝"] else 0
        包裝 = col5.selectbox("包裝", ["袋裝", "桶裝", "箱裝"], index=index)
        備註 = col6.text_input("備註", value=st.session_state.get("form_color_色備註", ""))

        submitted = st.form_submit_button("💾 儲存")

        if submitted:
            if not 色粉編號:
                st.warning("色粉編號必填！")
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
                    try:
                        df_color.iloc[st.session_state.edit_color_index] = new_row
                        st.success("修改完成！")
                    except IndexError:
                        st.warning("修改失敗。")
                else:
                    if 色粉編號 in df_color["色粉編號"].values:
                        st.warning(f"色粉編號【{色粉編號}】已存在！請改用修改功能。")
                    else:
                        df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("新增完成！")
                save_sheet(ws_color, df_color)
                st.session_state.edit_color_index = None
                st.session_state.rerun_needed = True

    # --- 序列 ---
    st.subheader("📋 色粉列表")
    for i, row in df_disp.iterrows():
        cols = st.columns([2,2,2,2,2,2,1,1])
        cols[0].text(row["色粉編號"])
        cols[1].text(row["國際色號"])
        cols[2].text(row["名稱"])
        cols[3].text(row["色粉類別"])
        cols[4].text(row["包裝"])
        cols[5].text(row["備註"])
        if cols[6].button("✏️ 修改", key=f"edit_color_{i}"):
            for k in row.index:
                st.session_state[f"form_color_{k}"] = row[k]
            st.session_state.edit_color_index = i
            st.session_state.rerun_needed = True
        if cols[7].button("🗑️ 刪除", key=f"del_color_{i}"):
            confirm_key = f"confirm_color_{i}"
            if st.button(f"❗ 確認刪除【{row['色粉編號']}】", key=confirm_key):
                df_color = df_color.drop(i).reset_index(drop=True)
                save_sheet(ws_color, df_color)
                st.success(f"已刪除【{row['色粉編號']}】")
                st.session_state.rerun_needed = True

# --- 客戶名單 ---
def customer_module():
    st.header("👥 客戶名單")

    ws_cust, df_cust = load_sheet("客戶名單", ["客戶編號", "客戶簡稱", "備註"])

    # 搜尋
    search_val = st.text_input("🔍 搜尋 (編號/簡稱)", st.session_state.get("customer_search_input", ""))
    st.session_state.customer_search_input = search_val

    if search_val:
        df_disp = df_cust[
            df_cust.apply(lambda row: search_val in str(row.to_dict()), axis=1)
        ]
        if df_disp.empty:
            st.warning("找不到符合的客戶。")
    else:
        df_disp = df_cust

    # 新增 / 修改
    st.subheader("➕ 新增 / 修改 客戶")
    with st.form("customer_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        客戶編號 = col1.text_input("客戶編號", value=st.session_state.get("form_customer_客戶編號", ""))
        客戶簡稱 = col2.text_input("客戶簡稱", value=st.session_state.get("form_customer_客戶簡稱", ""))
        備註 = st.text_input("備註", value=st.session_state.get("form_customer_備註", ""))

        submitted = st.form_submit_button("💾 儲存")

        if submitted:
            if not 客戶編號:
                st.warning("客戶編號必填！")
            else:
                new_row = {
                    "客戶編號": 客戶編號,
                    "客戶簡稱": 客戶簡稱,
                    "備註": 備註
                }
                if "edit_customer_index" in st.session_state and st.session_state.edit_customer_index is not None:
                    try:
                        df_cust.iloc[st.session_state.edit_customer_index] = new_row
                        st.success("修改完成！")
                    except IndexError:
                        st.warning("修改失敗。")
                else:
                    if 客戶編號 in df_cust["客戶編號"].values:
                        st.warning(f"客戶編號【{客戶編號}】已存在！請改用修改功能。")
                    else:
                        df_cust = pd.concat([df_cust, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("新增完成！")
                save_sheet(ws_cust, df_cust)
                st.session_state.edit_customer_index = None
                st.session_state.rerun_needed = True

    # 列表
    st.subheader("📋 客戶列表")
    for i, row in df_disp.iterrows():
        cols = st.columns([2,2,2,1,1])
        cols[0].text(row["客戶編號"])
        cols[1].text(row["客戶簡稱"])
        cols[2].text(row["備註"])
        if cols[3].button("✏️ 修改", key=f"edit_cust_{i}"):
            for k in row.index:
                st.session_state[f"form_customer_{k}"] = row[k]
            st.session_state.edit_customer_index = i
            st.session_state.rerun_needed = True
        if cols[4].button("🗑️ 刪除", key=f"del_cust_{i}"):
            confirm_key = f"confirm_cust_{i}"
            if st.button(f"❗ 確認刪除【{row['客戶編號']}】", key=confirm_key):
                df_cust = df_cust.drop(i).reset_index(drop=True)
                save_sheet(ws_cust, df_cust)
                st.success(f"已刪除【{row['客戶編號']}】")
                st.session_state.rerun_needed = True

# --- Run modules ---
st.sidebar.title("選單")
module = st.sidebar.radio("請選擇模組", ["色粉管理", "客戶名單"])

if module == "色粉管理":
    color_module()
elif module == "客戶名單":
    customer_module()

# rerun if needed
if st.session_state.get("rerun_needed", False):
    st.session_state.rerun_needed = False
    st.experimental_rerun()
