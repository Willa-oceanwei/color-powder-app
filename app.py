import streamlit as st
import pandas as pd
import os
import json
from google.oauth2.service_account import Credentials
import gspread

# ======= GOOGLE SHEETS 連線設定 =======

# 權限範圍
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# 從環境變數讀取 service_account JSON
service_account_info = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])

# 建立憑證
creds = Credentials.from_service_account_info(
    service_account_info, scopes=scope
)

# gspread 授權
client = gspread.authorize(creds)

# 開啟試算表 & 工作表
spreadsheet = client.open("色粉管理")
worksheet = spreadsheet.worksheet("工作表1")

# ======= 讀取 Google Sheet 資料為 DataFrame =======

# 讀取所有資料
data = worksheet.get_all_records()

# 轉換成 DataFrame
df = pd.DataFrame(data)

# ======= Streamlit UI 開始 =======

st.set_page_config(page_title="色粉管理", layout="wide")

st.title("🎨 色粉管理系統")

# ==== 清除輸入區塊 ====
if st.button("清除輸入", help="清除所有輸入欄位", type="secondary"):
    st.session_state.clear()
    st.experimental_rerun()

# ==== 搜尋色粉 ====
# 保留搜尋欄位，但移除搜尋按鈕
search_query = st.text_input("🔎 搜尋色粉編號或名稱", value=st.session_state.get("search_query", ""))

# 若按 Enter 執行搜尋
if search_query:
    df_filtered = df[
        df["色粉編號"].astype(str).str.contains(search_query, case=False, na=False) |
        df["名稱"].str.contains(search_query, case=False, na=False)
    ]
    st.write("搜尋結果：", len(df_filtered))
else:
    df_filtered = df

# ==== 新增或修改色粉 ====

# 分兩欄排版
col1, col2 = st.columns(2)

with col1:
    code = st.text_input("色粉編號", value=st.session_state.get("code", ""))
    name = st.text_input("名稱", value=st.session_state.get("name", ""))
    color_number = st.text_input("國際色號", value=st.session_state.get("color_number", ""))
    color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"], index=0)
with col2:
    spec = st.selectbox("規格", ["kg", "箱", "袋"], index=0)
    origin = st.text_input("產地", value=st.session_state.get("origin", ""))
    remark = st.text_input("備註", value=st.session_state.get("remark", ""))

if st.button("新增/修改色粉", type="primary"):
    # 檢查是否有重複編號
    if not code:
        st.warning("請輸入色粉編號！")
    elif (df["色粉編號"].astype(str) == str(code)).any():
        st.warning(f"編號 {code} 已存在，不可重複新增。若需修改，請使用修改功能。")
    else:
        # 新增新資料
        new_row = {
            "色粉編號": code,
            "名稱": name,
            "國際色號": color_number,
            "色粉類別": color_type,
            "規格": spec,
            "產地": origin,
            "備註": remark
        }
        df = df.append(new_row, ignore_index=True)
        # 寫回 Google Sheet
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success(f"已新增色粉【{code}】")
        st.experimental_rerun()

# ====== 顯示色粉總表 ======

st.subheader("📋 色粉總表")

for idx, row in df_filtered.iterrows():
    st.markdown(
        f"""
        <div style='display:flex; justify-content:space-between; align-items:center; border:1px solid #eee; padding:6px; margin-bottom:4px; background-color: {"#FDFCDC" if idx%2==0 else "#FED9B7"}'>
            <span>
                <b>編號</b>：{row['色粉編號']} &nbsp;｜&nbsp;
                <b>名稱</b>：{row['名稱']} &nbsp;｜&nbsp;
                <b>國際色號</b>：{row['國際色號']} &nbsp;｜&nbsp;
                <b>類別</b>：{row['色粉類別']} &nbsp;｜&nbsp;
                <b>規格</b>：{row['規格']} &nbsp;｜&nbsp;
                <b>產地</b>：{row['產地']} &nbsp;｜&nbsp;
                <b>備註</b>：{row['備註']}
            </span>
            <span style='display:flex; gap:10px;'>
                <form action="" method="get">
                    <button name="edit" value="{idx}" type="submit" style="
                        background-color: #FFA500;
                        color: white;
                        border: none;
                        padding: 4px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                        cursor: pointer;
                    ">修改</button>
                </form>
                <form action="" method="get">
                    <button name="delete" value="{idx}" type="submit" style="
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
        unsafe_allow_html=True,
    )

# ===== 處理修改 =====
query_params = st.experimental_get_query_params()
if "edit" in query_params:
    edit_idx = int(query_params["edit"][0])
    row = df.iloc[edit_idx]
    st.session_state["code"] = row["色粉編號"]
    st.session_state["name"] = row["名稱"]
    st.session_state["color_number"] = row["國際色號"]
    st.session_state["color_type"] = row["色粉類別"]
    st.session_state["spec"] = row["規格"]
    st.session_state["origin"] = row["產地"]
    st.session_state["remark"] = row["備註"]
    st.experimental_rerun()

# ===== 處理刪除 =====
if "delete" in query_params:
    delete_idx = int(query_params["delete"][0])
    row = df.iloc[delete_idx]
    if st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？"):
        df = df.drop(delete_idx).reset_index(drop=True)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success(f"已刪除色粉【{row['色粉編號']}】")
        st.experimental_rerun()
