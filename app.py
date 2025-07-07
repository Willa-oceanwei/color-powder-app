import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ----- 美化 CSS -----
st.markdown("""
    <style>
    /* 頂部選單顏色 */
    .st-emotion-cache-18ni7ap {
        background-color: #0081A7;
    }
    /* 按鈕顏色 */
    .stButton>button {
        background-color: #F07167;
        color: white;
        border-radius: 5px;
        font-weight: bold;
        height: 40px;
    }
    /* DataFrame 表格字體 */
    .stDataFrame {
        font-size: 16px;
    }
    </style>
""", unsafe_allow_html=True)

# ----- Google Sheets 授權 -----
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])

credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)

gc = gspread.authorize(credentials)

# ----- 開啟試算表 -----
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
sh = gc.open_by_key(sheet_key)

# ----- 開啟分頁 (工作表1) -----
worksheet = sh.worksheet("工作表1")

# ----- 讀取資料 -----
data = worksheet.get_all_records()
df = pd.DataFrame(data)

st.title("🎨 色粉管理")

# ----- 新增區 -----
with st.form("add_form", clear_on_submit=True):
    st.subheader("➕ 新增色粉")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        new_id = st.text_input("色粉編號")
    with col2:
        new_name = st.text_input("色粉名稱")
    with col3:
        new_colorcode = st.text_input("國際色號")
    with col4:
        new_origin = st.text_input("產地")
    with col5:
        new_type = st.selectbox("色粉類別", ["色粉", "配方", "色母", "添加劑", "其他"])

    submitted = st.form_submit_button("新增")

    if submitted:
        # 檢查編號是否已存在
        if new_id in df["色粉編號"].values:
            st.warning("⚠️ 此編號已存在，請重新輸入！")
        else:
            worksheet.append_row([new_id, new_name, new_colorcode, new_origin, new_type])
            st.success("✅ 新增成功！")
            st.experimental_rerun()

# ----- 搜尋區 -----
st.subheader("🔍 搜尋色粉")
search_id = st.text_input("輸入色粉編號進行搜尋")

if search_id:
    filtered_df = df[df["色粉編號"].str.contains(search_id, na=False)]
else:
    filtered_df = df

# ----- 顯示 DataFrame -----
if not filtered_df.empty:
    st.markdown("### 📋 色粉總表")
    st.dataframe(
        filtered_df.style
        .set_properties(**{
            'text-align': 'left',
            'background-color': '#FDFCDC',
            'color': 'black'
        })
        .apply(
            lambda x: ['background-color: #FED9B7' if i%2 else '' for i in range(len(x))],
            axis=1
        ),
        use_container_width=True
    )
else:
    st.info("查無資料")

# ----- 編輯 / 刪除按鈕 -----
for idx, row in filtered_df.iterrows():
    col1, col2, col3 = st.columns([7, 1, 1])
    with col1:
        st.write(
            f"➡️ 色粉編號：{row['色粉編號']} ｜ 色粉名稱：{row['色粉名稱']} ｜ 國際色號：{row['國際色號']} ｜ "
            f"產地：{row['產地']} ｜ 類別：{row['色粉類別']}"
        )
    with col2:
        if st.button("✏️ 修改", key=f"edit_{idx}"):
            st.session_state["edit_row"] = idx
    with col3:
        if st.button("🗑️ 刪除", key=f"delete_{idx}"):
            worksheet.delete_rows(idx + 2)
            st.success("✅ 已刪除資料")
            st.experimental_rerun()

# ----- 編輯模式 -----
if "edit_row" in st.session_state:
    edit_idx = st.session_state["edit_row"]
    edit_row = filtered_df.iloc[edit_idx]

    st.markdown("---")
    st.subheader("✏️ 編輯色粉")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        new_id = st.text_input("色粉編號", value=edit_row["色粉編號"])
    with col2:
        new_name = st.text_input("色粉名稱", value=edit_row["色粉名稱"])
    with col3:
        new_colorcode = st.text_input("國際色號", value=edit_row["國際色號"])
    with col4:
        new_origin = st.text_input("產地", value=edit_row["產地"])
    with col5:
        new_type = st.selectbox("色粉類別", ["色粉", "配方", "色母", "添加劑", "其他"], index=[
            "色粉", "配方", "色母", "添加劑", "其他"
        ].index(edit_row["色粉類別"]))

    if st.button("✅ 確定修改"):
        worksheet.update(f"A{edit_idx+2}", [[
            new_id, new_name, new_colorcode, new_origin, new_type
        ]])
        st.success("✅ 修改成功！")
        st.session_state.pop("edit_row")
        st.experimental_rerun()

    if st.button("取消修改"):
        st.session_state.pop("edit_row")
        st.experimental_rerun()
