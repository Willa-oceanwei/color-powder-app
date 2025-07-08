import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# 寬版畫面
st.set_page_config(layout="wide")

# ===== GSpread connect =====

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)
gc = gspread.authorize(credentials)

sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
sh = gc.open_by_key(sheet_key)
worksheet = sh.worksheet("工作表1")

# ===== functions =====

def load_data():
    rows = worksheet.get_all_records()
    return pd.DataFrame(rows)

def save_data(df):
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    worksheet.append_rows(df.values.tolist())

# ===== 初始化 =====

if "mode" not in st.session_state:
    st.session_state.mode = "view"
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "search_code" not in st.session_state:
    st.session_state.search_code = ""

# ===== 頁面選單 =====

page = st.sidebar.radio("功能模組", ["色粉管理", "配方管理"])

if page == "色粉管理":

    st.title("🎨 色粉管理")

    df = load_data()

    # ===== 搜尋列 =====

    col_search, col_clear = st.columns([4,1])

    with col_search:
        search_code = st.text_input("請輸入色粉編號或名稱", value=st.session_state.search_code)

    with col_clear:
        if st.button("🔄 清除輸入"):
            st.session_state.mode = "view"
            st.session_state.edit_index = None
            st.session_state.search_code = ""
            st.rerun()

    search_btn = st.button("搜尋色粉")

    df_display = df.copy()

    if search_btn:
        st.session_state.search_code = search_code
        if search_code.strip() == "":
            st.warning("請輸入色粉編號或名稱進行搜尋")
        else:
            found = df[
                (df["色粉編號"].astype(str) == search_code.strip()) |
                (df["色粉名稱"].str.contains(search_code.strip(), case=False, na=False))
            ]
            if found.empty:
                st.info(f"查無色粉資料：{search_code}")
                df_display = pd.DataFrame()
            else:
                df_display = found
                st.success(f"找到 {len(found)} 筆資料")

    # ===== 新增 / 編輯表單 =====

    st.subheader("➕ 新增 / 編輯 色粉")

    editing = st.session_state.mode == "edit"

    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input(
            "色粉編號",
            value="" if not editing else df.iloc[st.session_state.edit_index]["色粉編號"]
        )
        color_name = st.text_input(
            "色粉名稱",
            value="" if not editing else df.iloc[st.session_state.edit_index]["色粉名稱"]
        )
        pantone = st.text_input(
            "國際色號",
            value="" if not editing else df.iloc[st.session_state.edit_index]["國際色號"]
        )
        color_type = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=0 if not editing else
            ["色粉", "色母", "添加劑"].index(df.iloc[st.session_state.edit_index]["色粉類別"])
        )
    with col2:
        spec = st.selectbox(
            "規格",
            ["kg", "箱", "袋"],
            index=0 if not editing else
            ["kg", "箱", "袋"].index(df.iloc[st.session_state.edit_index]["規格"])
        )
        origin = st.text_input(
            "產地",
            value="" if not editing else df.iloc[st.session_state.edit_index]["產地"]
        )
        remark = st.text_input(
            "備註",
            value="" if not editing else df.iloc[st.session_state.edit_index]["備註"]
        )

    # ===== 新增 / 儲存 按鈕 =====

    col_submit, _ = st.columns([1,9])

    with col_submit:
        if editing:
            if st.button("💾 儲存修改"):
                duplicate = df[
                    (df["色粉編號"] == code) &
                    (df.index != st.session_state.edit_index)
                ]
                if not duplicate.empty:
                    st.error(f"色粉編號 {code} 已存在。")
                else:
                    df.loc[st.session_state.edit_index] = [
                        code, pantone, color_name, color_type, spec, origin, remark
                    ]
                    save_data(df)
                    st.success(f"已修改 {code}")
                    st.session_state.mode = "view"
                    st.rerun()
        else:
            if st.button("➕ 新增色粉"):
                if code in df["色粉編號"].astype(str).values:
                    st.error(f"色粉編號 {code} 已存在。")
                else:
                    new_row = {
                        "色粉編號": code,
                        "國際色號": pantone,
                        "色粉名稱": color_name,
                        "色粉類別": color_type,
                        "規格": spec,
                        "產地": origin,
                        "備註": remark
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(df)
                    st.success(f"新增色粉 {code} 成功！")
                    st.rerun()

    # ===== 顯示序列 =====

    st.subheader("📋 色粉總表")

    if not df_display.empty:
        for idx, row in df_display.iterrows():
            bg_color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"

            st.markdown(
                f"""
                <div style="
                    background-color:{bg_color};
                    padding:8px;
                    border-radius:4px;
                    font-size:14px;
                    display: flex;
                    flex-direction: row;
                    align-items: center;
                    text-align: left;
                    white-space: nowrap;
                    margin-bottom:4px;
                ">
                    ➡️ <strong>{row['色粉編號']}</strong> | {row['色粉名稱']} | {row['國際色號']}
                    <div style="margin-left:auto;">
                        <a href="?edit={idx}" style="
                            background-color:#808080;
                            color:white;
                            padding:2px 8px;
                            text-decoration:none;
                            font-size:12px;
                            border-radius:4px;
                            margin-right:4px;
                        ">修改</a>
                        <a href="?delete={idx}" style="
                            background-color:#2E8BFF;
                            color:white;
                            padding:2px 8px;
                            text-decoration:none;
                            font-size:12px;
                            border-radius:4px;
                        ">刪除</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # ===== 處理 URL 參數 =====

    query_params = st.query_params

    if "edit" in query_params:
        index = int(query_params["edit"])
        st.session_state.mode = "edit"
        st.session_state.edit_index = index
        st.query_params.clear()
        st.rerun()

    if "delete" in query_params:
        index = int(query_params["delete"])
        row = df.iloc[index]
        st.warning(f"⚠️ 確定要刪除【{row['色粉編號']} - {row['色粉名稱']}】嗎？")

        if st.button("✅ 確定刪除"):
            df = df.drop(index).reset_index(drop=True)
            save_data(df)
            st.success(f"已刪除 {row['色粉編號']}！")
            st.query_params.clear()
            st.rerun()
        elif st.button("❌ 取消"):
            st.query_params.clear()
            st.rerun()

elif page == "配方管理":
    st.title("🧪 配方管理")
    st.info("配方管理功能開發中。")
