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

    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1,9)],
        *[f"色粉重量{i}" for i in range(1,9)],
        "合計類別", "建檔時間"
    ]

    # 初始化 state
    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe_code",
        "search_pantone",
        "search_customer"
    ])
    for col in columns:
        st.session_state.form_recipe.setdefault(col, "")

    # 讀取表單
    try:
        df = pd.DataFrame(ws_recipe.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)

    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    # --- 搜尋區塊 ---
    st.subheader("🎯 配方搜尋🔎")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.search_recipe_code = st.text_input("配方搜尋", st.session_state.search_recipe_code)
    with col2:
        st.session_state.search_pantone = st.text_input("Pantone色號搜尋", st.session_state.search_pantone)
    with col3:
        st.session_state.search_customer = st.text_input("客戶編號/名稱搜尋", st.session_state.search_customer)

    # 篩選
    df_filtered = df
    if st.session_state.search_recipe_code.strip():
        df_filtered = df_filtered[
            df_filtered["配方編號"].str.contains(st.session_state.search_recipe_code, case=False, na=False)
        ]

    if st.session_state.search_pantone.strip():
        df_filtered = df_filtered[
            df_filtered["Pantone色號"].str.contains(st.session_state.search_pantone, case=False, na=False)
        ]

    if st.session_state.search_customer.strip():
        df_filtered = df_filtered[
            df_filtered["客戶編號"].str.contains(st.session_state.search_customer, case=False, na=False) |
            df_filtered["客戶名稱"].str.contains(st.session_state.search_customer, case=False, na=False)
        ]

    if (st.session_state.search_recipe_code.strip() or
        st.session_state.search_pantone.strip() or
        st.session_state.search_customer.strip()) and df_filtered.empty:
        st.warning("❗ 查無符合的配方資料")

    # --- 新增 / 修改區塊 ---
    st.subheader("➕ 新增 / 修改配方")

    # 第一排
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方編號"] = st.text_input("配方編號", st.session_state.form_recipe["配方編號"])
    with col2:
        st.session_state.form_recipe["顏色"] = st.text_input("顏色", st.session_state.form_recipe["顏色"])
    with col3:
        st.session_state.form_recipe["客戶編號"] = st.text_input("客戶編號", st.session_state.form_recipe["客戶編號"])

    # 第二排
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["配方類別"] = st.selectbox(
            "配方類別",
            ["原始配方", "附加配方"],
            index=["原始配方", "附加配方"].index(st.session_state.form_recipe["配方類別"])
            if st.session_state.form_recipe["配方類別"] in ["原始配方", "附加配方"]
            else 0
        )
    with col2:
        st.session_state.form_recipe["狀態"] = st.selectbox(
            "狀態",
            ["啟用", "停用"],
            index=["啟用", "停用"].index(st.session_state.form_recipe["狀態"])
            if st.session_state.form_recipe["狀態"] in ["啟用", "停用"]
            else 0
        )
    with col3:
        st.session_state.form_recipe["原始配方"] = st.text_input(
            "原始配方", st.session_state.form_recipe["原始配方"]
        )

    # 第三排
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.form_recipe["色粉類別"] = st.selectbox(
            "色粉類別",
            ["配方", "色母", "色粉", "添加劑", "其他"],
            index=["配方", "色母", "色粉", "添加劑", "其他"].index(st.session_state.form_recipe["色粉類別"])
            if st.session_state.form_recipe["色粉類別"] in ["配方", "色母", "色粉", "添加劑", "其他"]
            else 0
        )
    with col2:
        st.session_state.form_recipe["計量單位"] = st.selectbox(
            "計量單位",
            ["包", "桶", "kg", "其他"],
            index=["包", "桶", "kg", "其他"].index(st.session_state.form_recipe["計量單位"])
            if st.session_state.form_recipe["計量單位"] in ["包", "桶", "kg", "其他"]
            else 0
        )
    with col3:
        st.session_state.form_recipe["Pantone色號"] = st.text_input(
            "Pantone色號", st.session_state.form_recipe["Pantone色號"]
        )

    # 比例欄位 (修正單位顯示)
    col_ratio_1, col_colon, col_ratio_2, col_ratio_3 = st.columns([2.5, 0.5, 2.5, 2.5])
    with col_ratio_1:
        st.session_state.form_recipe["比例1"] = st.text_input(
            "比例欄位1", st.session_state.form_recipe["比例1"], label_visibility="collapsed"
        )
    with col_colon:
        st.markdown("<p style='text-align:center; font-weight:bold;'>:</p>", unsafe_allow_html=True)
    with col_ratio_2:
        st.session_state.form_recipe["比例2"] = st.text_input(
            "比例欄位2", st.session_state.form_recipe["比例2"], label_visibility="collapsed"
        )
    with col_ratio_3:
        ratio_value = st.text_input(
            "比例欄位3", st.session_state.form_recipe["比例3"], label_visibility="collapsed"
        )
        st.session_state.form_recipe["比例3"] = ratio_value
        unit_text = st.session_state.form_recipe["淨重單位"] or "g/kg"
        st.markdown(
            f"<span style='margin-left:10px;'>{unit_text}</span>",
            unsafe_allow_html=True
        )

    # 淨重 + 單位
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_recipe["淨重"] = st.text_input(
            "色粉淨重", st.session_state.form_recipe["淨重"]
        )
    with col2:
        st.session_state.form_recipe["淨重單位"] = st.selectbox(
            "單位",
            ["g", "kg"],
            index=["g", "kg"].index(st.session_state.form_recipe["淨重單位"])
            if st.session_state.form_recipe["淨重單位"] in ["g", "kg"]
            else 0
        )

    # 顯示標題列
    col_a, col_b, col_c = st.columns([3, 3, 1])
    col_a.markdown("**色粉編號**")
    col_b.markdown("**色粉重量**")
    col_c.markdown("&nbsp;", unsafe_allow_html=True)

    for i in range(1, 9):
        col_a, col_b, col_c = st.columns([3, 3, 1])
        with col_a:
            st.session_state.form_recipe[f"色粉編號{i}"] = st.text_input(
                f"色粉編號{i}",
                st.session_state.form_recipe[f"色粉編號{i}"],
                label_visibility="collapsed"
            )
        with col_b:
            st.session_state.form_recipe[f"色粉重量{i}"] = st.text_input(
                f"色粉重量{i}",
                st.session_state.form_recipe[f"色粉重量{i}"],
                label_visibility="collapsed"
            )
        with col_c:
            unit = st.session_state.form_recipe["淨重單位"] or "g/kg"
            st.markdown(f"<p style='text-align:left;'>{unit}</p>", unsafe_allow_html=True)

    # 合計類別
    st.session_state.form_recipe["合計類別"] = st.selectbox(
        "合計類別",
        ["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"],
        index=["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"].index(
            st.session_state.form_recipe["合計類別"]
        ) if st.session_state.form_recipe["合計類別"] in ["LA", "MA", "CA", "流動劑", "滑粉", "其他", "料", "T9"] else 0
    )

    # 儲存按鈕
    if st.button("💾 儲存"):
        new_data = st.session_state.form_recipe.copy()
        if new_data["配方編號"].strip() == "":
            st.warning("⚠️ 請輸入配方編號！")
        elif new_data["配方類別"] == "附加配方" and new_data["原始配方"].strip() == "":
            st.warning("⚠️ 附加配方必須填寫原始配方！")
        else:
            if st.session_state.edit_recipe_index is not None:
                df.iloc[st.session_state.edit_recipe_index] = new_data
                st.success("✅ 配方已更新！")
            else:
                if new_data["配方編號"] in df["配方編號"].values:
                    st.warning("⚠️ 此配方編號已存在！")
                else:
                    new_data["建檔時間"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增成功！")

            save_df_to_sheet(ws_recipe, df)
            st.session_state.form_recipe = {col: "" for col in columns}
            st.session_state.edit_recipe_index = None
            st.rerun()

    # 刪除確認
    if st.session_state.show_delete_recipe_confirm:
        target_row = df.iloc[st.session_state.delete_recipe_index]
        target_text = f'{target_row["配方編號"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("是"):
            df.drop(index=st.session_state.delete_recipe_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_recipe, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_recipe_confirm = False
            st.rerun()
        if c2.button("否"):
            st.session_state.show_delete_recipe_confirm = False
            st.rerun()

    # 配方清單
    if not df_filtered.empty:
        st.subheader("📋 配方清單序列")
        for i, row in df_filtered.iterrows():
            cols = st.columns([2, 2, 2, 2, 2])
            cols[0].write(row["配方編號"])
            cols[1].write(row["客戶編號"] + " / " + row["客戶名稱"])
            cols[2].write(row["顏色"])
            cols[3].write(row["Pantone色號"])
            cols[4].write(row["建檔時間"])
            with cols[4]:
                c1, c2 = st.columns(2, gap="small")
                if c1.button("✏️改", key=f"edit_recipe_{i}"):
                    st.session_state.edit_recipe_index = i
                    st.session_state.form_recipe = row.to_dict()
                    st.rerun()
                if c2.button("🗑️刪", key=f"delete_recipe_{i}"):
                    st.session_state.delete_recipe_index = i
                    st.session_state.show_delete_recipe_confirm = True
                    st.rerun()
