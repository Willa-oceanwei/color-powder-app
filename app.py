# ===== app.py =====
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"

# ======== 建立 Spreadsheet 物件 (避免重複連線) =========
if "spreadsheet" not in st.session_state:
    try:
        st.session_state["spreadsheet"] = client.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"❗ 無法連線 Google Sheet：{e}")
        st.stop()

spreadsheet = st.session_state["spreadsheet"]

# ======== Sidebar 修正 =========
with st.sidebar:
    st.title("🎨 管理系統")
    with st.expander("👉 點此展開 / 收合選單", expanded=True):
        menu = st.radio("請選擇模組", ["色粉管理", "客戶名單", "配方管理"], key="main_menu")

# ======== 初始化 session_state =========
def init_states(key_list):
    for key in key_list:
        if key not in st.session_state:
            if key.startswith("form_"):
                st.session_state[key] = {}
            elif key.startswith("edit_") or key.startswith("delete_"):
                st.session_state[key] = None
            elif key.startswith("show_delete"):
                st.session_state[key] = False
            elif key.startswith("search"):
                st.session_state[key] = ""

# ======== 共用儲存函式 =========
def save_df_to_sheet(ws, df):
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update("A1", values)

# ======== 色粉管理 =========
if menu == "色粉管理":
    worksheet = spreadsheet.worksheet("色粉管理")
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    init_states(["form_color", "edit_color_index", "delete_color_index", "show_delete_color_confirm", "search_color"])
    for col in required_columns:
        st.session_state.form_color.setdefault(col, "")

    try:
        df = pd.DataFrame(worksheet.get_all_records())
    except:
        df = pd.DataFrame(columns=required_columns)
    df = df.astype(str)
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    st.subheader("📜  色粉搜尋🔎")
    search_input = st.text_input("請輸入色粉編號或國際色號", st.session_state.search_color)
    if search_input != st.session_state.search_color:
        st.session_state.search_color = search_input
    df_filtered = df[
        df["色粉編號"].str.contains(st.session_state.search_color, case=False, na=False)
        | df["國際色號"].str.contains(st.session_state.search_color, case=False, na=False)
    ] if st.session_state.search_color.strip() else df

    if st.session_state.search_color.strip() and df_filtered.empty:
        st.warning("❗ 查無符合的色粉編號")

    st.subheader("➕ 新增 / 修改 色粉")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input("色粉編號", st.session_state.form_color["色粉編號"])
        st.session_state.form_color["國際色號"] = st.text_input("國際色號", st.session_state.form_color["國際色號"])
        st.session_state.form_color["名稱"] = st.text_input("名稱", st.session_state.form_color["名稱"])
    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(st.session_state.form_color["色粉類別"]) if st.session_state.form_color["色粉類別"] in ["色粉", "色母", "添加劑"] else 0)
        st.session_state.form_color["包裝"] = st.selectbox("包裝", ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(st.session_state.form_color["包裝"]) if st.session_state.form_color["包裝"] in ["袋", "箱", "kg"] else 0)
        st.session_state.form_color["備註"] = st.text_input("備註", st.session_state.form_color["備註"])

    if st.button("💾 儲存"):
        new_data = st.session_state.form_color.copy()
        if new_data["色粉編號"].strip() == "":
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if st.session_state.edit_color_index is not None:
                df.iloc[st.session_state.edit_color_index] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增成功！")
            save_df_to_sheet(worksheet, df)
            st.session_state.form_color = {col: "" for col in required_columns}
            st.session_state.edit_color_index = None
            st.rerun()

    if st.session_state.show_delete_color_confirm:
        target_row = df.iloc[st.session_state.delete_color_index]
        target_text = f'{target_row["色粉編號"]} {target_row["名稱"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("刪除"):
            df.drop(index=st.session_state.delete_color_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(worksheet, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_color_confirm = False
            st.rerun()
        if c2.button("取消"):
            st.session_state.show_delete_color_confirm = False
            st.rerun()

    st.subheader("📋 色粉清單")
    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 3])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        with cols[5]:
            c1, c2 = st.columns(2, gap="small")
            if c1.button("✏️ 修改", key=f"edit_color_{i}"):
                st.session_state.edit_color_index = i
                st.session_state.form_color = row.to_dict()
                st.rerun()
            if c2.button("🗑️ 刪除", key=f"delete_color_{i}"):
                st.session_state.delete_color_index = i
                st.session_state.show_delete_color_confirm = True
                st.rerun()

# ======== 客戶名單 =========
elif menu == "客戶名單":
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
    except:
        ws_customer = spreadsheet.add_worksheet("客戶名單", rows=100, cols=10)
    columns = ["客戶編號", "客戶簡稱", "備註"]
    init_states(["form_customer", "edit_customer_index", "delete_customer_index", "show_delete_customer_confirm", "search_customer"])
    for col in columns:
        st.session_state.form_customer.setdefault(col, "")

    try:
        df = pd.DataFrame(ws_customer.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)
    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    st.subheader("🗿  客戶搜尋🔎")
    search_input = st.text_input("請輸入客戶編號或簡稱", st.session_state.search_customer)
    if search_input != st.session_state.search_customer:
        st.session_state.search_customer = search_input
    df_filtered = df[
        df["客戶編號"].str.contains(st.session_state.search_customer, case=False, na=False)
        | df["客戶簡稱"].str.contains(st.session_state.search_customer, case=False, na=False)
    ] if st.session_state.search_customer.strip() else df

    if st.session_state.search_customer.strip() and df_filtered.empty:
        st.warning("❗ 查無符合的客戶編號或簡稱")

    st.subheader("➕ 新增 / 修改 客戶")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_customer["客戶編號"] = st.text_input("客戶編號", st.session_state.form_customer["客戶編號"])
        st.session_state.form_customer["客戶簡稱"] = st.text_input("客戶簡稱", st.session_state.form_customer["客戶簡稱"])
    with col2:
        st.session_state.form_customer["備註"] = st.text_input("備註", st.session_state.form_customer["備註"])

    if st.button("💾 儲存"):
        new_data = st.session_state.form_customer.copy()
        if new_data["客戶編號"].strip() == "":
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_index is not None:
                df.iloc[st.session_state.edit_customer_index] = new_data
                st.success("✅ 客戶已更新！")
            else:
                if new_data["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增成功！")
            save_df_to_sheet(ws_customer, df)
            st.session_state.form_customer = {col: "" for col in columns}
            st.session_state.edit_customer_index = None
            st.rerun()

    if st.session_state.show_delete_customer_confirm:
        target_row = df.iloc[st.session_state.delete_customer_index]
        target_text = f'{target_row["客戶編號"]} {target_row["客戶簡稱"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("刪除"):
            df.drop(index=st.session_state.delete_customer_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_customer, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_customer_confirm = False
            st.rerun()
        if c2.button("取消"):
            st.session_state.show_delete_customer_confirm = False
            st.rerun()

    st.subheader("📋 客戶清單")
    for i, row in df_filtered.iterrows():
        cols = st.columns([3, 3, 3, 3])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        with cols[3]:
            c1, c2 = st.columns(2, gap="small")
            with c1:
                if st.button("✏️\n改", key=f"edit_customer_{i}"):
                    st.session_state.edit_customer_index = i
                    st.session_state.form_customer = row.to_dict()
                    st.rerun()
            with c2:
                if st.button("🗑️\n刪", key=f"delete_color_{i}"):
                    st.session_state.delete_customer_index = i
                    st.session_state.show_delete_customer_confirm = True
                    st.rerun()


import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# ======== 初始化 session_state =========
def init_states(key_list):
    for key in key_list:
        if key not in st.session_state:
            if key.startswith("form_"):
                st.session_state[key] = {}
            elif key.startswith("edit_") or key.startswith("delete_"):
                st.session_state[key] = None
            elif key.startswith("show_delete"):
                st.session_state[key] = False
            elif key.startswith("search"):
                st.session_state[key] = ""

# ======== 共用儲存函式 =========
def save_df_to_sheet(ws, df):
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update("A1", values)

# ======== 色粉管理（維持原狀） =========
if menu == "色粉管理":
    # ... 你的色粉管理程式保留不動
    pass

# ======== 客戶名單（維持原狀） =========
elif menu == "客戶名單":
    # ... 你的客戶名單程式保留不動
    pass

import streamlit as st
import pandas as pd
from datetime import datetime

# ========== 初始化 ==========

# 先連 Google Sheet (請依你原始程式保留以下連線程式)
# 例如：
# spreadsheet = gc.open_by_key(spreadsheet_key)

# 我這裡假設 spreadsheet 已存在
ws_recipe = spreadsheet.worksheet("配方管理")
ws_customer = spreadsheet.worksheet("客戶名單")
ws_color = spreadsheet.worksheet("色粉管理")

# 定義欄位
recipe_cols = [
    "配方編號", "顏色", "客戶編號", "配方類別", "狀態", "原始配方",
    "色粉類別", "計量單位", "Pantone色號",
    "比例1", "比例2", "比例3",
    "備註", "色粉淨重", "淨重單位",
    "色粉1_編號", "色粉1_重量",
    "色粉2_編號", "色粉2_重量",
    "色粉3_編號", "色粉3_重量",
    "色粉4_編號", "色粉4_重量",
    "色粉5_編號", "色粉5_重量",
    "色粉6_編號", "色粉6_重量",
    "色粉7_編號", "色粉7_重量",
    "色粉8_編號", "色粉8_重量",
    "合計類別", "建檔時間"
]

# 初始化 session state
if "form_recipe" not in st.session_state:
    st.session_state.form_recipe = {col: "" for col in recipe_cols}

# 讀取 data
data_recipe = ws_recipe.get_all_records()
df_recipe = pd.DataFrame(data_recipe) if data_recipe else pd.DataFrame(columns=recipe_cols)
df_recipe = df_recipe.astype(str)

# 讀客戶名單
df_customer = pd.DataFrame(ws_customer.get_all_records())
if not df_customer.empty:
    df_customer["combo"] = df_customer["客戶編號"] + " - " + df_customer["客戶簡稱"]
customer_list = df_customer["combo"].tolist() if not df_customer.empty else []

# 讀色粉資料
df_color = pd.DataFrame(ws_color.get_all_records())
color_codes = df_color["色粉編號"].tolist() if not df_color.empty else []

# ========== UI ==========

st.subheader("🗃️ 配方搜尋🔎")

col_srch1, col_srch2, col_srch3 = st.columns(3)
search_recipe = col_srch1.text_input("配方編號搜尋")
search_pantone = col_srch2.text_input("Pantone色號搜尋")
search_customer = col_srch3.text_input("客戶編號/名稱搜尋")

# 客戶模糊搜尋
if search_customer:
    mask1 = df_customer["客戶編號"].str.contains(search_customer, case=False, na=False)
    mask2 = df_customer["客戶簡稱"].str.contains(search_customer, case=False, na=False)
    matched_customers = df_customer[mask1 | mask2]
    matched_codes = matched_customers["客戶編號"].unique().tolist()
else:
    matched_codes = df_customer["客戶編號"].unique().tolist()

if not df_recipe.empty:
    filtered = df_recipe[
        df_recipe["配方編號"].str.contains(search_recipe, case=False, na=False)
        & df_recipe["Pantone色號"].str.contains(search_pantone, case=False, na=False)
        & df_recipe["客戶編號"].isin(matched_codes)
    ]
else:
    filtered = pd.DataFrame()

if (search_recipe or search_pantone or search_customer) and filtered.empty:
    st.warning("❗ 查無符合的配方")

# ========== 新增 / 修改配方 ==========

st.subheader("📝 新增 / 修改配方")

c1, c2, c3 = st.columns(3)
st.session_state.form_recipe["配方編號"] = c1.text_input(
    "配方編號",
    st.session_state.form_recipe["配方編號"]
)
st.session_state.form_recipe["顏色"] = c2.text_input(
    "顏色",
    st.session_state.form_recipe["顏色"]
)

# 客戶下拉 → 改成空預設 + 模糊搜尋
customer_input = c3.text_input(
    "客戶編號 / 簡稱",
    st.session_state.form_recipe["客戶編號"]
)

suggestions = []
if customer_input:
    mask1 = df_customer["客戶編號"].str.contains(customer_input, case=False, na=False)
    mask2 = df_customer["客戶簡稱"].str.contains(customer_input, case=False, na=False)
    suggestions = (df_customer[mask1 | mask2]["combo"]).tolist()

if suggestions:
    selected = c3.selectbox("選擇客戶", [""] + suggestions, index=0)
    if selected:
        code = selected.split(" - ")[0]
        st.session_state.form_recipe["客戶編號"] = code
else:
    st.session_state.form_recipe["客戶編號"] = customer_input

c4, c5, c6 = st.columns(3)
st.session_state.form_recipe["配方類別"] = c4.selectbox(
    "配方類別",
    ["原始配方", "附加配方"],
    index=["原始配方", "附加配方"].index(st.session_state.form_recipe["配方類別"]) if st.session_state.form_recipe["配方類別"] else 0
)
st.session_state.form_recipe["狀態"] = c5.selectbox(
    "狀態",
    ["啟用", "停用"],
    index=["啟用", "停用"].index(st.session_state.form_recipe["狀態"]) if st.session_state.form_recipe["狀態"] else 0
)
st.session_state.form_recipe["原始配方"] = c6.text_input(
    "原始配方",
    st.session_state.form_recipe["原始配方"]
)

c7, c8, c9 = st.columns(3)
st.session_state.form_recipe["色粉類別"] = c7.selectbox(
    "色粉類別",
    ["配方", "色母", "色粉", "添加劑", "其他"],
    index=["配方", "色母", "色粉", "添加劑", "其他"].index(st.session_state.form_recipe["色粉類別"]) if st.session_state.form_recipe["色粉類別"] else 0
)
st.session_state.form_recipe["計量單位"] = c8.selectbox(
    "計量單位",
    ["包", "桶", "kg", "其他"],
    index=["包", "桶", "kg", "其他"].index(st.session_state.form_recipe["計量單位"]) if st.session_state.form_recipe["計量單位"] else 0
)
st.session_state.form_recipe["Pantone色號"] = c9.text_input(
    "Pantone色號",
    st.session_state.form_recipe["Pantone色號"]
)

# 比例區塊（橫向）
col_ratio = st.columns([2, 0.3, 2, 1])
st.session_state.form_recipe["比例1"] = col_ratio[0].text_input(
    "",
    st.session_state.form_recipe["比例1"],
    label_visibility="collapsed",
    key="比例1_input"
)
col_ratio[1].write("：")
st.session_state.form_recipe["比例2"] = col_ratio[2].text_input(
    "",
    st.session_state.form_recipe["比例2"],
    label_visibility="collapsed",
    key="比例2_input"
)
col_ratio[3].write("g/kg")

# 備註
st.session_state.form_recipe["備註"] = st.text_input(
    "備註",
    st.session_state.form_recipe["備註"]
)

c10, c11 = st.columns([2, 1])
st.session_state.form_recipe["色粉淨重"] = c10.text_input(
    "色粉淨重",
    st.session_state.form_recipe["色粉淨重"]
)
st.session_state.form_recipe["淨重單位"] = c11.selectbox(
    "單位",
    ["g", "kg"],
    index=["g", "kg"].index(st.session_state.form_recipe["淨重單位"]) if st.session_state.form_recipe["淨重單位"] else 0
)

# 色粉 1~8 橫向排版
total_powder = 0
for idx in range(1, 9):
    row = st.columns([1, 4, 4, 1])
    row[0].write(f"色粉{idx}")
    st.session_state.form_recipe[f"色粉{idx}_編號"] = row[1].text_input(
        "",
        st.session_state.form_recipe[f"色粉{idx}_編號"],
        key=f"色粉{idx}_編號"
    )
    st.session_state.form_recipe[f"色粉{idx}_重量"] = row[2].text_input(
        "",
        st.session_state.form_recipe[f"色粉{idx}_重量"],
        key=f"色粉{idx}_重量"
    )
    row[3].write(st.session_state.form_recipe["淨重單位"])

    # 驗證色粉是否存在
    code = st.session_state.form_recipe[f"色粉{idx}_編號"]
    if code and code not in color_codes:
        st.warning(f"❗ 色粉編號 {code} 尚未建檔！")

    try:
        total_powder += float(st.session_state.form_recipe[f"色粉{idx}_重量"] or 0)
    except:
        pass

# 合計類別
c_sum1, c_sum2 = st.columns([1, 2])
st.session_state.form_recipe["合計類別"] = c_sum1.selectbox(
    "合計類別",
    ["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"],
    index=["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"].index(st.session_state.form_recipe["合計類別"]) if st.session_state.form_recipe["合計類別"] else 0
)
net_weight = float(st.session_state.form_recipe["色粉淨重"] or 0)
diff = net_weight - total_powder
c_sum2.write(f"合計自動計算：{diff} g/kg")

# 儲存
if st.button("💾 儲存配方"):
    new_data = st.session_state.form_recipe.copy()
    if not new_data["配方編號"]:
        st.warning("❗ 請輸入配方編號")
    elif new_data["配方類別"] == "附加配方" and not new_data["原始配方"]:
        st.warning("❗ 附加配方必填原始配方")
    elif new_data["配方編號"] in df_recipe["配方編號"].values:
        st.warning("⚠️ 此配方編號已存在")
    else:
        new_data["建檔時間"] = datetime.now().strftime("%y/%m/%d")
        df_recipe = pd.concat([df_recipe, pd.DataFrame([new_data])], ignore_index=True)
        save_df_to_sheet(ws_recipe, df_recipe)
        st.success("✅ 新增成功！")
        st.experimental_rerun()

# ========== 配方清單 ==========

st.subheader("📋 配方清單")
if not filtered.empty:
    for i, row in filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(row["配方編號"])
        cols[1].write(row["顏色"])
        cols[2].write(row["客戶編號"])
        # 找客戶簡稱
        custname = df_customer.loc[df_customer["客戶編號"] == row["客戶編號"], "客戶簡稱"]
        cols[3].write(custname.values[0] if not custname.empty else "")
        cols[4].write(row["Pantone色號"])
        cols[5].write(row["建檔時間"])
        if cols[6].button("✏️改", key=f"edit_{i}"):
            st.session_state.form_recipe = row.to_dict()
            st.experimental_rerun()
        if cols[7].button("🗑️刪", key=f"delete_{i}"):
            df_recipe.drop(index=i, inplace=True)
            df_recipe.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_recipe, df_recipe)
            st.success("✅ 已刪除")
            st.experimental_rerun()
else:
    st.write("（尚無配方資料）")
