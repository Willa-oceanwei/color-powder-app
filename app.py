import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2 import service_account
from gspread.exceptions import WorksheetNotFound, APIError

# --------- 認證 Google Sheets ----------
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(
    gcp_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
client = gspread.authorize(creds)

SHEET_URL = st.secrets["gcp"]["sheet_url"]
spreadsheet = client.open_by_url(SHEET_URL)

# --------- 工具函式 ----------
def load_sheet(name, columns):
    try:
        ws = spreadsheet.worksheet(name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=columns)
        else:
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
        return ws, df
    except WorksheetNotFound:
        existing_titles = [ws.title for ws in spreadsheet.worksheets()]
        if name not in existing_titles:
            spreadsheet.add_worksheet(name, rows=1000, cols=len(columns))
        ws = spreadsheet.worksheet(name)
        ws.append_row(columns)
        df = pd.DataFrame(columns=columns)
        return ws, df

def save_sheet(ws, df):
    ws.clear()
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.values.tolist())

# --------- 載入資料 ----------
# 色粉管理
color_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
ws_color, df_color = load_sheet("色粉管理", color_columns)

# 客戶名單
customer_columns = ["客戶編號", "客戶簡稱", "備註"]
ws_customer, df_customer = load_sheet("客戶名單", customer_columns)

# --------- Streamlit 頁面選單 ----------
st.sidebar.header("模組選擇")
module = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"],
)

# --------- 色粉管理 ----------
if module == "色粉管理":

    st.subheader("色粉管理")

    # 初始化 session_state
    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None

    # 搜尋欄位
    color_search_input = st.text_input("輸入色粉編號或名稱搜尋", "")
    st.session_state.color_search_input = color_search_input

    if color_search_input:
        filtered_color = df_color[
            df_color["色粉編號"].astype(str).str.contains(color_search_input, case=False, na=False) |
            df_color["名稱"].astype(str).str.contains(color_search_input, case=False, na=False)
        ]
        if filtered_color.empty:
            st.warning("查無相關色粉資料！")
    else:
        filtered_color = df_color

    # 新增/修改表單
    st.markdown("### 新增 / 修改色粉")

    col1, col2 = st.columns(2)
    色粉編號 = col1.text_input(
        "色粉編號",
        value="" if st.session_state.edit_color_index is None else str(
            df_color.loc[st.session_state.edit_color_index, "色粉編號"]
        ),
        key="form_color_色粉編號"
    )
    國際色號 = col2.text_input(
        "國際色號",
        value="" if st.session_state.edit_color_index is None else str(
            df_color.loc[st.session_state.edit_color_index, "國際色號"]
        ),
        key="form_color_國際色號"
    )

    col3, col4 = st.columns(2)
    名稱 = col3.text_input(
        "名稱",
        value="" if st.session_state.edit_color_index is None else str(
            df_color.loc[st.session_state.edit_color_index, "名稱"]
        ),
        key="form_color_名稱"
    )

    色粉類別_value = "" if st.session_state.edit_color_index is None else str(
        df_color.loc[st.session_state.edit_color_index, "色粉類別"]
    )
    if 色粉類別_value not in ["色粉", "色母", "添加劑"]:
        色粉類別_value = "色粉"

    色粉類別 = col4.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(色粉類別_value),
        key="form_color_色粉類別"
    )

    col5, col6 = st.columns(2)
    包裝 = col5.text_input(
        "包裝",
        value="" if st.session_state.edit_color_index is None else str(
            df_color.loc[st.session_state.edit_color_index, "包裝"]
        ),
        key="form_color_包裝"
    )
    備註 = col6.text_input(
        "備註",
        value="" if st.session_state.edit_color_index is None else str(
            df_color.loc[st.session_state.edit_color_index, "備註"]
        ),
        key="form_color_備註"
    )

    # 儲存按鈕
    if st.button("💾 儲存"):
        if 色粉編號.strip() == "":
            st.warning("色粉編號為必填欄位！")
        else:
            new_row = {
                "色粉編號": 色粉編號,
                "國際色號": 國際色號,
                "名稱": 名稱,
                "色粉類別": 色粉類別,
                "包裝": 包裝,
                "備註": 備註,
            }

            # 修改
            if st.session_state.edit_color_index is not None:
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.success("修改成功！")
                st.session_state.edit_color_index = None
            else:
                # 檢查重複
                if (df_color["色粉編號"] == 色粉編號).any():
                    st.warning("色粉編號已存在！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("新增成功！")

            save_sheet(ws_color, df_color)
            st.experimental_rerun()

    st.markdown("---")

    # 序列
    st.markdown("### 色粉列表")

    for i, row in filtered_color.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(str(row.get("色粉編號", "")))
        cols[1].write(str(row.get("國際色號", "")))
        cols[2].write(str(row.get("名稱", "")))
        cols[3].write(str(row.get("色粉類別", "")))
        cols[4].write(str(row.get("包裝", "")))
        cols[5].write(str(row.get("備註", "")))

        if cols[5].button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state.edit_color_index = i
            st.experimental_rerun()

        if cols[6].button("🗑️ 刪除", key=f"delete_color_{i}"):
            df_color.drop(i, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            save_sheet(ws_color, df_color)
            st.success("已刪除色粉！")
            st.experimental_rerun()

# --------- 客戶名單 ----------
elif module == "客戶名單":

    st.subheader("客戶名單")

    if "edit_customer_index" not in st.session_state:
        st.session_state.edit_customer_index = None

    # 搜尋
    customer_search_input = st.text_input("輸入客戶編號或名稱搜尋", "")
    st.session_state.customer_search_input = customer_search_input

    if customer_search_input:
        filtered_customer = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(customer_search_input, case=False, na=False) |
            df_customer["客戶簡稱"].astype(str).str.contains(customer_search_input, case=False, na=False)
        ]
        if filtered_customer.empty:
            st.warning("查無相關客戶資料！")
    else:
        filtered_customer = df_customer

    st.markdown("### 新增 / 修改客戶")

    col1, col2 = st.columns(2)
    客戶編號 = col1.text_input(
        "客戶編號",
        value="" if st.session_state.edit_customer_index is None else str(
            df_customer.loc[st.session_state.edit_customer_index, "客戶編號"]
        ),
        key="form_customer_客戶編號"
    )
    客戶簡稱 = col2.text_input(
        "客戶簡稱",
        value="" if st.session_state.edit_customer_index is None else str(
            df_customer.loc[st.session_state.edit_customer_index, "客戶簡稱"]
        ),
        key="form_customer_客戶簡稱"
    )

    col3, _ = st.columns([2, 1])
    備註 = col3.text_input(
        "備註",
        value="" if st.session_state.edit_customer_index is None else str(
            df_customer.loc[st.session_state.edit_customer_index, "備註"]
        ),
        key="form_customer_備註"
    )

    if st.button("💾 儲存", key="save_customer"):
        if 客戶編號.strip() == "":
            st.warning("客戶編號為必填欄位！")
        else:
            new_row = {
                "客戶編號": 客戶編號,
                "客戶簡稱": 客戶簡稱,
                "備註": 備註,
            }

            if st.session_state.edit_customer_index is not None:
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.success("修改成功！")
                st.session_state.edit_customer_index = None
            else:
                if (df_customer["客戶編號"] == 客戶編號).any():
                    st.warning("客戶編號已存在！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("新增成功！")

            save_sheet(ws_customer, df_customer)
            st.experimental_rerun()

    st.markdown("---")

    st.markdown("### 客戶列表")

    for i, row in filtered_customer.iterrows():
        cols = st.columns([2, 2, 3, 1, 1])
        cols[0].write(str(row.get("客戶編號", "")))
        cols[1].write(str(row.get("客戶簡稱", "")))
        cols[2].write(str(row.get("備註", "")))

        if cols[3].button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state.edit_customer_index = i
            st.experimental_rerun()

        if cols[4].button("🗑️ 刪除", key=f"delete_customer_{i}"):
            df_customer.drop(i, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            save_sheet(ws_customer, df_customer)
            st.success("已刪除客戶！")
            st.experimental_rerun()
