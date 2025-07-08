import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# 設定寬版 Layout
st.set_page_config(layout="wide")

# ===== 連線 GSpread =====

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

# 讀取資料
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ===== Function =====

def load_data():
    rows = worksheet.get_all_records()
    return pd.DataFrame(rows)

def save_data(df):
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    worksheet.append_rows(df.values.tolist())

def style_row(row_idx):
    color = "#FDFCDC" if row_idx % 2 == 0 else "#FED9B7"
    return f"background-color: {color}"

# ===== 初始化 Session State =====

if "mode" not in st.session_state:
    st.session_state.mode = "view"

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

if "search_code" not in st.session_state:
    st.session_state.search_code = ""

# ===== 主選單 =====

page = st.sidebar.radio("功能模組", ["色粉管理", "配方管理"])

if page == "色粉管理":

    st.title("🎨 色粉管理")

    # ===== 清除輸入按鈕 =====
    if st.button("🔄 清除輸入"):
        st.session_state.mode = "view"
        st.session_state.edit_index = None
        st.session_state.search_code = ""
        st.experimental_rerun()

    # ===== 搜尋色粉 =====
    st.subheader("🔎 搜尋色粉")
    search_code = st.text_input("請輸入色粉編號或名稱", value=st.session_state.search_code)

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
                df_display = pd.DataFrame()  # 清空結果
            else:
                df_display = found
                st.success(f"找到 {len(found)} 筆資料")

    # ===== 新增或編輯色粉 =====
    st.subheader("➕ 新增 / 編輯 色粉")

    # 檢查是否是編輯模式
    editing = st.session_state.mode == "edit"

    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("色粉編號", value="" if not editing else df.iloc[st.session_state.edit_index]["色粉編號"])
        color_name = st.text_input("色粉名稱", value="" if not editing else df.iloc[st.session_state.edit_index]["色粉名稱"])
        pantone = st.text_input("國際色號", value="" if not editing else df.iloc[st.session_state.edit_index]["國際色號"])
        color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"], index=0 if not editing else
                                  ["色粉", "色母", "添加劑"].index(df.iloc[st.session_state.edit_index]["色粉類別"]))
    with col2:
        spec = st.selectbox("規格", ["kg", "箱", "袋"], index=0 if not editing else
                            ["kg", "箱", "袋"].index(df.iloc[st.session_state.edit_index]["規格"]))
        origin = st.text_input("產地", value="" if not editing else df.iloc[st.session_state.edit_index]["產地"])
        remark = st.text_input("備註", value="" if not editing else df.iloc[st.session_state.edit_index]["備註"])

    # ===== 新增或更新 按鈕 =====

    if editing:
        save_btn = st.button("💾 儲存修改")
        if save_btn:
            # 確保色粉編號不重複 (若編號已被其他列占用)
            duplicate = df[
                (df["色粉編號"] == code) &
                (df.index != st.session_state.edit_index)
            ]
            if not duplicate.empty:
                st.error(f"色粉編號 {code} 已存在，請使用其他編號。")
            else:
                df.loc[st.session_state.edit_index] = [
                    code, pantone, color_name, color_type, spec, origin, remark
                ]
                save_data(df)
                st.success(f"色粉編號 {code} 已更新！")
                st.session_state.mode = "view"
                st.experimental_rerun()
    else:
        add_btn = st.button("➕ 新增色粉")
        if add_btn:
            # 檢查編號重複
            if code in df["色粉編號"].astype(str).values:
                st.error(f"色粉編號 {code} 已存在，請使用其他編號。")
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
                df = df.append(new_row, ignore_index=True)
                save_data(df)
                st.success(f"新增色粉 {code} 成功！")
                st.experimental_rerun()

    # ===== 顯示色粉序列 =====
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
                        <button onclick="window.location.href='?edit={idx}'"
                            style="
                                background-color:#808080;
                                color:white;
                                border:none;
                                padding:2px 8px;
                                margin-left:4px;
                                font-size:12px;
                                border-radius:4px;
                                cursor:pointer;
                            ">
                            修改
                        </button>
                        <button onclick="window.location.href='?delete={idx}'"
                            style="
                                background-color:#2E8BFF;
                                color:white;
                                border:none;
                                padding:2px 8px;
                                margin-left:4px;
                                font-size:12px;
                                border-radius:4px;
                                cursor:pointer;
                            ">
                            刪除
                        </button>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # ===== 處理 URL 參數 (修改、刪除) =====
    query_params = st.experimental_get_query_params()

    if "edit" in query_params:
        index = int(query_params["edit"][0])
        st.session_state.mode = "edit"
        st.session_state.edit_index = index
        st.experimental_set_query_params()
        st.experimental_rerun()

    if "delete" in query_params:
        index = int(query_params["delete"][0])
        row = df.iloc[index]
        confirm = st.warning(
            f"⚠️ 確定要刪除【{row['色粉編號']} - {row['色粉名稱']}】嗎？",
            icon="⚠️"
        )
        if st.button("✅ 確定刪除"):
            df = df.drop(index).reset_index(drop=True)
            save_data(df)
            st.success(f"已刪除 {row['色粉編號']}！")
            st.experimental_set_query_params()
            st.experimental_rerun()
        elif st.button("❌ 取消"):
            st.experimental_set_query_params()
            st.experimental_rerun()

elif page == "配方管理":
    st.title("🧪 配方管理")
    st.info("配方管理功能開發中。")

