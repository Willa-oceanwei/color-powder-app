import streamlit as st
import json
import gspread
import pandas as pd
from google.oauth2 import service_account

service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

client = gspread.authorize(creds)

SPREADSHEET_ID = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
sheet = client.open_by_key(SPREADSHEET_ID)
worksheet = sheet.worksheet("工作表1")

data = worksheet.get_all_records()
df = pd.DataFrame(data)

st.write(df)

# ---------------------------
# 讀取資料
# ---------------------------

data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 處理空表格
if df.empty:
    df = pd.DataFrame(
        columns=[
            "色粉編號", "國際色號", "名稱",
            "色粉類別", "包裝", "kg", "備註"
        ]
    )

# 清理欄位名
df.columns = df.columns.str.strip()

# ---------------------------
# 初始化 session state
# ---------------------------

if "search_input" not in st.session_state:
    st.session_state["search_input"] = ""

if "edit_data" not in st.session_state:
    st.session_state["edit_data"] = None

# ---------------------------
# 頁面選單
# ---------------------------

menu = st.radio(
    "功能選擇",
    ["色粉管理", "配方管理"],
    horizontal=True
)

if menu == "配方管理":
    st.warning("配方管理開發中… 敬請期待！")
    st.stop()

# ---------------------------
# 搜尋區塊
# ---------------------------

col_search, col_clear = st.columns([5, 1])
with col_search:
    search_term = st.text_input(
        "請輸入色粉編號或名稱後按 Enter",
        value=st.session_state["search_input"],
        key="search_input"
    )
    st.session_state["search_input"] = search_term

with col_clear:
    if st.button("清空畫面"):
        st.session_state["search_input"] = ""
        st.query_params.clear()
        st.rerun()

# ---------------------------
# 篩選結果
# ---------------------------

filtered_df = df.copy()

if search_term.strip():
    mask = (
        df["色粉編號"].astype(str).str.contains(search_term, case=False, na=False) |
        df["名稱"].astype(str).str.contains(search_term, case=False, na=False)
    )
    filtered_df = df[mask]

    if filtered_df.empty:
        st.info("查無此色粉。")

# ---------------------------
# 新增 / 修改 區塊
# ---------------------------

st.markdown("### ➕ 新增 / 修改 色粉資料")

# 如果是「修改」，把資料帶進欄位
edit_row = None
if st.query_params.get("edit"):
    edit_no = st.query_params.get("edit")[0]
    edit_row = df[df["色粉編號"] == edit_no]
    if not edit_row.empty:
        edit_data = edit_row.iloc[0].to_dict()
        st.session_state["edit_data"] = edit_data
else:
    st.session_state["edit_data"] = None

# 顯示輸入欄位
col1, col2, col3, col4 = st.columns(4)

with col1:
    color_no = st.text_input(
        "色粉編號",
        value=st.session_state["edit_data"]["色粉編號"]
        if st.session_state["edit_data"] else ""
    )

with col2:
    intl_no = st.text_input(
        "國際色號",
        value=st.session_state["edit_data"]["國際色號"]
        if st.session_state["edit_data"] else ""
    )

with col3:
    name = st.text_input(
        "名稱",
        value=st.session_state["edit_data"]["名稱"]
        if st.session_state["edit_data"] else ""
    )

with col4:
    kg = st.text_input(
        "kg",
        value=st.session_state["edit_data"]["kg"]
        if st.session_state["edit_data"] else ""
    )

col5, col6, col7, col8 = st.columns(4)

with col5:
    category = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=[
            ["色粉", "色母", "添加劑"].index(
                st.session_state["edit_data"]["色粉類別"]
            )
            if st.session_state["edit_data"] else 0
        ][0]
    )

with col6:
    spec = st.selectbox(
        "包裝",
        ["袋", "箱", "kg"],
        index=[
            ["袋", "箱", "kg"].index(
                st.session_state["edit_data"]["包裝"]
            )
            if st.session_state["edit_data"] else 0
        ][0]
    )

with col7:
    remark = st.text_input(
        "備註",
        value=st.session_state["edit_data"]["備註"]
        if st.session_state["edit_data"] else ""
    )

# 新增 / 修改按鈕
if st.button("儲存"):
    # 檢查是否重複
    if st.session_state["edit_data"] is None and color_no in df["色粉編號"].values:
        st.warning("❌ 色粉編號已存在！請改用修改功能。")
    else:
        new_row = {
            "色粉編號": color_no,
            "國際色號": intl_no,
            "名稱": name,
            "色粉類別": category,
            "包裝": spec,
            "kg": kg,
            "備註": remark
        }
        if st.session_state["edit_data"]:
            # 修改
            df.loc[df["色粉編號"] == color_no] = new_row
            st.success("✅ 修改成功！")
        else:
            # 新增
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ 新增成功！")

        # 存回 Google Sheet
        worksheet.clear()
        worksheet.update([df.columns.tolist()] + df.values.tolist())
        st.query_params.clear()
        st.rerun()

# ---------------------------
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
                kg: <b>{row['kg']}</b>&nbsp;&nbsp;&nbsp;
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
