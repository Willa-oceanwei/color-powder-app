import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ====== Google Sheets 認證 ======
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

# ====== 頁面選擇 ======
page = st.selectbox("請選擇功能", ["色粉管理", "配方管理"])

# ====== 初始化 Session State ======
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# 預設欄位 Session State
fields = ["code_input", "name_input", "int_color_input",
          "color_type_input", "spec_input", "origin_input", "remark_input"]
for f in fields:
    st.session_state.setdefault(f, "")

if page == "色粉管理":

    st.subheader("➕ 新增 / 修改 色粉資料")

    # ====== 四列兩欄排版 ======
    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("色粉編號", value=st.session_state.code_input)
    with col2:
        name = st.text_input("色粉名稱", value=st.session_state.name_input)

    col3, col4 = st.columns(2)
    with col3:
        int_color = st.text_input("國際色號", value=st.session_state.int_color_input)
    with col4:
        color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"], index=0
                                  if st.session_state.color_type_input == "" else
                                  ["色粉", "色母", "添加劑"].index(st.session_state.color_type_input))

    col5, col6 = st.columns(2)
    with col5:
        spec = st.selectbox("規格", ["kg", "箱", "袋"], index=0
                            if st.session_state.spec_input == "" else
                            ["kg", "箱", "袋"].index(st.session_state.spec_input))
    with col6:
        origin = st.text_input("產地", value=st.session_state.origin_input)

    col7, col8 = st.columns(2)
    with col7:
        remark = st.text_input("備註", value=st.session_state.remark_input)
    with col8:
        if st.button("🧹 清除輸入", use_container_width=True):
            for f in fields:
                st.session_state[f] = ""
            st.session_state.edit_mode = False
            st.session_state.edit_index = None
            st.experimental_rerun()

    # ====== 新增或修改按鈕 ======
    if st.session_state.edit_mode:
        submit_label = "✅ 更新色粉"
    else:
        submit_label = "➕ 新增色粉"

    if st.button(submit_label, use_container_width=True):
        # 讀取現有資料
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # 防止空表
        if df.empty:
            df = pd.DataFrame(columns=[
                "色粉編號", "色粉名稱", "國際色號", "色粉類別", "規格", "產地", "備註"
            ])

        # 若是新增，檢查是否重複編號
        if not st.session_state.edit_mode:
            if (df["色粉編號"].astype(str) == code).any():
                st.error(f"🚫 編號 {code} 已存在，請勿重複新增！")
            else:
                new_row = pd.DataFrame({
                    "色粉編號": [code],
                    "色粉名稱": [name],
                    "國際色號": [int_color],
                    "色粉類別": [color_type],
                    "規格": [spec],
                    "產地": [origin],
                    "備註": [remark]
                })
                df = pd.concat([df, new_row], ignore_index=True)
                worksheet.update([df.columns.tolist()] + df.values.tolist())
                st.success(f"✅ 已成功新增 {code}")
                st.experimental_rerun()

        else:
            # 修改模式
            df.loc[st.session_state.edit_index, :] = [
                code, name, int_color, color_type, spec, origin, remark
            ]
            worksheet.update([df.columns.tolist()] + df.values.tolist())
            st.success(f"✅ 已成功修改 {code}")
            st.session_state.edit_mode = False
            st.session_state.edit_index = None
            for f in fields:
                st.session_state[f] = ""
            st.experimental_rerun()

    st.divider()

    # ====== 搜尋色粉 ======
    st.subheader("🔍 搜尋色粉")
    search_code = st.text_input("請輸入色粉編號進行搜尋", key="search_code")

    if st.button("搜尋色粉", use_container_width=True):
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # 若色粉編號是數字，也要轉成 str 做比對
        df["色粉編號"] = df["色粉編號"].astype(str)
        if search_code.strip() == "":
            st.warning("請輸入色粉編號")
        else:
            result = df[df["色粉編號"] == search_code.strip()]
            if result.empty:
                st.info(f"⚠️ 尚無編號 {search_code} 的色粉資料")
            else:
                st.success(f"✅ 找到編號 {search_code}！")
                st.dataframe(result)

    st.divider()

    # ====== 顯示色粉總表 ======
    st.subheader("📋 色粉總表")

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        st.info("⚠️ 尚無色粉資料")
    else:
        # 序列交錯顏色 + 按鈕
        for i, row in df.iterrows():
            bg_color = "#FDFCDC" if i % 2 == 0 else "#FED9B7"
            col1, col2, col3 = st.columns([8, 1, 1])
            with col1:
                st.markdown(
                    f"""
                    <div style="
                        background-color:{bg_color};
                        padding:8px;
                        border-radius:4px;
                        font-size:14px;
                        display: flex;
                        justify-content: space-between;
                    ">
                    ➡️ <strong>{row['色粉編號']}</strong> | {row['色粉名稱']} | {row['國際色號']}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col2:
                edit_key = f"edit_{i}"
                if st.button("✏️", key=edit_key):
                    # 帶入欄位到表單
                    st.session_state.code_input = str(row["色粉編號"])
                    st.session_state.name_input = row["色粉名稱"]
                    st.session_state.int_color_input = row["國際色號"]
                    st.session_state.color_type_input = row["色粉類別"]
                    st.session_state.spec_input = row["規格"]
                    st.session_state.origin_input = row["產地"]
                    st.session_state.remark_input = row["備註"]
                    st.session_state.edit_mode = True
                    st.session_state.edit_index = i
                    st.experimental_rerun()
            with col3:
                del_key = f"delete_{i}"
                if st.button("🗑️", key=del_key):
                    confirm = st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？")
                    if confirm:
                        df = df.drop(i).reset_index(drop=True)
                        worksheet.update([df.columns.tolist()] + df.values.tolist())
                        st.success(f"✅ 已刪除 {row['色粉編號']}")
                        st.experimental_rerun()

    # ====== 按鈕 CSS 美化 ======
    st.markdown("""
    <style>
    button {
        height: 30px !important;
        padding: 2px 8px !important;
        font-size: 12px !important;
    }
    </style>
    """, unsafe_allow_html=True)

elif page == "配方管理":
    st.subheader("🚧 配方管理模組開發中…")

