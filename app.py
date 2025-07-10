import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ====== GCP 認證 ======
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)

# ====== Google Sheet 設定 ======
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)
worksheet_color = spreadsheet.get_worksheet(0)
worksheet_customer = spreadsheet.get_worksheet(1)

# ====== Streamlit 頁面選單 ======
st.sidebar.title("模組選擇")
module = st.sidebar.radio("請選擇模組", ["色粉管理", "客戶名單"])

# ====== 色粉管理模組 ======
if module == "色粉管理":
    st.title("🎨 色粉管理系統")

    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

    try:
        data = worksheet_color.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df.columns = df.columns.str.strip()

    for col in required_columns:
        st.session_state.setdefault(f"form_color_{col}", "")

    st.session_state.setdefault("edit_index_color", None)
    st.session_state.setdefault("delete_index_color", None)
    st.session_state.setdefault("show_delete_color", False)
    st.session_state.setdefault("search_color", "")

    st.subheader("🔍 搜尋色粉")
    search_input = st.text_input("請輸入色粉編號或國際色號", key="search_color")

    if search_input:
        df_filtered = df[
            df["色粉編號"].astype(str).str.contains(search_input, case=False, na=False)
            | df["國際色號"].astype(str).str.contains(search_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("找不到符合的色粉資料。")
    else:
        df_filtered = df

    st.subheader("➕ 新增 / 修改 色粉")
    col1, col2 = st.columns(2)

    with col1:
        色粉編號 = st.text_input("色粉編號", key="form_color_色粉編號")
        國際色號 = st.text_input("國際色號", key="form_color_國際色號")
        名稱 = st.text_input("名稱", key="form_color_名稱")

    with col2:
        色粉類別 = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(st.session_state.get("form_color_色粉類別", "色粉")),
            key="form_color_色粉類別"
        )
        包裝 = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(st.session_state.get("form_color_包裝", "袋")),
            key="form_color_包裝"
        )
        備註 = st.text_input("備註", key="form_color_備註")

    if st.button("💾 儲存色粉", key="save_color"):
        if not 色粉編號:
            st.warning("❗ 請輸入色粉編號！")
        else:
            new_data = {
                "色粉編號": 色粉編號,
                "國際色號": 國際色號,
                "名稱": 名稱,
                "色粉類別": 色粉類別,
                "包裝": 包裝,
                "備註": 備註,
            }
            if st.session_state.edit_index_color is not None:
                df.iloc[st.session_state.edit_index_color] = new_data
                st.success("✅ 色粉資料已更新！")
            else:
                if 色粉編號 in df["色粉編號"].values:
                    st.warning("⚠️ 色粉編號已存在，請勿重複新增！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            try:
                worksheet_color.update([df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist())
            except Exception as e:
                st.error(f"❌ 更新 Google Sheet 失敗: {e}")

            st.session_state.edit_index_color = None
            for col in required_columns:
                st.session_state[f"form_color_{col}"] = ""
            st.experimental_rerun()

    if st.session_state.show_delete_color:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_del_yes, col_del_no = st.columns(2)
        if col_del_yes.button("是，刪除", key="yes_delete_color"):
            df.drop(index=st.session_state.delete_index_color, inplace=True)
            df.reset_index(drop=True, inplace=True)
            worksheet_color.update([df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist())
            st.success("✅ 色粉已刪除！")
            st.session_state.show_delete_color = False
            st.experimental_rerun()
        if col_del_no.button("否，取消", key="no_delete_color"):
            st.session_state.show_delete_color = False
            st.experimental_rerun()

    st.subheader("📋 色粉清單")
    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        with cols[5]:
            if st.button("✏️ 修改", key=f"edit_color_{i}"):
                st.session_state.edit_index_color = i
                for col in required_columns:
                    st.session_state[f"form_color_{col}"] = row[col]
                st.experimental_rerun()
        with cols[6]:
            if st.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_index_color = i
                st.session_state.show_delete_color = True
                st.experimental_rerun()

# ====== 客戶名單模組 ======
elif module == "客戶名單":
    st.title("📁 客戶名單管理")

    customer_columns = ["客戶編號", "客戶簡稱", "備註"]

    try:
        data = worksheet_customer.get_all_records()
        df_cust = pd.DataFrame(data)
    except:
        df_cust = pd.DataFrame(columns=customer_columns)

    for col in customer_columns:
        if col not in df_cust.columns:
            df_cust[col] = ""

    df_cust.columns = df_cust.columns.str.strip()

    for col in customer_columns:
        st.session_state.setdefault(f"form_customer_{col}", "")

    st.session_state.setdefault("edit_index_cust", None)
    st.session_state.setdefault("delete_index_cust", None)
    st.session_state.setdefault("show_delete_cust", False)
    st.session_state.setdefault("search_cust", "")

    st.subheader("🔍 搜尋客戶")
    cust_input = st.text_input("請輸入客戶編號或簡稱", key="search_cust")

    if cust_input:
        df_cust_filtered = df_cust[
            df_cust["客戶編號"].astype(str).str.contains(cust_input, case=False, na=False)
            | df_cust["客戶簡稱"].astype(str).str.contains(cust_input, case=False, na=False)
        ]
        if df_cust_filtered.empty:
            st.info("找不到符合的客戶資料。")
    else:
        df_cust_filtered = df_cust

    st.subheader("➕ 新增 / 修改 客戶")
    col1, col2 = st.columns(2)

    with col1:
        客戶編號 = st.text_input("客戶編號", key="form_customer_客戶編號")
        客戶簡稱 = st.text_input("客戶簡稱", key="form_customer_客戶簡稱")
    with col2:
        備註 = st.text_area("備註", key="form_customer_備註")

    if st.button("💾 儲存客戶", key="save_customer"):
        if not 客戶編號:
            st.warning("❗ 請輸入客戶編號！")
        else:
            new_data = {
                "客戶編號": 客戶編號,
                "客戶簡稱": 客戶簡稱,
                "備註": 備註,
            }
            if st.session_state.edit_index_cust is not None:
                df_cust.iloc[st.session_state.edit_index_cust] = new_data
                st.success("✅ 客戶資料已更新！")
            else:
                if 客戶編號 in df_cust["客戶編號"].values:
                    st.warning("⚠️ 客戶編號已存在，請勿重複新增！")
                else:
                    df_cust = pd.concat([df_cust, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                worksheet_customer.update([df_cust.columns.values.tolist()] + df_cust.fillna("").astype(str).values.tolist())
            except Exception as e:
                st.error(f"❌ 更新 Google Sheet 失敗: {e}")

            st.session_state.edit_index_cust = None
            for col in customer_columns:
                st.session_state[f"form_customer_{col}"] = ""
            st.experimental_rerun()

    if st.session_state.show_delete_cust:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_del_yes, col_del_no = st.columns(2)
        if col_del_yes.button("是，刪除", key="yes_delete_cust"):
            df_cust.drop(index=st.session_state.delete_index_cust, inplace=True)
            df_cust.reset_index(drop=True, inplace=True)
            worksheet_customer.update([df_cust.columns.values.tolist()] + df_cust.fillna("").astype(str).values.tolist())
            st.success("✅ 客戶已刪除！")
            st.session_state.show_delete_cust = False
            st.experimental_rerun()
        if col_del_no.button("否，取消", key="no_delete_cust"):
            st.session_state.show_delete_cust = False
            st.experimental_rerun()

    st.subheader("📋 客戶清單")
    for i, row in df_cust_filtered.iterrows():
        cols = st.columns([3, 3, 3, 1, 1])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        with cols[3]:
            if st.button("✏️ 修改", key=f"edit_cust_{i}"):
                st.session_state.edit_index_cust = i
                for col in customer_columns:
                    st.session_state[f"form_customer_{col}"] = row[col]
                st.experimental_rerun()
        with cols[4]:
            if st.button("🗑️ 刪除", key=f"delete_cust_{i}"):
                st.session_state.delete_index_cust = i
                st.session_state.show_delete_cust = True
                st.experimental_rerun()
