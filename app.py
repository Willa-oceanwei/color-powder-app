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
worksheet = spreadsheet.get_worksheet(0)

# ========== INITIALIZATION ==========

required_columns = [
    "色粉編號",
    "國際色號",
    "名稱",
    "色粉類別",
    "包裝",
    "備註",
]

try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame(columns=required_columns)

# 確保欄位存在
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

# 全部轉字串，避免 NaN 出錯
for col in ["色粉編號", "國際色號"]:
    df[col] = df[col].fillna("").astype(str)

# ========== SESSION STATE DEFAULTS ==========

for col in required_columns:
    st.session_state.setdefault(f"form_{col}", "")

st.session_state.setdefault("edit_mode", False)
st.session_state.setdefault("edit_index", None)
st.session_state.setdefault("delete_index", None)
st.session_state.setdefault("show_delete_confirm", False)
st.session_state.setdefault("search_input", "")
st.session_state.setdefault("do_rerun", False)

# ========== UI START ==========

st.title("🎨 色粉管理系統")

# 功能模組
selected_tab = st.radio(
    "功能模組",
    ["色粉管理", "配方管理"],
    horizontal=True,
)

if selected_tab == "配方管理":
    st.info("🔧 配方管理開發中...")
    st.stop()

# ========== SEARCH ==========

search_input = st.text_input(
    "請輸入色粉編號或國際色號",
    value=st.session_state["search_input"],
    key="search_input",
)

# 檢索
if search_input:
    mask = (
        df["色粉編號"].str.contains(search_input, case=False)
        | df["國際色號"].str.contains(search_input, case=False)
    )
    df_filtered = df[mask]
else:
    df_filtered = df

# ========== BUTTONS ==========

col_clear, = st.columns([1])
if col_clear.button("清空畫面"):
    st.session_state["search_input"] = ""
    st.session_state["edit_mode"] = False
    st.session_state["edit_index"] = None
    for col in required_columns:
        st.session_state[f"form_{col}"] = ""
    st.session_state["do_rerun"] = True

# ========== NEW / EDIT FORM ==========

st.subheader("➕ 新增 / 修改 色粉")

col1, col2 = st.columns(2)

with col1:
    st.session_state["form_色粉編號"] = st.text_input(
        "色粉編號",
        value=st.session_state["form_色粉編號"],
        key="form_色粉編號",
    )

    st.session_state["form_國際色號"] = st.text_input(
        "國際色號",
        value=st.session_state["form_國際色號"],
        key="form_國際色號",
    )

    st.session_state["form_名稱"] = st.text_input(
        "名稱",
        value=st.session_state["form_名稱"],
        key="form_名稱",
    )

with col2:
    st.session_state["form_色粉類別"] = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(
            st.session_state["form_色粉類別"]
        ) if st.session_state["form_色粉類別"] in ["色粉", "色母", "添加劑"] else 0,
        key="form_色粉類別",
    )

    st.session_state["form_包裝"] = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=["袋", "箱", "kg"].index(
            st.session_state["form_包裝"]
        ) if st.session_state["form_包裝"] in ["袋", "箱", "kg"] else 0,
        key="form_包裝",
    )

    st.session_state["form_備註"] = st.text_input(
        "備註",
        value=st.session_state["form_備註"],
        key="form_備註",
    )

# SAVE BUTTON
if st.button("💾 儲存"):
    new_data = {
        col: st.session_state[f"form_{col}"] for col in required_columns
    }

    if st.session_state["edit_mode"]:
        # 修改
        df.iloc[st.session_state["edit_index"]] = new_data
        st.success("✅ 已修改色粉")
    else:
        # 新增
        if new_data["色粉編號"] in df["色粉編號"].values:
            st.warning("⚠️ 此色粉編號已存在！")
        else:
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            st.success("✅ 已新增色粉")

    # 更新 Google Sheets
    try:
        values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        worksheet.update(values)
    except Exception as e:
        st.error(f"❌ 寫入失敗: {e}")

    # 清空
    st.session_state["edit_mode"] = False
    st.session_state["edit_index"] = None
    for col in required_columns:
        st.session_state[f"form_{col}"] = ""
    st.session_state["do_rerun"] = True

# ========== DELETE CONFIRM ==========

if st.session_state["show_delete_confirm"]:
    st.warning("⚠️ 確定要刪除此筆色粉嗎？")
    col_yes, col_no = st.columns(2)
    if col_yes.button("是，刪除"):
        df.drop(index=st.session_state["delete_index"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        try:
            values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            worksheet.update(values)
            st.success("✅ 已刪除色粉！")
        except Exception as e:
            st.error(f"❌ 刪除失敗: {e}")
        st.session_state["show_delete_confirm"] = False
        st.session_state["do_rerun"] = True

    if col_no.button("否，取消"):
        st.session_state["show_delete_confirm"] = False
        st.session_state["do_rerun"] = True

# ========== POWDER LIST ==========

st.subheader("📋 色粉清單")

for i, row in df_filtered.iterrows():
    cols = st.columns([2, 2, 2, 2, 2, 1, 1])
    cols[0].write(row["色粉編號"])
    cols[1].write(row["國際色號"])
    cols[2].write(row["名稱"])
    cols[3].write(row["色粉類別"])
    cols[4].write(row["包裝"])

    if cols[5].button("✏️ 修改", key=f"edit_{i}"):
        for col in required_columns:
            st.session_state[f"form_{col}"] = row[col]
        st.session_state["edit_mode"] = True
        st.session_state["edit_index"] = i
        st.session_state["do_rerun"] = True

    if cols[6].button("🗑️ 刪除", key=f"delete_{i}"):
        st.session_state["delete_index"] = i
        st.session_state["show_delete_confirm"] = True
        st.session_state["do_rerun"] = True

# Rerun if needed
if st.session_state["do_rerun"]:
    st.session_state["do_rerun"] = False
    st.experimental_rerun()
