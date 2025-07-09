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

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ========== GCP SERVICE ACCOUNT ==========

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
worksheet_powder = spreadsheet.get_worksheet(0)   # 工作表1
worksheet_customers = spreadsheet.get_worksheet(1)  # 工作表2

# ========== 初始化 session_state ==========

st.session_state.setdefault("module", "色粉管理")

# ================== 模組選單 ==================

module = st.radio(
    "請選擇模組：",
    ["色粉管理", "客戶名單", "配方管理"],
    index=["色粉管理", "客戶名單", "配方管理"].index(st.session_state["module"]),
    horizontal=True,
)
st.session_state["module"] = module

# ================== 色粉管理模組 ==================

if module == "色粉管理":

    # 保留你原本的色粉管理程式碼不動
    st.title("🎨 色粉管理系統")
    # 你的色粉管理程式碼放在這裡……
    # （此處省略，維持你前面確定過的那版 app.py）

# ================== 客戶名單模組 ==================

elif module == "客戶名單":
    st.title("👥 客戶名單管理")

    # Google Sheet 欄位
    customer_cols = ["客戶編號", "客戶簡稱", "備註"]

    # 載入客戶名單
    try:
        data_cust = worksheet_customers.get_all_records()
        df_cust = pd.DataFrame(data_cust)
    except:
        df_cust = pd.DataFrame(columns=customer_cols)

    for col in customer_cols:
        if col not in df_cust.columns:
            df_cust[col] = ""

    df_cust = df_cust.fillna("")

    # 初始化 session_state
    for col in customer_cols:
        st.session_state.setdefault(f"cust_form_{col}", "")

    st.session_state.setdefault("cust_edit_mode", False)
    st.session_state.setdefault("cust_edit_index", None)
    st.session_state.setdefault("cust_delete_index", None)
    st.session_state.setdefault("cust_show_delete_confirm", False)
    st.session_state.setdefault("cust_search_input", "")

    # ------- 搜尋區 -------
    st.subheader("🔎 搜尋客戶")

    cust_search_input = st.text_input(
        "請輸入客戶編號或客戶簡稱（支援模糊搜尋）",
        st.session_state.cust_search_input,
        key="cust_search_input",
    )

    if cust_search_input != st.session_state.cust_search_input:
        st.session_state.cust_search_input = cust_search_input

    # ------- 新增/修改區 -------
    st.subheader("➕ 新增 / 修改 客戶名單")

    st.session_state["cust_form_客戶編號"] = st.text_input(
        "客戶編號", st.session_state["cust_form_客戶編號"]
    )
    st.session_state["cust_form_客戶簡稱"] = st.text_input(
        "客戶簡稱", st.session_state["cust_form_客戶簡稱"]
    )
    st.session_state["cust_form_備註"] = st.text_area(
        "備註", st.session_state["cust_form_備註"], height=80
    )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = {
            col: st.session_state[f"cust_form_{col}"] for col in customer_cols
        }

        if new_data["客戶編號"] == "":
            st.warning("⚠️ 客戶編號不可空白！")
        else:
            # 檢查重複
            if not st.session_state.cust_edit_mode and new_data["客戶編號"] in df_cust["客戶編號"].values:
                st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
            else:
                if st.session_state.cust_edit_mode:
                    # 修改
                    df_cust.iloc[st.session_state.cust_edit_index] = new_data
                    st.success("✅ 客戶已更新！")
                else:
                    # 新增
                    df_cust = pd.concat(
                        [df_cust, pd.DataFrame([new_data])],
                        ignore_index=True,
                    )
                    st.success("✅ 新增客戶成功！")

                # 寫回 Google Sheet
                try:
                    values = [df_cust.columns.tolist()] + df_cust.fillna("").astype(str).values.tolist()
                    worksheet_customers.update(values)
                except Exception as e:
                    st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

                # 清空表單
                st.session_state.cust_edit_mode = False
                st.session_state.cust_edit_index = None
                for col in customer_cols:
                    st.session_state[f"cust_form_{col}"] = ""

                st.experimental_rerun()

    # ------- 刪除確認 -------
    if st.session_state.cust_show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆客戶資料嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.cust_delete_index
            df_cust.drop(index=idx, inplace=True)
            df_cust.reset_index(drop=True, inplace=True)
            try:
                values = [df_cust.columns.tolist()] + df_cust.fillna("").astype(str).values.tolist()
                worksheet_customers.update(values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.cust_show_delete_confirm = False
            st.experimental_rerun()
        if col_no.button("否，取消"):
            st.session_state.cust_show_delete_confirm = False
            st.experimental_rerun()

    # ------- 搜尋過濾 -------
    if st.session_state.cust_search_input:
        df_cust_filtered = df_cust[
            df_cust["客戶編號"].str.contains(st.session_state.cust_search_input, case=False, na=False)
            | df_cust["客戶簡稱"].str.contains(st.session_state.cust_search_input, case=False, na=False)
        ]
        if df_cust_filtered.empty:
            st.info("🔍 查無符合的客戶資料。")
    else:
        df_cust_filtered = df_cust

    # ------- 清單 -------
    st.subheader("📋 客戶清單")

    for i, row in df_cust_filtered.iterrows():
        cols = st.columns([2, 3, 3, 1, 1])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])

        if cols[3].button("✏️ 修改", key=f"cust_edit_{i}"):
            st.session_state.cust_edit_mode = True
            st.session_state.cust_edit_index = i
            for col in customer_cols:
                st.session_state[f"cust_form_{col}"] = row[col]
            st.experimental_rerun()

        if cols[4].button("🗑️ 刪除", key=f"cust_delete_{i}"):
            st.session_state.cust_delete_index = i
            st.session_state.cust_show_delete_confirm = True
            st.experimental_rerun()

# ================== 配方管理模組 ==================

elif module == "配方管理":
    st.title("🧪 配方管理 (開發中)")
    st.info("此模組尚在開發中。")

