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

# ============== 建立狀態 =======================
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# ============== 新增 / 修改色粉 ================
st.divider()
st.subheader("➕ 新增 / 修改色粉")

col1, col2, col3, col4 = st.columns(4)
with col1:
    code = st.text_input("色粉編號", key="code")
with col2:
    name = st.text_input("色粉名稱", key="name")
with col3:
    int_color = st.text_input("國際色號", key="int_color")
with col4:
    color_type = st.selectbox(
        "色粉類別", ["色粉", "色母", "添加劑"], key="color_type"
    )

col5, col6, col7, col8 = st.columns(4)
with col5:
    spec = st.selectbox("規格", ["kg", "箱", "袋"], key="spec")
with col6:
    origin = st.text_input("產地", key="origin")
with col7:
    remark = st.text_input("備註", key="remark")
with col8:
    st.write("")
    # 新增或更新按鈕
    if st.session_state.edit_mode:
        if st.button("💾 更新色粉", use_container_width=True, key="update_btn"):
            # 檢查重複編號 (但允許自己)
            if (
                code in df["色粉編號"].values
                and df.iloc[st.session_state.edit_index]["色粉編號"] != code
            ):
                st.error(f"⚠️ 色粉編號【{code}】已存在，請勿重複！")
            else:
                df.at[st.session_state.edit_index, "色粉編號"] = code
                df.at[st.session_state.edit_index, "色粉名稱"] = name
                df.at[st.session_state.edit_index, "國際色號"] = int_color
                df.at[st.session_state.edit_index, "色粉類別"] = color_type
                df.at[st.session_state.edit_index, "規格"] = spec
                df.at[st.session_state.edit_index, "產地"] = origin
                df.at[st.session_state.edit_index, "備註"] = remark

                worksheet.clear()
                worksheet.append_row(df.columns.tolist())
                worksheet.append_rows(df.values.tolist())

                st.success(f"✅ 已更新色粉：{code}")
                st.session_state.edit_mode = False
                st.experimental_rerun()
    else:
        if st.button("✅ 新增色粉", use_container_width=True, key="add_btn"):
            if code in df["色粉編號"].values:
                st.error(f"⚠️ 色粉編號【{code}】已存在，請勿重複新增！")
            else:
                new_row = {
                    "色粉編號": code,
                    "色粉名稱": name,
                    "國際色號": int_color,
                    "色粉類別": color_type,
                    "規格": spec,
                    "產地": origin,
                    "備註": remark,
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                worksheet.append_row(list(new_row.values()))
                st.success(f"✅ 已新增色粉：{code}")
                st.experimental_rerun()

# ============== 列出所有色粉序列 ===============
st.divider()
st.subheader("📋 色粉總表")

def style_row(row):
    idx = row.name
    color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"
    return ["background-color: {}".format(color)] * len(row)

# 顯示 DataFrame (縮表格寬度)
st.dataframe(
    df.style.apply(style_row, axis=1)
             .set_properties(**{
                 'text-align': 'center',
                 'font-size': '13px'
             }),
    use_container_width=True,
)

# 序列一筆一列，按鈕放右邊
for i, row in df.iterrows():
    cols = st.columns([8, 1, 1])
    with cols[0]:
        st.write(
            f"➡️ {row['色粉編號']} ｜ {row['色粉名稱']} ｜ {row['國際色號']}"
        )
    with cols[1]:
        if st.button("✏️ 修改", key=f"edit_{i}"):
            st.session_state.edit_mode = True
            st.session_state.edit_index = i

            # 帶入該筆資料
            st.session_state.code = row["色粉編號"]
            st.session_state.name = row["色粉名稱"]
            st.session_state.int_color = row["國際色號"]
            st.session_state.color_type = row["色粉類別"]
            st.session_state.spec = row["規格"]
            st.session_state.origin = row["產地"]
            st.session_state.remark = row["備註"]
            st.experimental_rerun()

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
