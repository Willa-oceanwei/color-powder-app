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
        menu = st.radio("請選擇模組", ["色粉管理", "客戶名單", "配方管理"])

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

elif menu == "配方管理":

    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except:
        ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)

# 預設配方欄位
RECIPE_COLUMNS = ["客戶編號", "客戶簡稱", "配方名稱", "建檔時間", "原始配方編號",
                  "比例1", "比例2", "比例單位", "備註", "色粉淨重", "淨重單位"]

for i in range(1, 11):
    RECIPE_COLUMNS += [f"色粉編號{i}", f"色粉名稱{i}", f"色粉比例{i}"]

# 快取資料
@st.cache_data
def load_data():
    df_recipe = pd.DataFrame(sheet_recipe.get_all_records())
    df_powder = pd.DataFrame(sheet_powder.get_all_records())
    df_client = pd.DataFrame(sheet_client.get_all_records())
    return df_recipe, df_powder, df_client

df_recipe, df_powder, df_client = load_data()

# ----------- 功能區塊：主畫面 ----------- #
st.set_page_config(page_title="色粉配方管理系統", layout="wide")
st.title("🎨 色粉配方管理系統")

# ----------- 側邊選單 ----------- #
menu = st.sidebar.selectbox("選單", ["首頁", "配方管理"], key="menu")

# ----------- 配方管理 ----------- #
if menu == "配方管理":

    st.subheader("📋 配方清單")

    # ------- 搜尋欄位 ------- #
    with st.expander("🔍 搜尋條件", expanded=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            keyword = st.text_input("配方名稱 / 客戶編號 / 客戶簡稱").strip()
        with col2:
            filter_type = st.radio("過濾類型", ["全部", "原始配方", "附加配方"], horizontal=True)
        with col3:
            search_btn = st.button("🔍 搜尋")
            reset_btn = st.button("🔄 清除")

    # ------- 資料篩選 ------- #
    def filter_recipes():
        df = df_recipe.copy()
        if keyword:
            df = df[df.apply(lambda row: keyword.lower() in str(row["配方名稱"]).lower() or
                             keyword in str(row["客戶編號"]) or keyword in str(row["客戶簡稱"]), axis=1)]
        if filter_type == "原始配方":
            df = df[df["原始配方編號"] == ""]
        elif filter_type == "附加配方":
            df = df[df["原始配方編號"] != ""]
        return df

    # ------- 清單結果 ------- #
    if search_btn:
        result_df = filter_recipes()
        if result_df.empty:
            st.warning("找不到符合條件的配方。")
        else:
            for i, row in result_df.iterrows():
                cols = st.columns([1.2, 2.2, 2, 1.5, 1, 1.5, 1.5, 2, 1.5, 1.2])
                cols[0].markdown(f"**{i+1}**")
                cols[1].write(row["配方名稱"])
                cols[2].write(row["客戶簡稱"][:6])
                cols[3].write(row["建檔時間"][:10])
                cols[4].write("附加" if row["原始配方編號"] else "原始")
                cols[5].write(f"{row['比例1']} / {row['比例2']}")
                cols[6].write(row["比例單位"])
                cols[7].write(row["備註"][:6])
                with cols[8]:
                    if st.button("✏️改", key=f"edit_{i}"):
                        st.info(f"你按下修改：{row['配方名稱']}")
                with cols[9]:
                    if st.button("🗑️刪", key=f"delete_{i}"):
                        st.warning(f"你按下刪除：{row['配方名稱']}")

    # ------- 建立配方 ------- #
    with st.expander("🆕 新增配方", expanded=True):
        if "form_recipe" not in st.session_state:
            st.session_state.form_recipe = {col: "" for col in RECIPE_COLUMNS}

        # 客戶模糊搜尋
        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            input_code = st.text_input("🔢 客戶編號", st.session_state.form_recipe["客戶編號"], key="client_code_input")
            match_df = df_client[df_client["客戶編號"].str.contains(input_code)]
            if not match_df.empty:
                st.session_state.form_recipe["客戶簡稱"] = match_df.iloc[0]["客戶簡稱"]
            st.session_state.form_recipe["客戶編號"] = input_code
        with col_c2:
            st.text_input("🧾 客戶簡稱", st.session_state.form_recipe["客戶簡稱"], key="client_name_output", disabled=True)

        # 基本欄位
        col_f1, col_f2 = st.columns(2)
        st.session_state.form_recipe["配方名稱"] = col_f1.text_input("配方名稱", st.session_state.form_recipe["配方名稱"])
        st.session_state.form_recipe["原始配方編號"] = col_f2.text_input("原始配方編號（留空為原始配方）", st.session_state.form_recipe["原始配方編號"])
        col_f3, col_f4, col_f5 = st.columns(3)
        st.session_state.form_recipe["比例1"] = col_f3.text_input("比例1", st.session_state.form_recipe["比例1"])
        st.session_state.form_recipe["比例2"] = col_f4.text_input("比例2", st.session_state.form_recipe["比例2"])
        st.session_state.form_recipe["比例單位"] = col_f5.selectbox("比例單位", ["%", "g", "kg"], index=0)

        col_f6, col_f7, col_f8 = st.columns(3)
        st.session_state.form_recipe["色粉淨重"] = col_f6.text_input("色粉淨重", st.session_state.form_recipe["色粉淨重"])
        st.session_state.form_recipe["淨重單位"] = col_f7.selectbox("淨重單位", ["g", "kg"], index=0)
        st.session_state.form_recipe["備註"] = col_f8.text_input("備註", st.session_state.form_recipe["備註"])

        # 色粉輸入（橫排）
        st.markdown("---")
        st.markdown("🎨 **色粉資料輸入（最多10筆）**")
        for i in range(1, 11):
            powder_col = st.columns([2, 3, 2, 1])
            編號 = st.session_state.form_recipe.get(f"色粉編號{i}", "")
            名稱 = df_powder[df_powder["色粉編號"] == 編號]["色粉名稱"].values[0] if 編號 in df_powder["色粉編號"].values else ""
            比例 = st.session_state.form_recipe.get(f"色粉比例{i}", "")
            st.session_state.form_recipe[f"色粉編號{i}"] = powder_col[0].text_input(f"色粉編號{i}", 編號, key=f"粉號{i}")
            st.session_state.form_recipe[f"色粉名稱{i}"] = powder_col[1].text_input(f"色粉名稱{i}", 名稱, key=f"粉名{i}", disabled=True)
            st.session_state.form_recipe[f"色粉比例{i}"] = powder_col[2].text_input(f"比例{i}", 比例, key=f"比例{i}")
            powder_col[3].markdown("g")

        # 建立按鈕
        if st.button("✅ 儲存配方"):
            st.session_state.form_recipe["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            values = [st.session_state.form_recipe.get(col, "") for col in RECIPE_COLUMNS]
            sheet_recipe.append_row(values)
            st.success("✅ 配方已成功新增！")
            st.cache_data.clear()
            time.sleep(1)
            st.experimental_rerun()
