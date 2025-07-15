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

    # 先連線工作表
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except:
        ws_recipe = spreadsheet.add_worksheet("配方管理", rows=100, cols=30)

    # 先載入客戶名單，做下拉或搜尋用
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customers = pd.DataFrame(ws_customer.get_all_records())
    except:
        df_customers = pd.DataFrame(columns=["客戶編號", "客戶簡稱"])

    # 載入色粉管理
    try:
        ws_color = spreadsheet.worksheet("色粉管理")
        df_colors = pd.DataFrame(ws_color.get_all_records())
    except:
        df_colors = pd.DataFrame(columns=["色粉編號"])

    # 欄位
    recipe_cols = [
        "配方編號", "顏色", "客戶編號", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例A", "比例B", "比例C", "比例單位",
        "備註", "色粉淨重", "淨重單位",
        "色粉1編號","色粉1重量",
        "色粉2編號","色粉2重量",
        "色粉3編號","色粉3重量",
        "色粉4編號","色粉4重量",
        "色粉5編號","色粉5重量",
        "色粉6編號","色粉6重量",
        "色粉7編號","色粉7重量",
        "色粉8編號","色粉8重量",
        "合計類別", "合計數值", "建檔時間"
    ]

    # session_state
    init_states(["form_recipe", "edit_recipe_index", "delete_recipe_index", "show_delete_recipe_confirm", "search_recipe", "search_pantone", "search_customer_recipe"])
    for col in recipe_cols:
        st.session_state.form_recipe.setdefault(col, "")

    # 載入現有配方
    try:
        df_recipe = pd.DataFrame(ws_recipe.get_all_records())
    except:
        df_recipe = pd.DataFrame(columns=recipe_cols)

    df_recipe = df_recipe.astype(str)

    # ====== 搜尋區塊 ======
    st.subheader("🔎 搜尋配方")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.search_recipe = st.text_input("配方搜尋", st.session_state.search_recipe)
    with c2:
        st.session_state.search_pantone = st.text_input("Pantone色號搜尋", st.session_state.search_pantone)
    with c3:
        st.session_state.search_customer_recipe = st.text_input("客戶編號/名稱搜尋", st.session_state.search_customer_recipe)

    df_filtered = df_recipe
    if st.session_state.search_recipe.strip():
        df_filtered = df_filtered[
            df_filtered["配方編號"].str.contains(st.session_state.search_recipe, case=False, na=False)
        ]
    if st.session_state.search_pantone.strip():
        df_filtered = df_filtered[
            df_filtered["Pantone色號"].str.contains(st.session_state.search_pantone, case=False, na=False)
        ]
    if st.session_state.search_customer_recipe.strip():
        df_filtered = df_filtered[
            df_filtered["客戶編號"].str.contains(st.session_state.search_customer_recipe, case=False, na=False)
            | df_filtered["顧客名稱"].str.contains(st.session_state.search_customer_recipe, case=False, na=False)
        ]

    if (st.session_state.search_recipe or st.session_state.search_pantone or st.session_state.search_customer_recipe) and df_filtered.empty:
        st.warning("❗ 查無符合的配方資料")

    # ====== 新增 / 修改配方 ======
    st.subheader("➕ 新增 / 修改 配方")

    # 第一行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方編號"] = st.text_input("配方編號", st.session_state.form_recipe["配方編號"])
    with col2:
        st.session_state.form_recipe["顏色"] = st.text_input("顏色", st.session_state.form_recipe["顏色"])
    with col3:
        customer_input = st.text_input("客戶編號", st.session_state.form_recipe["客戶編號"])
        # 若有已建檔的客戶就顯示建議選項
        customer_options = df_customers[df_customers["客戶編號"].str.contains(customer_input, case=False, na=False)]["客戶編號"].unique().tolist() if customer_input else []
        if customer_options:
            st.session_state.form_recipe["客戶編號"] = st.selectbox("選擇客戶編號", customer_options, index=0)
        else:
            st.session_state.form_recipe["客戶編號"] = customer_input

    # 第二行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方類別"] = st.selectbox("配方類別", ["原始配方", "附加配方"],
            index=["原始配方", "附加配方"].index(st.session_state.form_recipe["配方類別"]) if st.session_state.form_recipe["配方類別"] else 0)
    with col2:
        st.session_state.form_recipe["狀態"] = st.selectbox("狀態", ["啟用", "停用"],
            index=["啟用", "停用"].index(st.session_state.form_recipe["狀態"]) if st.session_state.form_recipe["狀態"] else 0)
    with col3:
        st.session_state.form_recipe["原始配方"] = st.text_input("原始配方", st.session_state.form_recipe["原始配方"])

    # 第三行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["色粉類別"] = st.selectbox("色粉類別", ["配方", "色母", "色粉", "添加劑", "其他"],
            index=["配方", "色母", "色粉", "添加劑", "其他"].index(st.session_state.form_recipe["色粉類別"]) if st.session_state.form_recipe["色粉類別"] else 0)
    with col2:
        st.session_state.form_recipe["計量單位"] = st.selectbox("計量單位", ["包", "桶", "kg", "其他"],
            index=["包", "桶", "kg", "其他"].index(st.session_state.form_recipe["計量單位"]) if st.session_state.form_recipe["計量單位"] else 0)
    with col3:
        st.session_state.form_recipe["Pantone色號"] = st.text_input("Pantone色號", st.session_state.form_recipe["Pantone色號"])

    # 比例欄位
    col1, col2, col3 = st.columns([1,1,0.5])
    with col1:
        st.session_state.form_recipe["比例A"] = st.text_input("比例欄位1", st.session_state.form_recipe["比例A"])
    with col2:
        st.session_state.form_recipe["比例B"] = st.text_input("比例欄位2", st.session_state.form_recipe["比例B"])
    with col3:
        st.session_state.form_recipe["比例單位"] = st.selectbox("單位", ["g", "kg"], index=["g", "kg"].index(st.session_state.form_recipe["比例單位"]) if st.session_state.form_recipe["比例單位"] else 0)

    st.session_state.form_recipe["備註"] = st.text_input("備註", st.session_state.form_recipe["備註"])

    # 色粉淨重
    st.write("### 色粉淨重")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_recipe["色粉淨重"] = st.text_input("淨重", st.session_state.form_recipe["色粉淨重"])
    with col2:
        st.session_state.form_recipe["淨重單位"] = st
