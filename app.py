import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========

# 放在 secrets.toml:
# [gcp]
# gcp_service_account = '''{...}'''

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

# 載入工作表資料
try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame(columns=required_columns)

# 確保所有欄位存在
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

# 統一欄位名稱
df.columns = df.columns.str.strip()

# 全部強制轉字串 → 預防搜尋、編號顯示問題
df = df.astype(str)

# ======== SESSION STATE DEFAULTS =========

for col in required_columns:
    st.session_state.setdefault(f"form_{col}", "")

st.session_state.setdefault("edit_mode", False)
st.session_state.setdefault("edit_index", None)
st.session_state.setdefault("delete_index", None)
st.session_state.setdefault("show_delete_confirm", False)
st.session_state.setdefault("search_input", "")

# ======== MODULE SWITCHER =========

module = st.radio(
    "請選擇功能模組",
    ["色粉管理", "配方管理"],
    horizontal=True,
)

if module == "配方管理":
    st.subheader("🔧 配方管理模組 (尚未建置)")
    st.info("配方管理功能還在開發中，敬請期待！")
else:
    # ========== 色粉管理系統 ==========

    st.title("🎨 色粉管理系統")

    # ---------- Search Bar ----------
    st.subheader("🔎 搜尋色粉")

    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        value=st.session_state.search_input,
        key="search_input",
        placeholder="例如 001 或 PANTONE-123",
    )
    # 不用再做 st.button("搜尋")

    # ---------- New/Edit Form ----------
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state["form_色粉編號"],
        )

        st.session_state["form_國際色號"] = st.text_input(
            "國際色號",
            st.session_state["form_國際色號"],
        )

        st.session_state["form_名稱"] = st.text_input(
            "名稱",
            st.session_state["form_名稱"],
        )

    with col2:
        st.session_state["form_色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=[
                "色粉",
                "色母",
                "添加劑",
            ].index(st.session_state["form_色粉類別"])
            if st.session_state["form_色粉類別"] in ["色粉", "色母", "添加劑"]
            else 0,
        )

        st.session_state["form_包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=[
                "袋",
                "箱",
                "kg",
            ].index(st.session_state["form_包裝"])
            if st.session_state["form_包裝"] in ["袋", "箱", "kg"]
            else 0,
        )

        st.session_state["form_備註"] = st.text_input(
            "備註",
            st.session_state["form_備註"],
        )

    save_btn = st.button("💾 儲存")

    if save_btn:
        new_data = {
            col: st.session_state[f"form_{col}"] for col in required_columns
        }

        # 確保色粉編號唯一
        if st.session_state.edit_mode:
            # 編輯模式
            df.iloc[st.session_state.edit_index] = new_data
            st.success("✅ 色粉已更新！")
        else:
            # 新增模式
            if new_data["色粉編號"] in df["色粉編號"].values:
                st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
            else:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增色粉成功！")

        # 儲存回 Google Sheet
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.update(values)
        except Exception as e:
            st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

        # Reset form
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
        for col in required_columns:
            st.session_state[f"form_{col}"] = ""

    # ======= DELETE CONFIRMATION =======

    if st.session_state.show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除"):
            idx = st.session_state.delete_index
            df.drop(index=idx, inplace=True)
            df.reset_index(drop=True, inplace=True)
            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.show_delete_confirm = False
            st.session_state.delete_index = None

        if col_no.button("否，取消"):
            st.session_state.show_delete_confirm = False
            st.session_state.delete_index = None

    # ======= SEARCH FILTER =======

    if search_input:
        df_filtered = df[
            df["色粉編號"].astype(str).str.contains(search_input, case=False, na=False)
            | df["國際色號"].astype(str).str.contains(search_input, case=False, na=False)
        ]
    else:
        df_filtered = df

    # ======= Powder List =======

    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])

        if cols[5].button("✏️ 修改", key=f"edit_{i}", use_container_width=True):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i
            for col in required_columns:
                st.session_state[f"form_{col}"] = row[col]

        if cols[6].button("🗑️ 刪除", key=f"delete_{i}", use_container_width=True):
            st.session_state.delete_index = i
            st.session_state.show_delete_confirm = True
