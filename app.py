import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ---------- Google Sheet 設定 ----------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"

# 從 secrets 讀取 GCP json
gcp_info = st.secrets["gcp"]["gcp_json"]
creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(SHEET_URL)

# ---------- 工作表 ----------
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ---------- Streamlit 頁面選單 ----------
st.sidebar.title("系統選單")
page = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"]
)

# ========================================
# =============== 色粉管理 ===============
# ========================================
if page == "色粉管理":

    st.title("🎨 色粉管理")

    # 讀取 Google Sheet
    data_color = ws_color.get_all_records()
    df_color = pd.DataFrame(data_color)

    # 確保 dataframe 不為空
    if df_color.empty:
        df_color = pd.DataFrame(columns=["色粉編號", "色粉名稱", "色粉類別", "備註"])

    # 搜尋
    st.subheader("🔍 搜尋色粉")
    color_search_input = st.text_input("輸入色粉編號或名稱")

    df_color["色粉編號"] = df_color["色粉編號"].fillna("").astype(str)
    df_color["色粉名稱"] = df_color["色粉名稱"].fillna("").astype(str)

    if color_search_input:
        df_color_filtered = df_color[
            df_color["色粉編號"].str.contains(color_search_input, case=False, na=False)
            | df_color["色粉名稱"].str.contains(color_search_input, case=False, na=False)
        ]
        if df_color_filtered.empty:
            st.warning("⚠️ 查無符合的色粉資料！")
    else:
        df_color_filtered = df_color

    # 顯示結果
    st.dataframe(df_color_filtered)

    # 新增/修改表單
    st.subheader("📝 新增 / 修改色粉")

    色粉類別_options = ["色粉", "色母", "添加劑"]
    色粉類別 = st.session_state.get("form_color_色粉類別", "色粉")
    if 色粉類別 not in 色粉類別_options:
        色粉類別 = "色粉"

    st.session_state["form_color_色粉類別"] = st.selectbox(
        "色粉類別",
        色粉類別_options,
        index=色粉類別_options.index(色粉類別)
    )

    色粉編號 = st.text_input("色粉編號", value=st.session_state.get("form_color_色粉編號", ""))
    色粉名稱 = st.text_input("色粉名稱", value=st.session_state.get("form_color_色粉名稱", ""))
    備註 = st.text_input("備註", value=st.session_state.get("form_color_色粉_備註", ""))

    save_color_btn = st.button("💾 儲存")

    if save_color_btn:
        if not 色粉編號:
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            new_data = {
                "色粉編號": 色粉編號,
                "色粉名稱": 色粉名稱,
                "色粉類別": 色粉類別,
                "備註": 備註,
            }

            # 是否修改
            edit_mode = st.session_state.get("color_edit_mode", False)
            edit_index = st.session_state.get("color_edit_index", None)

            if edit_mode and edit_index is not None:
                df_color.iloc[edit_index] = new_data
                ws_color.update([df_color.columns.values.tolist()] + df_color.values.tolist())
                st.success("✅ 色粉修改完成！")
            else:
                # 檢查是否重複
                if 色粉編號 in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    ws_color.update([df_color.columns.values.tolist()] + df_color.values.tolist())
                    st.success("✅ 新增色粉成功！")

            # 清空表單
            for key in ["form_color_色粉編號", "form_color_色粉名稱", "form_color_色粉類別", "form_color_色粉_備註"]:
                st.session_state[key] = ""
            st.session_state["color_edit_mode"] = False
            st.experimental_rerun()

    # 修改 / 刪除按鈕
    for i, row in df_color_filtered.iterrows():
        col1, col2 = st.columns(2)
        if col1.button(f"✏️ 修改 {row['色粉編號']}", key=f"color_edit_{i}"):
            st.session_state["form_color_色粉編號"] = row["色粉編號"]
            st.session_state["form_color_色粉名稱"] = row["色粉名稱"]
            st.session_state["form_color_色粉類別"] = row["色粉類別"]
            st.session_state["form_color_色粉_備註"] = row["備註"]
            st.session_state["color_edit_mode"] = True
            st.session_state["color_edit_index"] = df_color.index[df_color["色粉編號"] == row["色粉編號"]].tolist()[0]
            st.experimental_rerun()

        if col2.button(f"🗑️ 刪除 {row['色粉編號']}", key=f"color_delete_{i}"):
            confirm = st.confirm(f"確定要刪除 {row['色粉編號']} 嗎？")
            if confirm:
                df_color = df_color[df_color["色粉編號"] != row["色粉編號"]].reset_index(drop=True)
                ws_color.update([df_color.columns.values.tolist()] + df_color.values.tolist())
                st.success(f"✅ 已刪除 {row['色粉編號']}！")
                st.experimental_rerun()

# ========================================
# =============== 客戶名單 ===============
# ========================================
elif page == "客戶名單":

    st.title("👥 客戶名單")

    # 讀取 Google Sheet
    data_customer = ws_customer.get_all_records()
    df_customer = pd.DataFrame(data_customer)

    # 確保 dataframe 不為空
    if df_customer.empty:
        df_customer = pd.DataFrame(columns=["客戶編號", "客戶簡稱", "備註"])

    # 搜尋
    st.subheader("🔍 搜尋客戶")
    customer_search_input = st.text_input("輸入客戶編號或名稱")

    df_customer["客戶編號"] = df_customer["客戶編號"].fillna("").astype(str)
    df_customer["客戶簡稱"] = df_customer["客戶簡稱"].fillna("").astype(str)

    if customer_search_input:
        df_customer_filtered = df_customer[
            df_customer["客戶編號"].str.contains(customer_search_input, case=False, na=False)
            | df_customer["客戶簡稱"].str.contains(customer_search_input, case=False, na=False)
        ]
        if df_customer_filtered.empty:
            st.warning("⚠️ 找不到符合條件的客戶！")
    else:
        df_customer_filtered = df_customer

    st.dataframe(df_customer_filtered)

    # 新增 / 修改表單
    st.subheader("📝 新增 / 修改客戶")

    customer_required_columns = ["客戶編號", "客戶簡稱", "備註"]
    form_inputs = {}
    for col in customer_required_columns:
        form_inputs[col] = st.text_input(
            f"{col}",
            value=st.session_state.get(f"form_customer_{col}", "")
        )

    save_customer_btn = st.button("💾 儲存客戶")

    if save_customer_btn:
        new_data = {col: form_inputs[col] for col in customer_required_columns}

        edit_mode = st.session_state.get("customer_edit_mode", False)
        edit_index = st.session_state.get("customer_edit_index", None)

        if edit_mode and edit_index is not None:
            for col in customer_required_columns:
                df_customer.at[edit_index, col] = new_data[col]
            ws_customer.update([df_customer.columns.values.tolist()] + df_customer.values.tolist())
            st.success("✅ 客戶已更新！")
        else:
            if new_data["客戶編號"] in df_customer["客戶編號"].values:
                st.warning("⚠️ 此客戶編號已存在！")
            else:
                df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                ws_customer.update([df_customer.columns.values.tolist()] + df_customer.values.tolist())
                st.success("✅ 新增客戶成功！")

        # 清空表單
        for col in customer_required_columns:
            st.session_state[f"form_customer_{col}"] = ""
        st.session_state["customer_edit_mode"] = False
        st.experimental_rerun()

    # 修改 / 刪除按鈕
    for i, row in df_customer_filtered.iterrows():
        col1, col2 = st.columns(2)
        if col1.button(f"✏️ 修改 {row['客戶編號']}", key=f"customer_edit_{i}"):
            for col in customer_required_columns:
                st.session_state[f"form_customer_{col}"] = str(row[col]) if pd.notna(row[col]) else ""
            st.session_state["customer_edit_mode"] = True
            st.session_state["customer_edit_index"] = df_customer.index[df_customer["客戶編號"] == row["客戶編號"]].tolist()[0]
            st.experimental_rerun()

        if col2.button(f"🗑️ 刪除 {row['客戶編號']}", key=f"customer_delete_{i}"):
            confirm = st.confirm(f"確定要刪除 {row['客戶編號']} 嗎？")
            if confirm:
                df_customer = df_customer[df_customer["客戶編號"] != row["客戶編號"]].reset_index(drop=True)
                ws_customer.update([df_customer.columns.values.tolist()] + df_customer.values.tolist())
                st.success(f"✅ 已刪除 {row['客戶編號']}！")
                st.experimental_rerun()
