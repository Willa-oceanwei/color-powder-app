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

# ======== 配方管理 =========
elif menu == "配方管理":
    worksheet_recipe = spreadsheet.worksheet("配方管理")

    required_columns = [
        "配方編號", "顏色", "客戶編號", "客戶簡稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例項目", "比例數值", "比例單位",
        "色粉淨重", "淨重單位",
        "色粉編號1", "色粉重量1",
        "色粉編號2", "色粉重量2",
        "色粉編號3", "色粉重量3",
        "色粉編號4", "色粉重量4",
        "色粉編號5", "色粉重量5",
        "色粉編號6", "色粉重量6",
        "色粉編號7", "色粉重量7",
        "色粉編號8", "色粉重量8",
        "合計類別", "合計值", "建檔日期"
    ]

    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe",
        "search_pantone",
        "search_customer"
    ])

    for col in required_columns:
        st.session_state.form_recipe.setdefault(col, "")

    # 客戶名單下拉選單資料
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customer = pd.DataFrame(ws_customer.get_all_records())
    except:
        df_customer = pd.DataFrame(columns=["客戶編號", "客戶簡稱"])

    # 色粉名單下拉選單資料
    try:
        ws_color = spreadsheet.worksheet("色粉管理")
        df_color = pd.DataFrame(ws_color.get_all_records())
    except:
        df_color = pd.DataFrame(columns=["色粉編號"])

    # 讀取配方資料
    try:
        df_recipe = pd.DataFrame(worksheet_recipe.get_all_records())
    except:
        df_recipe = pd.DataFrame(columns=required_columns)
    df_recipe = df_recipe.astype(str)
    for col in required_columns:
        if col not in df_recipe.columns:
            df_recipe[col] = ""

    # ======== 搜尋區塊 ========
    st.subheader("🗃️ 配方搜尋🔎")
    col1, col2, col3 = st.columns(3)
    with col1:
        search_recipe = st.text_input("配方搜尋", st.session_state.search_recipe)
        st.session_state.search_recipe = search_recipe
    with col2:
        search_pantone = st.text_input("Pantone色號搜尋", st.session_state.search_pantone)
        st.session_state.search_pantone = search_pantone
    with col3:
        search_customer = st.text_input("客戶編號/名稱搜尋", st.session_state.search_customer)
        st.session_state.search_customer = search_customer

    # 過濾資料
    df_recipe_filtered = df_recipe.copy()
    if search_recipe:
        df_recipe_filtered = df_recipe_filtered[
            df_recipe_filtered["配方編號"].str.contains(search_recipe, case=False, na=False)
        ]
    if search_pantone:
        df_recipe_filtered = df_recipe_filtered[
            df_recipe_filtered["Pantone色號"].str.contains(search_pantone, case=False, na=False)
        ]
    if search_customer:
        df_recipe_filtered = df_recipe_filtered[
            df_recipe_filtered["客戶編號"].str.contains(search_customer, case=False, na=False) |
            df_recipe_filtered["客戶簡稱"].str.contains(search_customer, case=False, na=False)
        ]

    if (search_recipe or search_pantone or search_customer) and df_recipe_filtered.empty:
        st.warning("❗ 查無符合的配方資料")

    # ======== 新增 / 修改配方 ========
    st.subheader("➕ 新增 / 修改配方")

    # 第一行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方編號"] = st.text_input(
            "配方編號", st.session_state.form_recipe["配方編號"]
        )
    with col2:
        st.session_state.form_recipe["顏色"] = st.text_input(
            "顏色", st.session_state.form_recipe["顏色"]
        )
    with col3:
        # 客戶名單自動下拉
        customer_options = [
            f"{row['客戶編號']} - {row['客戶簡稱']}"
            for _, row in df_customer.iterrows()
        ]
        selected_customer = st.selectbox(
            "客戶編號/簡稱",
            customer_options,
            index=customer_options.index(
                f"{st.session_state.form_recipe['客戶編號']} - {st.session_state.form_recipe['客戶簡稱']}"
            ) if st.session_state.form_recipe["客戶編號"] and st.session_state.form_recipe["客戶簡稱"] and \
                 f"{st.session_state.form_recipe['客戶編號']} - {st.session_state.form_recipe['客戶簡稱']}" in customer_options else 0
        )
        if selected_customer:
            customer_no, customer_name = selected_customer.split(" - ")
            st.session_state.form_recipe["客戶編號"] = customer_no
            st.session_state.form_recipe["客戶簡稱"] = customer_name

    # 第二行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方類別"] = st.selectbox(
            "配方類別",
            ["原始配方", "附加配方"],
            index=["原始配方", "附加配方"].index(st.session_state.form_recipe["配方類別"]) if st.session_state.form_recipe["配方類別"] else 0
        )
    with col2:
        st.session_state.form_recipe["狀態"] = st.selectbox(
            "狀態",
            ["啟用", "停用"],
            index=["啟用", "停用"].index(st.session_state.form_recipe["狀態"]) if st.session_state.form_recipe["狀態"] else 0
        )
    with col3:
        st.session_state.form_recipe["原始配方"] = st.text_input(
            "原始配方", st.session_state.form_recipe["原始配方"]
        )

    # 第三行
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["色粉類別"] = st.selectbox(
            "色粉類別",
            ["配方", "色母", "色粉", "添加劑", "其他"],
            index=["配方", "色母", "色粉", "添加劑", "其他"].index(st.session_state.form_recipe["色粉類別"]) if st.session_state.form_recipe["色粉類別"] else 0
        )
    with col2:
        st.session_state.form_recipe["計量單位"] = st.selectbox(
            "計量單位",
            ["包", "桶", "kg", "其他"],
            index=["包", "桶", "kg", "其他"].index(st.session_state.form_recipe["計量單位"]) if st.session_state.form_recipe["計量單位"] else 0
        )
    with col3:
        st.session_state.form_recipe["Pantone色號"] = st.text_input(
            "Pantone色號", st.session_state.form_recipe["Pantone色號"]
        )

    # 比例欄位
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.session_state.form_recipe["比例項目"] = st.text_input(
            "比例項目", st.session_state.form_recipe["比例項目"]
        )
    with col2:
        st.session_state.form_recipe["比例數值"] = st.text_input(
            "比例數值", st.session_state.form_recipe["比例數值"]
        )
    with col3:
        st.session_state.form_recipe["比例單位"] = st.selectbox(
            "比例單位", ["g", "kg"],
            index=["g", "kg"].index(st.session_state.form_recipe["比例單位"]) if st.session_state.form_recipe["比例單位"] else 0,
            key="比例單位"
        )

    # 備註
    st.session_state.form_recipe["備註"] = st.text_input(
        "備註", st.session_state.form_recipe.get("備註", "")
    )

    # 色粉淨重
    col1, col2 = st.columns([3, 1])
    with col1:
        st.session_state.form_recipe["色粉淨重"] = st.text_input(
            "色粉淨重", st.session_state.form_recipe["色粉淨重"]
        )
    with col2:
        st.session_state.form_recipe["淨重單位"] = st.selectbox(
            "單位", ["g", "kg"],
            index=["g", "kg"].index(st.session_state.form_recipe["淨重單位"]) if st.session_state.form_recipe["淨重單位"] else 0,
            key="淨重單位"
        )

    # 色粉明細
    for i in range(1, 9):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.session_state.form_recipe[f"色粉編號{i}"] = st.text_input(
                f"色粉{i}編號",
                st.session_state.form_recipe[f"色粉編號{i}"]
            )
            # 檢查色粉是否存在
            if st.session_state.form_recipe[f"色粉編號{i}"]:
                if st.session_state.form_recipe[f"色粉編號{i}"] not in df_color["色粉編號"].values:
                    st.warning(f"⚠️ 色粉編號 {st.session_state.form_recipe[f'色粉編號{i}']} 不存在！")
        with col2:
            st.session_state.form_recipe[f"色粉重量{i}"] = st.text_input(
                f"色粉{i}重量",
                st.session_state.form_recipe[f"色粉重量{i}"]
            )
        with col3:
            st.write(st.session_state.form_recipe["淨重單位"] or "")

    # 合計類別 & 自動計算
    合計類別選項 = ["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"]
    col1, col2 = st.columns([2, 2])
    with col1:
        st.session_state.form_recipe["合計類別"] = st.selectbox(
            "合計類別", 合計類別選項,
            index=合計類別選項.index(st.session_state.form_recipe["合計類別"]) if st.session_state.form_recipe["合計類別"] else 0,
            key="合計類別"
        )
    with col2:
        # 計算合計值
        total_powder_weight = 0
        for i in range(1, 9):
            value = st.session_state.form_recipe.get(f"色粉重量{i}", "")
            try:
                total_powder_weight += float(value) if value else 0
            except:
                pass
        try:
            net_weight = float(st.session_state.form_recipe["色粉淨重"]) if st.session_state.form_recipe["色粉淨重"] else 0
        except:
            net_weight = 0
        合計值 = net_weight - total_powder_weight
        st.text_input(
            "合計值", value=str(合計值), disabled=True
        )
