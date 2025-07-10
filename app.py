import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
import json

# ---------- GCP 認證 ----------
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)

SHEET_URL = st.secrets["gcp"]["sheet_url"]
spreadsheet = client.open_by_url(SHEET_URL)

# ---------- 工具函式 ----------

def load_sheet(sheet_name, columns):
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=len(columns))
        ws.update([columns])
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=columns)
    return ws, df


def save_sheet(ws, df):
    if df.empty:
        st.warning(f"《{ws.title}》是空的，未更新！")
        return
    values = df.astype(str).fillna("").values.tolist()
    ws.update([df.columns.values.tolist()] + values)


# ---------- 色粉管理 ----------

def color_module():
    st.subheader("🎨 色粉管理")

    ws_color, df_color = load_sheet(
        "色粉管理",
        ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"],
    )

    # --- 搜尋 ---
    st.markdown("#### 🔎 搜尋色粉")
    color_search_input = st.text_input("請輸入色粉編號或名稱", key="color_search_input")
    if color_search_input:
        df_color_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(color_search_input, case=False, na=False) |
            df_color["名稱"].astype(str).str.contains(color_search_input, case=False, na=False)
        ]
        if df_color_filtered.empty:
            st.warning("查無符合資料。")
        else:
            df_color = df_color_filtered

    # --- 新增/編輯表單 ---
    st.markdown("#### ➕ 新增/編輯色粉")

    # 建立 form 預設值
    for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
        st.session_state.setdefault(f"form_color_{col}", "")

    col1, col2 = st.columns(2)
    st.session_state["form_color_色粉編號"] = col1.text_input("色粉編號", st.session_state["form_color_色粉編號"])
    st.session_state["form_color_國際色號"] = col2.text_input("國際色號", st.session_state["form_color_國際色號"])

    col3, col4 = st.columns(2)
    st.session_state["form_color_名稱"] = col3.text_input("名稱", st.session_state["form_color_名稱"])
    st.session_state["form_color_色粉類別"] = col4.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(
            st.session_state.get("form_color_色粉類別", "色粉")
        ) if st.session_state.get("form_color_色粉類別") else 0
    )

    col5, col6 = st.columns(2)
    st.session_state["form_color_包裝"] = col5.text_input("包裝", st.session_state["form_color_包裝"])
    st.session_state["form_color_備註"] = col6.text_input("備註", st.session_state["form_color_備註"])

    # 儲存按鈕
    save_color = st.button("💾 儲存色粉")

    if save_color:
        if not st.session_state["form_color_色粉編號"]:
            st.warning("色粉編號不可空白！")
        else:
            new_row = {col: st.session_state[f"form_color_{col}"] for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]}

            # 新增或修改
            if st.session_state.get("edit_color_index") is not None:
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.success("色粉修改完成！")
                st.session_state.edit_color_index = None
            else:
                if (df_color["色粉編號"] == new_row["色粉編號"]).any():
                    st.warning("色粉編號重複！請更換編號。")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("色粉新增完成！")

            save_sheet(ws_color, df_color)
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = ""
            st.experimental_rerun()

    # --- 列表 ---
    st.markdown("#### 📋 色粉清單")

    for i, row in df_color.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        for j, colname in enumerate(["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]):
            cols[j].markdown(str(row[colname]))

        if cols[-2].button("修改", key=f"edit_color_{i}"):
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = row[col]
            st.session_state.edit_color_index = i
            st.experimental_rerun()

        if cols[-1].button("刪除", key=f"delete_color_{i}"):
            st.session_state.delete_color_index = i

    if st.session_state.get("delete_color_index") is not None:
        index = st.session_state.delete_color_index
        if index in df_color.index:
            row = df_color.loc[index]
            if st.confirm(f"確定要刪除色粉編號【{row['色粉編號']}】嗎？"):
                df_color.drop(index, inplace=True)
                df_color.reset_index(drop=True, inplace=True)
                save_sheet(ws_color, df_color)
                st.success("已刪除！")
                st.session_state.delete_color_index = None
                st.experimental_rerun()
        else:
            st.session_state.delete_color_index = None

# ---------- 客戶名單 ----------

def customer_module():
    st.subheader("📒 客戶名單")

    ws_customer, df_customer = load_sheet(
        "客戶名單",
        ["客戶編號", "客戶簡稱", "備註"],
    )

    # --- 搜尋 ---
    st.markdown("#### 🔎 搜尋客戶")
    customer_search_input = st.text_input("請輸入客戶編號或簡稱", key="customer_search_input")
    if customer_search_input:
        df_filtered = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(customer_search_input, case=False, na=False) |
            df_customer["客戶簡稱"].astype(str).str.contains(customer_search_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.warning("查無符合客戶！")
        else:
            df_customer = df_filtered

    # --- 新增/編輯表單 ---
    st.markdown("#### ➕ 新增/編輯客戶")

    for col in ["客戶編號", "客戶簡稱", "備註"]:
        st.session_state.setdefault(f"form_customer_{col}", "")

    col1, col2 = st.columns(2)
    st.session_state["form_customer_客戶編號"] = col1.text_input("客戶編號", st.session_state["form_customer_客戶編號"])
    st.session_state["form_customer_客戶簡稱"] = col2.text_input("客戶簡稱", st.session_state["form_customer_客戶簡稱"])

    col3, _ = st.columns([2, 2])
    st.session_state["form_customer_備註"] = col3.text_input("備註", st.session_state["form_customer_備註"])

    save_customer = st.button("💾 儲存客戶")

    if save_customer:
        if not st.session_state["form_customer_客戶編號"]:
            st.warning("客戶編號不可空白！")
        else:
            new_row = {col: st.session_state[f"form_customer_{col}"] for col in ["客戶編號", "客戶簡稱", "備註"]}

            if st.session_state.get("edit_customer_index") is not None:
                df_customer.iloc[st.session_state.edit_customer_index] = new_row
                st.success("客戶修改完成！")
                st.session_state.edit_customer_index = None
            else:
                if (df_customer["客戶編號"] == new_row["客戶編號"]).any():
                    st.warning("客戶編號重複！請更換編號。")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("客戶新增完成！")

            save_sheet(ws_customer, df_customer)
            for col in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = ""
            st.experimental_rerun()

    # --- 列表 ---
    st.markdown("#### 📋 客戶清單")

    for i, row in df_customer.iterrows():
        cols = st.columns([2, 2, 2, 1, 1])
        for j, colname in enumerate(["客戶編號", "客戶簡稱", "備註"]):
            cols[j].markdown(str(row[colname]))

        if cols[-2].button("修改", key=f"edit_customer_{i}"):
            for col in ["客戶編號", "客戶簡稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.session_state.edit_customer_index = i
            st.experimental_rerun()

        if cols[-1].button("刪除", key=f"delete_customer_{i}"):
            st.session_state.delete_customer_index = i

    if st.session_state.get("delete_customer_index") is not None:
        index = st.session_state.delete_customer_index
        if index in df_customer.index:
            row = df_customer.loc[index]
            if st.confirm(f"確定要刪除客戶編號【{row['客戶編號']}】嗎？"):
                df_customer.drop(index, inplace=True)
                df_customer.reset_index(drop=True, inplace=True)
                save_sheet(ws_customer, df_customer)
                st.success("已刪除！")
                st.session_state.delete_customer_index = None
                st.experimental_rerun()
        else:
            st.session_state.delete_customer_index = None

# ---------- 主選單 ----------

st.sidebar.title("模組選擇")
module = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"],
)

if module == "色粉管理":
    color_module()
elif module == "客戶名單":
    customer_module()
