import json
import streamlit as st
from google.oauth2 import service_account

service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(service_account_info)
client = gspread.authorize(creds)
spreadsheet = client.open("色粉管理")
worksheet = spreadsheet.worksheet("工作表1")

# ====== 連線 Google Sheet ======
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

# 請放你的 Google Sheet 名稱
sheet = client.open("色粉管理")
worksheet = sheet.worksheet("工作表1")

# 讀取現有資料
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 如果 Google Sheet 是空的，就建立空的 DataFrame
if df.empty:
    df = pd.DataFrame(columns=[
        "色粉編號", "名稱", "國際色號", "色粉類別",
        "規格", "產地", "備註"
    ])

# ====== 初始化 Session State ======

fields = [
    "code_input", "name_input", "pantone_input",
    "color_type_select", "spec_select",
    "origin_input", "remark_input", "search_value"
]

for f in fields:
    if f not in st.session_state:
        st.session_state[f] = ""

# ====== 頁面佈局 ======

# 頁面標題
st.set_page_config(layout="wide")

# 模組選擇
module = st.sidebar.selectbox(
    "請選擇模組",
    ["色粉管理", "配方管理"]
)

if module == "配方管理":
    st.title("配方管理 (尚未開發)")
    st.stop()

st.title("色粉管理系統")

# ====== 功能區 ======

# 搜尋區
search_col1, search_col2 = st.columns([6,1])

with search_col1:
    st.session_state["search_value"] = st.text_input(
        "🔍 搜尋色粉編號或名稱（輸入後按 Enter 即可）",
        st.session_state["search_value"]
    )

with search_col2:
    if st.button("🧹 清除輸入", key="clear", help="清除所有輸入欄位"):
        for f in fields:
            st.session_state[f] = ""
        st.success("✅ 已清除所有輸入欄位！")
        st.experimental_rerun()

# ====== 新增 / 修改 區域 ======

# 輸入欄位 (兩欄排版)
col1, col2 = st.columns(2)

with col1:
    st.session_state["code_input"] = st.text_input(
        "色粉編號",
        st.session_state["code_input"]
    )
    st.session_state["pantone_input"] = st.text_input(
        "國際色號",
        st.session_state["pantone_input"]
    )
    st.session_state["color_type_select"] = st.selectbox(
        "色粉類別",
        ["色粉", "色母", "添加劑"],
        index=0 if st.session_state["color_type_select"] == "" else
               ["色粉", "色母", "添加劑"].index(st.session_state["color_type_select"])
    )
    st.session_state["origin_input"] = st.text_input(
        "產地",
        st.session_state["origin_input"]
    )

with col2:
    st.session_state["name_input"] = st.text_input(
        "名稱",
        st.session_state["name_input"]
    )
    st.session_state["spec_select"] = st.selectbox(
        "規格",
        ["kg", "箱", "袋"],
        index=0 if st.session_state["spec_select"] == "" else
               ["kg", "箱", "袋"].index(st.session_state["spec_select"])
    )
    st.session_state["remark_input"] = st.text_input(
        "備註",
        st.session_state["remark_input"]
    )
    # 新增 / 修改按鈕放在此右側空位
    if st.button("💾 新增 / 修改色粉", key="save", help="新增或修改色粉紀錄",
                 type="primary"):
        code = st.session_state["code_input"].strip()

        if code == "":
            st.warning("請輸入色粉編號！")
        else:
            # 檢查是否存在
            exists = code in df["色粉編號"].astype(str).values

            if exists:
                # 修改
                df.loc[
                    df["色粉編號"].astype(str) == code,
                    ["名稱", "國際色號", "色粉類別", "規格", "產地", "備註"]
                ] = [
                    st.session_state["name_input"],
                    st.session_state["pantone_input"],
                    st.session_state["color_type_select"],
                    st.session_state["spec_select"],
                    st.session_state["origin_input"],
                    st.session_state["remark_input"]
                ]
                st.success(f"✅ 已更新色粉【{code}】！")
            else:
                if code in df["色粉編號"].astype(str).values:
                    st.warning(f"⚠️ 色粉編號【{code}】已存在，請勿重複新增！")
                else:
                    new_row = {
                        "色粉編號": code,
                        "名稱": st.session_state["name_input"],
                        "國際色號": st.session_state["pantone_input"],
                        "色粉類別": st.session_state["color_type_select"],
                        "規格": st.session_state["spec_select"],
                        "產地": st.session_state["origin_input"],
                        "備註": st.session_state["remark_input"]
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"✅ 已新增色粉【{code}】！")

            # 寫回 Google Sheet
            worksheet.clear()
            worksheet.update(
                [df.columns.tolist()] +
                df.fillna("").astype(str).values.tolist()
            )

            # 清空表單
            for f in fields:
                st.session_state[f] = ""

            st.experimental_rerun()

# ====== 顯示色粉總表 ======

st.markdown("### 色粉總表")

# 篩選顯示
search_value = st.session_state["search_value"].strip()

if search_value != "":
    search_df = df[
        df["色粉編號"].astype(str).str.contains(search_value, case=False) |
        df["名稱"].astype(str).str.contains(search_value, case=False)
    ]
else:
    search_df = df

if search_df.empty:
    st.info("⚠️ 尚無符合條件的色粉資料。")
else:
    for idx, row in search_df.iterrows():
        bg = "#FED9B7" if idx % 2 == 0 else "#FDFCDC"

        col_text, col_edit, col_delete = st.columns([8,1,1])

        with col_text:
            st.markdown(
                f"""
                <div style='background-color:{bg};padding:8px;text-align:left;'>
                ➡️ <b>色粉編號</b>: {row['色粉編號']} ｜ 
                <b>名稱</b>: {row['名稱']} ｜ 
                <b>國際色號</b>: {row['國際色號']} ｜ 
                <b>色粉類別</b>: {row['色粉類別']} ｜ 
                <b>規格</b>: {row['規格']} ｜ 
                <b>產地</b>: {row['產地']} ｜ 
                <b>備註</b>: {row['備註']}
                </div>
                """,
                unsafe_allow_html=True
            )

        with col_edit:
            if st.button("✏️ 修改", key=f"edit_{idx}",
                         help="修改此筆資料",
                         type="primary"):
                st.session_state["code_input"] = str(row["色粉編號"])
                st.session_state["name_input"] = str(row["名稱"])
                st.session_state["pantone_input"] = str(row["國際色號"])
                st.session_state["color_type_select"] = str(row["色粉類別"])
                st.session_state["spec_select"] = str(row["規格"])
                st.session_state["origin_input"] = str(row["產地"])
                st.session_state["remark_input"] = str(row["備註"])
                st.success(f"✅ 已載入色粉【{row['色粉編號']}】以供修改。")
                st.experimental_rerun()

        with col_delete:
            if st.button("🗑️ 刪除", key=f"delete_{idx}",
                         help="刪除此筆資料",
                         type="secondary"):
                confirm = st.warning(
                    f"⚠️ 確定要刪除【{row['色粉編號']}】嗎？"
                )
                if st.button("✅ 確定刪除", key=f"confirm_{idx}"):
                    df.drop(index=row.name, inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    worksheet.clear()
                    worksheet.update(
                        [df.columns.tolist()] +
                        df.fillna("").astype(str).values.tolist()
                    )
                    st.success(f"✅ 已刪除色粉【{row['色粉編號']}】！")
                    st.experimental_rerun()
