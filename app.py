# ===== app.py =====
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import json
import time

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
    st.title("🌈配方管理系統")
    with st.expander("🎏 展開 / 收合選單", expanded=True):
        menu = st.radio("請選擇模組", ["色粉管理", "客戶名單", "配方管理", "生產單管理"])

# ======== 初始化 session_state =========
def init_states(keys=None):
    if keys is None:
        keys = [
            "selected_order_code_edit",
            "editing_order",
            "show_edit_panel",
            "search_order_input",
            "order_page",
        ]
    for key in keys:
        if key not in st.session_state:
            if key.startswith("form_"):
                st.session_state[key] = {}
            elif key.startswith("edit_") or key.startswith("delete_"):
                st.session_state[key] = None
            elif key.startswith("show_"):
                st.session_state[key] = False
            elif key.startswith("search"):
                st.session_state[key] = ""
            elif key == "order_page":
                st.session_state[key] = 1
            else:
                st.session_state[key] = None

# ✅ 初始只處理生產單頁用的 key
init_states()

# --------------- 新增：列印專用 HTML 生成函式 ---------------
def generate_print_page_content(order, recipe_row, additional_recipe_row=None):
    if recipe_row is None:
        recipe_row = {}

    # 呼叫產生純文字列印內容函式
    content = generate_production_order_print(order, recipe_row, additional_recipe_row)
    created_time = order.get("建立時間", "")

    html_template = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>生產單列印</title>
        <style>
            @page {
                size: A5 landscape;
                margin: 10mm;
            }
            body {
                margin: 0;
            }
            .title {
                text-align: center;
                font-size: 24px;
                margin-bottom: -4px; /* 生產單與配方欄縮近 */
            }
            .timestamp {
                font-size: 12px;
                color: #000;  /* 改成純黑 */
                text-align: center;
                margin-bottom: 2px;
                font-family: Arial, Helvetica, sans-serif;
                font-weight: normal;
            }
            pre {
                white-space: pre-wrap;
                font-family: 'Courier New', Courier, monospace;
                font-size: 22px;
                line-height: 1.4;
                margin-left: 25px;
                margin-top: 0px;
            }
            b {
                font-weight: normal;
            }
        </style>
        <script>
            window.onload = function() {
                window.print();
            }
        </script>
    </head>
    <body>
        <div class="timestamp">{created_time}</div>
        <div class="title">生產單</div>
        <pre><code>{content}</code></pre>
    </body>
    </html>
    """

    html = html_template.replace("{created_time}", created_time).replace("{content}", content)
    return html


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
#-----
    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #0099cc; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">📜色粉搜尋🔎</div>', unsafe_allow_html=True)
#---

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

    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #0099cc; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🗿客戶搜尋🔎</div>', unsafe_allow_html=True)
  
    search_input = st.text_input("請輸入客戶編號或簡稱", st.session_state.search_customer)
    if search_input != st.session_state.search_customer:
        st.session_state.search_customer = search_input
    
    search = st.session_state.search_customer.strip()
    
    if search:
        df_filtered = df[
            df["客戶編號"].str.contains(search, case=False, na=False) |
            df["客戶簡稱"].str.contains(search, case=False, na=False)
        ]
    else:
        df_filtered = df

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

    from pathlib import Path
    from datetime import datetime
    import pandas as pd
    import streamlit as st

    # 載入「客戶名單」資料（假設來自 Google Sheet 工作表2）
    ws_customer = spreadsheet.worksheet("客戶名單")
    df_customers = pd.DataFrame(ws_customer.get_all_records())

    # 建立「客戶選單」選項，例如：["C001 - 三商行", "C002 - 光陽"]
    customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]

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

    def init_states(keys):
        for k in keys:
            if k not in st.session_state:
                st.session_state[k] = None

    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe_code",
        "search_pantone",
        "search_customer"
    ])

    # 初始 form_recipe
    if st.session_state.form_recipe is None:
        st.session_state.form_recipe = {col: "" for col in columns}

    # 讀取表單
    try:
        df = pd.DataFrame(ws_recipe.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)

    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    import streamlit as st

    if "df" not in st.session_state:
        try:
            df = pd.DataFrame(ws_recipe.get_all_records())
        except:
            df = pd.DataFrame(columns=columns)

        df = df.astype(str)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        st.session_state.df = df# 儲存進 session_state
    
    # ✅ 後續操作都從 session_state 中抓資料

    #-------
    df = st.session_state.df

    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #F9DC5C; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🎯配方搜尋🔎</div>', unsafe_allow_html=True)
  
    col1, col2, col3 = st.columns(3)
    with col1:
        search_recipe_top = st.text_input("配方編號", key="search_recipe_code_top")
    with col2:
        search_customer_top = st.text_input("客戶名稱或編號", key="search_customer_top")
    with col3:
        search_pantone_top = st.text_input("Pantone色號", key="search_pantone_top")

    # === 欄位定義 ===
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "重要提醒", "備註", "建檔時間"
    ]

    order_file = Path("data/df_recipe.csv")

    # 載入 Google Sheets
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customers = pd.DataFrame(ws_customer.get_all_records())
        customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]
    except:
        st.error("無法載入客戶名單")

    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except:
        ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)

    # 初始化 session_state
    def init_states(keys):
        for k in keys:
            if k not in st.session_state:
                st.session_state[k] = None

    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe_code",
        "search_pantone",
        "search_customer",
        "df"
    ])

    # 載入資料
    if st.session_state.df is None:
        try:
            values = ws_recipe.get_all_values()
            if len(values) > 1:
                df_loaded = pd.DataFrame(values[1:], columns=values[0]).astype(str)
            else:
                df_loaded = pd.DataFrame(columns=columns)
        except:
            if order_file.exists():
                df_loaded = pd.read_csv(order_file, dtype=str).fillna("")
            else:
                df_loaded = pd.DataFrame(columns=columns)
        for col in columns:
            if col not in df_loaded.columns:
                df_loaded[col] = ""
        st.session_state.df = df_loaded

    df = st.session_state.df

    # 初始化表單欄位
    if st.session_state.form_recipe is None or st.session_state.form_recipe == {}:
        st.session_state.form_recipe = {col: "" for col in columns}
    else:
        for col in columns:
            if col not in st.session_state.form_recipe:
                st.session_state.form_recipe[col] = ""

    fr = st.session_state.form_recipe

    st.subheader("➕ 新增 / 修改配方")

    with st.form("recipe_form"):

        col1, col2, col3 = st.columns(3)
        with col1:
            fr["配方編號"] = st.text_input("配方編號", value=fr["配方編號"], key="form_recipe_配方編號")
        with col2:
            fr["顏色"] = st.text_input("顏色", value=fr["顏色"], key="form_recipe_顏色")
        with col3:
            default_customer = next((opt for opt in customer_options if opt.startswith(fr["客戶編號"])), "")
            index = customer_options.index(default_customer) + 1 if default_customer else 0
            selected = st.selectbox("客戶編號", [""] + customer_options, index=index, key="form_recipe_selected_customer")
            客戶編號, 客戶簡稱 = selected.split(" - ", 1) if " - " in selected else ("", "")
            fr["客戶編號"] = 客戶編號
            fr["客戶名稱"] = 客戶簡稱

        col4, col5, col6 = st.columns(3)
        with col4:
            options = ["原始配方", "附加配方"]
            fr["配方類別"] = st.selectbox("配方類別", options, index=options.index(fr["配方類別"] or options[0]), key="form_recipe_配方類別")
        with col5:
            options = ["啟用", "停用"]
            fr["狀態"] = st.selectbox("狀態", options, index=options.index(fr["狀態"] or options[0]), key="form_recipe_狀態")
        with col6:
            fr["原始配方"] = st.text_input("原始配方", fr["原始配方"], key="form_recipe_原始配方")

        col7, col8, col9 = st.columns(3)
        with col7:
            options = ["配方", "色母", "色粉", "添加劑", "其他"]
            fr["色粉類別"] = st.selectbox("色粉類別", options, index=options.index(fr["色粉類別"] or options[0]), key="form_recipe_色粉類別")
        with col8:
            options = ["包", "桶", "kg", "其他"]
            fr["計量單位"] = st.selectbox("計量單位", options, index=options.index(fr["計量單位"] or options[0]), key="form_recipe_計量單位")
        with col9:
            fr["Pantone色號"] = st.text_input("Pantone色號", fr["Pantone色號"], key="form_recipe_Pantone色號")

        fr["重要提醒"] = st.text_input("重要提醒", value=fr["重要提醒"], key="form_recipe_重要提醒")

        colr1, colon, colr2, colr3, unit = st.columns([2, 1, 2, 2, 1])
        with colr1:
            fr["比例1"] = st.text_input("", fr["比例1"], key="ratio1", label_visibility="collapsed")
        with colon:
            st.markdown(":", unsafe_allow_html=True)
        with colr2:
            fr["比例2"] = st.text_input("", fr["比例2"], key="ratio2", label_visibility="collapsed")
        with colr3:
            fr["比例3"] = st.text_input("", fr["比例3"], key="ratio3", label_visibility="collapsed")
        with unit:
            st.markdown("g/kg", unsafe_allow_html=True)

        fr["備註"] = st.text_area("備註", value=fr["備註"], key="form_recipe_備註")

        col1, col2 = st.columns(2)
        with col1:
            fr["淨重"] = st.text_input("色粉淨重", fr["淨重"], key="form_recipe_淨重")
        with col2:
            options = ["g", "kg"]
            fr["淨重單位"] = st.selectbox("單位", options, index=options.index(fr["淨重單位"] or "g"), key="form_recipe_淨重單位")

        for i in range(1, 9):
            c1, c2, c3, c4 = st.columns([1, 3, 3, 1])
            with c1:
                st.write(f"色粉{i}")
            with c2:
                fr[f"色粉編號{i}"] = st.text_input(f"色粉編號{i}", fr[f"色粉編號{i}"], key=f"form_recipe_色粉編號{i}")
            with c3:
                fr[f"色粉重量{i}"] = st.text_input(f"色粉重量{i}", fr[f"色粉重量{i}"], key=f"form_recipe_色粉重量{i}")
            with c4:
                st.markdown(fr["淨重單位"], unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            fr["合計類別"] = st.text_input("合計類別", value=fr["合計類別"], key="form_recipe_合計類別")
        with col2:
            try:
                net = float(fr["淨重"] or "0")
                total = sum(float(fr[f"色粉重量{i}"] or "0") for i in range(1, 9))
                st.write(f"合計差額: {net - total:.2f} g/kg")
            except:
                st.write("合計差額: 計算錯誤")
        
        submitted = st.form_submit_button("💾 儲存配方")

        if submitted:
            if fr["配方編號"].strip() == "":
                st.warning("⚠️ 請輸入配方編號！")
            elif fr["配方類別"] == "附加配方" and fr["原始配方"].strip() == "":
                st.warning("⚠️ 附加配方必須填寫原始配方！")
            else:
                if st.session_state.edit_recipe_index is not None:
                    df.iloc[st.session_state.edit_recipe_index] = pd.Series(fr)
                    st.success(f"✅ 配方 {fr['配方編號']} 已更新！")
                else:
                    if fr["配方編號"] in df["配方編號"].values:
                        st.warning("⚠️ 此配方編號已存在！")
                    else:
                        fr["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df = pd.concat([df, pd.DataFrame([fr])], ignore_index=True)
                        st.success(f"✅ 新增配方 {fr['配方編號']} 成功！")

                try:
                    ws_recipe.clear()
                    ws_recipe.update([df.columns.tolist()] + df.values.tolist())
                    order_file.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(order_file, index=False, encoding="utf-8-sig")
                except Exception as e:
                    st.error(f"❌ 儲存失敗：{e}")
                    st.stop()

                st.session_state.df = df
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

    # --------- 客戶選單 ---------
    # 初始化布林遮罩（全部為 True）
    mask = pd.Series(True, index=df.index)

    # 初始化搜尋關鍵字，避免KeyError或型態錯誤
    for key in ["recipe_kw", "customer_kw", "pantone_kw"]:
        if key not in st.session_state:
            st.session_state[key] = ""
    
    recipe_kw = st.session_state.get("recipe_kw", "")
    if not isinstance(recipe_kw, str):
        recipe_kw = ""
    recipe_kw = recipe_kw.strip()
    
    customer_kw = st.session_state.get("customer_kw", "")
    if not isinstance(customer_kw, str):
        customer_kw = ""
    customer_kw = customer_kw.strip()
    
    pantone_kw = st.session_state.get("pantone_kw", "")
    if not isinstance(pantone_kw, str):
        pantone_kw = ""
    pantone_kw = pantone_kw.strip()

    # 依條件逐項過濾（多條件 AND）
    if recipe_kw:
        mask &= df["配方編號"].astype(str).str.contains(recipe_kw, case=False, na=False)

    if customer_kw:
        mask &= (
            df["客戶名稱"].astype(str).str.contains(customer_kw, case=False, na=False) |
            df["客戶編號"].astype(str).str.contains(customer_kw, case=False, na=False)
        )

    if pantone_kw:
        mask &= df["Pantone色號"].astype(str).str.contains(pantone_kw, case=False, na=False)

    # 套用遮罩，完成篩選
    df_filtered = df[mask]

    # 3. 唯一的主顯示區
    # --- 🔍 搜尋列區塊 ---

    st.subheader("🔎下方搜尋區")
    col1, col2, col3 = st.columns(3)
    with col1:
        search_recipe_bottom = st.text_input("配方編號", key="search_recipe_code_bottom")
    with col2:
        search_customer_bottom = st.text_input("客戶名稱或編號", key="search_customer_bottom")
    with col3:
        search_pantone_bottom = st.text_input("Pantone色號", key="search_pantone_bottom")

    # 先初始化 top 欄位變數
    search_recipe_top = ""
    search_customer_top = ""
    search_pantone_top = ""

    # 用這組輸入的資料做搜尋
    search_recipe = search_recipe_bottom or search_recipe_top
    search_customer = search_customer_bottom or search_customer_top
    search_pantone = search_pantone_bottom or search_pantone_top

    # 取搜尋關鍵字
    recipe_kw = (st.session_state.get("search_recipe_code_bottom") or st.session_state.get("search_recipe_code_top") or "").strip()
    customer_kw = (st.session_state.get("search_customer_bottom") or st.session_state.get("search_customer_top") or "").strip()
    pantone_kw = (st.session_state.get("search_pantone_bottom") or st.session_state.get("search_pantone_top") or "").strip()

    st.write(f"搜尋條件：配方編號={recipe_kw}, 客戶名稱={customer_kw}, Pantone={pantone_kw}")

    # 篩選
    mask = pd.Series(True, index=df.index)
    if recipe_kw:
        mask &= df["配方編號"].astype(str).str.contains(recipe_kw, case=False, na=False)
    if customer_kw:
       mask &= (
            df["客戶名稱"].astype(str).str.contains(customer_kw, case=False, na=False) |
            df["客戶編號"].astype(str).str.contains(customer_kw, case=False, na=False)
        )
    if pantone_kw:
        pantone_kw_clean = pantone_kw.replace(" ", "").upper()
        mask &= df["Pantone色號"].astype(str).str.replace(" ", "").str.upper().str.contains(pantone_kw_clean, na=False)

    df_filtered = df[mask]

    st.write("🎯 篩選後筆數：", df_filtered.shape[0])

    # --- 分頁設定 ---
    limit = st.selectbox("每頁顯示筆數", [10, 20, 50, 100], index=0)
    total_rows = df_filtered.shape[0]
    total_pages = max((total_rows - 1) // limit + 1, 1)

    # 初始化分頁 page
    if "page" not in st.session_state:
        st.session_state.page = 1

    # 搜尋條件改變時，分頁回到1
    search_id = (recipe_kw, customer_kw, pantone_kw)
    if "last_search_id" not in st.session_state or st.session_state.last_search_id != search_id:
        st.session_state.page = 1
        st.session_state.last_search_id = search_id

    start_idx = (st.session_state.page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx]

    # 計算目前頁面資料起迄索引
    start_idx = (st.session_state.page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx]

    # 4. 顯示資料表格區 (獨立塊)
    show_cols = ["配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方", "Pantone色號"]
    existing_cols = [c for c in show_cols if c in df_filtered.columns]

    st.markdown("---")  # 分隔線

    if not df_filtered.empty and existing_cols:
        st.dataframe(page_data[existing_cols], use_container_width=True)
    else:
        st.info("查無符合條件的配方。")

    # 5. 配方編號選擇 + 修改／刪除 按鈕群組，使用 columns 水平排列
    code_list = page_data["配方編號"].dropna().tolist()

    st.markdown("---")  # 分隔線

    cols = st.columns([3, 1, 1])  # 配方編號下拉+修改+刪除 按鈕
    with cols[0]:
        if code_list:
            if len(code_list) == 1:
                selected_code = code_list[0]
                st.info(f"🔹 自動選取唯一配方編號：{selected_code}")
            else:
                selected_code = st.selectbox("選擇配方編號", code_list, key="select_recipe_code_page")
        else:
            selected_code = None
            st.info("🟦 沒有可選的配方編號")

    with cols[1]:
        if selected_code and st.button("✏️ 修改", key="edit_btn"):
            df_idx = df[df["配方編號"] == selected_code].index[0]
            st.session_state.edit_recipe_index = df_idx
            st.session_state.form_recipe = df.loc[df_idx].to_dict()
            st.rerun()

    with cols[2]:
        if selected_code and st.button("🗑️ 刪除", key="del_btn"):
            df_idx = df[df["配方編號"] == selected_code].index[0]
            st.session_state.delete_recipe_index = df_idx
            st.session_state.show_delete_recipe_confirm = True
            st.rerun()

    # 6. 分頁控制按鈕 & 跳頁輸入欄，置於頁面底部並排
    cols_page = st.columns([1,1,1,2])
    with cols_page[0]:
        if st.button("回到首頁"):
            st.session_state.page = 1
    with cols_page[1]:
        if st.button("上一頁") and st.session_state.page > 1:
            st.session_state.page -= 1
    with cols_page[2]:
        if st.button("下一頁") and st.session_state.page < total_pages:
            st.session_state.page += 1
    with cols_page[3]:
        input_page = st.number_input("跳至頁碼", 1, total_pages, st.session_state.page)
        if input_page != st.session_state.page:
            st.session_state.page = input_page

    # 7. 分頁資訊顯示
    st.markdown(f"目前第 **{st.session_state.page}** / **{total_pages}** 頁，總筆數：{total_rows}")


    # --- 生產單分頁 ----------------------------------------------------
elif menu == "生產單管理":
    
    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #ff3366; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🚀生產單建立</div>', unsafe_allow_html=True)
    

    from pathlib import Path
    from datetime import datetime, timedelta
    import pandas as pd

    # ✅ 本地 CSV 路徑
    order_file = Path("data/df_order.csv")
    st.write("CSV 檔案完整路徑：", order_file.resolve())

    # ✅ 嘗試從 Google Sheets 載入生產單工作表
    try:
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法讀取『生產單』工作表：{e}")
        st.stop()

    # ✅ 初始化 df_order（優先使用 Google Sheets，再 fallback 到本地）
    if "df_order" not in st.session_state:
        try:
            values = ws_order.get_all_values()
            if values:
                st.session_state.df_order = pd.DataFrame(values[1:], columns=values[0]).astype(str)
            else:
                st.session_state.df_order = pd.DataFrame(columns=[
                    "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "建立時間",
                    "Pantone 色號", "計量單位", "原料",
                    "包裝重量1", "包裝重量2", "包裝重量3", "包裝重量4",
                    "包裝份數1", "包裝份數2", "包裝份數3", "包裝份數4",
                    "重要提醒",
                    "備註",
                    "色粉編號1", "色粉編號2", "色粉編號3", "色粉編號4",
                    "色粉編號5", "色粉編號6", "色粉編號7", "色粉編號8", "色粉合計",
                    "合計類別"
                ])
        except Exception as e:
            if order_file.exists():
                st.warning("⚠️ 無法連線 Google Sheets，改用本地 CSV")
                st.session_state.df_order = pd.read_csv(order_file, dtype=str).fillna("")
            else:
                st.error(f"❌ 無法讀取生產單資料：{e}")
                st.stop()

    # ✅ 後續統一使用 df_order
    df_order = st.session_state.df_order

    # 欄位標題
    header = list(df_order.columns)

    # 📦 嘗試載入 Google Sheets 的工作表
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法載入工作表：{e}")
        st.stop()

    if "df_recipe" not in st.session_state:
        try:
            records = ws_recipe.get_all_records()
            df_temp = pd.DataFrame(records)
            df_temp.columns = df_temp.columns.str.strip()
            df_temp.fillna("", inplace=True)
            st.session_state.df_recipe = df_temp
            st.write("配方管理資料載入成功")
        except Exception as e:
            st.error(f"❌ 讀取『配方管理』工作表失敗：{e}")
            st.stop()
    
    df_recipe = st.session_state.df_recipe

    sheet_names = [s.title for s in spreadsheet.worksheets()]
    
    # 檢查欄位是否已存在，若無則寫入
    existing_values = ws_order.get_all_values()
    if len(existing_values) == 0:
        ws_order.append_row(header)

    # 初始化 session_state
    for key in ["order_page", "editing_order", "show_edit_panel", "new_order", "show_confirm_panel"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "order_page" else 1

    # ---------- 搜尋及新增區 ----------
    st.subheader("🔎 配方搜尋與新增生產單")
    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")

        # 模糊搜尋
        if search_text:
            df_recipe["配方編號"] = df_recipe["配方編號"].astype(str)
            df_recipe["客戶名稱"] = df_recipe["客戶名稱"].astype(str)
            search_text = search_text.strip()
        
            if exact:
                filtered = df_recipe[
                    (df_recipe["配方編號"] == search_text) | (df_recipe["客戶名稱"] == search_text)
                ]
            else:
                filtered = df_recipe[
                    df_recipe["配方編號"].str.contains(search_text, case=False, na=False) |
                    df_recipe["客戶名稱"].str.contains(search_text, case=False, na=False)
                ]
        else:
            filtered = df_recipe.copy()

        # 建立選單選項顯示名稱
        def format_option(r):
            label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
            if r.get("配方類別", "") == "附加配方":
                label += "（附加配方）"
            return label

        # 生成下拉選單選項
        if not filtered.empty:
            options = filtered.apply(format_option, axis=1).tolist()
            default_option = options[0] if len(options) == 1 else "請選擇"
            select_options = [default_option] if default_option != "請選擇" else ["請選擇"] + options
            selected_label = st.selectbox("選擇配方", select_options, key="selected_recipe")
            selected_option = None if selected_label == "請選擇" else selected_label
        else:
            selected_option = None
            st.info("無法取得任何符合的配方")

        if add_btn:
            if not selected_option:
                st.warning("請先選擇配方")
            else:
                # 安全處理 idx
                idx = None
                for i, opt in enumerate(options):
                    if opt == selected_label:
                        idx = i
                        break
        
                if idx is None:
                    st.error("選擇的配方不在搜尋結果中")
                    st.stop()
        
                recipe_row = filtered.iloc[idx].to_dict()
        
                if recipe_row.get("狀態") == "停用":
                    st.warning("⚠️ 此配方已停用，請勿使用")
                    st.stop()
                else:
                    # ✅ 正確建立生產單號
                    df_all_orders = st.session_state.df_order.copy()
                    today_str = datetime.now().strftime("%Y%m%d")
                    count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
                    new_id = f"{today_str}-{count_today + 1:03}"
                    
                    # ✅ 查找附加配方（修正版）
                    main_recipe_code = recipe_row.get("配方編號", "").strip()
                    附加配方 = df_recipe[
                        (df_recipe["配方類別"] == "附加配方") &
                        (df_recipe["原始配方"] == main_recipe_code)
                    ]
                    additional_recipe_row = None
                    if not 附加配方.empty:
                        additional_recipe_row = 附加配方.iloc[0].to_dict()

                # ✅ 色粉合併處理：主配方 + 附加配方
                all_colorants = []
                for i in range(1, 9):
                    id_key = f"色粉編號{i}"
                    wt_key = f"色粉重量{i}"
                    id_val = recipe_row.get(id_key, "")
                    wt_val = recipe_row.get(wt_key, "")
                    if id_val or wt_val:
                        all_colorants.append((id_val, wt_val))

                for _, sub in 附加配方.iterrows():
                    for i in range(1, 9):
                        id_key = f"色粉編號{i}"
                        wt_key = f"色粉重量{i}"
                        id_val = sub.get(id_key, "")
                        wt_val = sub.get(wt_key, "")
                        if id_val or wt_val:
                            all_colorants.append((id_val, wt_val))

                
                # ✅ 建立生產單資料
                new_entry = {
                    "生產單號": new_id,
                    "生產日期": datetime.now().strftime("%Y-%m-%d"),
                    "建立時間": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                    "配方編號": recipe_row.get("配方編號", ""),
                    "顏色": recipe_row.get("顏色", ""),
                    "客戶名稱": recipe_row.get("客戶名稱", ""),
                    "Pantone 色號": recipe_row.get("Pantone色號", ""),
                    "計量單位": recipe_row.get("計量單位", ""),
                    "備註": str(recipe_row.get("備註", "")).strip(),
                    "重要提醒": str(recipe_row.get("重要提醒", "")).strip(),
                    "合計類別": str(recipe_row.get("合計類別", "")).strip(),
                }


                # ✅ 寫入色粉欄位（最多 8 筆，超過略過）
                colorant_total = 0
                for i in range(8):
                    id_val, wt_val = all_colorants[i] if i < len(all_colorants) else ("", "")
                    new_entry[f"色粉編號{i+1}"] = id_val
                    try:
                        wt = float(wt_val) if wt_val else 0
                    except:
                        wt = 0
                    colorant_total += wt
                    new_entry[f"色粉重量{i+1}"] = f"{wt:.2f}" if wt else ""

                new_entry["色粉合計"] = f"{colorant_total:.2f}"

                # ✅ 存入 session 狀態
                st.session_state.new_order = new_entry
                st.session_state.show_confirm_panel = True   

    # ===== 自訂函式：產生生產單列印格式 =====      
    def generate_production_order_print(order, recipe_row, additional_recipe_row=None):
        if recipe_row is None:
            recipe_row = {}
    
        unit = recipe_row.get("計量單位", "kg")
        ratio = recipe_row.get("比例3", "")
        total_type = recipe_row.get("合計類別", "").strip() or "合計"
    
        powder_label_width = 12
        pack_col_width = 11
        number_col_width = 6
        column_offsets = [1, 5, 5, 5.5]
        total_offsets = [1.3, 5, 5, 6]
    
        packing_weights = [
            float(order.get(f"包裝重量{i}", 0)) if str(order.get(f"包裝重量{i}", "")).replace(".", "", 1).isdigit() else 0
            for i in range(1, 5)
        ]
        packing_counts = [
            float(order.get(f"包裝份數{i}", 0)) if str(order.get(f"包裝份數{i}", "")).replace(".", "", 1).isdigit() else 0
            for i in range(1, 5)
        ]
    
        lines = []
        lines.append("")
    
        # 配方資訊列
        recipe_id = recipe_row.get('配方編號', '')
        color = order.get('顏色', '')
        pantone = order.get('Pantone 色號', '')
        info_line = f"編號：<b>{recipe_id:<8}</b>顏色：{color:<4}   比例：{ratio} g/kg   Pantone：{pantone}"
        lines.append(info_line)
        lines.append("")
    
        # 包裝列
        pack_line = []
        for i in range(4):
            w = packing_weights[i]
            c = packing_counts[i]
            if w > 0 or c > 0:
                if unit == "包":
                    real_w = w * 25
                    unit_str = f"{real_w:.0f}K"
                elif unit == "桶":
                    real_w = w * 100
                    unit_str = f"{real_w:.0f}K"
                else:
                    real_w = w
                    unit_str = f"{real_w:.2f}kg"
                count_str = str(int(c)) if c == int(c) else str(c)
                text = f"{unit_str} × {count_str}"
                pack_line.append(f"{text:<{pack_col_width}}")
        packing_indent = " " * 14
        lines.append(packing_indent + "".join(pack_line))
    
        # 主配方色粉列
        colorant_ids = [recipe_row.get(f"色粉編號{i+1}", "") for i in range(8)]
        colorant_weights = []
        for i in range(8):
            try:
                val_str = recipe_row.get(f"色粉重量{i+1}", "") or "0"
                val = float(val_str)
            except:
                val = 0.0
            colorant_weights.append(val)
    
        multipliers = packing_weights
    
        for idx in range(8):
            c_id = colorant_ids[idx]
            c_weight = colorant_weights[idx]
            if not c_id:
                continue
            row = f"<b>{c_id.ljust(powder_label_width)}</b>"
            for i in range(4):
                val = c_weight * multipliers[i] if multipliers[i] > 0 else 0
                val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
                padding = " " * max(0, int(round(column_offsets[i])))
                row += padding + f"<b>{val_str:>{number_col_width}}</b>"
            lines.append(row)
    
        lines.append("＿" * 30)
    
        # 合計列
        try:
            net_weight = float(recipe_row.get("淨重", 0))
        except:
            net_weight = 0.0
        total_line = total_type.ljust(powder_label_width)
        for i in range(4):
            result = net_weight * multipliers[i] if multipliers[i] > 0 else 0
            val_str = f"{result:.2f}".rstrip('0').rstrip('.') if result else ""
            padding = " " * max(0, int(round(total_offsets[i])))
            total_line += padding + f"<b class='total-num'>{val_str:>{number_col_width}}</b>"
        lines.append(total_line)
    
        # 附加配方列印
        # === 附加配方（如果有）===
        if additional_recipe_row:
            lines.append("")  # 空一行分隔
            lines.append("附加配方色粉")
            add_colorant_ids = [additional_recipe_row.get(f"色粉編號{i+1}", "") for i in range(8)]
            add_colorant_weights = []
            for i in range(8):
                try:
                    val = float(additional_recipe_row.get(f"色粉重量{i+1}", 0) or 0)
                except:
                    val = 0.0
                add_colorant_weights.append(val)
            for idx, c_id in enumerate(add_colorant_ids):
                if not c_id:
                    continue
                c_id_str = str(c_id or "")
                row = f"<b>{c_id_str.ljust(powder_label_width)}</b>"
                for i in range(4):
                    val = add_colorant_weights[idx] * multipliers[i] if multipliers[i] > 0 else 0
                    val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
                    padding = " " * max(0, int(round(column_offsets[i])))
                    row += padding + f"<b>{val_str:>{number_col_width}}</b>"
                lines.append(row)
    
            # 附加配方淨重
            try:
                add_net_weight = float(additional_recipe_row.get("淨重", 0))
            except:
                add_net_weight = 0.0
            lines.append(f"\n附加配方淨重: {add_net_weight:.2f} {additional_recipe_row.get('淨重單位', '')}")
    
        lines.append("")
        lines.append(f"備註 : {order.get('備註', '')}")
    
        return "\n".join(lines)
          
    # ---------- 新增後欄位填寫區塊 ----------
    # ===== 主流程頁面切換 =====
    page = st.session_state.get("page", "新增生產單")
    if page == "新增生產單":
        order = st.session_state.get("new_order")
        if order is None or not isinstance(order, dict):
            order = {}
    
        recipe_id = order.get("配方編號", "").strip()
    
        # 取得配方資料
        matched = df_recipe[df_recipe["配方編號"] == recipe_id]
        if not matched.empty:
            recipe_row = matched.iloc[0].to_dict()
            # 清理欄位名稱及欄位值，確保都轉成乾淨字串且避免 None/NaN
            recipe_row = {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in recipe_row.items()}
            st.session_state["recipe_row_cache"] = recipe_row
            show_confirm_panel = True  # 有配方資料，顯示新增生產單區塊
        else:
            recipe_row = {}  # 空 dict 避免 None
            show_confirm_panel = False  # 無配方資料，不顯示新增生產單區塊
    
        # 強制帶入配方欄位值，避免原本 order 已有空字串導致沒更新
        for field in ["合計類別", "備註", "重要提醒"]:
            order[field] = recipe_row.get(field, "")
        
        st.session_state.new_order = order
        st.session_state.show_confirm_panel = show_confirm_panel
    
        # 搜尋或配方存在時才顯示新增生產單表單
        if st.session_state.get("show_confirm_panel"):
            unit = recipe_row.get("計量單位", "kg") if recipe_row else "kg"
            print_html = generate_print_page_content(order, recipe_row)
    
            st.markdown("---")
            st.subheader("新增生產單詳情填寫")
    
            # 不可編輯欄位
            c1, c2, c3, c4 = st.columns(4)
            c1.text_input("生產單號", value=order.get("生產單號", ""), disabled=True)
            c2.text_input("配方編號", value=order.get("配方編號", ""), disabled=True)
            c3.text_input("客戶編號", value=recipe_row.get("客戶編號", ""), disabled=True)
            c4.text_input("客戶名稱", value=order.get("客戶名稱", ""), disabled=True)
    
            with st.form("order_detail_form"):
                c5, c6, c7, c8 = st.columns(4)
                c5.text_input("計量單位", value=unit, disabled=True)
                color = c6.text_input("顏色", value=order.get("顏色", ""), key="form_color")
                pantone = c7.text_input("Pantone 色號", value=order.get("Pantone 色號", recipe_row.get("Pantone色號", "")), key="form_pantone")
                raw_material = c8.text_input("原料", value=order.get("原料", ""), key="form_raw_material")
    
                c9, c10 = st.columns(2)
                important_note = c9.text_input("重要提醒", value=order.get("重要提醒", ""), key="form_important_note")
                total_category = c10.text_input("合計類別", value=order.get("合計類別", ""), key="form_total_category")
                remark_default = order.get("備註", "")
                remark = st.text_area("備註", value=remark_default, key="form_remark")

    
                st.markdown("**包裝重量與份數**")
                w_cols = st.columns(4)
                c_cols = st.columns(4)
                weights = []
                counts = []
                for i in range(1, 5):
                    w = w_cols[i - 1].text_input(f"包裝重量{i}", value=order.get(f"包裝重量{i}", ""), key=f"form_weight{i}")
                    c = c_cols[i - 1].text_input(f"包裝份數{i}", value=order.get(f"包裝份數{i}", ""), key=f"form_count{i}")
                    weights.append(w)
                    counts.append(c)
    
                st.markdown("### 色粉用量（編號與重量）")
                色粉編號欄, 色粉重量欄 = st.columns(2)
                for i in range(1, 9):
                    with 色粉編號欄:
                        st.text_input(f"色粉編號{i}", value=recipe_row.get(f"色粉編號{i}", ""), disabled=True, key=f"form_color_id_{i}")
                    with 色粉重量欄:
                        st.text_input(f"色粉重量{i}", value=recipe_row.get(f"色粉重量{i}", ""), disabled=True, key=f"form_color_weight_{i}")
                # 顯示配方淨重（表格外、右下角）
                st.markdown(
                    f"<div style='text-align:right; font-size:16px; margin-top:-10px;'>🔢 配方淨重：{recipe_row.get('淨重', '')} {recipe_row.get('淨重單位', '')}</div>",
                    unsafe_allow_html=True
                )
                # --- 新增：附加配方色粉顯示 ---
                附加配方 = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"] == recipe_row.get("配方編號", ""))
                 ]
                if not 附加配方.empty:
                    st.markdown("### 附加配方色粉用量（編號與重量）")
                    idx = 1
                    for _, sub in 附加配方.iterrows():
                        st.markdown(f"#### 附加配方：{sub.get('配方編號', '')}")
                        add_color_id_col, add_color_wt_col = st.columns(2)
                        for i in range(1, 9):
                            with add_color_id_col:
                                st.text_input(f"附加色粉編號_{idx}_{i}", value=sub.get(f"色粉編號{i}", ""), disabled=True, key=f"form_add_color_id_{idx}_{i}")
                            with add_color_wt_col:
                                st.text_input(f"附加色粉重量_{idx}_{i}", value=sub.get(f"色粉重量{i}", ""), disabled=True, key=f"form_add_color_wt_{idx}_{i}")
                        idx += 1
                
                    # ✅ 附加配方總淨重顯示（只在有附加配方時顯示）
                    total_net = 0
                    for _, sub in 附加配方.iterrows():
                        try:
                            total_net += float(sub.get("淨重", 0))
                        except:
                            continue
                
                    unit = 附加配方.iloc[0].get("淨重單位", "")
                    st.markdown(
                        f"<div style='text-align:right; font-size:16px;'>📦 附加配方總淨重：{total_net:.2f} {unit}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.info("無附加配方色粉")

                   
                submitted = st.form_submit_button("💾 儲存生產單")
    
            if submitted:
                order["顏色"] = st.session_state.form_color
                order["Pantone 色號"] = st.session_state.form_pantone
                order["原料"] = st.session_state.form_raw_material
                order["備註"] = st.session_state.form_remark
                order["重要提醒"] = st.session_state.form_important_note
                order["合計類別"] = st.session_state.form_total_category
    
                for i in range(1, 5):
                    order[f"包裝重量{i}"] = st.session_state.get(f"form_weight{i}", "").strip()
                    order[f"包裝份數{i}"] = st.session_state.get(f"form_count{i}", "").strip()
    
                # 儲存色粉編號與重量
                for i in range(1, 9):
                    key_id = f"色粉編號{i}"
                    key_weight = f"色粉重量{i}"
                    order[key_id] = recipe_row.get(key_id, "")
                    order[key_weight] = recipe_row.get(key_weight, "")
                
                
                # 計算色粉合計
                net_weight = float(recipe_row.get("淨重", 0))
                color_weight_list = []
                for i in range(1, 5):
                    try:
                        w_str = st.session_state.get(f"form_weight{i}", "").strip()
                        weight = float(w_str) if w_str else 0.0
                        if weight > 0:
                            color_weight_list.append({
                                "項次": i,
                                "重量": weight,
                                "結果": net_weight * weight
                            })
                    except:
                        continue
                order["色粉合計清單"] = color_weight_list
                order["色粉合計類別"] = recipe_row.get("合計類別", "")
                

                # ➕ 寫入 Google Sheets、CSV 等流程
                header = [col for col in df_order.columns if col and str(col).strip() != ""]
                row_data = [str(order.get(col, "")).strip() if order.get(col) is not None else "" for col in header]
                try:
                    ws_order.append_row(row_data)
                    df_new = pd.DataFrame([order], columns=df_order.columns)
                    df_order = pd.concat([df_order, df_new], ignore_index=True)
                    df_order.to_csv("data/order.csv", index=False, encoding="utf-8-sig")
                    st.session_state.df_order = df_order
                    st.session_state.new_order_saved = True
                    st.success(f"✅ 生產單 {order['生產單號']} 已存！")
                except Exception as e:
                    st.error(f"❌ 寫入失敗：{e}")

            # 在此先找附加配方
            main_recipe_code = recipe_row.get("配方編號", "").strip()
            附加配方 = df_recipe[
                (df_recipe["配方類別"] == "附加配方") &
                (df_recipe["原始配方"] == main_recipe_code)
            ]
            additional_recipe_row = None
            if not 附加配方.empty:
                additional_recipe_row = 附加配方.iloc[0].to_dict()
            
            print_html = generate_print_page_content(order, recipe_row, additional_recipe_row)
            st.download_button(
                label="📥 下載 A5 HTML",
                data=print_html.encode("utf-8"),
                file_name=f"{order['生產單號']}_列印.html",
                mime="text/html"
            )
            
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.session_state.get("new_order_saved"):
                    st.warning("⚠️ 生產單已存")
            with btn2:
                if st.button("🔙 返回", key="back_button"):
                    st.session_state.new_order = None
                    st.session_state.show_confirm_panel = False
                    st.session_state.new_order_saved = False
                    st.rerun()
            
            # 另一個下載連結（選擇性）
            if st.session_state.get("new_order_saved"):
                html_content = generate_print_page_content(order, recipe_row, additional_recipe_row)
                b64 = base64.b64encode(html_content.encode("utf-8")).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="生產單.html">📥 下載生產單 HTML (A5列印)</a>'
                st.markdown(href, unsafe_allow_html=True)
                
                # ---------- 生產單清單 + 修改 / 刪除 ----------
                st.markdown("---")
                st.subheader("📄 生產單清單")
                
                search_order = st.text_input("搜尋生產單 (生產單號 配方編號 客戶名稱 顏色)", key="search_order_input_order_page", value="")
                
                # 初始化 order_page
                if "order_page" not in st.session_state:
                    st.session_state.order_page = 1
    
    # 篩選條件
    if search_order.strip():
        mask = (
            df_order["生產單號"].astype(str).str.contains(search_order, case=False, na=False) |
            df_order["配方編號"].astype(str).str.contains(search_order, case=False, na=False) |
            df_order["客戶名稱"].astype(str).str.contains(search_order, case=False, na=False) |
            df_order["顏色"].astype(str).str.contains(search_order, case=False, na=False)
        )
        df_filtered = df_order[mask].copy()
        df_filtered["建立時間"] = pd.to_datetime(df_filtered["建立時間"], errors="coerce")
        df_filtered = df_filtered.sort_values(by="建立時間", ascending=False)
    else:
        df_order["建立時間"] = pd.to_datetime(df_order["建立時間"], errors="coerce")
        df_filtered = df_order.sort_values(by="建立時間", ascending=False)
    
    limit = st.selectbox("每頁顯示筆數", [10, 20, 50], index=0, key="selectbox_order_limit")
    
    total_rows = len(df_filtered)
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    # 修正 order_page 範圍，避免超出
    st.session_state.order_page = max(1, min(st.session_state.order_page, total_pages))
    start_idx = (st.session_state.order_page - 1) * limit
    page_data = df_filtered.iloc[start_idx:start_idx + limit].copy()  # 使用 copy 避免警告
    
    # 產生下拉選單選項，依建立時間由近到遠排序
    page_data = page_data.sort_values(by="建立時間", ascending=False)
    options = []
    code_to_id = {}
    for idx, row in page_data.iterrows():
        label = f"{row['生產單號']} / {row['配方編號']} / {row.get('顏色', '')} / {row.get('客戶名稱', '')}"
        options.append(label)
        code_to_id[label] = row["生產單號"]
    
    selected_label = st.selectbox("選擇生產單號", options, key="select_order_for_edit_from_list")
    selected_code_edit = code_to_id.get(selected_label)
    
    def calculate_shipment(row):
        try:
            unit = str(row.get("計量單位", "")).strip()
            formula_id = str(row.get("配方編號", "")).strip()
            multipliers = {"包": 25, "桶": 100, "kg": 1}
            unit_labels = {"包": "K", "桶": "K", "kg": "kg"}
    
            if not formula_id:
                return ""
    
            try:
                matched = df_recipe.loc[df_recipe["配方編號"] == formula_id, "色粉類別"]
                category = matched.values[0] if not matched.empty else ""
            except Exception:
                category = ""
    
            if unit == "kg" and category == "色母":
                multiplier = 100
                label = "K"
            else:
                multiplier = multipliers.get(unit, 1)
                label = unit_labels.get(unit, "")
    
            results = []
            for i in range(1, 5):
                try:
                    weight = float(row.get(f"包裝重量{i}", 0))
                    count = int(float(row.get(f"包裝份數{i}", 0)))
                    if weight > 0 and count > 0:
                        show_weight = int(weight * multiplier) if label == "K" else weight
                        results.append(f"{show_weight}{label}*{count}")
                except Exception:
                    continue
    
            return " + ".join(results) if results else ""
    
        except Exception as e:
            st.error(f"calculate_shipment error at row index {row.name}: {e}")
            st.write(row)
            return ""
    
    # 計算出貨數量並加入新欄位
    if not page_data.empty:
        shipment_series = page_data.apply(calculate_shipment, axis=1)
        page_data["出貨數量"] = shipment_series
    
        # 顯示表格（去除生產日期欄位）
        st.dataframe(
            page_data[["生產單號", "配方編號", "顏色", "客戶名稱", "出貨數量", "建立時間"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("查無符合的生產單")
    
    # 分頁控制列（始終顯示）
    cols_page = st.columns([1, 1, 1, 2])
    if cols_page[0].button("首頁"):
        st.session_state.order_page = 1
        st.experimental_rerun()
    if cols_page[1].button("上一頁") and st.session_state.order_page > 1:
        st.session_state.order_page -= 1
        st.experimental_rerun()
    if cols_page[2].button("下一頁") and st.session_state.order_page < total_pages:
        st.session_state.order_page += 1
        st.experimental_rerun()
    
    jump_page = cols_page[3].number_input("跳至頁碼", 1, total_pages, st.session_state.order_page)
    if jump_page != st.session_state.order_page:
        st.session_state.order_page = jump_page
        st.experimental_rerun()
    
    st.caption(f"頁碼 {st.session_state.order_page} / {total_pages}，總筆數 {total_rows}")
    
    # 修改 & 刪除功能區塊
    codes = df_order["生產單號"].tolist()
    cols_mod = st.columns([1, 1])
    
    with cols_mod[0]:
        if st.button("✏️ 修改", key="edit_button_1") and selected_code_edit:
            row = df_order[df_order["生產單號"] == selected_code_edit]
            if not row.empty:
                st.session_state.editing_order = row.iloc[0].to_dict()
                st.session_state.show_edit_panel = True
            else:
                st.warning("找不到該筆生產單")
    
    with cols_mod[1]:
        if st.button("🗑️ 刪除", key="delete_button_1") and selected_code_edit:
            try:
                cell = ws_order.find(selected_code_edit)
                if cell:
                    ws_order.delete_rows(cell.row)
                    st.success(f"✅ 已從 Google Sheets 刪除生產單 {selected_code_edit}")
                else:
                    st.warning("⚠️ Google Sheets 找不到該筆生產單，無法刪除")
            except Exception as e:
                st.error(f"Google Sheets 刪除錯誤：{e}")
    
            # 同步刪除本地資料
            df_order = df_order[df_order["生產單號"] != selected_code_edit]
            df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
            st.session_state.df_order = df_order
            st.success(f"✅ 本地資料也已刪除生產單 {selected_code_edit}")
    
            # 清理狀態並重新整理
            st.session_state.pop("selected_order_code_edit", None)
            st.session_state.show_edit_panel = False
            st.session_state.editing_order = None
            st.rerun()
    
    # 顯示修改面板
    if st.session_state.get("show_edit_panel") and st.session_state.get("editing_order"):
        st.markdown("---")
        st.subheader(f"✏️ 修改生產單 {st.session_state.editing_order['生產單號']}")
    
        edit_order = st.session_state.editing_order
    
        new_customer = st.text_input("客戶名稱", value=edit_order.get("客戶名稱", ""), key="edit_customer_name")
        new_color = st.text_input("顏色", value=edit_order.get("顏色", ""), key="edit_color")
    
        # 包裝重量 1~4
        pack_weights_cols = st.columns(4)
        new_packing_weights = []
        for i in range(1, 5):
            weight = pack_weights_cols[i - 1].text_input(
                f"包裝重量{i}", value=edit_order.get(f"包裝重量{i}", ""), key=f"edit_packing_weight_{i}"
            )
            new_packing_weights.append(weight)
    
        # 包裝份數 1~4
        pack_counts_cols = st.columns(4)
        new_packing_counts = []
        for i in range(1, 5):
            count = pack_counts_cols[i - 1].text_input(
                f"包裝份數{i}", value=edit_order.get(f"包裝份數{i}", ""), key=f"edit_packing_count_{i}"
            )
            new_packing_counts.append(count)
    
        new_remark = st.text_area("備註", value=edit_order.get("備註", ""), key="edit_remark")
    
        # 先取得對應配方資料
        recipe_id = edit_order.get("配方編號", "")
        recipe_rows = df_recipe[df_recipe["配方編號"] == recipe_id]
        if recipe_rows.empty:
            st.warning(f"找不到配方編號：{recipe_id}")
            st.stop()
        recipe_row = recipe_rows.iloc[0]
    
        # 產生 HTML 預覽內容
        print_html = generate_print_page_content(edit_order, recipe_row)
    
        import urllib.parse
        print_html = generate_print_page_content(edit_order, recipe_row)
        encoded_html = urllib.parse.quote(print_html)
    
        st.markdown(
            f"[👉 點此開啟列印頁面（新分頁，會自動叫出列印）](data:text/html;charset=utf-8,{encoded_html})",
            unsafe_allow_html=True,
        )
        st.download_button(
            label="📄 下載列印 HTML",
            data=print_html.encode("utf-8"),
            file_name=f"{edit_order['生產單號']}_print.html",
            mime="text/html"
        )
    
        cols_edit = st.columns([1, 1, 1])
    
        with cols_edit[0]:
            if st.button("儲存修改", key="save_edit_button"):
                idx_list = df_order.index[df_order["生產單號"] == edit_order["生產單號"]].tolist()
                if idx_list:
                    idx = idx_list[0]
    
                    # 更新本地 DataFrame
                    df_order.at[idx, "客戶名稱"] = new_customer
                    df_order.at[idx, "顏色"] = new_color
                    for i in range(4):
                        df_order.at[idx, f"包裝重量{i + 1}"] = new_packing_weights[i]
                        df_order.at[idx, f"包裝份數{i + 1}"] = new_packing_counts[i]
                    df_order.at[idx, "備註"] = new_remark
    
                    # 同步更新 Google Sheets
                    try:
                        cell = ws_order.find(edit_order["生產單號"])
                        if cell:
                            row_idx = cell.row
                            row_data = df_order.loc[idx].fillna("").astype(str).tolist()
                            last_col_letter = chr(65 + len(row_data) - 1)
                            ws_order.update(f"A{row_idx}:{last_col_letter}{row_idx}", [row_data])
                            st.success("✅ Google Sheets 同步更新成功")
                        else:
                            st.warning("⚠️ Google Sheets 找不到該筆生產單，未更新")
                    except Exception as e:
                        st.error(f"Google Sheets 更新錯誤：{e}")
    
                    # 寫入本地檔案
                    os.makedirs(os.path.dirname(order_file), exist_ok=True)
                    df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
                    st.session_state.df_order = df_order
                    st.success("✅ 本地資料更新成功，修改已儲存")
    
                    # 不關閉編輯面板，方便繼續預覽或再修改
                    # st.session_state.show_edit_panel = False
                    # st.session_state.editing_order = None
    
                    st.rerun()
                else:
                    st.error("⚠️ 找不到該筆生產單資料")
    
        with cols_edit[1]:
            if st.button("返回", key="return_button"):
                st.session_state.show_edit_panel = False
                st.session_state.editing_order = None
                st.experimental_rerun()
