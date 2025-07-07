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
    if df_filtered.empty:
        st.warning("⚠️ 查無此色粉編號！")
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

# 如果在編輯，就預填入欄位
if st.session_state.edit_mode and st.session_state.edit_index is not None:
    current_row = df.iloc[st.session_state.edit_index]
    code_value = current_row["色粉編號"]
    name_value = current_row["色粉名稱"]
    int_color_value = current_row["國際色號"]
    color_type_value = current_row["色粉類別"]
    spec_value = current_row["規格"]
    origin_value = current_row["產地"]
    remark_value = current_row["備註"]
else:
    code_value = ""
    name_value = ""
    int_color_value = ""
    color_type_value = "色粉"
    spec_value = "kg"
    origin_value = ""
    remark_value = ""

col1, col2, col3, col4 = st.columns(4)
with col1:
    code = st.text_input("色粉編號", value=code_value, key="code_input")
with col2:
    name = st.text_input("色粉名稱", value=name_value, key="name_input")
with col3:
    int_color = st.text_input("國際色號", value=int_color_value, key="int_color_input")
with col4:
    color_type = st.selectbox(
        "色粉類別", ["色粉", "色母", "添加劑"],
        index=["色粉", "色母", "添加劑"].index(color_type_value) if color_type_value else 0,
        key="color_type_input"
    )

col5, col6, col7, col8 = st.columns(4)
with col5:
    spec = st.selectbox("規格", ["kg", "箱", "袋"],
                        index=["kg", "箱", "袋"].index(spec_value) if spec_value else 0,
                        key="spec_input")
with col6:
    origin = st.text_input("產地", value=origin_value, key="origin_input")
with col7:
    remark = st.text_input("備註", value=remark_value, key="remark_input")
with col8:
    st.write("")
    if st.session_state.edit_mode:
        if st.button("💾 更新色粉", use_container_width=True, key="update_btn"):
            # 檢查重複編號 (允許自己)
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

# ============== 顯示搜尋結果 or 全部資料 =====================
st.divider()
st.subheader("📋 色粉總表")

show_df = df_filtered

if not show_df.empty:
    def style_row(row):
        idx = row.name
        color = "#FDFCDC" if idx % 2 == 0 else "#FED9B7"
        return ["background-color: {}".format(color)] * len(row)

    st.dataframe(
        show_df.style.apply(style_row, axis=1)
                     .set_properties(**{
                         'text-align': 'center',
                         'font-size': '13px'
                     }),
        use_container_width=True,
    )

    for i, row in show_df.iterrows():
        cols = st.columns([8, 1, 1])
        with cols[0]:
            st.write(
                f"➡️ {row['色粉編號']} ｜ {row['色粉名稱']} ｜ {row['國際色號']}"
            )
        with cols[1]:
            if st.button("✏️ 修改", key=f"edit_{i}"):
                st.session_state.edit_mode = True
                st.session_state.edit_index = i
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
else:
    st.info("尚無資料可顯示。")
