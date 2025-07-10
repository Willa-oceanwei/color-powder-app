import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# -----------------------------
# GCP AUTH
# -----------------------------

# 讀取 GCP secrets
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# Google Sheets URLs
SHEET_URL_COLOR = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
SHEET_URL_CUSTOMER = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"   # 改成你的客戶工作表 gid

# -----------------------------
# Initialize Session State
# -----------------------------

# 共用 State
if "active_module" not in st.session_state:
    st.session_state.active_module = "色粉管理"

# -----------------------------
# Sidebar 選單
# -----------------------------

st.sidebar.title("功能選單")
module_choice = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"],
    index=0 if st.session_state.active_module == "色粉管理" else 1,
)

st.session_state.active_module = module_choice

# -----------------------------
# 色粉管理模組
# -----------------------------

if st.session_state.active_module == "色粉管理":

    st.title("🎨 色粉管理系統")

    # Sheet & DataFrame
    worksheet = client.open_by_url(SHEET_URL_COLOR).get_worksheet(0)
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

    try:
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
    except:
        df = pd.DataFrame(columns=required_columns)

    # 確保所有欄位存在
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    # 防止 dtype 不一致
    df["色粉編號"] = df["色粉編號"].astype(str)
    df["國際色號"] = df["國際色號"].astype(str)

    # 初始化狀態
    for col in required_columns:
        st.session_state.setdefault(f"form_color_{col}", "")

    st.session_state.setdefault("edit_mode_color", False)
    st.session_state.setdefault("edit_index_color", None)
    st.session_state.setdefault("delete_index_color", None)
    st.session_state.setdefault("show_delete_confirm_color", False)
    st.session_state.setdefault("search_input_color", "")

    # ---------- Search ----------
    st.subheader("🔎 搜尋色粉")

    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        value=st.session_state.search_input_color,
        key="search_input_color_input",
        on_change=lambda: st.session_state.update(search_input_color=st.session_state.search_input_color_input)
    )

    # Apply search filter
    if st.session_state.search_input_color:
        pattern = st.session_state.search_input_color
        df_filtered = df[
            df["色粉編號"].fillna("").astype(str).str.contains(pattern, case=False, na=False)
            | df["國際色號"].fillna("").astype(str).str.contains(pattern, case=False, na=False)
        ]
        if df_filtered.empty:
            st.warning("❗ 查無符合的色粉資料。")
    else:
        df_filtered = df

    # ---------- Form ----------
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        色粉編號 = st.text_input(
    "色粉編號",
    value=st.session_state.get("form_color_色粉編號", ""),
    key="form_color_色粉編號"
        )

        st.session_state["form_color_國際色號"] = st.text_input(
            "國際色號",
            st.session_state["form_color_國際色號"],
            key="form_color_國際色號",
        )

        st.session_state["form_color_名稱"] = st.text_input(
            "名稱",
            st.session_state["form_color_名稱"],
            key="form_color_名稱",
        )

    with col2:
        st.session_state["form_color_色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state["form_color_色粉類別"]
            ) if st.session_state["form_color_色粉類別"] in ["色粉", "色母", "添加劑"] else 0,
            key="form_color_色粉類別",
        )

        st.session_state["form_color_包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state["form_color_包裝"]
            ) if st.session_state["form_color_包裝"] in ["袋", "箱", "kg"] else 0,
            key="form_color_包裝",
        )

        st.session_state["form_color_備註"] = st.text_input(
            "備註",
            st.session_state["form_color_備註"],
            key="form_color_備註",
        )

    save_btn = st.button("💾 儲存", key="save_btn_color")

    if save_btn:
        new_data = {
            col: st.session_state[f"form_color_{col}"] for col in required_columns
        }

        if not new_data["色粉編號"]:
            st.warning("⚠️ 色粉編號為必填！")
        else:
            if st.session_state.edit_mode_color:
                df.iloc[st.session_state.edit_index_color] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            # Write to Google Sheets
            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.edit_mode_color = False
            st.session_state.edit_index_color = None
            for col in required_columns:
                st.session_state[f"form_color_{col}"] = ""
            st.experimental_rerun()

    # ---------- Delete confirmation ----------
    if st.session_state.show_delete_confirm_color:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ 是", key="confirm_delete_color_yes"):
            idx = st.session_state.delete_index_color
            df.drop(index=idx, inplace=True)
            df.reset_index(drop=True, inplace=True)
            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_color = False
            st.experimental_rerun()

        if col_no.button("❌ 否", key="confirm_delete_color_no"):
            st.session_state.show_delete_confirm_color = False
            st.experimental_rerun()

    # ---------- Display List ----------
    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 2])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        with cols[5]:
            c1, c2 = st.columns([1, 1])
            if c1.button("✏️ 修改", key=f"edit_color_{i}"):
                st.session_state.edit_mode_color = True
                st.session_state.edit_index_color = i
                for col in required_columns:
                    st.session_state[f"form_color_{col}"] = row[col]
                st.experimental_rerun()
            if c2.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_index_color = i
                st.session_state.show_delete_confirm_color = True
                st.experimental_rerun()

# -----------------------------
# 客戶名單模組
# -----------------------------

if st.session_state.active_module == "客戶名單":

    st.title("👥 客戶名單管理")

    # Sheet & DataFrame
    worksheet = client.open_by_url(SHEET_URL_CUSTOMER).get_worksheet(0)
    required_columns = ["客戶編號", "客戶簡稱", "備註"]

    try:
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
    except:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df["客戶編號"] = df["客戶編號"].astype(str)
    df["客戶簡稱"] = df["客戶簡稱"].astype(str)

    for col in required_columns:
        st.session_state.setdefault(f"form_customer_{col}", "")

    st.session_state.setdefault("edit_mode_customer", False)
    st.session_state.setdefault("edit_index_customer", None)
    st.session_state.setdefault("delete_index_customer", None)
    st.session_state.setdefault("show_delete_confirm_customer", False)
    st.session_state.setdefault("search_input_customer", "")

    # ---------- Search ----------
    st.subheader("🔎 搜尋客戶")

    search_input = st.text_input(
        "請輸入客戶編號或客戶簡稱",
        value=st.session_state.search_input_customer,
        key="search_input_customer_input",
        on_change=lambda: st.session_state.update(search_input_customer=st.session_state.search_input_customer_input)
    )

    # Apply search filter
    if st.session_state.search_input_customer:
        pattern = st.session_state.search_input_customer
        df_filtered = df[
            df["客戶編號"].fillna("").astype(str).str.contains(pattern, case=False, na=False)
            | df["客戶簡稱"].fillna("").astype(str).str.contains(pattern, case=False, na=False)
        ]
        if df_filtered.empty:
            st.warning("❗ 查無符合的客戶資料。")
    else:
        df_filtered = df

    # ---------- Form ----------
    st.subheader("➕ 新增 / 修改 客戶")

    st.session_state["form_customer_客戶編號"] = st.text_input(
        "客戶編號",
        st.session_state["form_customer_客戶編號"],
        key="form_customer_客戶編號",
    )
    st.session_state["form_customer_客戶簡稱"] = st.text_input(
        "客戶簡稱",
        st.session_state["form_customer_客戶簡稱"],
        key="form_customer_客戶簡稱",
    )
    st.session_state["form_customer_備註"] = st.text_area(
        "備註",
        st.session_state["form_customer_備註"],
        key="form_customer_備註",
    )

    save_btn = st.button("💾 儲存", key="save_btn_customer")

    if save_btn:
        new_data = {
            col: st.session_state[f"form_customer_{col}"] for col in required_columns
        }

        if not new_data["客戶編號"]:
            st.warning("⚠️ 客戶編號為必填！")
        else:
            if st.session_state.edit_mode_customer:
                df.iloc[st.session_state.edit_index_customer] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.edit_mode_customer = False
            st.session_state.edit_index_customer = None
            for col in required_columns:
                st.session_state[f"form_customer_{col}"] = ""
            st.experimental_rerun()

    # ---------- Delete confirm ----------
    if st.session_state.show_delete_confirm_customer:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ 是", key="confirm_delete_customer_yes"):
            idx = st.session_state.delete_index_customer
            df.drop(index=idx, inplace=True)
            df.reset_index(drop=True, inplace=True)
            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm_customer = False
            st.experimental_rerun()

        if col_no.button("❌ 否", key="confirm_delete_customer_no"):
            st.session_state.show_delete_confirm_customer = False
            st.experimental_rerun()

    # ---------- Display List ----------
    st.subheader("📋 客戶清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 3, 4, 2])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        with cols[3]:
            c1, c2 = st.columns([1, 1])
            if c1.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_mode_customer = True
                st.session_state.edit_index_customer = i
                for col in required_columns:
                    st.session_state[f"form_customer_{col}"] = row[col]
                st.experimental_rerun()
            if c2.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_index_customer = i
                st.session_state.show_delete_confirm_customer = True
                st.experimental_rerun()
