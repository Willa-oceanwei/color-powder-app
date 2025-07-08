import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# --------------------------
# Google Sheets 授權
# --------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)
gc = gspread.authorize(credentials)

SHEET_KEY = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
SHEET_NAME = "工作表1"

# --------------------------
# 讀取 Google Sheet
# --------------------------
try:
    sh = gc.open_by_key(SHEET_KEY)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"無法讀取 Google Sheet: {e}")
    st.stop()

# 確保 DataFrame 欄位完整
required_cols = ["色粉編號", "名稱", "國際色號", "色粉類別", "規格", "產地", "備註"]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

# --------------------------
# 初始化 session_state
# --------------------------
fields = [
    "code_input", "name_input", "pantone_input",
    "color_type_select", "spec_select", "origin_input", "remark_input",
    "search_input"
]
for f in fields:
    if f not in st.session_state:
        st.session_state[f] = ""

# --------------------------
# 模組切換
# --------------------------
module = st.sidebar.radio(
    "選擇模組",
    ["色粉管理", "配方管理"]
)

if module == "色粉管理":

    st.title("🎨 色粉管理系統")

    # --------------------------
    # 搜尋輸入框
    # --------------------------
    st.markdown("#### 搜尋色粉")
    st.session_state["search_input"] = st.text_input(
        "請輸入色粉編號或名稱後按 Enter 搜尋 (保留此欄位即可，不需要按鈕)",
        st.session_state["search_input"]
    )

    # 若有搜尋值，先篩選 DataFrame
    search_df = df.copy()
    search_value = st.session_state["search_input"].strip()
    if search_value != "":
        search_df = search_df[
            (search_df["色粉編號"].astype(str).str.contains(search_value, case=False, na=False)) |
            (search_df["名稱"].astype(str).str.contains(search_value, case=False, na=False))
        ]
        if search_df.empty:
            st.warning("⚠️ 查無符合的色粉資料。")

    st.markdown("---")

    # --------------------------
    # 新增色粉表單
    # --------------------------
    st.markdown("#### 新增色粉")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state["code_input"] = st.text_input("色粉編號", st.session_state["code_input"])
        st.session_state["name_input"] = st.text_input("色粉名稱", st.session_state["name_input"])
        st.session_state["pantone_input"] = st.text_input("國際色號", st.session_state["pantone_input"])
        st.session_state["origin_input"] = st.text_input("產地", st.session_state["origin_input"])
    with col2:
        st.session_state["color_type_select"] = st.selectbox(
            "色粉類別", ["色粉", "色母", "添加劑"],
            index=0 if st.session_state["color_type_select"] == "" else
                   ["色粉", "色母", "添加劑"].index(st.session_state["color_type_select"])
        )
        st.session_state["spec_select"] = st.selectbox(
            "規格", ["kg", "箱", "袋"],
            index=0 if st.session_state["spec_select"] == "" else
                   ["kg", "箱", "袋"].index(st.session_state["spec_select"])
        )
        st.session_state["remark_input"] = st.text_input("備註", st.session_state["remark_input"])

        if st.button("新增色粉"):
            code = st.session_state["code_input"].strip()
            if code == "":
                st.warning("請輸入色粉編號。")
            elif code in df["色粉編號"].astype(str).values:
                st.warning(f"色粉編號 {code} 已存在，無法重複新增。")
            else:
                new_row = {
                    "色粉編號": code,
                    "名稱": st.session_state["name_input"],
                    "國際色號": st.session_state["pantone_input"],
                    "色粉類別": st.session_state["color_type_select"],
                    "規格": st.session_state["spec_select"],
                    "產地": st.session_state["origin_input"],
                    "備註": st.session_state["remark_input"]
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                # 寫回 Google Sheet
                worksheet.clear()
                worksheet.update(
                    [df.columns.tolist()] +
                    df.fillna("").astype(str).values.tolist()
                )
                st.success(f"✅ 已成功新增色粉【{code}】！")

                # 清空欄位
                for f in fields:
                    st.session_state[f] = ""

    # --------------------------
    # 清除輸入
    # --------------------------
    if st.button("清除輸入"):
        for f in fields:
            st.session_state[f] = ""
        st.info("已清空所有輸入。")

    st.markdown("---")

    # --------------------------
    # 色粉總表
    # --------------------------
    st.markdown("#### 色粉總表")

    show_df = search_df if search_value != "" else df

    if not show_df.empty:
        for idx, row in show_df.iterrows():
            bg_color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"
            with st.container():
                col_a, col_b = st.columns([8, 2])
                with col_a:
                    st.markdown(
                        f"""
                        <div style='background-color:{bg_color};padding:8px;'>
                            ➡️ <b>色粉編號</b>: {row['色粉編號']} ｜ 
                            <b>名稱</b>: {row['名稱']} ｜ 
                            <b>國際色號</b>: {row['國際色號']} ｜ 
                            <b>色粉類別</b>: {row['色粉類別']} ｜ 
                            <b>規格</b>: {row['規格']} ｜ 
                            <b>產地</b>: {row['產地']} ｜ 
                            <b>備註</b>: {row['備註']}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with col_b:
                    edit_clicked = st.button("修改", key=f"edit_{idx}")
                    delete_clicked = st.button("刪除", key=f"delete_{idx}")
                    if edit_clicked:
                        st.info(f"點擊修改：{row['色粉編號']}")
                        # 可放入修改邏輯
                    if delete_clicked:
                        confirm = st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？")
                        if confirm:
                            df = df.drop(idx).reset_index(drop=True)
                            worksheet.clear()
                            worksheet.update(
                                [df.columns.tolist()] +
                                df.fillna("").astype(str).values.tolist()
                            )
                            st.success("已刪除。")
                            st.experimental_rerun()

else:
    st.title("🧪 配方管理模組")
    st.info("配方管理功能開發中...")
