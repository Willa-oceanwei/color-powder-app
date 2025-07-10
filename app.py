import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# =========== GCP SERVICE ACCOUNT ===========

service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# ========== SHEETS URL ==========
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit"

# ========== 色粉管理模組 ==========
spreadsheet = client.open_by_url(SHEET_URL)
worksheet_color = spreadsheet.get_worksheet(0)

required_color_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

# 讀取色粉資料
try:
    data_color = worksheet_color.get_all_records()
    df_color = pd.DataFrame(data_color)
except:
    df_color = pd.DataFrame(columns=required_color_columns)

# 確保欄位存在
for col in required_color_columns:
    if col not in df_color.columns:
        df_color[col] = ""

# 清理欄位名稱
df_color.columns = df_color.columns.str.strip()

# 初始化 session_state
for col in required_color_columns:
    st.session_state.setdefault(f"form_color_{col}", "")

st.session_state.setdefault("edit_color_mode", False)
st.session_state.setdefault("edit_color_index", None)
st.session_state.setdefault("delete_color_index", None)
st.session_state.setdefault("show_color_delete_confirm", False)
st.session_state.setdefault("search_color_input", "")

# =========== 色粉管理畫面 ==========

st.header("🎨 色粉管理")

# Search
search_color_input = st.text_input(
    "請輸入色粉編號或國際色號 (Enter搜尋)",
    st.session_state.search_color_input,
    key="search_color_input"
)

# 只要改值就 rerun
if search_color_input != st.session_state.search_color_input:
    st.session_state.search_color_input = search_color_input
    st.experimental_rerun()

# 新增 / 修改 form
st.subheader("➕ 新增 / 修改色粉")

col1, col2 = st.columns(2)

with col1:
    色粉編號 = st.text_input(
        "色粉編號",
        key="form_color_色粉編號"
    )
    
    國際色號 = st.text_input(
        "國際色號",
         key="form_color_國際色號"
    )
    
    名稱 = st.text_input(
        "名稱",
         key="form_color_名稱"
    )
    
    色粉類別 = st.text_input(
        "色粉類別",
         key="form_color_色粉類別"
    )
    包裝 = st.text_input(
        "包裝",
         key="form_color_包裝"
    )
    備註 = st.text_input(
        "備註",
         key="form_color_備註"
    )
with col2:
    # 色粉類別
    色粉類別選項 = ["色粉", "色母", "添加劑"]
    目前選項 = st.session_state.get("form_color_色粉類別", "色粉")
    index = 色粉類別選項.index(目前選項) if 目前選項 in 色粉類別選項 else 0

    st.session_state["form_color_色粉類別"] = st.selectbox(
        "色粉類別",
        色粉類別選項,
        index=index,
        key="form_color_色粉類別"
    )

    # 包裝
    包裝選項 = ["袋", "箱", "kg"]
    目前包裝 = st.session_state.get("form_color_包裝", "袋")
    index_pack = 包裝選項.index(目前包裝) if 目前包裝 in 包裝選項 else 0

    st.session_state["form_color_包裝"] = st.selectbox(
        "包裝",
        包裝選項,
        index=index_pack,
        key="form_color_包裝"
    )

    st.session_state["form_color_備註"] = st.text_input(
        "備註",
        st.session_state["form_color_備註"],
        key="form_color_備註"
    )

save_btn = st.button("💾 儲存色粉", key="save_color")

if save_btn:
    new_data = {
        col: st.session_state[f"form_color_{col}"] for col in required_color_columns
    }

    if new_data["色粉編號"] == "":
        st.error("❌ 色粉編號不得為空！")
    else:
        if st.session_state.edit_color_mode:
            df_color.iloc[st.session_state.edit_color_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            if new_data["色粉編號"] in df_color["色粉編號"].values:
                st.warning("⚠️ 此色粉編號已存在！")
            else:
                df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增色粉成功！")

        # 更新 Google Sheet
        try:
            worksheet_color.update(
                [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
            )
        except Exception as e:
            st.error(f"❌ 更新 Google Sheet 失敗: {e}")

        # 清空表單
        st.session_state.edit_color_mode = False
        st.session_state.edit_color_index = None
        for col in required_color_columns:
            st.session_state[f"form_color_{col}"] = ""
        st.experimental_rerun()

if st.session_state.show_color_delete_confirm:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除", key="yes_delete_color"):
        idx = st.session_state.delete_color_index
        df_color.drop(index=idx, inplace=True)
        df_color.reset_index(drop=True, inplace=True)
        try:
            worksheet_color.update(
                [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
            )
            st.success("✅ 色粉已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state.show_color_delete_confirm = False
        st.session_state.delete_color_index = None
        st.experimental_rerun()
    if col_no.button("否，取消", key="no_delete_color"):
        st.session_state.show_color_delete_confirm = False
        st.experimental_rerun()

# 色粉搜尋
if st.session_state.search_color_input:
    df_color_filtered = df_color[
        df_color["色粉編號"].astype(str).str.contains(st.session_state.search_color_input, case=False, na=False)
        | df_color["國際色號"].astype(str).str.contains(st.session_state.search_color_input, case=False, na=False)
    ]
else:
    df_color_filtered = df_color

st.subheader("📋 色粉清單")

for i, row in df_color_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2, 2, 2])
    cols[0].write(str(row["色粉編號"]))
    cols[1].write(str(row["國際色號"]))
    cols[2].write(str(row["名稱"]))
    cols[3].write(str(row["色粉類別"]))
    cols[4].write(str(row["包裝"]))
    with cols[5]:
        c1, c2 = st.columns(2)
        if c1.button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state.edit_color_mode = True
            st.session_state.edit_color_index = i
            for col in required_color_columns:
                st.session_state[f"form_color_{col}"] = str(row.get(col, ""))
            st.experimental_rerun()
        if c2.button("🗑️ 刪除", key=f"delete_color_{i}"):
            st.session_state.delete_color_index = i
            st.session_state.show_color_delete_confirm = True
            st.experimental_rerun()

# ========== 客戶名單模組 ==========

worksheet_customer = spreadsheet.get_worksheet(1)

required_customer_columns = [
    "客戶編號",
    "客戶簡稱",
    "備註"
]

try:
    data_customer = worksheet_customer.get_all_records()
    df_customer = pd.DataFrame(data_customer)
except:
    df_customer = pd.DataFrame(columns=required_customer_columns)

for col in required_customer_columns:
    if col not in df_customer.columns:
        df_customer[col] = ""

df_customer.columns = df_customer.columns.str.strip()

for col in required_customer_columns:
    st.session_state.setdefault(f"form_customer_{col}", "")

st.session_state.setdefault("edit_customer_mode", False)
st.session_state.setdefault("edit_customer_index", None)
st.session_state.setdefault("delete_customer_index", None)
st.session_state.setdefault("show_customer_delete_confirm", False)
st.session_state.setdefault("search_customer_input", "")

st.header("👥 客戶名單")

search_customer_input = st.text_input(
    "請輸入客戶編號或客戶簡稱 (Enter搜尋)",
    st.session_state.search_customer_input,
    key="search_customer_input"
)

if search_customer_input != st.session_state.search_customer_input:
    st.session_state.search_customer_input = search_customer_input
    st.experimental_rerun()

st.subheader("➕ 新增 / 修改客戶")

col1, col2 = st.columns(2)

with col1:
    st.session_state["form_customer_客戶編號"] = st.text_input(
        "客戶編號", 
        st.session_state["form_customer_客戶編號"],
        key="form_customer_客戶編號"
    )
    st.session_state["form_customer_客戶簡稱"] = st.text_input(
        "客戶簡稱",
        st.session_state["form_customer_客戶簡稱"],
        key="form_customer_客戶簡稱"
    )

with col2:
    st.session_state["form_customer_備註"] = st.text_area(
        "備註",
        st.session_state["form_customer_備註"],
        key="form_customer_備註"
    )

save_customer_btn = st.button("💾 儲存客戶", key="save_customer")

if save_customer_btn:
    new_customer_data = {
        col: st.session_state[f"form_customer_{col}"] for col in required_customer_columns
    }

    if new_customer_data["客戶編號"] == "":
        st.error("❌ 客戶編號不得為空！")
    else:
        if st.session_state.edit_customer_mode:
            df_customer.iloc[st.session_state.edit_customer_index] = new_customer_data
            st.success("✅ 客戶已更新！")
        else:
            if new_customer_data["客戶編號"] in df_customer["客戶編號"].values:
                st.warning("⚠️ 此客戶編號已存在！")
            else:
                df_customer = pd.concat([df_customer, pd.DataFrame([new_customer_data])], ignore_index=True)
                st.success("✅ 新增客戶成功！")

        try:
            worksheet_customer.update(
                [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
            )
        except Exception as e:
            st.error(f"❌ 更新 Google Sheet 失敗: {e}")

        st.session_state.edit_customer_mode = False
        st.session_state.edit_customer_index = None
        for col in required_customer_columns:
            st.session_state[f"form_customer_{col}"] = ""
        st.experimental_rerun()

if st.session_state.show_customer_delete_confirm:
    st.warning("⚠️ 確定要刪除此筆客戶嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除", key="yes_delete_customer"):
        idx = st.session_state.delete_customer_index
        df_customer.drop(index=idx, inplace=True)
        df_customer.reset_index(drop=True, inplace=True)
        try:
            worksheet_customer.update(
                [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
            )
            st.success("✅ 客戶已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state.show_customer_delete_confirm = False
        st.session_state.delete_customer_index = None
        st.experimental_rerun()
    if col_no.button("否，取消", key="no_delete_customer"):
        st.session_state.show_customer_delete_confirm = False
        st.experimental_rerun()

# 搜尋客戶
if st.session_state.search_customer_input:
    df_customer_filtered = df_customer[
        df_customer["客戶編號"].astype(str).str.contains(st.session_state.search_customer_input, case=False, na=False)
        | df_customer["客戶簡稱"].astype(str).str.contains(st.session_state.search_customer_input, case=False, na=False)
    ]
else:
    df_customer_filtered = df_customer

st.subheader("📋 客戶清單")

for i, row in df_customer_filtered.iterrows():
    cols = st.columns([3, 3, 3, 3])
    cols[0].write(str(row["客戶編號"]))
    cols[1].write(str(row["客戶簡稱"]))
    cols[2].write(str(row["備註"]))
    with cols[3]:
        c1, c2 = st.columns(2)
        if c1.button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state.edit_customer_mode = True
            st.session_state.edit_customer_index = i
            for col in required_customer_columns:
                st.session_state[f"form_customer_{col}"] = str(row.get(col, ""))
            st.experimental_rerun()
        if c2.button("🗑️ 刪除", key=f"delete_customer_{i}"):
            st.session_state.delete_customer_index = i
            st.session_state.show_customer_delete_confirm = True
            st.experimental_rerun()
