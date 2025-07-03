import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Color Powder Management")

st.title("🌈 Color Powder Management")

# 連線 GCP
if "gcp_credentials" not in st.secrets:
    st.warning("❗ 尚未設定 gcp_credentials Secrets。請到 Settings → Secrets 設定")
    st.stop()

gcp_info = st.secrets["gcp_credentials"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scope
)
gc = gspread.authorize(credentials)

# UI - 輸入試算表 Key
spreadsheet_key = st.text_input("請輸入 Google Sheets Key")

if spreadsheet_key:
    try:
        sh = gc.open_by_key(spreadsheet_key)
        worksheet = sh.worksheet("ColorPowder")

        # --- 搜尋 ---
        st.subheader("🔍 搜尋色粉")

        search_code = st.text_input("請輸入色粉編號")

        if st.button("搜尋"):
            data = worksheet.get_all_values()
            headers = data[0]
            rows = data[1:]

            matched_rows = [row for row in rows if row[0] == search_code]

            if matched_rows:
                st.success("找到以下結果：")
                st.write(dict(zip(headers, matched_rows[0])))
            else:
                st.warning("查無此編號。")

        st.markdown("---")

        # --- 新增 ---
        st.subheader("➕ 新增色粉資料")

        col1, col2 = st.columns(2)

        with col1:
            code = st.text_input("色粉編號 (必填)", key="new_code")
            name = st.text_input("名稱", key="new_name")
            pantone = st.text_input("國際編號", key="new_pantone")

        with col2:
            unit = st.selectbox("進量單位", ["kg", "袋", "桶", "箱", "其他"], key="new_unit")
            category = st.selectbox("色粉類別", ["色粉", "配方", "色母", "添加劑", "其他"], key="new_category")
            note = st.text_input("備註", key="new_note")

        if st.button("新增色粉"):
            if not code:
                st.error("請輸入色粉編號！")
            else:
                data = worksheet.get_all_values()
                existing_codes = [row[0] for row in data[1:]]

                if code in existing_codes:
                    st.warning("已有相同編號，無法新增！")
                else:
                    new_row = [code, name, pantone, unit, category, note]
                    worksheet.append_row(new_row)
                    st.success(f"已新增色粉編號：{code}")

        st.markdown("---")

        # --- 刪除 ---
        st.subheader("🗑 刪除色粉資料")

        del_code = st.text_input("請輸入欲刪除的色粉編號", key="del_code")

        if st.button("刪除色粉"):
            data = worksheet.get_all_values()
            headers = data[0]
            rows = data[1:]

            found = False
            for idx, row in enumerate(rows, start=2):
                if row[0] == del_code:
                    worksheet.delete_rows(idx)
                    st.success(f"已刪除色粉編號：{del_code}")
                    found = True
                    break

            if not found:
                st.warning("查無此編號，無法刪除。")

    except Exception as e:
        st.error(f"讀取失敗：{e}")
