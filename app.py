import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide")

# ============== GCP 認證 ===================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
gcp_info = json.loads(st.secrets["gcp"]["gcp_json"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    gcp_info, scopes=scope
)
gc = gspread.authorize(credentials)

# ============== Google Sheets 讀取 ==========
sheet_key = "1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk"
sh = gc.open_by_key(sheet_key)
worksheet = sh.worksheet("工作表1")
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 如果表格為空，先建立欄位
if df.empty:
    df = pd.DataFrame(columns=[
        "色粉編號", "色粉名稱", "國際色號",
        "色粉類別", "規格", "產地", "備註"
    ])

# ============== 搜尋欄位 =======================
st.subheader("🔍 搜尋色粉")
search_code = st.text_input("輸入色粉編號搜尋")

if search_code:
    df_filtered = df[df["色粉編號"].str.contains(search_code, case=False, na=False)]
else:
    df_filtered = df

# ============== 新增色粉 =======================
st.divider()
st.subheader("➕ 新增色粉")

# 四欄 layout
col1, col2, col3, col4 = st.columns(4)
with col1:
    new_code = st.text_input("色粉編號", key="add_code")
with col2:
    new_name = st.text_input("色粉名稱", key="add_name")
with col3:
    new_int_color = st.text_input("國際色號", key="add_int_color")
with col4:
    new_color_type = st.selectbox(
        "色粉類別", ["色粉", "色母", "添加劑"], key="add_color_type"
    )

col5, col6, col7, col8 = st.columns(4)
with col5:
    new_spec = st.selectbox("規格", ["kg", "箱", "袋"], key="add_spec")
with col6:
    new_origin = st.text_input("產地", key="add_origin")
with col7:
    new_remark = st.text_input("備註", key="add_remark")
with col8:
    st.write("")
    if st.button("✅ 新增色粉", use_container_width=True, key="add_button"):
        if new_code in df["色粉編號"].values:
            st.error(f"⚠️ 色粉編號【{new_code}】已存在，請勿重複新增！")
        else:
            # 新增到 DataFrame
            new_row = {
                "色粉編號": new_code,
                "色粉名稱": new_name,
                "國際色號": new_int_color,
                "色粉類別": new_color_type,
                "規格": new_spec,
                "產地": new_origin,
                "備註": new_remark,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            worksheet.append_row(list(new_row.values()))
            st.success(f"✅ 已新增色粉：{new_code} - {new_name}")

# ============== 批次編輯 data_editor ===========
st.divider()
st.subheader("📝 批次編輯色粉資料")

# 用 data_editor 顯示
edited_df = st.data_editor(
    df_filtered,
    use_container_width=True,
    num_rows="dynamic",
    key="data_editor"
)

if st.button("💾 儲存修改", use_container_width=True, key="save_button"):
    confirm = st.confirm("⚠️ 是否確認儲存所有修改？")
    if confirm:
        # 這邊假設只 demo，你可以改成上傳到 Google Sheet
        df.update(edited_df)
        # 也可寫回 Google Sheet
        worksheet.clear()
        worksheet.append_row(df.columns.tolist())
        worksheet.append_rows(df.values.tolist())
        st.success("✅ 所有修改已儲存！")

# ============== 列出所有色粉序列 ===============
st.divider()
st.subheader("📋 色粉總表")

# 設定交錯顏色
def style_row(row):
    idx = row.name
    color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"
    return ["background-color: {}".format(color)] * len(row)

# 顯示 DataFrame
st.dataframe(
    df.style.apply(style_row, axis=1)
             .set_properties(**{
                 'text-align': 'center',
                 'font-size': '14px'
             }),
    use_container_width=True,
)

# 單筆修改、刪除按鈕（demo 範例）
for i, row in df.iterrows():
    cols = st.columns([8, 1, 1])
    with cols[0]:
        st.write(
            f"➡️ {row['色粉編號']} ｜ {row['色粉名稱']} ｜ {row['國際色號']}"
        )
    with cols[1]:
        if st.button("✏️ 修改", key=f"edit_{i}"):
            st.info(f"進入【{row['色粉編號']}】修改頁面 (示範)")

    with cols[2]:
        if st.button("🗑️ 刪除", key=f"delete_{i}"):
            confirm = st.confirm(f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？")
            if confirm:
                df = df.drop(i).reset_index(drop=True)
                worksheet.clear()
                worksheet.append_row(df.columns.tolist())
                worksheet.append_rows(df.values.tolist())
                st.success(f"✅ 已刪除色粉編號：{row['色粉編號']}")
                st.experimental_rerun()
