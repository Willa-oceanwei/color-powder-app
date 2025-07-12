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
worksheet = spreadsheet.get_worksheet(0)

# ======== INITIALIZATION =========
required_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

# 載入資料
try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame(columns=required_columns)

# 強制所有欄位都轉成字串
df = df.astype(str)

# 確保欄位存在
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

df.columns = df.columns.str.strip()

# ======== SESSION STATE =========
if "form_data" not in st.session_state:
    st.session_state.form_data = {col: "" for col in required_columns}
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "delete_index" not in st.session_state:
    st.session_state.delete_index = None
if "show_delete_confirm" not in st.session_state:
    st.session_state.show_delete_confirm = False
if "search_input" not in st.session_state:
    st.session_state.search_input = ""

# ======== UI START =========
st.title("🎨 色粉管理系統")

# ---------- Search ----------
st.subheader("🔎 搜尋色粉")
search_input = st.text_input(
    "請輸入色粉編號或國際色號",
    st.session_state.search_input,
    placeholder="直接按 Enter 搜尋"
)

# 更新搜尋
if search_input != st.session_state.search_input:
    st.session_state.search_input = search_input

# ======= Search Filter =======
if st.session_state.search_input.strip():
    df_filtered = df[
        df["色粉編號"].str.contains(st.session_state.search_input, case=False, na=False) |
        df["國際色號"].str.contains(st.session_state.search_input, case=False, na=False)
    ]
    if df_filtered.empty:
        st.info("🔍 查無此色粉資料")
else:
    df_filtered = df

# ---------- New/Edit Form ----------
st.subheader("➕ 新增 / 修改 色粉")

col1, col2 = st.columns(2)

with col1:
    st.session_state.form_data["色粉編號"] = st.text_input(
        "色粉編號",
        st.session_state.form_data["色粉編號"]
    )
    st.session_state.form_data["國際色號"] = st.text_input(
        "國際色號",
        st.session_state.form_data["國際色號"]
    )
    st.session_state.form_data["名稱"] = st.text_input(
        "名稱",
        st.session_state.form_data["名稱"]
    )

with col2:
    st.session_state.form_data["色粉類別"] = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(
            st.session_state.form_data["色粉類別"]
        ) if st.session_state.form_data["色粉類別"] in ["色粉", "色母", "添加劑"] else 0
    )
    st.session_state.form_data["包裝"] = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=["袋", "箱", "kg"].index(
            st.session_state.form_data["包裝"]
        ) if st.session_state.form_data["包裝"] in ["袋", "箱", "kg"] else 0
    )
    st.session_state.form_data["備註"] = st.text_input(
        "備註",
        st.session_state.form_data["備註"]
    )

save_btn = st.button("💾 儲存")

# ======== SAVE / UPDATE LOGIC =========
if save_btn:
    new_data = st.session_state.form_data.copy()

    if new_data["色粉編號"].strip() == "":
        st.warning("⚠️ 請輸入色粉編號！")
    else:
        if st.session_state.edit_mode:
            df.iloc[st.session_state.edit_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            if new_data["色粉編號"] in df["色粉編號"].values:
                st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
            else:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增色粉成功！")

        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        st.session_state.form_data = {col: "" for col in required_columns}
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
        st.rerun()

# ======== DELETE CONFIRM =========
if st.session_state.show_delete_confirm:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        idx = st.session_state.delete_index
        df.drop(index=idx, inplace=True)
        df.reset_index(drop=True, inplace=True)
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.clear()
            worksheet.update("A1", values)
            st.success("✅ 色粉已刪除！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
        st.rerun()
    if col_no.button("否，取消"):
        st.session_state.show_delete_confirm = False
        st.session_state.delete_index = None
        st.rerun()

# ======== Powder List =========
st.subheader("📋 色粉清單")

for i, row in df_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2, 2, 3])
    cols[0].write(row["色粉編號"])
    cols[1].write(row["國際色號"])
    cols[2].write(row["名稱"])
    cols[3].write(row["色粉類別"])
    cols[4].write(row["包裝"])

    # 橫排放兩顆按鈕
    with cols[5]:
        col_edit, col_delete = st.columns(2)
        if col_edit.button("✏️ 修改", key=f"edit_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i
            st.session_state.form_data = row.to_dict()
            st.rerun()
        if col_delete.button("🗑️ 刪除", key=f"delete_{i}"):
            st.session_state.delete_index = i
            st.session_state.show_delete_confirm = True
            st.rerun()
 1 個附件
  • Gmail 已掃描檢查

OceaN Wei <ocean700120@gmail.com>
7月11日 週五 下午5:48 (2 天前)
寄給 我

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

# ======== SHEETS =========
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# 從完美版沿用 sheet 名稱
ws_color = spreadsheet.worksheet("色粉管理")
ws_customer = spreadsheet.worksheet("客戶名單")

# ======== COLOR MODULE =========

color_cols = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

try:
    color_data = ws_color.get_all_records()
    df_color = pd.DataFrame(color_data)
except:
    df_color = pd.DataFrame(columns=color_cols)

df_color = df_color.astype(str)
for col in color_cols:
    if col not in df_color.columns:
        df_color[col] = ""

if "form_color" not in st.session_state:
    st.session_state.form_color = {col: "" for col in color_cols}
if "edit_color_mode" not in st.session_state:
    st.session_state.edit_color_mode = False
if "edit_color_index" not in st.session_state:
    st.session_state.edit_color_index = None
if "delete_color_index" not in st.session_state:
    st.session_state.delete_color_index = None
if "show_delete_color_confirm" not in st.session_state:
    st.session_state.show_delete_color_confirm = False
if "search_color" not in st.session_state:
    st.session_state.search_color = ""

# ======== CUSTOMER MODULE =========

customer_cols = [
    "客戶編號",
    "客戶簡稱",
    "備註",
]

try:
    customer_data = ws_customer.get_all_records()
    df_customer = pd.DataFrame(customer_data)
except:
    df_customer = pd.DataFrame(columns=customer_cols)

df_customer = df_customer.astype(str)
for col in customer_cols:
    if col not in df_customer.columns:
        df_customer[col] = ""

if "form_customer" not in st.session_state:
    st.session_state.form_customer = {col: "" for col in customer_cols}
if "edit_customer_mode" not in st.session_state:
    st.session_state.edit_customer_mode = False
if "edit_customer_index" not in st.session_state:
    st.session_state.edit_customer_index = None
if "delete_customer_index" not in st.session_state:
    st.session_state.delete_customer_index = None
if "show_delete_customer_confirm" not in st.session_state:
    st.session_state.show_delete_customer_confirm = False
if "search_customer" not in st.session_state:
    st.session_state.search_customer = ""

# ======== UI START =========

menu = st.sidebar.radio("請選擇模組", ["色粉管理", "客戶名單"])

# ----------------------------------------------------
#                   色粉管理
# ----------------------------------------------------
if menu == "色粉管理":
    st.title("🎨 色粉管理系統")

    st.subheader("🔎 搜尋色粉")
    search_color = st.text_input(
        "請輸入色粉編號或國際色號",
        st.session_state.search_color,
        placeholder="直接按 Enter 搜尋"
    )

    if search_color != st.session_state.search_color:
        st.session_state.search_color = search_color

    if st.session_state.search_color.strip():
        df_filtered = df_color[
            df_color["色粉編號"].str.contains(st.session_state.search_color, case=False, na=False) |
            df_color["國際色號"].str.contains(st.session_state.search_color, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("🔍 查無此色粉資料")
    else:
        df_filtered = df_color

    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state.form_color["色粉編號"]
        )
        st.session_state.form_color["國際色號"] = st.text_input(
            "國際色號",
            st.session_state.form_color["國際色號"]
        )
        st.session_state.form_color["名稱"] = st.text_input(
            "名稱",
            st.session_state.form_color["名稱"]
        )

    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state.form_color["色粉類別"]
            ) if st.session_state.form_color["色粉類別"] in ["色粉", "色母", "添加劑"] else 0
        )
        st.session_state.form_color["包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state.form_color["包裝"]
            ) if st.session_state.form_color["包裝"] in ["袋", "箱", "kg"] else 0
        )
        st.session_state.form_color["備註"] = st.text_input(
            "備註",
            st.session_state.form_color["備註"]
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_color.copy()
        if new_data["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_color_mode:
                df_color.iloc[st.session_state.edit_color_index] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df_color["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df_color = pd.concat([df_color, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.clear()
                ws_color.update("A1", values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.form_color = {col: "" for col in color_cols}
            st.session_state.edit_color_mode = False
            st.session_state.edit_color_index = None

    if st.session_state.show_delete_color_confirm:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_color_index
            df_color.drop(index=idx, inplace=True)
            df_color.reset_index(drop=True, inplace=True)
            try:
                values = [df_color.columns.tolist()] + df_color.fillna("").astype(str).values.tolist()
                ws_color.clear()
                ws_color.update("A1", values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_color_confirm = False
            st.session_state.delete_color_index = None

        if col_no.button("否，取消"):
            st.session_state.show_delete_color_confirm = False
            st.session_state.delete_color_index = None

    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 3])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        with cols[5]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_color_{i}"):
                st.session_state.edit_color_mode = True
                st.session_state.edit_color_index = i
                st.session_state.form_color = row.to_dict()
            if col_delete.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_color_index = i
                st.session_state.show_delete_color_confirm = True

# ----------------------------------------------------
#                   客戶名單
# ----------------------------------------------------
if menu == "客戶名單":
    st.title("👥 客戶名單")

    st.subheader("🔎 搜尋客戶")
    search_customer = st.text_input(
        "請輸入客戶編號或簡稱",
        st.session_state.search_customer,
        placeholder="直接按 Enter 搜尋"
    )

    if search_customer != st.session_state.search_customer:
        st.session_state.search_customer = search_customer

    if st.session_state.search_customer.strip():
        df_filtered = df_customer[
            df_customer["客戶編號"].str.contains(st.session_state.search_customer, case=False, na=False) |
            df_customer["客戶簡稱"].str.contains(st.session_state.search_customer, case=False, na=False)
        ]
        if df_filtered.empty:
            st.info("🔍 查無此客戶資料")
    else:
        df_filtered = df_customer

    st.subheader("➕ 新增 / 修改 客戶")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state.form_customer["客戶編號"]
        )
        st.session_state.form_customer["客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state.form_customer["客戶簡稱"]
        )
    with col2:
        st.session_state.form_customer["備註"] = st.text_input(
            "備註",
            st.session_state.form_customer["備註"]
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = st.session_state.form_customer.copy()
        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_mode:
                df_customer.iloc[st.session_state.edit_customer_index] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df_customer["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.clear()
                ws_customer.update("A1", values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.form_customer = {col: "" for col in customer_cols}
            st.session_state.edit_customer_mode = False
            st.session_state.edit_customer_index = None

    if st.session_state.show_delete_customer_confirm:
        st.warning("⚠️ 確定要刪除此筆客戶嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_customer_index
            df_customer.drop(index=idx, inplace=True)
            df_customer.reset_index(drop=True, inplace=True)
            try:
                values = [df_customer.columns.tolist()] + df_customer.fillna("").astype(str).values.tolist()
                ws_customer.clear()
                ws_customer.update("A1", values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_customer_confirm = False
            st.session_state.delete_customer_index = None

        if col_no.button("否，取消"):
            st.session_state.show_delete_customer_confirm = False
            st.session_state.delete_customer_index = None

    st.subheader("📋 客戶清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        with cols[2]:
            col_edit, col_delete = st.columns(2)
            if col_edit.button("✏️ 修改", key=f"edit_customer_{i}"):
                st.session_state.edit_customer_mode = True
                st.session_state.edit_customer_index = i
                st.session_state.form_customer = row.to_dict()
            if col_delete.button("🗑️ 刪除", key=f"delete_customer_{i}"):
                st.session_state.delete_customer_index = i
                st.session_state.show_delete_customer_confirm = True
