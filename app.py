import json
import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

# 修正讀取 secrets
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)
gcp_info = json.loads(st.secrets["gcp"]["gcps_ervice_account"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scopes=scope)
gc = gspread.authorize(credentials)
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
worksheet = gc.open_by_key(sheet_key).worksheet("工作表1")

# ============================
# 初始化 Session State
# ============================
def reset_inputs():
    st.session_state.clear()
    st.rerun()

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

# ============================
# 資料載入
# ============================
try:
    df = pd.DataFrame(worksheet.get_all_records())
except Exception as e:
    st.error(f"讀取資料失敗：{e}")
    df = pd.DataFrame()

# ============================
# 頁面佈局與輸入欄位
# ============================
st.set_page_config(layout="wide")
st.title("🎨 色粉管理系統")

col1, col2 = st.columns(2)
with col1:
    code = st.text_input("色粉編號", value=st.session_state.get("code", ""))
    name = st.text_input("色粉名稱", value=st.session_state.get("name", ""))
    color_no = st.text_input("國際色號", value=st.session_state.get("color_no", ""))
    color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"], index=0)

with col2:
    spec = st.selectbox("規格", ["kg", "箱", "袋"], index=0)
    origin = st.text_input("產地", value=st.session_state.get("origin", ""))
    remark = st.text_input("備註", value=st.session_state.get("remark", ""))

# ============================
# 操作按鍵區塊
# ============================
st.markdown("---")
col3, col4 = st.columns([1, 5])
with col3:
    search_code = st.text_input("🔍 搜尋色粉編號")

with col4:
    if st.button("🔁 清除輸入"):
        reset_inputs()

# ============================
# 搜尋功能
# ============================
if search_code:
    matched_df = df[df["色粉編號"].astype(str) == search_code]
    if not matched_df.empty:
        st.success("✅ 搜尋成功，以下為結果：")
        df = matched_df.copy()
    else:
        st.warning("⚠️ 查無此色粉資料")

# ============================
# 新增或修改色粉
# ============================
col5, _ = st.columns([1, 3])
with col5:
    if st.session_state.editing_index is not None:
        if st.button("✅ 確認修改"):
            df.iloc[st.session_state.editing_index] = {
                "色粉編號": code,
                "色粉名稱": name,
                "國際色號": color_no,
                "色粉類別": color_type,
                "規格": spec,
                "產地": origin,
                "備註": remark
            }
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            st.success("✅ 修改完成")
            reset_inputs()
    else:
        if st.button("➕ 新增色粉"):
            if code in df["色粉編號"].astype(str).values:
                st.warning("⚠️ 該色粉編號已存在！")
            else:
                new_row = {
                    "色粉編號": code,
                    "色粉名稱": name,
                    "國際色號": color_no,
                    "色粉類別": color_type,
                    "規格": spec,
                    "產地": origin,
                    "備註": remark
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success("✅ 新增完成")
                reset_inputs()

# ============================
# 顯示色粉總表（交錯顏色）
# ============================
st.markdown("---")
st.subheader("📋 色粉總表")

for idx, row in df.iterrows():
    bg_color = "#F7F7F7" if idx % 2 == 0 else "#FFFFFF"
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; background-color:{bg_color}; padding:6px; border-radius:5px;'>
        <div style='flex:1;'>
            <strong>➡️ {row['色粉編號']} | {row['色粉名稱']} | {row['國際色號']}</strong>
        </div>
        <div style='display:flex; gap:8px;'>
            <form action="?edit={idx}" method="get">
                <button style='background:#FFA500;color:white;padding:4px 8px;font-size:12px;border:none;border-radius:4px;'>修改</button>
            </form>
            <form action="?delete={idx}" method="get">
                <button style='background:#007BFF;color:white;padding:4px 8px;font-size:12px;border:none;border-radius:4px;'>刪除</button>
            </form>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================
# 修改／刪除邏輯（透過 query string）
# ============================
query_params = st.query_params

if "edit" in query_params:
    idx = int(query_params["edit"])
    for key in df.columns:
        st.session_state[key] = df.iloc[idx][key]
    st.session_state.editing_index = idx
    st.experimental_set_query_params()
    st.rerun()

elif "delete" in query_params:
    idx = int(query_params["delete"])
    if st.confirm(f"⚠️ 確定要刪除【{df.iloc[idx]['色粉編號']}】嗎？"):
        df = df.drop(idx).reset_index(drop=True)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("✅ 刪除完成")
        st.experimental_set_query_params()
        st.rerun()
