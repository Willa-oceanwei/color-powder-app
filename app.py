import streamlit as st
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ---------- 基本設定 ----------
st.set_page_config(layout="wide")

# ---------- 連線 Google Sheets ----------
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

# ---------- 讀取現有資料 ----------
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 如果是空表，先補上表頭
if df.empty:
    df = pd.DataFrame(columns=[
        "色粉編號", "國際色號", "色粉名稱",
        "色粉類別", "規格", "產地", "備註"
    ])

# ---------- 新增或修改邏輯 ----------
# 記錄是否在修改模式
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

st.title("色粉管理系統")

# ---------- 新增 / 修改表單 ----------
st.subheader("➕ 新增或修改色粉資料")

# 雙欄排版
col1, col2 = st.columns(2)

with col1:
    powder_id = st.text_input("色粉編號", key="powder_id")
    color_code = st.text_input("國際色號", key="color_code")
    powder_name = st.text_input("色粉名稱", key="powder_name")
    color_type = st.selectbox("色粉類別", ["色粉", "色母", "添加劑", "配方", "其他"], key="color_type")

with col2:
    spec = st.selectbox("規格", ["kg", "箱", "袋", "桶", "其他"], key="spec")
    origin = st.text_input("產地", key="origin")
    remark = st.text_input("備註", key="remark")

# ---------- 儲存按鈕 ----------
if st.session_state.edit_mode:
    save_label = "✅ 確定修改"
else:
    save_label = "✅ 新增色粉"

if st.button(save_label, key="save_button"):
    # 建立字典
    new_data = {
        "色粉編號": powder_id,
        "國際色號": color_code,
        "色粉名稱": powder_name,
        "色粉類別": color_type,
        "規格": spec,
        "產地": origin,
        "備註": remark
    }
    # 檢查必填
    if powder_id == "":
        st.warning("請輸入色粉編號。")
    else:
        if st.session_state.edit_mode:
            # 修改模式
            duplicate = df[(df["色粉編號"] == powder_id) & (df.index != st.session_state.editing_index)]
            if not duplicate.empty:
                st.warning("此色粉編號已存在，請重新輸入。")
            else:
                df.loc[st.session_state.editing_index] = new_data
                worksheet.update(
                    f"A{st.session_state.editing_index + 2}",
                    [list(new_data.values())]
                )
                st.success("已成功修改資料！")
                st.session_state.edit_mode = False
                st.experimental_rerun()
        else:
            # 新增模式
            if powder_id in df["色粉編號"].values:
                st.warning("此色粉編號已存在，請重新輸入。")
            else:
                worksheet.append_row(list(new_data.values()))
                st.success("新增成功！")
                st.experimental_rerun()

# ---------- 顯示色粉總表 ----------
st.subheader("📄 色粉總表")

# 產生交錯色背景
def style_row(idx):
    color = "#FED9B7" if idx % 2 == 0 else "#FDFCDC"
    return [f"background-color: {color}; text-align: center;" for _ in range(len(df.columns))]

if not df.empty:
    # 加上按鈕欄位
    df_display = df.copy()
    df_display["操作"] = ""

    for i in df_display.index:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✏️ 修改", key=f"edit_{i}"):
                # 將資料帶到輸入區
                st.session_state.edit_mode = True
                st.session_state.editing_index = i
                row = df.loc[i]
                st.session_state.powder_id = row["色粉編號"]
                st.session_state.color_code = row["國際色號"]
                st.session_state.powder_name = row["色粉名稱"]
                st.session_state.color_type = row["色粉類別"]
                st.session_state.spec = row["規格"]
                st.session_state.origin = row["產地"]
                st.session_state.remark = row["備註"]
                st.experimental_rerun()
        with col2:
            if st.button("🗑 刪除", key=f"delete_{i}"):
                confirm = st.confirm(f"確定要刪除色粉編號 {df.loc[i, '色粉編號']} 嗎？")
                if confirm:
                    worksheet.delete_rows(i + 2)
                    st.success("刪除成功！")
                    st.experimental_rerun()

    # 顯示表格
    st.dataframe(
        df.style.apply(style_row, axis=1).set_properties(**{
            'text-align': 'center',
            'font-size': '14px'
        }),
        use_container_width=True
    )
else:
    st.info("目前無色粉資料。")
