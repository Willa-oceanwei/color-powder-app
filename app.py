import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------------
# GOOGLE SHEET 授權
# ---------------------------------
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

# ---------------------------------
# 讀取 Google Sheet
# ---------------------------------
try:
    sh = gc.open_by_key(SHEET_KEY)
    worksheet = sh.worksheet(SHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"無法讀取 Google Sheet: {e}")
    st.stop()

# ---------------------------------
# 預設 session_state
# ---------------------------------
for key in ["code", "name", "pantone", "color_type", "spec", "origin", "remark"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# ---------------------------------
# 模組切換
# ---------------------------------
module = st.sidebar.radio(
    "選擇模組",
    ["色粉管理", "配方管理"]
)

if module == "色粉管理":

    st.title("🎨 色粉管理系統")

    # --- 上方輸入表單區 ---
    st.markdown("## 新增色粉")

    col1, col2 = st.columns([1, 1])

    with col1:
        code = st.text_input("色粉編號", st.session_state.code, key="code_input")
        name = st.text_input("色粉名稱", st.session_state.name, key="name_input")
        pantone = st.text_input("國際色號", st.session_state.pantone, key="pantone_input")
        origin = st.text_input("產地", st.session_state.origin, key="origin_input")
    with col2:
        color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"],
                                  index=0 if st.session_state.color_type == "" else ["色粉", "色母", "添加劑"].index(st.session_state.color_type),
                                  key="color_type_select")
        spec = st.selectbox("規格", ["kg", "箱", "袋"],
                            index=0 if st.session_state.spec == "" else ["kg", "箱", "袋"].index(st.session_state.spec),
                            key="spec_select")
        remark = st.text_input("備註", st.session_state.remark, key="remark_input")

        # 新增色粉按鈕放在色粉類別右邊
        if st.button("新增色粉"):
            # 檢查是否重複
            if code in df["色粉編號"].astype(str).values:
                st.warning(f"色粉編號 {code} 已存在，無法重複新增。")
            else:
                # 新增到 DataFrame
                new_row = {
                    "色粉編號": code,
                    "名稱": name,
                    "國際色號": pantone,
                    "色粉類別": color_type,
                    "規格": spec,
                    "產地": origin,
                    "備註": remark
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                # 寫回 Google Sheet
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"已成功新增色粉【{code}】！")
                # 清空表單
                for k in ["code", "name", "pantone", "color_type", "spec", "origin", "remark"]:
                    st.session_state[k] = ""

    # --- 清除輸入 ---
    if st.button("清除輸入"):
        for k in ["code", "name", "pantone", "color_type", "spec", "origin", "remark"]:
            st.session_state[k] = ""
        st.info("已清空輸入欄位。")

    st.markdown("---")

    # --- 色粉總表 ---
    st.markdown("## 色粉總表")

    if not df.empty:
        for idx, row in df.iterrows():
            bg_color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"
            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background-color:{bg_color};
                        padding:8px;
                        margin-bottom:4px;
                        font-size:14px;
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                    ">
                        <div style="text-align:left;">
                            ➡️ <b>色粉編號</b>：{row['色粉編號']} &nbsp;｜&nbsp;
                            <b>名稱</b>：{row['名稱']} &nbsp;｜&nbsp;
                            <b>國際色號</b>：{row['國際色號']} &nbsp;｜&nbsp;
                            <b>色粉類別</b>：{row['色粉類別']} &nbsp;｜&nbsp;
                            <b>規格</b>：{row['規格']} &nbsp;｜&nbsp;
                            <b>產地</b>：{row['產地']} &nbsp;｜&nbsp;
                            <b>備註</b>：{row['備註']}
                        </div>
                        <div style="display:flex; gap:10px;">
                            <form action="" method="post">
                                <button name="edit_{idx}" type="submit" style="
                                    background-color: #FFA500;
                                    color: white;
                                    border: none;
                                    padding: 4px 8px;
                                    border-radius: 3px;
                                    font-size: 12px;
                                    cursor: pointer;
                                ">修改</button>
                            </form>
                            <form action="" method="post">
                                <button name="delete_{idx}" type="submit" style="
                                    background-color: #007BFF;
                                    color: white;
                                    border: none;
                                    padding: 4px 8px;
                                    border-radius: 3px;
                                    font-size: 12px;
                                    cursor: pointer;
                                ">刪除</button>
                            </form>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Streamlit 內部的邏輯改寫為 native
                if st.session_state.get(f"edit_{idx}"):
                    # 帶入待修改
                    for key in ["code", "name", "pantone", "color_type", "spec", "origin", "remark"]:
                        st.session_state[key] = row.get({
                            "code": "色粉編號",
                            "name": "名稱",
                            "pantone": "國際色號",
                            "color_type": "色粉類別",
                            "spec": "規格",
                            "origin": "產地",
                            "remark": "備註"
                        }[key], "")
                    st.success(f"已進入【{row['色粉編號']}】修改模式。")

                if st.session_state.get(f"delete_{idx}"):
                    if st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？"):
                        df = df.drop(idx)
                        worksheet.clear()
                        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                        st.success(f"已刪除【{row['色粉編號']}】。")
                        st.experimental_rerun()

else:
    st.title("🧪 配方管理模組")
    st.info("配方管理功能開發中...")

