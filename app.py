import streamlit as st
import json
import gspread
import pandas as pd
from google.oauth2 import service_account

# ===========================
# GCP 認證
# ===========================
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
sheet = client.open_by_key(SPREADSHEET_ID)
worksheet = sheet.worksheet("工作表1")

# ===========================
# 讀取資料
# ===========================
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 保證空 DataFrame 也有正確欄位
required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
for col in required_columns:
    if col not in df.columns:
        df[col] = ""

# ===========================
# Session State 初始化
# ===========================
if "search_input" not in st.session_state:
    st.session_state.search_input = ""

if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# ===========================
# 頁面標題 & 模組選單
# ===========================
st.set_page_config(page_title="色粉管理系統", layout="wide")

module = st.sidebar.radio(
    "請選擇模組",
    ["色粉管理", "配方管理"],
    horizontal=False
)

if module == "配方管理":
    st.info("配方管理功能尚未實作。請先使用色粉管理。")
    st.stop()

st.title("色粉管理系統")

# ===========================
# 搜尋功能
# ===========================
col1, col2 = st.columns([3, 1])

with col1:
    search_term = st.text_input(
        "搜尋色粉編號或名稱",
        value=st.session_state.search_input,
        placeholder="輸入色粉編號或名稱後按 Enter"
    )

with col2:
    if st.button("清空畫面"):
        st.session_state.search_input = ""
        search_term = ""

if search_term:
    st.session_state.search_input = search_term
    mask = (
        df["色粉編號"].astype(str).str.contains(search_term, case=False, na=False)
        | df["名稱"].astype(str).str.contains(search_term, case=False, na=False)
    )
    filtered_df = df[mask]
else:
    filtered_df = df

# ===========================
# 編輯 / 刪除按鈕
# ===========================
for i, row in filtered_df.iterrows():
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"✏️ 修改（色粉編號 {row['色粉編號']}）", key=f"edit_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = row["序號"]
    with c2:
        if st.button(f"🗑️ 刪除（序號 {row['序號']}）", key=f"delete_{i}"):
            confirm = st.warning(f"確定刪除色粉編號 {row['色粉編號']}？", icon="⚠️")
            if st.button(f"再次確認刪除（序號 {row['序號']}）", key=f"confirm_delete_{i}"):
                df.drop(index=row["序號"], inplace=True)
                worksheet.update([df.columns.tolist()] + df.values.tolist())
                st.success("已刪除！")
                st.experimental_rerun()

st.divider()

# ===========================
# 新增 / 修改 區塊
# ===========================
st.write("## 新增 / 修改 色粉資料")

if st.session_state.edit_mode:
    edit_row = df.loc[st.session_state.edit_index]
else:
    edit_row = pd.Series({col: "" for col in required_columns})

with st.form("color_form"):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        色粉編號 = st.text_input("色粉編號", value=str(edit_row["色粉編號"]))
    with c2:
        國際色號 = st.text_input("國際色號", value=str(edit_row["國際色號"]))
    with c3:
        名稱 = st.text_input("名稱", value=str(edit_row["名稱"]))
    with c4:
        色粉類別 = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(str(edit_row["色粉類別"])) if edit_row["色粉類別"] in ["色粉", "色母", "添加劑"] else 0
        )

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        包裝 = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(str(edit_row["包裝"])) if edit_row["包裝"] in ["袋", "箱", "kg"] else 0
        )
    with c6:
        備註 = st.text_input("備註", value=str(edit_row["備註"]))

    submitted = st.form_submit_button("儲存")

if submitted:
    # 檢查重複編號（僅限新增）
    if not st.session_state.edit_mode:
        if 色粉編號 in df["色粉編號"].astype(str).values:
            st.error(f"色粉編號 {色粉編號} 已存在，請勿重複新增。")
            st.stop()

    new_row = pd.Series({
        "色粉編號": 色粉編號,
        "國際色號": 國際色號,
        "名稱": 名稱,
        "色粉類別": 色粉類別,
        "包裝": 包裝,
        "備註": 備註
    })

    if st.session_state.edit_mode:
        # 更新現有
        df.loc[st.session_state.edit_index] = new_row
        st.success("資料已更新！")
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
    else:
        df = pd.concat([df, new_row.to_frame().T], ignore_index=True)
        st.success("已新增新色粉！")

    # 寫回試算表
    worksheet.update([df.columns.tolist()] + df.values.tolist())
    st.experimental_rerun()

# ===========================
# 顯示資料序列
# ---------------------------

st.markdown("### 📋 色粉清單")

if not filtered_df.empty:
    for i, row in filtered_df.iterrows():
        bg_color = "#333333" if i % 2 == 0 else "#444444"
        text_color = "#ffffff"

        # 單列區塊
        col1, col2, col3 = st.columns([10, 1, 1])
        with col1:
            st.markdown(
                f"""
                <div style='
                    background-color: {bg_color};
                    color: {text_color};
                    padding: 10px;
                    border-radius: 5px;
                    margin-bottom: 5px;
                    font-size: 16px;
                '>
                色粉編號: <b>{row['色粉編號']}</b>&nbsp;&nbsp;&nbsp;
                名稱: <b>{row['名稱']}</b>&nbsp;&nbsp;&nbsp;
                國際色號: <b>{row['國際色號']}</b>&nbsp;&nbsp;&nbsp;
                色粉類別: <b>{row['色粉類別']}</b>&nbsp;&nbsp;&nbsp;
                包裝: <b>{row['包裝']}</b>&nbsp;&nbsp;&nbsp;
                備註: <b>{row['備註']}</b>&nbsp;&nbsp;&nbsp;
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            if st.button("修改", key=f"edit_{i}"):
                st.query_params.clear()
                st.query_params.update({"edit": row["色粉編號"]})
                st.rerun()

        with col3:
            if st.button("刪除", key=f"delete_{i}"):
                if st.confirm(f"確定要刪除色粉 {row['色粉編號']} 嗎？"):
                    df = df[df["色粉編號"] != row["色粉編號"]]
                    worksheet.clear()
                    worksheet.update([df.columns.tolist()] + df.values.tolist())
                    st.success(f"✅ 已刪除 {row['色粉編號']}")
                    st.rerun()
