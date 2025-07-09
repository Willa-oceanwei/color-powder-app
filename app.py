import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2 import service_account

# ---------- 認證 ----------
# 透過 secrets 取得 service account json
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(credentials)

# ---------- Google Sheet ----------
SHEET_NAME = "色粉管理"
WORKSHEET_NAME = "工作表1"

sheet = client.open(SHEET_NAME)
worksheet = sheet.worksheet(WORKSHEET_NAME)

# 讀取整個 Sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ---------- UI ----------
st.title("🎨 色粉管理系統")

# ---------- 模組切換 ----------
tabs = st.tabs(["色粉總表", "新增 / 修改色粉"])

# ---------------------------------------------------------------
# ====================== 色粉總表 ================================
# ---------------------------------------------------------------
with tabs[0]:
    st.subheader("色粉總表")

    # 顯示 DataFrame + 按鈕
    if not df.empty:
        for i, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 2])
            with col1:
                st.write(str(i + 1))
            with col2:
                st.write(row["色粉編號"])
            with col3:
                st.write(row["名稱"])
            with col4:
                st.write(row["國際色號"])
            with col5:
                edit_link = f"?edit={row['色粉編號']}"
                st.markdown(
                    f'<a href="{edit_link}" style="color:white; background-color:#FFA500; padding:4px 8px; border-radius:3px; text-decoration:none;">修改</a>',
                    unsafe_allow_html=True,
                )
            with col6:
                delete_link = f"?delete={row['色粉編號']}"
                st.markdown(
                    f'<a href="{delete_link}" style="color:white; background-color:#007BFF; padding:4px 8px; border-radius:3px; text-decoration:none;">刪除</a>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("尚無任何色粉資料。")

# ---------------------------------------------------------------
# ==================== 新增 / 修改色粉 ==========================
# ---------------------------------------------------------------
with tabs[1]:
    st.subheader("新增 / 修改色粉")

    # 判斷是否在修改狀態
    query_params = st.experimental_get_query_params()
    edit_mode = False
    edit_data = None

    if "edit" in query_params:
        edit_id = query_params["edit"][0]
        if edit_id in df["色粉編號"].values:
            edit_mode = True
            edit_data = df[df["色粉編號"] == edit_id].iloc[0]

    # 建立輸入欄位
    color_id = st.text_input("色粉編號", value=edit_data["色粉編號"] if edit_mode else "")
    color_name = st.text_input("名稱", value=edit_data["名稱"] if edit_mode else "")
    color_code = st.text_input("國際色號", value=edit_data["國際色號"] if edit_mode else "")

    col_save, col_clear = st.columns([1, 1])
    with col_save:
        if st.button("💾 儲存 / 新增", key="save_btn"):
            # 判斷是否為修改
            if edit_mode:
                # 修改現有資料
                df.loc[df["色粉編號"] == edit_id, ["色粉編號", "名稱", "國際色號"]] = [
                    color_id,
                    color_name,
                    color_code,
                ]
                worksheet.update(
                    [df.columns.values.tolist()] + df.values.tolist()
                )
                st.success(f"已修改色粉【{color_id}】。")
                st.experimental_set_query_params()  # 清空 URL
                st.experimental_rerun()

            else:
                # 檢查重複編號
                if color_id in df["色粉編號"].values:
                    st.warning(f"色粉編號【{color_id}】已存在，請勿重複新增！")
                else:
                    new_row = {
                        "色粉編號": color_id,
                        "名稱": color_name,
                        "國際色號": color_code,
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    worksheet.update(
                        [df.columns.values.tolist()] + df.values.tolist()
                    )
                    st.success(f"已新增色粉【{color_id}】。")
                    st.experimental_rerun()

    with col_clear:
        if st.button("🧹 清除輸入", key="clear_btn"):
            st.experimental_set_query_params()  # 清掉 URL query
            st.experimental_rerun()

# ---------------------------------------------------------------
# ========================== 刪除 ================================
# ---------------------------------------------------------------
# 處理刪除流程
query_params = st.experimental_get_query_params()
if "delete" in query_params:
    del_id = query_params["delete"][0]

    if del_id in df["色粉編號"].values:
        confirm = st.warning(
            f"⚠️ 確定要刪除色粉【{del_id}】嗎？", icon="⚠️"
        )
        confirm_btn = st.button("✅ 確定刪除")
        cancel_btn = st.button("❌ 取消")

        if confirm_btn:
            df = df[df["色粉編號"] != del_id]
            worksheet.update(
                [df.columns.values.tolist()] + df.values.tolist()
            )
            st.success(f"已刪除色粉【{del_id}】。")
            st.experimental_set_query_params()  # 清空 URL
            st.experimental_rerun()

        if cancel_btn:
            st.experimental_set_query_params()  # 清空 URL
            st.experimental_rerun()
    else:
        st.warning(f"找不到色粉編號【{del_id}】。")
        st.experimental_set_query_params()
        st.experimental_rerun()
