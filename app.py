import streamlit as st
import gspread
import pandas as pd
import json
from google.oauth2.service_account import Credentials

# ===========================
# Google Sheet 授權
# ===========================

# 讀取 secrets
gcp_service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
credentials = Credentials.from_service_account_info(
    gcp_service_account_info,
    scopes=scope
)

gc = gspread.authorize(credentials)

# Google Sheet URL
SHEET_URL = st.secrets["gcp"]["sheet_url"]
spreadsheet = gc.open_by_url(SHEET_URL)

# ===========================
# 共用 Functions
# ===========================

def load_sheet(sheet_name, columns):
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=len(columns))
        ws.append_row(columns)
        ws = spreadsheet.worksheet(sheet_name)

    data = ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(columns=columns)

    return ws, df

def save_sheet(ws, df):
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.values.tolist())
    else:
        # 如果清空，至少保留表頭
        ws.update([df.columns.values.tolist()])

# ===========================
# 色粉管理模組
# ===========================

def color_module():
    st.header("🎨 色粉管理")

    ws_color, df_color = load_sheet(
        "色粉管理",
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    )

    # 初始化 Session State
    for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
        if f"form_color_{col}" not in st.session_state:
            st.session_state[f"form_color_{col}"] = ""

    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None

    # 搜尋
    color_search_input = st.text_input(
        "搜尋色粉編號或名稱",
        st.session_state.get("color_search_input", "")
    )

    filtered_df = df_color
    if color_search_input:
        filtered_df = df_color[
            df_color["色粉編號"].str.contains(color_search_input, na=False) |
            df_color["名稱"].str.contains(color_search_input, na=False)
        ]


    # 新增/修改
    cols = st.columns(2)
    cols[0].text_input("色粉編號", key="form_color_色粉編號")
    cols[1].text_input("國際色號", key="form_color_國際色號")

    cols2 = st.columns(2)
    cols2[0].text_input("名稱", key="form_color_名稱")
    cols2[1].selectbox(
        "色粉類別",
        options=["色粉", "色母", "添加劑"],
        key="form_color_色粉類別"
    )

    cols3 = st.columns(2)
    cols3[0].selectbox(
        "包裝",
        options=["袋裝", "桶裝", "散裝"],
        key="form_color_包裝"
    )
    cols3[1].text_input("備註", key="form_color_備註")

    if st.button("儲存色粉資料"):
        new_row = {
            "色粉編號": st.session_state["form_color_色粉編號"],
            "國際色號": st.session_state["form_color_國際色號"],
            "名稱": st.session_state["form_color_名稱"],
            "色粉類別": st.session_state["form_color_色粉類別"],
            "包裝": st.session_state["form_color_包裝"],
            "備註": st.session_state["form_color_備註"]
        }

        if st.session_state.edit_color_index is not None:
            if st.session_state.edit_color_index < len(df_color):
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.session_state.edit_color_index = None
            else:
                st.error("修改失敗：索引超出範圍")
        else:
            # 檢查是否已有同色粉編號
            if new_row["色粉編號"] in df_color["色粉編號"].values:
                st.warning("此色粉編號已存在，請使用修改！")
                return
            df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)

        save_sheet(ws_color, df_color)
        st.success("儲存完成！")

        # 清空
        for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
            st.session_state[f"form_color_{col}"] = ""

        st.experimental_rerun()

         # 序列
    for i, row in filtered_df.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].markdown(row["色粉編號"])
        cols[1].markdown(row["國際色號"])
        cols[2].markdown(row["名稱"])
        cols[3].markdown(row["色粉類別"])
        cols[4].markdown(row["包裝"])
        cols[5].markdown(row["備註"])

        if cols[5].button("修改", key=f"edit_color_{i}"):
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = row[col]
            st.session_state.edit_color_index = i
            st.experimental_rerun()

        if cols[6].button("刪除", key=f"delete_color_{i}"):
            if st.confirm(f"確定要刪除色粉編號【{row['色粉編號']}】嗎？"):
                df_color.drop(index=i, inplace=True)
                df_color.reset_index(drop=True, inplace=True)
                save_sheet(ws_color, df_color)
                st.success("刪除成功！")
                st.experimental_rerun()

# ===========================
# 客戶名單模組
# ===========================

def customer_module():
    st.header("🧾 客戶名單")

    ws_customer, df_customer = load_sheet(
        "客戶名單",
        ["客戶編號", "客戶簡稱", "備註"]
    )

    for col in ["客戶編號", "客戶簡稱", "備註"]:
        if f"form_customer_{col}" not in st.session_state:
            st.session_state[f"form_customer_{col}"] = ""

    if "edit_customer_index" not in st.session_state:
        st.session_state.edit_customer_index = None

    # 搜尋
    customer_search_input = st.text_input(
        "搜尋客戶簡稱",
        st.session_state.get("customer_search_input", "")
    )

    filtered_df = df_customer
    if customer_search_input:
        filtered_df = df_customer[
            df_customer["客戶簡稱"].str.contains(customer_search_input, na=False)
        ]

    for i, row in filtered_df.iterrows():
        cols = st.columns([3, 3, 3, 1, 1])
        cols[0].markdown(row["客戶編號"])
        cols[1].markdown(row["客戶簡稱"])
        cols[2].markdown(row["備註"])

        if cols[3].button("修改", key=f"edit_customer_{i}"):
            for col in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.session_state.edit_customer_index = i
            st.experimental_rerun()

        if cols[4].button("刪除", key=f"delete_customer_{i}"):
            if st.confirm(f"確定要刪除客戶編號【{row['客戶編號']}】嗎？"):
                df_customer.drop(index=i, inplace=True)
                df_customer.reset_index(drop=True, inplace=True)
                save_sheet(ws_customer, df_customer)
                st.success("刪除成功！")
                st.experimental_rerun()

    cols = st.columns(2)
    cols[0].text_input("客戶編號", key="form_customer_客戶編號")
    cols[1].text_input("客戶簡稱", key="form_customer_客戶簡稱")
    st.text_area("備註", key="form_customer_備註")

    if st.button("儲存客戶資料"):
        new_row = {
            "客戶編號": st.session_state["form_customer_客戶編號"],
            "客戶簡稱": st.session_state["form_customer_客戶簡稱"],
            "備註": st.session_state["form_customer_備註"]
        }

        if st.session_state.edit_customer_index is not None:
            if st.session_state.edit_customer_index < len(df_customer):
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.session_state.edit_customer_index = None
            else:
                st.error("修改失敗：索引超出範圍")
        else:
            if new_row["客戶編號"] in df_customer["客戶編號"].values:
                st.warning("此客戶編號已存在，請使用修改！")
                return
            df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)

        save_sheet(ws_customer, df_customer)
        st.success("儲存完成！")

        for col in ["客戶編號", "客戶簡稱", "備註"]:
            st.session_state[f"form_customer_{col}"] = ""

        st.experimental_rerun()

# ===========================
# 主程式
# ===========================

tab1, tab2 = st.tabs(["色粉管理", "客戶名單"])

with tab1:
    color_module()

with tab2:
    customer_module()
