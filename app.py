import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ============ GCP Service Account ============
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# Your Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# ============ Load Worksheets ============

# 色粉管理 - 工作表1
color_ws = spreadsheet.get_worksheet(0)
color_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

try:
    data_color = color_ws.get_all_records()
    df_color = pd.DataFrame(data_color)
except:
    df_color = pd.DataFrame(columns=color_columns)

for col in color_columns:
    if col not in df_color.columns:
        df_color[col] = ""

# 客戶名單 - 工作表2
customer_ws = spreadsheet.get_worksheet(1)
customer_columns = ["客戶編號", "客戶簡稱", "備註"]

try:
    data_customer = customer_ws.get_all_records()
    df_customer = pd.DataFrame(data_customer)
except:
    df_customer = pd.DataFrame(columns=customer_columns)

for col in customer_columns:
    if col not in df_customer.columns:
        df_customer[col] = ""

# ============ Session State Defaults ============
for col in color_columns:
    st.session_state.setdefault(f"form_color_{col}", "")

for col in customer_columns:
    st.session_state.setdefault(f"form_customer_{col}", "")

# 色粉
st.session_state.setdefault("color_edit_mode", False)
st.session_state.setdefault("color_edit_index", None)
st.session_state.setdefault("color_show_delete_confirm", False)
st.session_state.setdefault("color_delete_index", None)
st.session_state.setdefault("color_search_input", "")

# 客戶
st.session_state.setdefault("customer_edit_mode", False)
st.session_state.setdefault("customer_edit_index", None)
st.session_state.setdefault("customer_show_delete_confirm", False)
st.session_state.setdefault("customer_delete_index", None)
st.session_state.setdefault("customer_search_input", "")

# ============ Sidebar for Navigation ============
st.sidebar.title("🔧 模組選單")
module = st.sidebar.radio("請選擇模組", ["色粉管理", "客戶名單"])

# ============ 色粉管理 ============

if module == "色粉管理":
    st.title("🎨 色粉管理系統")

    # 搜尋
    st.subheader("🔎 搜尋色粉")
    color_search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        st.session_state.color_search_input,
        key="color_search_input",
    )

    if color_search_input:
        df_color_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(color_search_input, case=False, na=False) |
            df_color["國際色號"].astype(str).str.contains(color_search_input, case=False, na=False)
        ]
        if df_color_filtered.empty:
            st.warning("❗ 查無符合條件的色粉。")
    else:
        df_color_filtered = df_color

    # 新增 / 修改
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_color_色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state["form_color_色粉編號"],
        )
        st.session_state["form_color_國際色號"] = st.text_input(
            "國際色號",
            st.session_state["form_color_國際色號"],
        )
        st.session_state["form_color_名稱"] = st.text_input(
            "名稱",
            st.session_state["form_color_名稱"],
        )

    with col2:
        st.session_state["form_color_色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.get("form_color_色粉類別", "色粉")
            )
            if st.session_state.get("form_color_色粉類別", "色粉") in ["色粉", "色母", "添加劑"]
            else 0,
        )

        st.session_state["form_color_包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.get("form_color_包裝", "袋")
            )
            if st.session_state.get("form_color_包裝", "袋") in ["袋", "箱", "kg"]
            else 0,
        )

        st.session_state["form_color_備註"] = st.text_input(
            "備註",
            st.session_state["form_color_備註"],
        )

    save_btn = st.button("💾 儲存", key="save_color_btn")

    if save_btn:
        new_data = {
            col: st.session_state[f"form_color_{col}"] for col in color_columns
        }

        if not new_data["色粉編號"]:
            st.warning("⚠️ 請輸入色粉編號！")
            st.stop()

        if not st.session_state.color_edit_mode:
            if new_data["色粉編號"] in df_color["色粉編號"].astype(str).values:
                st.warning("⚠️ 此色粉編號已存在！")
                st.stop()

        if st.session_state.color_edit_mode:
            df_color.iloc[st.session_state.color_edit_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
            st.success("✅ 新增色粉成功！")

        try:
            values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
            color_ws.update(values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        st.session_state.color_edit_mode = False
        st.session_state.color_edit_index = None
        for col in color_columns:
            st.session_state[f"form_color_{col}"] = ""
        st.experimental_rerun()

    # 列表
    st.subheader("📋 色粉清單")

    for i, row in df_color_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(str(row["色粉編號"]))
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        if cols[5].button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state.color_edit_mode = True
            st.session_state.color_edit_index = i
            for col in color_columns:
                st.session_state[f"form_color_{col}"] = row[col]
            st.experimental_rerun()
        if cols[6].button("🗑️ 刪除", key=f"delete_color_{i}"):
            st.session_state.color_delete_index = i
            st.session_state.color_show_delete_confirm = True
            st.experimental_rerun()

    if st.session_state.color_show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.color_delete_index
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                color_ws.update(values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.color_show_delete_confirm = False
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.color_show_delete_confirm = False
            st.experimental_rerun()

# ============ 客戶名單 ============

elif module == "客戶名單":
    st.title("👥 客戶名單")

    st.subheader("🔎 搜尋客戶")
    customer_search_input = st.text_input(
        "請輸入客戶編號或名稱",
        st.session_state.customer_search_input,
        key="customer_search_input",
    )

    if customer_search_input:
        df_customer_filtered = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(customer_search_input, case=False, na=False) |
            df_customer["客戶簡稱"].astype(str).str.contains(customer_search_input, case=False, na=False)
        ]
        if df_customer_filtered.empty:
            st.warning("❗ 查無符合條件的客戶。")
    else:
        df_customer_filtered = df_customer

    st.subheader("➕ 新增 / 修改 客戶名單")

    st.session_state["form_customer_客戶編號"] = st.text_input(
        "客戶編號",
        st.session_state["form_customer_客戶編號"],
    )
    st.session_state["form_customer_客戶簡稱"] = st.text_input(
        "客戶簡稱",
        st.session_state["form_customer_客戶簡稱"],
    )
    st.session_state["form_customer_備註"] = st.text_area(
        "備註",
        st.session_state["form_customer_備註"],
    )

    save_customer_btn = st.button("💾 儲存", key="save_customer_btn")

    if save_customer_btn:
        new_customer = {
            col: st.session_state[f"form_customer_{col}"] for col in customer_columns
        }

        if not new_customer["客戶編號"]:
            st.warning("⚠️ 請輸入客戶編號！")
            st.stop()

        if not st.session_state.customer_edit_mode:
            if new_customer["客戶編號"] in df_customer["客戶編號"].astype(str).values:
                st.warning("⚠️ 此客戶編號已存在！")
                st.stop()

        if st.session_state.customer_edit_mode:
            df_customer.iloc[st.session_state.customer_edit_index] = new_customer
            st.success("✅ 客戶已更新！")
        else:
            df_customer = pd.concat([df_customer, pd.DataFrame([new_customer])], ignore_index=True)
            st.success("✅ 新增客戶成功！")

        try:
            values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
            customer_ws.update(values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        st.session_state.customer_edit_mode = False
        st.session_state.customer_edit_index = None
        for col in customer_columns:
            st.session_state[f"form_customer_{col}"] = ""
        st.experimental_rerun()

    st.subheader("📋 客戶清單")

    for i, row in df_customer_filtered.iterrows():
        cols = st.columns([2, 3, 3, 1, 1])
        cols[0].write(str(row["客戶編號"]))
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        if cols[3].button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state.customer_edit_mode = True
            st.session_state.customer_edit_index = i
            for col in customer_columns:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.experimental_rerun()
        if cols[4].button("🗑️ 刪除", key=f"delete_customer_{i}"):
            st.session_state.customer_delete_index = i
            st.session_state.customer_show_delete_confirm = True
            st.experimental_rerun()

    if st.session_state.customer_show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.customer_delete_index
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                customer_ws.update(values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.customer_show_delete_confirm = False
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.customer_show_delete_confirm = False
            st.experimental_rerun()
