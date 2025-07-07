import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ---------- CSS 區 ----------
st.markdown("""
    <style>
        div.stButton > button {
            background-color: #0081A7;
            color: white;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 12px;
            height: 28px;
        }
        .dataframe th, .dataframe td {
            text-align: center !important;
            vertical-align: middle !important;
            font-size: 14px;
        }
        /* 刪除鍵亮藍底，白字 */
        .delete-btn {
            background-color: #0081A7;
            color: white;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 12px;
            height: 28px;
            border: none;
            cursor: pointer;
        }
    </style>
""", unsafe_allow_html=True)

# ---------- Google Sheets 設定 ----------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])

credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)

gc = gspread.authorize(credentials)

# 你的 Google Sheet Key
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"

try:
    sh = gc.open_by_key(sheet_key)
    worksheet = sh.worksheet("工作表1")
    st.success("✅ 成功開啟 Google Sheets!")

except Exception as e:
    st.error(f"發生錯誤：{e}")
    st.stop()

# ---------- 讀取 Sheet ----------
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ---------- 新增色粉 ----------
st.header("➕ 新增色粉")

with st.form("add_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        color_id = st.text_input("色粉編號")
        color_name = st.text_input("色粉名稱")
        color_type = st.selectbox("色粉類別", ["色粉", "配方", "色母", "添加劑", "其他"])
    with col2:
        intl_code = st.text_input("國際色號")
        spec = st.text_input("規格")
    with col3:
        origin = st.text_input("產地")
        remark = st.text_input("備註")

    submit = st.form_submit_button("新增色粉")

if submit:
    worksheet.append_row([
        color_id, intl_code, color_name,
        color_type, spec, origin, remark
    ])
    st.success("✅ 已新增色粉！")
    st.experimental_rerun()

# ---------- 顯示色粉總表 ----------
st.subheader("📄 色粉總表")

if not df.empty:
    for idx, row in df.iterrows():
        bg_color = "#FED9B7" if idx % 2 == 0 else "#FDFCDC"

        # 顯示每筆資料
        st.markdown(
            f"""
            <div style="
                background-color: {bg_color};
                padding: 8px;
                border-radius: 5px;
                margin-bottom: 4px;
            ">
                ➡️ <b>色粉編號：</b>{row['色粉編號']} ｜ 
                <b>名稱：</b>{row['色粉名稱']} ｜ 
                <b>國際色號：</b>{row['國際色號']} ｜ 
                <b>類別：</b>{row['色粉類別']} ｜ 
                <b>規格：</b>{row['規格']} ｜ 
                <b>產地：</b>{row['產地']} ｜ 
                <b>備註：</b>{row['備註']}
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("修改", key=f"edit_{idx}"):
                st.session_state["edit_idx"] = idx
                st.experimental_rerun()

        with col2:
            delete_btn = st.button("刪除", key=f"del_{idx}")
            if delete_btn:
                worksheet.delete_rows(idx + 2)
                st.success("✅ 已刪除！")
                st.experimental_rerun()

# ---------- 修改功能 ----------
if "edit_idx" in st.session_state:
    edit_idx = st.session_state["edit_idx"]
    row_data = df.iloc[edit_idx]

    st.subheader("✏️ 修改色粉")

    with st.form("edit_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            color_id = st.text_input("色粉編號", value=row_data["色粉編號"])
            color_name = st.text_input("色粉名稱", value=row_data["色粉名稱"])
            color_type = st.selectbox("色粉類別",
                                      ["色粉", "配方", "色母", "添加劑", "其他"],
                                      index=["色粉", "配方", "色母", "添加劑", "其他"].index(row_data["色粉類別"]))
        with col2:
            intl_code = st.text_input("國際色號", value=row_data["國際色號"])
            spec = st.text_input("規格", value=row_data["規格"])
        with col3:
            origin = st.text_input("產地", value=row_data["產地"])
            remark = st.text_input("備註", value=row_data["備註"])

        save = st.form_submit_button("儲存修改")

    if save:
        # 替換整行
        worksheet.update(
            f"A{edit_idx+2}:G{edit_idx+2}",
            [[color_id, intl_code, color_name, color_type, spec, origin, remark]]
        )
        st.success("✅ 已完成修改！")
        del st.session_state["edit_idx"]
        st.experimental_rerun()

else:
    st.write("")  # 保持版面整齊
