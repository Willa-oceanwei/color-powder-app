import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ====== GCP Service Account ======
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# ====== Google Sheets 設定 ======
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# ====== 載入工作表 ======
try:
    ws_color = spreadsheet.worksheet("色粉管理")
    color_data = ws_color.get_all_records()
    df_color = pd.DataFrame(color_data)
except:
    df_color = pd.DataFrame(columns=[
        "色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"
    ])

try:
    ws_customer = spreadsheet.worksheet("客戶名單")
    customer_data = ws_customer.get_all_records()
    df_customer = pd.DataFrame(customer_data)
except:
    df_customer = pd.DataFrame(columns=[
        "客戶編號", "客戶簡稱", "備註"
    ])

# ====== Sidebar 模組選單 ======
st.sidebar.title("📁 模組選擇")
module = st.sidebar.radio("請選擇模組", ["色粉管理", "客戶名單"])

# ====== 色粉管理 模組 ======
if module == "色粉管理":
    st.title("🎨 色粉管理系統")

    # 預設 Session State
    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None

    # ------- 搜尋區塊 -------
    search_text = st.text_input("🔍 搜尋色粉編號 / 國際色號", key="color_search_input")

    if search_text:
        df_color_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(search_text, case=False, na=False)
            | df_color["國際色號"].astype(str).str.contains(search_text, case=False, na=False)
        ]
        if df_color_filtered.empty:
            st.warning("查無符合的色粉資料！")
    else:
        df_color_filtered = df_color.copy()

    # ------- 新增/修改區塊 -------
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)
    with col1:
        色粉編號 = st.text_input("色粉編號", st.session_state.get("form_color_色粉編號", ""))
        國際色號 = st.text_input("國際色號", st.session_state.get("form_color_國際色號", ""))
        名稱 = st.text_input("名稱", st.session_state.get("form_color_名稱", ""))
    with col2:
        色粉類別 = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.get("form_color_色粉類別", "色粉")
            ),
        )
        包裝 = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.get("form_color_包裝", "袋")
            ),
        )
        備註 = st.text_input("備註", st.session_state.get("form_color_備註", ""))

    if st.button("💾 儲存"):
        if not 色粉編號:
            st.warning("請輸入色粉編號！")
        else:
            new_row = {
                "色粉編號": 色粉編號,
                "國際色號": 國際色號,
                "名稱": 名稱,
                "色粉類別": 色粉類別,
                "包裝": 包裝,
                "備註": 備註,
            }

            if st.session_state.edit_color_index is not None:
                # 修改
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.success("色粉資料已修改！")
            else:
                if 色粉編號 in df_color["色粉編號"].values:
                    st.warning("色粉編號已存在，請勿重複新增！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("色粉新增完成！")

            # 存回 Google Sheet
            ws_color.update([df_color.columns.values.tolist()] + df_color.fillna("").values.tolist())

            # 清空表單
            st.session_state.edit_color_index = None
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = ""

    # ------- 列表區塊 -------
    st.subheader("📋 色粉清單")
    for i, row in df_color_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        if cols[5].button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state.edit_color_index = i
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = row[col]
        if cols[6].button("🗑️ 刪除", key=f"delete_color_{i}"):
            if st.confirm(f"確定要刪除色粉【{row['色粉編號']}】嗎？"):
                df_color.drop(i, inplace=True)
                df_color.reset_index(drop=True, inplace=True)
                ws_color.update([df_color.columns.values.tolist()] + df_color.fillna("").values.tolist())
                st.success("色粉已刪除！")

# ====== 客戶名單 模組 ======
elif module == "客戶名單":
    st.title("🧾 客戶名單系統")

    if "edit_customer_index" not in st.session_state:
        st.session_state.edit_customer_index = None

    # ------- 搜尋區塊 -------
    search_text = st.text_input("🔍 搜尋客戶編號 / 客戶簡稱", key="customer_search_input")

    if search_text:
        df_customer_filtered = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(search_text, case=False, na=False)
            | df_customer["客戶簡稱"].astype(str).str.contains(search_text, case=False, na=False)
        ]
        if df_customer_filtered.empty:
            st.warning("查無符合的客戶資料！")
    else:
        df_customer_filtered = df_customer.copy()

    # ------- 新增/修改區塊 -------
    st.subheader("➕ 新增 / 修改 客戶名單")

    col1, col2 = st.columns(2)
    with col1:
        客戶編號 = st.text_input("客戶編號", st.session_state.get("form_customer_客戶編號", ""))
        客戶簡稱 = st.text_input("客戶簡稱", st.session_state.get("form_customer_客戶簡稱", ""))
    with col2:
        備註 = st.text_input("備註", st.session_state.get("form_customer_備註", ""))

    if st.button("💾 儲存", key="customer_save_btn"):
        if not 客戶編號:
            st.warning("請輸入客戶編號！")
        else:
            new_row = {
                "客戶編號": 客戶編號,
                "客戶簡稱": 客戶簡稱,
                "備註": 備註,
            }

            if st.session_state.edit_customer_index is not None:
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.success("客戶資料已修改！")
            else:
                if 客戶編號 in df_customer["客戶編號"].values:
                    st.warning("客戶編號已存在，請勿重複新增！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("客戶新增完成！")

            ws_customer.update([df_customer.columns.values.tolist()] + df_customer.fillna("").values.tolist())

            st.session_state.edit_customer_index = None
            for col in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = ""

    # ------- 列表區塊 -------
    st.subheader("📋 客戶清單")
    for i, row in df_customer_filtered.iterrows():
        cols = st.columns([2, 2, 3, 1, 1])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        if cols[3].button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state.edit_customer_index = i
            for col in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = row[col]
        if cols[4].button("🗑️ 刪除", key=f"delete_customer_{i}"):
            if st.confirm(f"確定要刪除客戶【{row['客戶編號']}】嗎？"):
                df_customer.drop(i, inplace=True)
                df_customer.reset_index(drop=True, inplace=True)
                ws_customer.update([df_customer.columns.values.tolist()] + df_customer.fillna("").values.tolist())
                st.success("客戶已刪除！")
