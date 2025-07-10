import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ========= GCP SERVICE ACCOUNT =========
# secrets.toml 內容：
# [gcp]
# gcp_service_account = '''{...}'''

gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)

# ========= SHEETS =========
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)
sheet_color = spreadsheet.worksheet("工作表1")
sheet_customer = spreadsheet.worksheet("工作表2")

# ========= DEFAULT COLUMNS =========

color_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
customer_columns = ["客戶編號", "客戶簡稱", "備註"]

# ========= LOAD DATA =========

def load_sheet(worksheet, columns):
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"無法讀取 Google Sheet: {e}")
        return pd.DataFrame(columns=columns)

df_color = load_sheet(sheet_color, color_columns)
df_customer = load_sheet(sheet_customer, customer_columns)

# ========= SIDEBAR NAV =========

page = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "客戶名單"],
    index=0,
)

# ========= SESSION STATE INIT =========

for col in color_columns:
    st.session_state.setdefault(f"form_color_{col}", "")

for col in customer_columns:
    st.session_state.setdefault(f"form_customer_{col}", "")

st.session_state.setdefault("color_edit_index", None)
st.session_state.setdefault("customer_edit_index", None)
st.session_state.setdefault("color_delete_index", None)
st.session_state.setdefault("customer_delete_index", None)

# ========= 色粉管理 PAGE =========

if page == "色粉管理":
    st.title("🎨 色粉管理系統")

    # 搜尋
    color_search_input = st.text_input(
        "請輸入色粉編號或國際色號 (可模糊查詢)",
        key="color_search_input",
    )

    if color_search_input:
        # 轉成字串避免數字欄位出錯
        df_filtered = df_color[
            df_color["色粉編號"].astype(str).str.contains(color_search_input, case=False, na=False)
            | df_color["國際色號"].astype(str).str.contains(color_search_input, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("查無符合的色粉資料。")
    else:
        df_filtered = df_color

    # 新增 / 修改
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_color_色粉編號"] = st.text_input(
            "色粉編號",
            value=st.session_state["form_color_色粉編號"],
            key="form_color_色粉編號",
        )
        st.session_state["form_color_國際色號"] = st.text_input(
            "國際色號",
            value=st.session_state["form_color_國際色號"],
            key="form_color_國際色號",
        )
        st.session_state["form_color_名稱"] = st.text_input(
            "名稱",
            value=st.session_state["form_color_名稱"],
            key="form_color_名稱",
        )

    with col2:
        st.session_state["form_color_色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.get("form_color_色粉類別", "色粉")
            ) if st.session_state.get("form_color_色粉類別", "色粉") in ["色粉", "色母", "添加劑"] else 0,
            key="form_color_色粉類別"
        )
        st.session_state["form_color_包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.get("form_color_包裝", "袋")
            ) if st.session_state.get("form_color_包裝", "袋") in ["袋", "箱", "kg"] else 0,
            key="form_color_包裝"
        )
        st.session_state["form_color_備註"] = st.text_input(
            "備註",
            value=st.session_state["form_color_備註"],
            key="form_color_備註",
        )

    if st.button("💾 儲存色粉"):
        new_data = {col: st.session_state[f"form_color_{col}"] for col in color_columns}
        
        if not new_data["色粉編號"]:
            st.warning("⚠️ 色粉編號為必填！")
        else:
            duplicate = df_color[
                (df_color["色粉編號"] == new_data["色粉編號"])
            ]

            if st.session_state["color_edit_index"] is None and not duplicate.empty:
                st.warning("⚠️ 色粉編號已存在，不可重複新增！")
            else:
                if st.session_state["color_edit_index"] is not None:
                    df_color.iloc[st.session_state["color_edit_index"]] = new_data
                    st.success("✅ 色粉已更新！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                sheet_color.update(values)

                # reset
                for col in color_columns:
                    st.session_state[f"form_color_{col}"] = ""
                st.session_state["color_edit_index"] = None
                st.experimental_rerun()

    # 列表
    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(str(row["色粉編號"]))
        cols[1].write(str(row["國際色號"]))
        cols[2].write(str(row["名稱"]))
        cols[3].write(str(row["色粉類別"]))
        cols[4].write(str(row["包裝"]))

        if cols[5].button("✏️ 修改", key=f"edit_color_{i}"):
            st.session_state["color_edit_index"] = i
            for col in color_columns:
                st.session_state[f"form_color_{col}"] = row[col]
            st.experimental_rerun()

        if cols[6].button("🗑️ 刪除", key=f"delete_color_{i}"):
            df_color.drop(index=i, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
            sheet_color.update(values)
            st.success("✅ 色粉已刪除！")
            st.experimental_rerun()

# ========= 客戶名單 PAGE =========

elif page == "客戶名單":
    st.title("👥 客戶名單")

    customer_search_input = st.text_input(
        "請輸入客戶編號或名稱 (可模糊查詢)",
        key="customer_search_input"
    )

    if customer_search_input:
        df_cust_filtered = df_customer[
            df_customer["客戶編號"].astype(str).str.contains(customer_search_input, case=False, na=False)
            | df_customer["客戶簡稱"].astype(str).str.contains(customer_search_input, case=False, na=False)
        ]
        if df_cust_filtered.empty:
            st.info("查無符合的客戶資料。")
    else:
        df_cust_filtered = df_customer

    # 新增 / 修改
    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_customer_客戶編號"] = st.text_input(
            "客戶編號",
            value=st.session_state["form_customer_客戶編號"],
            key="form_customer_客戶編號",
        )
        st.session_state["form_customer_客戶簡稱"] = st.text_input(
            "客戶簡稱",
            value=st.session_state["form_customer_客戶簡稱"],
            key="form_customer_客戶簡稱",
        )

    with col2:
        st.session_state["form_customer_備註"] = st.text_area(
            "備註",
            value=st.session_state["form_customer_備註"],
            key="form_customer_備註",
            height=100
        )

    if st.button("💾 儲存客戶"):
        new_data = {col: st.session_state[f"form_customer_{col}"] for col in customer_columns}
        
        if not new_data["客戶編號"]:
            st.warning("⚠️ 客戶編號為必填！")
        else:
            duplicate = df_customer[
                (df_customer["客戶編號"] == new_data["客戶編號"])
            ]

            if st.session_state["customer_edit_index"] is None and not duplicate.empty:
                st.warning("⚠️ 客戶編號已存在，不可重複新增！")
            else:
                if st.session_state["customer_edit_index"] is not None:
                    df_customer.iloc[st.session_state["customer_edit_index"]] = new_data
                    st.success("✅ 客戶已更新！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                sheet_customer.update(values)

                for col in customer_columns:
                    st.session_state[f"form_customer_{col}"] = ""
                st.session_state["customer_edit_index"] = None
                st.experimental_rerun()

    # 列表
    st.subheader("📋 客戶清單")

    for i, row in df_cust_filtered.iterrows():
        cols = st.columns([2, 2, 3, 1, 1])
        cols[0].write(str(row["客戶編號"]))
        cols[1].write(str(row["客戶簡稱"]))
        cols[2].write(str(row["備註"]))

        if cols[3].button("✏️ 修改", key=f"edit_customer_{i}"):
            st.session_state["customer_edit_index"] = i
            for col in customer_columns:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.experimental_rerun()

        if cols[4].button("🗑️ 刪除", key=f"delete_customer_{i}"):
            df_customer.drop(index=i, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
            sheet_customer.update(values)
            st.success("✅ 客戶已刪除！")
            st.experimental_rerun()
