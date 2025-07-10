import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========

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

# 工作表
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ======== 初始化 SESSION =========

# 色粉管理
required_color_cols = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]
for col in required_color_cols:
    st.session_state.setdefault(f"form_color_{col}", "")
st.session_state.setdefault("color_edit_mode", False)
st.session_state.setdefault("color_edit_index", None)
st.session_state.setdefault("color_delete_index", None)
st.session_state.setdefault("color_show_delete_confirm", False)
st.session_state.setdefault("color_search_input", "")

# 客戶名單
required_customer_cols = [
    "客戶編號",
    "客戶簡稱",
    "備註",
]
for col in required_customer_cols:
    st.session_state.setdefault(f"form_customer_{col}", "")
st.session_state.setdefault("customer_edit_mode", False)
st.session_state.setdefault("customer_edit_index", None)
st.session_state.setdefault("customer_delete_index", None)
st.session_state.setdefault("customer_show_delete_confirm", False)
st.session_state.setdefault("customer_search_input", "")

# ======== 讀取 Google Sheets =========

# 色粉管理
try:
    df_color = pd.DataFrame(ws_color.get_all_records())
except:
    df_color = pd.DataFrame(columns=required_color_cols)
for col in required_color_cols:
    if col not in df_color.columns:
        df_color[col] = ""

# 客戶名單
try:
    df_customer = pd.DataFrame(ws_customer.get_all_records())
except:
    df_customer = pd.DataFrame(columns=required_customer_cols)
for col in required_customer_cols:
    if col not in df_customer.columns:
        df_customer[col] = ""

# ========= SIDEBAR NAV =========
st.sidebar.title("功能選單")
page = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"],
)

# =====================================
# ========== 色粉管理 模組 ==========
# =====================================

if page == "色粉管理":
    st.title("🎨 色粉管理系統")

    # --- 搜尋 ---
    color_search_input = st.text_input(
        "🔎 搜尋色粉編號或國際色號",
        value=st.session_state["color_search_input"],
        key="color_search_input",
    )

    if color_search_input.strip():
        df_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(color_search_input, case=False, na=False)
            | df_color["國際色號"].astype(str).str.contains(color_search_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.warning("❗ 查無資料，請檢查搜尋關鍵字。")
    else:
        df_filtered = df_color

    # --- 新增 / 修改 Form ---
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "色粉編號",
            value=st.session_state["form_color_色粉編號"],
            key="form_color_色粉編號",
        )
        st.text_input(
            "國際色號",
            value=st.session_state["form_color_國際色號"],
            key="form_color_國際色號",
        )
        st.text_input(
            "名稱",
            value=st.session_state["form_color_名稱"],
            key="form_color_名稱",
        )
    with col2:
        st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.get("form_color_色粉類別", "色粉")
            ),
            key="form_color_色粉類別",
        )
        st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.get("form_color_包裝", "袋")
            ),
            key="form_color_包裝",
        )
        st.text_input(
            "備註",
            value=st.session_state["form_color_備註"],
            key="form_color_備註",
        )

    if st.button("💾 儲存 (色粉管理)"):
        new_data = {
            col: st.session_state[f"form_color_{col}"]
            for col in required_color_cols
        }

        if not new_data["色粉編號"]:
            st.error("❗ 色粉編號為必填，請輸入。")
        elif (
            not st.session_state["color_edit_mode"]
            and new_data["色粉編號"] in df_color["色粉編號"].values
        ):
            st.error("❗ 此色粉編號已存在，請勿重複新增！")
        else:
            if st.session_state["color_edit_mode"]:
                df_color.iloc[st.session_state["color_edit_index"]] = new_data
                st.success("✅ 色粉資料已更新！")
            else:
                df_color = pd.concat(
                    [df_color, pd.DataFrame([new_data])],
                    ignore_index=True,
                )
                st.success("✅ 新增色粉成功！")

            # 寫回 Google Sheets
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            # 清空表單
            for col in required_color_cols:
                st.session_state[f"form_color_{col}"] = ""
            st.session_state["color_edit_mode"] = False
            st.experimental_rerun()

    # 刪除確認
    if st.session_state["color_show_delete_confirm"]:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state["color_delete_index"]
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.update(values)
                st.success("✅ 已刪除色粉！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state["color_show_delete_confirm"] = False
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state["color_show_delete_confirm"] = False
            st.experimental_rerun()

    # --- 色粉列表 ---
    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(str(row["色粉編號"]))
        cols[1].write(str(row["國際色號"]))
        cols[2].write(str(row["名稱"]))
        cols[3].write(str(row["色粉類別"]))
        cols[4].write(str(row["包裝"]))
        if cols[5].button("✏️ 修改", key=f"color_edit_{i}"):
            st.session_state["color_edit_mode"] = True
            st.session_state["color_edit_index"] = i
            for col in required_color_cols:
                st.session_state[f"form_color_{col}"] = row[col]
            st.experimental_rerun()
        if cols[6].button("🗑️ 刪除", key=f"color_delete_{i}"):
            st.session_state["color_delete_index"] = i
            st.session_state["color_show_delete_confirm"] = True
            st.experimental_rerun()

# =====================================
# ========== 客戶名單 模組 ==========
# =====================================

elif page == "客戶名單":
    st.title("👥 客戶名單")

    # --- 搜尋 ---
    customer_search_input = st.text_input(
        "🔎 搜尋客戶編號或客戶簡稱",
        value=st.session_state["customer_search_input"],
        key="customer_search_input",
    )

    if customer_search_input.strip():
        df_filtered = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(customer_search_input, case=False, na=False)
            | df_customer["客戶簡稱"].astype(str).str.contains(customer_search_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.warning("❗ 查無客戶資料，請檢查搜尋關鍵字。")
    else:
        df_filtered = df_customer

    # --- 新增 / 修改 Form ---
    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "客戶編號",
            value=st.session_state["form_customer_客戶編號"],
            key="form_customer_客戶編號",
        )
        st.text_input(
            "客戶簡稱",
            value=st.session_state["form_customer_客戶簡稱"],
            key="form_customer_客戶簡稱",
        )
    with col2:
        st.text_area(
            "備註",
            value=st.session_state["form_customer_備註"],
            key="form_customer_備註",
        )

    if st.button("💾 儲存 (客戶名單)"):
        new_data = {
            col: st.session_state[f"form_customer_{col}"]
            for col in required_customer_cols
        }

        if not new_data["客戶編號"]:
            st.error("❗ 客戶編號為必填，請輸入。")
        elif (
            not st.session_state["customer_edit_mode"]
            and new_data["客戶編號"] in df_customer["客戶編號"].values
        ):
            st.error("❗ 此客戶編號已存在，請勿重複新增！")
        else:
            if st.session_state["customer_edit_mode"]:
                df_customer.iloc[st.session_state["customer_edit_index"]] = new_data
                st.success("✅ 客戶資料已更新！")
            else:
                df_customer = pd.concat(
                    [df_customer, pd.DataFrame([new_data])],
                    ignore_index=True,
                )
                st.success("✅ 新增客戶成功！")

            # 寫回 Google Sheets
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            # 清空表單
            for col in required_customer_cols:
                st.session_state[f"form_customer_{col}"] = ""
            st.session_state["customer_edit_mode"] = False
            st.experimental_rerun()

    # 刪除確認
    if st.session_state["customer_show_delete_confirm"]:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state["customer_delete_index"]
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.update(values)
                st.success("✅ 已刪除客戶！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state["customer_show_delete_confirm"] = False
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state["customer_show_delete_confirm"] = False
            st.experimental_rerun()

    # --- 客戶清單 ---
    st.subheader("📋 客戶清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 3, 1, 1])
        cols[0].write(str(row["客戶編號"]))
        cols[1].write(str(row["客戶簡稱"]))
        cols[2].write(str(row["備註"]))
        if cols[3].button("✏️ 修改", key=f"customer_edit_{i}"):
            st.session_state["customer_edit_mode"] = True
            st.session_state["customer_edit_index"] = i
            for col in required_customer_cols:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.experimental_rerun()
        if cols[4].button("🗑️ 刪除", key=f"customer_delete_{i}"):
            st.session_state["customer_delete_index"] = i
            st.session_state["customer_show_delete_confirm"] = True
            st.experimental_rerun()
