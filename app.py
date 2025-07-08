import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------
# Google Sheets 授權
# -----------------------
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

# -----------------------
# 讀取 Google Sheet
# -----------------------
try:
    sh = gc.open_by_key(SHEET_KEY)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"無法讀取 Google Sheet: {e}")
    st.stop()

required_cols = ["色粉編號", "名稱", "國際色號", "色粉類別", "規格", "產地", "備註"]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

# -----------------------
# 初始化 session_state
# -----------------------
fields = [
    "code_input", "name_input", "pantone_input",
    "color_type_select", "spec_select", "origin_input", "remark_input",
    "search_input", "delete_confirm"
]
for f in fields:
    if f not in st.session_state:
        st.session_state[f] = ""

# -----------------------
# 模組切換
# -----------------------
module = st.sidebar.radio(
    "選擇模組",
    ["色粉管理", "配方管理"]
)

if module == "色粉管理":

    st.title("🎨 色粉管理系統")

    # -----------------------
    # 搜尋欄位
    # -----------------------
    st.markdown("#### 搜尋色粉")
    st.session_state["search_input"] = st.text_input(
        "請輸入色粉編號或名稱後按 Enter 搜尋",
        st.session_state["search_input"]
    )

    search_value = st.session_state["search_input"].strip()
    search_df = df.copy()
    if search_value != "":
        search_df = df[
            (df["色粉編號"].astype(str).str.contains(search_value, case=False, na=False)) |
            (df["名稱"].astype(str).str.contains(search_value, case=False, na=False))
        ]
        if search_df.empty:
            st.warning("⚠️ 查無符合的色粉資料。")

    st.markdown("---")

    # -----------------------
    # 新增 / 修改色粉表單
    # -----------------------
    st.markdown("#### 新增 / 修改色粉")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state["code_input"] = st.text_input(
            "色粉編號", st.session_state["code_input"]
        )
        st.session_state["name_input"] = st.text_input(
            "色粉名稱", st.session_state["name_input"]
        )
        st.session_state["pantone_input"] = st.text_input(
            "國際色號", st.session_state["pantone_input"]
        )
        st.session_state["origin_input"] = st.text_input(
            "產地", st.session_state["origin_input"]
        )
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
        st.session_state["remark_input"] = st.text_input(
            "備註", st.session_state["remark_input"]
        )

    # 新增 or 修改
    if st.button("💾 新增 / 修改色粉", key="save"):
        code = st.session_state["code_input"].strip()
        if code == "":
            st.warning("請輸入色粉編號。")
        else:
            if code in df["色粉編號"].astype(str).values:
                # 修改
                df.loc[
                    df["色粉編號"].astype(str) == code,
                    ["名稱", "國際色號", "色粉類別", "規格", "產地", "備註"]
                ] = [
                    st.session_state["name_input"],
                    st.session_state["pantone_input"],
                    st.session_state["color_type_select"],
                    st.session_state["spec_select"],
                    st.session_state["origin_input"],
                    st.session_state["remark_input"]
                ]
                st.success(f"✅ 已更新色粉【{code}】！")
            else:
                # 新增
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
                st.success(f"✅ 已新增色粉【{code}】！")

            # 寫回 Google Sheet
            worksheet.clear()
            worksheet.update(
                [df.columns.tolist()] +
                df.fillna("").astype(str).values.tolist()
            )
            for f in fields:
                st.session_state[f] = ""

    # 清除
    if st.button("🧹 清除輸入", key="clear"):
        for f in fields:
            st.session_state[f] = ""
        st.info("已清空所有輸入。")

    st.markdown("---")

    # -----------------------
    # 色粉總表
    # -----------------------
    st.markdown("#### 色粉總表")

    show_df = search_df if search_value != "" else df
    if not show_df.empty:
        for idx, row in show_df.iterrows():
            bg = "#FED9B7" if idx % 2 == 0 else "#FDFCDC"
            st.markdown(
                f"""
                <div style='background-color:{bg};padding:8px;'>
                    ➡️ <b>色粉編號</b>: {row['色粉編號']} ｜ 
                    <b>名稱</b>: {row['名稱']} ｜ 
                    <b>國際色號</b>: {row['國際色號']} ｜ 
                    <b>色粉類別</b>: {row['色粉類別']} ｜ 
                    <b>規格</b>: {row['規格']} ｜ 
                    <b>產地</b>: {row['產地']} ｜ 
                    <b>備註</b>: {row['備註']}
                    <span style='float:right;'>
                        <form action="" method="post">
                            <button name="edit_{idx}" type="submit" style="
                                background-color:#FFA500;
                                color:white;
                                border:none;
                                padding:4px 8px;
                                border-radius:3px;
                                font-size:12px;
                                cursor:pointer;">
                                修改
                            </button>
                        </form>
                        <form action="" method="post">
                            <button name="delete_{idx}" type="submit" style="
                                background-color:#007BFF;
                                color:white;
                                border:none;
                                padding:4px 8px;
                                border-radius:3px;
                                font-size:12px;
                                cursor:pointer;">
                                刪除
                            </button>
                        </form>
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 處理修改
            if f"edit_{idx}" in st.session_state:
                for f in required_cols:
                    st.session_state[f"{f.replace(' ', '_')}_input"] = str(row[f])
                st.info(f"已載入【{row['色粉編號']}】資料供修改。")

            # 處理刪除
            if f"delete_{idx}" in st.session_state:
                if not st.session_state["delete_confirm"]:
                    if st.button(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？"):
                        st.session_state["delete_confirm"] = True
                else:
                    df = df.drop(row.name).reset_index(drop=True)
                    worksheet.clear()
                    worksheet.update(
                        [df.columns.tolist()] +
                        df.fillna("").astype(str).values.tolist()
                    )
                    st.success(f"✅ 已刪除色粉【{row['色粉編號']}】")
                    st.session_state["delete_confirm"] = False
                    st.experimental_rerun()

else:
    st.title("🧪 配方管理模組")
    st.info("配方管理功能開發中...")
