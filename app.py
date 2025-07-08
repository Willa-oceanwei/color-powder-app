import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# ---------- Streamlit 頁面設定 ----------
st.set_page_config(
    page_title="色粉管理",
    layout="wide",
)

# ---------- Google Sheets 認證 ----------
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

# ---------- 讀取資料 ----------
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ---------- 初始化 Session State ----------
if "mode" not in st.session_state:
    st.session_state.mode = "view"
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "search_code" not in st.session_state:
    st.session_state.search_code = ""

# ---------- 功能列 ----------
col_search, col_clear = st.columns([5, 1])

with col_search:
    st.session_state.search_code = st.text_input(
        "請輸入色粉編號或名稱", value=st.session_state.search_code
    )

with col_clear:
    if st.button("🔄 清除輸入"):
        st.session_state.search_code = ""
        st.session_state.mode = "view"
        st.session_state.edit_index = None
        st.experimental_rerun()

# ---------- 搜尋結果 ----------
df_display = df.copy()

if st.session_state.search_code:
    keyword = str(st.session_state.search_code).strip()
    mask = df["色粉編號"].astype(str).str.contains(keyword, case=False) | \
           df["色粉名稱"].astype(str).str.contains(keyword, case=False)
    df_display = df[mask]
    if df_display.empty:
        st.warning(f"⚠️ 查無【{keyword}】的資料！")
    else:
        st.success(f"🔍 找到 {len(df_display)} 筆資料")

# ---------- 編輯模式 ----------
editing = False
edit_data = {}

if st.session_state.mode == "edit":
    idx = st.session_state.edit_index
    if idx is not None and idx < len(df):
        editing = True
        edit_data = df.iloc[idx].to_dict()
    else:
        st.info("無資料可顯示")
        st.session_state.mode = "view"

# ---------- 輸入區塊 (新增/修改) ----------
st.markdown("### ➕ 新增 / 修改色粉資料")

col1, col2 = st.columns(2)

with col1:
    code = st.text_input(
        "色粉編號",
        value=edit_data.get("色粉編號", "") if editing else "",
        key="code"
    )
    name = st.text_input(
        "色粉名稱",
        value=edit_data.get("色粉名稱", "") if editing else "",
        key="name"
    )
    pantone = st.text_input(
        "國際色號",
        value=edit_data.get("國際色號", "") if editing else "",
        key="pantone"
    )
    origin = st.text_input(
        "產地",
        value=edit_data.get("產地", "") if editing else "",
        key="origin"
    )
with col2:
    color_type = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(edit_data.get("色粉類別", "色粉")) if editing else 0,
        key="color_type"
    )
    spec = st.selectbox(
        "規格",
        ["kg", "箱", "袋"],
        index=["kg", "箱", "袋"].index(edit_data.get("規格", "kg")) if editing else 0,
        key="spec"
    )
    remark = st.text_input(
        "備註",
        value=edit_data.get("備註", "") if editing else "",
        key="remark"
    )
    if editing:
        if st.button("💾 確認修改"):
            # 檢查是否重複編號 (排除自己)
            if code in df["色粉編號"].values and code != df.iloc[idx]["色粉編號"]:
                st.error(f"❌ 色粉編號【{code}】已存在，請勿重複！")
            else:
                df.at[idx, "色粉編號"] = code
                df.at[idx, "色粉名稱"] = name
                df.at[idx, "國際色號"] = pantone
                df.at[idx, "色粉類別"] = color_type
                df.at[idx, "規格"] = spec
                df.at[idx, "產地"] = origin
                df.at[idx, "備註"] = remark
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"✅ 已修改色粉編號【{code}】")
                st.session_state.mode = "view"
                st.session_state.edit_index = None
                st.experimental_rerun()
    else:
        if st.button("➕ 新增色粉"):
            if code in df["色粉編號"].values:
                st.error(f"❌ 色粉編號【{code}】已存在！請勿重複新增。")
            else:
                new_row = pd.DataFrame([{
                    "色粉編號": code,
                    "色粉名稱": name,
                    "國際色號": pantone,
                    "色粉類別": color_type,
                    "規格": spec,
                    "產地": origin,
                    "備註": remark
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"✅ 成功新增色粉【{code}】")
                st.experimental_rerun()

# ---------- 序列顯示 ----------
st.markdown("### 📋 色粉總表")

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
                justify-content: space-between;
                align-items: center;
                margin-bottom:4px;
                white-space: nowrap;
                overflow-x: auto;
                text-align: left;
            ">
                <span>
                    ➡️ <strong>{row['色粉編號']}</strong> | 
                    {row['色粉名稱']} | 
                    {row['國際色號']} | 
                    {row['色粉類別']} | 
                    {row['規格']} | 
                    {row['產地']} | 
                    {row['備註']}
                </span>
                <span style="display:flex;gap:10px;">
                    <form method="post">
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
                    <form method="post">
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
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 監聽修改、刪除
        if st.session_state.get(f"edit_{idx}"):
            st.session_state.mode = "edit"
            st.session_state.edit_index = idx
            st.experimental_rerun()

        if st.session_state.get(f"delete_{idx}"):
            confirm = st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？")
            if confirm:
                df = df.drop(idx).reset_index(drop=True)
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"✅ 已刪除色粉【{row['色粉編號']}】")
                st.experimental_rerun()

else:
    st.info("目前無資料可顯示。")

