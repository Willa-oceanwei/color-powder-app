import streamlit as st
import gspread
import pandas as pd
import json
from oauth2client.service_account import ServiceAccountCredentials

# ---------- Streamlit 設定 ----------
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
for key in ["mode", "edit_index", "search_code",
            "code", "name", "pantone", "color_type", "spec", "origin", "remark"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "tab" not in st.session_state:
    st.session_state.tab = "色粉管理"

# ---------- 模組切換 ----------
tab = st.radio(
    "請選擇模組",
    ["色粉管理", "配方管理"],
    index=0 if st.session_state.tab == "色粉管理" else 1,
    horizontal=True
)
st.session_state.tab = tab

if tab == "配方管理":
    st.info("配方管理功能尚未完成。")
    st.stop()

# =========== 色粉管理 ===========

# ---------- 功能列 ----------
c1, c2, c3 = st.columns([3,1,1])

with c1:
    st.session_state.search_code = st.text_input(
        "搜尋色粉編號或名稱", value=st.session_state.search_code
    )

with c2:
    if st.button("🔍 搜尋"):
        # 不用 rerun，搜尋會即時變動
        pass

with c3:
    if st.button("🔄 清除輸入"):
        for key in ["search_code", "code", "name", "pantone", "origin", "remark"]:
            st.session_state[key] = ""
        st.session_state["color_type"] = "色粉"
        st.session_state["spec"] = "kg"
        st.session_state.mode = "view"

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

# ---------- 新增 / 修改 區塊 ----------
st.markdown("### ➕ 新增 / 修改色粉")

c1, c2 = st.columns(2)

with c1:
    st.session_state.code = st.text_input("色粉編號", value=st.session_state.code)
    st.session_state.name = st.text_input("色粉名稱", value=st.session_state.name)
    st.session_state.pantone = st.text_input("國際色號", value=st.session_state.pantone)
    st.session_state.origin = st.text_input("產地", value=st.session_state.origin)

with c2:
    st.session_state.color_type = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(st.session_state.color_type)
        if st.session_state.color_type else 0,
    )
    st.session_state.spec = st.selectbox(
        "規格",
        ["kg", "箱", "袋"],
        index=["kg", "箱", "袋"].index(st.session_state.spec)
        if st.session_state.spec else 0,
    )
    st.session_state.remark = st.text_input("備註", value=st.session_state.remark)

    if st.session_state.mode == "edit":
        if st.button("💾 確認修改"):
            idx = st.session_state.edit_index
            code = str(st.session_state.code).strip()
            if (code in df["色粉編號"].astype(str).values
                and code != str(df.iloc[idx]["色粉編號"])):
                st.error(f"❌ 色粉編號【{code}】已存在，請勿重複！")
            else:
                df.at[idx, "色粉編號"] = code
                df.at[idx, "色粉名稱"] = st.session_state.name
                df.at[idx, "國際色號"] = st.session_state.pantone
                df.at[idx, "色粉類別"] = st.session_state.color_type
                df.at[idx, "規格"] = st.session_state.spec
                df.at[idx, "產地"] = st.session_state.origin
                df.at[idx, "備註"] = st.session_state.remark
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"✅ 已修改色粉【{code}】")
                st.session_state.mode = "view"
                st.session_state.edit_index = None
                st.experimental_rerun()
    else:
        if st.button("➕ 新增色粉"):
            code = str(st.session_state.code).strip()
            if code in df["色粉編號"].astype(str).values:
                st.error(f"❌ 色粉編號【{code}】已存在，請勿重複新增！")
            else:
                new_row = pd.DataFrame([{
                    "色粉編號": code,
                    "色粉名稱": st.session_state.name,
                    "國際色號": st.session_state.pantone,
                    "色粉類別": st.session_state.color_type,
                    "規格": st.session_state.spec,
                    "產地": st.session_state.origin,
                    "備註": st.session_state.remark
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                worksheet.clear()
                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"✅ 已新增色粉【{code}】")
                st.session_state.mode = "view"
                st.experimental_rerun()

# ---------- 顯示序列 ----------
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
                justify-content: space-between;
                margin-bottom:4px;
                text-align: left;
                overflow-x:auto;
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
                <span style="display:flex;gap:8px;">
                    <button onclick="window.location.search='?edit={idx}'"
                        style="
                            background-color: #FFA500;
                            color: white;
                            border: none;
                            padding: 4px 8px;
                            border-radius: 3px;
                            font-size: 12px;
                            cursor: pointer;">
                        修改
                    </button>
                    <button onclick="window.location.search='?delete={idx}'"
                        style="
                            background-color: #007BFF;
                            color: white;
                            border: none;
                            padding: 4px 8px;
                            border-radius: 3px;
                            font-size: 12px;
                            cursor: pointer;">
                        刪除
                    </button>
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

    params = st.query_params
    if "edit" in params:
        idx = int(params["edit"][0])
        st.session_state.mode = "edit"
        st.session_state.edit_index = idx
        row = df.iloc[idx]
        for key in ["code", "name", "pantone", "origin", "remark"]:
            st.session_state[key] = row.get(key, "")
        st.session_state.color_type = row.get("色粉類別", "色粉")
        st.session_state.spec = row.get("規格", "kg")
        st.experimental_rerun()

    if "delete" in params:
        idx = int(params["delete"][0])
        code = df.iloc[idx]["色粉編號"]
        df = df.drop(idx).reset_index(drop=True)
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success(f"✅ 已刪除色粉【{code}】")
        st.experimental_rerun()

else:
    st.info("目前無資料可顯示。")
