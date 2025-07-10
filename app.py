import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ========= GOOGLE SHEET 連線 =========

# 從 secrets.toml 讀取 GCP service account
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)
worksheet_color = spreadsheet.get_worksheet(0)   # 色粉管理
worksheet_customer = spreadsheet.get_worksheet(1)  # 客戶名單

# ========= SIDEBAR 模組切換 =========

st.sidebar.title("系統選單")
module = st.sidebar.radio(
    "請選擇模組：",
    ("色粉管理", "客戶名單")
)

# ========= 色粉管理模組 =========

if module == "色粉管理":

    st.title("🎨 色粉管理")

    required_columns_color = [
        "色粉編號",
        "國際色號",
        "名稱",
        "色粉類別",
        "包裝",
        "備註",
    ]

    # 載入色粉資料
    try:
        data_color = worksheet_color.get_all_records()
        df_color = pd.DataFrame(data_color)
    except:
        df_color = pd.DataFrame(columns=required_columns_color)

    for col in required_columns_color:
        if col not in df_color.columns:
            df_color[col] = ""

    df_color.columns = df_color.columns.str.strip()

    # session_state 初始化
    for col in required_columns_color:
        st.session_state.setdefault(f"form_color_{col}", "")

    st.session_state.setdefault("edit_mode_color", False)
    st.session_state.setdefault("edit_index_color", None)
    st.session_state.setdefault("delete_index_color", None)
    st.session_state.setdefault("show_delete_confirm_color", False)
    st.session_state.setdefault("search_input_color", "")

    st.subheader("🔎 搜尋色粉")
    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        value=st.session_state["search_input_color"],
        key="search_input_color"
    )

    # 直接用 Enter 執行搜尋
    if search_input != st.session_state["search_input_color"]:
        st.session_state["search_input_color"] = search_input
        st.experimental_rerun()

    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        色粉編號 = st.text_input(
            "色粉編號",
            value=st.session_state.get("form_color_色粉編號", ""),
            key="form_color_色粉編號"
        )

        國際色號 = st.text_input(
            "國際色號",
            value=st.session_state.get("form_color_國際色號", ""),
            key="form_color_國際色號"
        )

        名稱 = st.text_input(
            "名稱",
            value=st.session_state.get("form_color_名稱", ""),
            key="form_color_名稱"
        )

    with col2:
        色粉類別 = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.get("form_color_色粉類別", "色粉")
            ),
            key="form_color_色粉類別"
        )

        包裝 = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.get("form_color_包裝", "袋")
            ),
            key="form_color_包裝"
        )

        備註 = st.text_input(
            "備註",
            value=st.session_state.get("form_color_備註", ""),
            key="form_color_備註"
        )

    save_btn_color = st.button("💾 儲存", key="save_color")

    if save_btn_color:
        new_data = {
            col: st.session_state[f"form_color_{col}"] for col in required_columns_color
        }

        if not new_data["色粉編號"]:
            st.warning("⚠️ 色粉編號不得為空！")
        else:
            if st.session_state.edit_mode_color:
                df_color.iloc[st.session_state.edit_index_color] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                worksheet_color.update(values)
            except Exception as e:
                st.error(f"❌ Google Sheet 寫入失敗: {e}")

            st.session_state.edit_mode_color = False
            st.session_state.edit_index_color = None
            for col in required_columns_color:
                st.session_state[f"form_color_{col}"] = ""
            st.experimental_rerun()

    # 刪除確認
    if st.session_state.show_delete_confirm_color:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="confirm_delete_color"):
            idx = st.session_state.delete_index_color
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                worksheet_color.update(values)
                st.success("✅ 已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_color = False
            st.experimental_rerun()
        if col_no.button("否，取消", key="cancel_delete_color"):
            st.session_state.show_delete_confirm_color = False
            st.experimental_rerun()

    # 過濾搜尋
    if st.session_state["search_input_color"]:
        df_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(st.session_state["search_input_color"], case=False, na=False)
            | df_color["國際色號"].astype(str).str.contains(st.session_state["search_input_color"], case=False, na=False)
        ]
    else:
        df_filtered = df_color

    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 2])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])

        with cols[5]:
            col_mod, col_del = st.columns(2)
            if col_mod.button("✏️ 修改", key=f"edit_color_{i}"):
                st.session_state.edit_mode_color = True
                st.session_state.edit_index_color = i
                for col in required_columns_color:
                    st.session_state[f"form_color_{col}"] = row[col]
                st.experimental_rerun()
            if col_del.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_index_color = i
                st.session_state.show_delete_confirm_color = True
                st.experimental_rerun()

# ========= 客戶名單模組 =========

elif module == "客戶名單":

    st.title("👥 客戶名單管理")

    required_columns_customer = [
        "客戶編號",
        "客戶簡稱",
        "備註"
    ]

    # 載入客戶資料
    try:
        data_customer = worksheet_customer.get_all_records()
        df_customer = pd.DataFrame(data_customer)
    except:
        df_customer = pd.DataFrame(columns=required_columns_customer)

    for col in required_columns_customer:
        if col not in df_customer.columns:
            df_customer[col] = ""

    df_customer.columns = df_customer.columns.str.strip()

    for col in required_columns_customer:
        st.session_state.setdefault(f"form_customer_{col}", "")

    st.session_state.setdefault("edit_mode_customer", False)
    st.session_state.setdefault("edit_index_customer", None)
    st.session_state.setdefault("delete_index_customer", None)
    st.session_state.setdefault("show_delete_confirm_customer", False)
    st.session_state.setdefault("search_input_customer", "")

    st.subheader("🔎 搜尋客戶")
    search_input_customer = st.text_input(
        "請輸入客戶編號或名稱",
        value=st.session_state["search_input_customer"],
        key="search_input_customer"
    )

    if search_input_customer != st.session_state["search_input_customer"]:
        st.session_state["search_input_customer"] = search_input_customer
        st.experimental_rerun()

    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)

    with col1:
        客戶編號 = st.text_input(
            "客戶編號",
            value=st.session_state.get("form_customer_客戶編號", ""),
            key="form_customer_客戶編號"
        )

        客戶簡稱 = st.text_input(
            "客戶簡稱",
            value=st.session_state.get("form_customer_客戶簡稱", ""),
            key="form_customer_客戶簡稱"
        )

    with col2:
        備註 = st.text_area(
            "備註",
            value=st.session_state.get("form_customer_備註", ""),
            key="form_customer_備註"
        )

    save_btn_customer = st.button("💾 儲存", key="save_customer")

    if save_btn_customer:
        new_data = {
            col: st.session_state[f"form_customer_{col}"] for col in required_columns_customer
        }

        if not new_data["客戶編號"]:
            st.warning("⚠️ 客戶編號不得為空！")
        else:
            if st.session_state.edit_mode_customer:
                df_customer.iloc[st.session_state.edit_index_customer] = new_data
                st.success("✅ 客戶資料已更新！")
            else:
                if new_data["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                worksheet_customer.update(values)
            except Exception as e:
                st.error(f"❌ Google Sheet 寫入失敗: {e}")

            st.session_state.edit_mode_customer = False
            st.session_state.edit_index_customer = None
            for col in required_columns_customer:
                st.session_state[f"form_customer_{col}"] = ""
            st.experimental_rerun()

    if st.session_state.show_delete_confirm_customer:
        st.warning("⚠️ 確定要刪除此筆客戶資料嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="confirm_delete_customer"):
            idx = st.session_state.delete_index_customer
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                worksheet_customer.update(values)
                st.success("✅ 已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_customer = False
            st.experimental_rerun()
        if col_no.button("否，取消", key="cancel_delete_customer"):
            st.session_state.show_delete_confirm_customer = False
            st.experimental_rerun()

    # 過濾搜尋
    if st.session_state["search_input_customer"]:
        df_filtered_customer = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(st.session_state["search_input_customer"], case=False, na=False)
            | df_customer["客戶簡稱"].astype(str).str.contains(st.session_state["search_input_customer"], case=False, na=False)
        ]
    else:
        df_filtered_customer = df_customer

    st.subheader("📋 客戶名單")

    for i, row in df_filtered_customer.iterrows():
        cols = st.columns([2, 2, 3, 2])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])

        with cols[3]:
            col_mod, col_del = st.columns(2)
            if col_mod.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_mode_customer = True
                st.session_state.edit_index_customer = i
                for col in required_columns_customer:
                    st.session_state[f"form_customer_{col}"] = row[col]
                st.experimental_rerun()
            if col_del.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_index_customer = i
                st.session_state.show_delete_confirm_customer = True
                st.experimental_rerun()
