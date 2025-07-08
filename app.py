import streamlit as st
import pandas as pd
import json
from google.oauth2 import service_account
import gspread

# 讀取 secrets
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(service_account_info)
client = gspread.authorize(creds)

# Google Sheet 設定
SHEET_NAME = '色粉管理'
WORKSHEET_NAME = '工作表1'

sheet = client.open("色粉管理")
worksheet = sheet.worksheet("工作表1")

# 載入資料
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Session State 初始化
if "editing_row" not in st.session_state:
    st.session_state.editing_row = None

if "search_text" not in st.session_state:
    st.session_state.search_text = ""

# UI
st.title("🎨 色粉管理系統")

# 模組切換
module = st.radio("請選擇模組", ["色粉總表", "新增/修改色粉"])

# 功能：色粉總表
if module == "色粉總表":

    # 搜尋輸入
    search_text = st.text_input("輸入關鍵字搜尋色粉", st.session_state.search_text, key="search_input")
    st.session_state.search_text = search_text

    # 搜尋結果
    if search_text:
        df_filtered = df[df.apply(lambda row: search_text.lower() in str(row).lower(), axis=1)]
    else:
        df_filtered = df.copy()

    # 顯示總表
    for idx, row in df_filtered.iterrows():
        cols = st.columns([6, 1, 1])

        with cols[0]:
            st.markdown(
                f"<b>色粉編號</b>: {row['色粉編號']} ｜ "
                f"<b>名稱</b>: {row['名稱']} ｜ "
                f"<b>類別</b>: {row['類別']} ｜ "
                f"<b>國際色號</b>: {row['國際色號']} ｜ "
                f"<b>備註</b>: {row['備註']}",
                unsafe_allow_html=True
            )

        with cols[1]:
            if st.button("✏️ 修改", key=f"edit_{idx}"):
                st.session_state.editing_row = idx
                st.experimental_rerun()

        with cols[2]:
            if st.button("🗑️ 刪除", key=f"delete_{idx}"):
                confirm = st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？")
                if confirm:
                    df.drop(idx, inplace=True)
                    worksheet.update([df.columns.tolist()] + df.values.tolist())
                    st.success(f"✅ 已刪除【{row['色粉編號']}】")
                    st.experimental_rerun()

# 功能：新增/修改
elif module == "新增/修改色粉":

    # 準備表單
    if st.session_state.editing_row is not None:
        row_data = df.loc[st.session_state.editing_row]
        color_id = st.text_input("色粉編號", row_data["色粉編號"])
        name = st.text_input("名稱", row_data["名稱"])
        category = st.text_input("類別", row_data["類別"])
        international_code = st.text_input("國際色號", row_data["國際色號"])
        note = st.text_input("備註", row_data["備註"])
    else:
        color_id = st.text_input("色粉編號")
        name = st.text_input("名稱")
        category = st.text_input("類別")
        international_code = st.text_input("國際色號")
        note = st.text_input("備註")

    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("✅ 儲存"):
            # 檢查重複
            if st.session_state.editing_row is None:
                if color_id in df["色粉編號"].values:
                    st.warning(f"⚠️ 色粉編號【{color_id}】已存在！請改其他編號。")
                else:
                    new_row = {
                        "色粉編號": color_id,
                        "名稱": name,
                        "類別": category,
                        "國際色號": international_code,
                        "備註": note
                    }
                    df = df.append(new_row, ignore_index=True)
                    worksheet.update([df.columns.tolist()] + df.values.tolist())
                    st.success(f"✅ 新增成功！色粉編號：{color_id}")
                    st.experimental_rerun()
            else:
                # 修改
                df.at[st.session_state.editing_row, "色粉編號"] = color_id
                df.at[st.session_state.editing_row, "名稱"] = name
                df.at[st.session_state.editing_row, "類別"] = category
                df.at[st.session_state.editing_row, "國際色號"] = international_code
                df.at[st.session_state.editing_row, "備註"] = note
                worksheet.update([df.columns.tolist()] + df.values.tolist())
                st.success(f"✅ 修改成功！色粉編號：{color_id}")
                st.session_state.editing_row = None
                st.experimental_rerun()

    with cols[1]:
        if st.button("🧹 清除輸入"):
            st.session_state.editing_row = None
            st.experimental_rerun()
