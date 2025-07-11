import streamlit as st
import gspread
import pandas as pd
import json
from google.oauth2.service_account import Credentials

# ===========================
# Google Sheet 授權
# ===========================

# 載入 GCP Service Account
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
        ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
    else:
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
        key = f"form_color_{col}"
        if key not in st.session_state:
            st.session_state[key] = ""

    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None

    if "color_search_input" not in st.session_state:
        st.session_state.color_search_input = ""

    def update_color_search():
        st.session_state.color_search_input = st.session_state.temp_color_search

    st.text_input(
        "搜尋色粉編號或名稱",
        st.session_state.color_search_input,
        key="temp_color_search",
        on_change=update_color_search
    )

    filtered_df = df_color.copy()
    if st.session_state.color_search_input:
        filtered_df = df_color[
            df_color["色粉編號"].astype(str).str.contains(st.session_state.color_search_input, na=False) |
            df_color["名稱"].astype(str).str.contains(st.session_state.color_search_input, na=False)
        ]

    st.subheader("新增 / 修改 色粉")

    cols1 = st.columns(2)
    cols1[0].text_input("色粉編號", key="form_color_色粉編號")
    cols1[1].text_input("國際色號", key="form_color_國際色號")

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
            "備註": st.session_state["form_color_備註"],
        }

        if st.session_state.edit_color_index is not None:
            if st.session_state.edit_color_index < len(df_color):
                df_color.iloc[st.session_state.edit_color_index] = new_row
                st.session_state.edit_color_index = None
            else:
                st.error("修改失敗：索引超出範圍")
        else:
            if new_row["色粉編號"] in df_color["色粉編號"].values:
                st.warning("此色粉編號已存在，請使用修改！")
                return
            df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)

        save_sheet(ws_color, df_color)
        st.success("儲存完成！")

        for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
            st.session_state[f"form_color_{col}"] = ""

        st.experimental_rerun()

    st.subheader("色粉清單")

    if filtered_df.empty:
        st.info("查無資料")
    else:
        for i, row in filtered_df.iterrows():
            row_filled = row.fillna("")
            cols = st.columns([2, 2, 2, 2, 2, 2, 1, 1])
            cols[0].markdown(f"**{row_filled['色粉編號']}**")
            cols[1].markdown(f"{row_filled['國際色號']}")
            cols[2].markdown(f"{row_filled['名稱']}")
            cols[3].markdown(f"{row_filled['色粉類別']}")
            cols[4].markdown(f"{row_filled['包裝']}")
            cols[5].markdown(f"{row_filled['備註']}")

            if cols[6].button("✏️ 修改", key=f"edit_color_{i}"):
                for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                    try:
                        st.session_state[f"form_color_{col}"] = str(row[col]) if pd.notna(row[col]) else ""
                    except:
                        st.session_state[f"form_color_{col}"] = ""
                st.session_state.edit_color_index = i
                st.experimental_rerun()

            if cols[7].button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_color_index = i
                st.session_state.delete_color_confirm = True

        if st.session_state.get("delete_color_confirm", False):
            idx = st.session_state.get("delete_color_index")
            row = df_color.iloc[idx]
            st.warning(f"確定要刪除色粉編號【{row['色粉編號']}】嗎？")
            confirm_cols = st.columns(2)
            if confirm_cols[0].button("✅ 確定刪除"):
                df_color.drop(index=idx, inplace=True)
                df_color.reset_index(drop=True, inplace=True)
                save_sheet(ws_color, df_color)
                st.success("刪除成功！")
                st.session_state.delete_color_confirm = False
                st.experimental_rerun()
            if confirm_cols[1].button("❌ 取消"):
                st.session_state.delete_color_confirm = False
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

    # 初始化 Session State
    for col in ["客戶編號", "客戶簡稱", "備註"]:
        key = f"form_customer_{col}"
        if key not in st.session_state:
            st.session_state[key] = ""

    if "edit_customer_index" not in st.session_state:
        st.session_state.edit_customer_index = None

    if "customer_search_input" not in st.session_state:
        st.session_state.customer_search_input = ""

    def update_customer_search():
        st.session_state.customer_search_input = st.session_state.temp_customer_search

    st.text_input(
        "搜尋客戶簡稱",
        st.session_state.customer_search_input,
        key="temp_customer_search",
        on_change=update_customer_search
    )

    filtered_df = df_customer.copy()
    if st.session_state.customer_search_input:
        filtered_df = df_customer[
            df_customer["客戶簡稱"].astype(str).str.contains(st.session_state.customer_search_input, na=False)
        ]

    st.subheader("新增 / 修改 客戶")

    cols = st.columns(2)
    cols[0].text_input("客戶編號", key="form_customer_客戶編號")
    cols[1].text_input("客戶簡稱", key="form_customer_客戶簡稱")
    st.text_input("備註", key="form_customer_備註")

    if st.button("儲存客戶資料"):
        new_row = {
            "客戶編號": st.session_state["form_customer_客戶編號"],
            "客戶簡稱": st.session_state["form_customer_客戶簡稱"],
            "備註": st.session_state["form_customer_備註"],
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

    st.subheader("客戶清單")

    if filtered_df.empty:
        st.info("查無資料")
    else:
        for i, row in filtered_df.iterrows():
            row_filled = row.fillna("")
            cols = st.columns([2, 2, 3, 1, 1])
            cols[0].markdown(f"**{row_filled['客戶編號']}**")
            cols[1].markdown(f"{row_filled['客戶簡稱']}")
            cols[2].markdown(f"{row_filled['備註']}")

            if cols[3].button("✏️ 修改", key=f"edit_customer_{i}"):
                for col in ["客戶編號", "客戶簡稱", "備註"]:
                    try:
                        st.session_state[f"form_customer_{col}"] = str(row[col]) if pd.notna(row[col]) else ""
                    except:
                        st.session_state[f"form_customer_{col}"] = ""
                st.session_state.edit_customer_index = i
                st.experimental_rerun()

            if cols[4].button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_customer_index = i
                st.session_state.delete_customer_confirm = True

        if st.session_state.get("delete_customer_confirm", False):
            idx = st.session_state.get("delete_customer_index")
            row = df_customer.iloc[idx]
            st.warning(f"確定要刪除客戶編號【{row['客戶編號']}】嗎？")
            confirm_cols = st.columns(2)
            if confirm_cols[0].button("✅ 確定刪除"):
                df_customer.drop(index=idx, inplace=True)
                df_customer.reset_index(drop=True, inplace=True)
                save_sheet(ws_customer, df_customer)
                st.success("刪除成功！")
                st.session_state.delete_customer_confirm = False
                st.experimental_rerun()
            if confirm_cols[1].button("❌ 取消"):
                st.session_state.delete_customer_confirm = False
                st.experimental_rerun()


# ===========================
# 主程式
# ===========================

tab1, tab2 = st.tabs(["色粉管理", "客戶名單"])

with tab1:
    color_module()

with tab2:
    customer_module()
