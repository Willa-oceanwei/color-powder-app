# ===== app.py =====
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import json
import time
import base64

# 自訂 CSS，針對 key="myselect" 的 selectbox 選項背景色調整
st.markdown(
    """
    <style>
    /* 選中項目背景色 */
    .st-key-myselect [data-baseweb="option"][aria-selected="true"] {
        background-color: #999999 !important;  /* 淺灰 */
        color: black !important;
        font-weight: bold;
    }
    /* 滑鼠滑過項目背景色 */
    .st-key-myselect [data-baseweb="option"]:hover {
        background-color: #bbbbbb !important;  /* 更淺灰 */
        color: black !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
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
import streamlit as st

menu_options = ["色粉管理", "客戶名單", "配方管理", "生產單管理", "匯入備份"]

if "menu" not in st.session_state:
    st.session_state.menu = "生產單管理"

with st.sidebar:
    st.title("🌈配方管理系統")
    with st.expander("🎏 展開 / 收合選單", expanded=True):
        selected_menu = st.radio(
            "請選擇模組",
            menu_options,
            key="menu"  # 會直接讀寫 st.session_state.menu
        )

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

# ===== 安全轉數字 =====
def safe_float(val):
    try:
        return float(str(val).strip()) if val not in [None, ""] else 0.0
    except:
        return 0.0

# ===== 整合版自訂函式：新增生產單 A5 列印（含安全格式化，色粉色母） =====
def generate_production_order_print_integrated(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}
    if additional_recipe_rows is None:
        additional_recipe_rows = []

    lines = []
    powder_label_width = 12
    number_col_width = 8
    pack_col_width = 12

    # Multipliers: 對應 4 欄包裝/計算
    multipliers = []
    for i in range(1, 5):
        w = safe_float(order.get(f"包裝重量{i}", 0))
        c = safe_float(order.get(f"包裝份數{i}", 0))
        multipliers.append(w * c if w > 0 and c > 0 else 0)

    # ---------- 包裝列 ----------
    pack_line = []
    unit = str(order.get("計量單位") or recipe_row.get("計量單位", "包"))
    for i in range(4):
        w = safe_float(order.get(f"包裝重量{i+1}", 0))
        c = safe_float(order.get(f"包裝份數{i+1}", 0))
        if w > 0 or c > 0:
            # 計算 real_w
            if unit == "包":
                real_w = w * 25
                unit_str = f"{real_w:.2f}".rstrip('0').rstrip('.') + "K"
            elif unit == "桶":
                real_w = w * 100
                unit_str = f"{real_w:.2f}".rstrip('0').rstrip('.') + "K"
            else:
                real_w = w
                unit_str = f"{real_w:.2f}".rstrip('0').rstrip('.') + "kg"
            count_str = str(int(c)) if c == int(c) else str(c)
            pack_line.append(f"{unit_str} × {count_str}".ljust(pack_col_width))
    if pack_line:
        lines.append(" " * 14 + "".join(pack_line))

    # ---------- 主配方色粉列 ----------
    for idx in range(1, 9):
        c_id = recipe_row.get(f"色粉編號{idx}", "")
        c_wt = safe_float(recipe_row.get(f"色粉重量{idx}", 0))
        if not c_id and c_wt == 0:
            continue
        row = f"<b>{str(c_id).ljust(powder_label_width)}</b>"
        for i in range(4):
            val = c_wt * multipliers[i] if multipliers[i] > 0 else 0
            # 顯示 real_w × count
            if val > 0:
                val_str = f"{val:.2f}".rstrip('0').rstrip('.')
            else:
                val_str = ""
            row += f"<b>{val_str:>{number_col_width}}</b>"
        lines.append(row)

    # ---------- 附加配方色粉 ----------
    for add in additional_recipe_rows:
        for idx in range(1, 9):
            c_id = add.get(f"色粉編號{idx}", "")
            c_wt = safe_float(add.get(f"色粉重量{idx}", 0))
            if not c_id and c_wt == 0:
                continue
            row = f"<b>{str(c_id).ljust(powder_label_width)}</b>"
            for i in range(4):
                val = c_wt * multipliers[i] if multipliers[i] > 0 else 0
                val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
                row += f"<b>{val_str:>{number_col_width}}</b>"
            lines.append(row)

    # ---------- 色粉橫線 ----------
    lines.append("＿" * 30)

    # ---------- 色母合計 ----------
    try:
        net_weight = safe_float(recipe_row.get("淨重", 0))
    except:
        net_weight = 0.0

    total_color_weight = 0.0
    for i in range(1, 9):
        total_color_weight += safe_float(recipe_row.get(f"色粉重量{i}", 0))
    for add in additional_recipe_rows:
        for i in range(1, 9):
            total_color_weight += safe_float(add.get(f"色粉重量{i}", 0))

    total_line = str(order.get("合計類別") or recipe_row.get("合計類別", "無")).ljust(powder_label_width)
    for i in range(4):
        val = (net_weight - total_color_weight) * multipliers[i] if multipliers[i] > 0 else 0
        val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
        total_line += f"<b class='total-num'>{val_str:>{number_col_width}}</b>"
    lines.append(total_line)

    # ---------- 色母換算顯示（real_w × count 格式） ----------
    if "色母" in recipe_row:  # 假如有色母欄位
        colorant_wt = safe_float(recipe_row.get("色母", 0))
        row = f"<b>{'色母'.ljust(powder_label_width)}</b>"
        for i in range(4):
            val = colorant_wt * multipliers[i] if multipliers[i] > 0 else 0
            val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
            row += f"<b>{val_str:>{number_col_width}}</b>"
        lines.append(row)

    # ---------- Pantone ----------
    pantone = order.get("Pantone 色號") or recipe_row.get("Pantone色號", "")
    if pantone:
        lines.append(f"Pantone: {pantone}")

    return "\n".join(lines)
    
# --------------- 外層 HTML 包裝函式（安全列印下載） ---------------
def generate_print_page_content(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    """
    將生產單內容整合成完整 HTML 頁面，含標題、建立時間、字體與自動列印
    """
    if recipe_row is None:
        recipe_row = {}
    if additional_recipe_rows is None:
        additional_recipe_rows = []

    # 如果只有一筆 dict，包成 list
    if additional_recipe_rows is not None and not isinstance(additional_recipe_rows, list):
        additional_recipe_rows = [additional_recipe_rows]

    # ✅ 傳入 show_additional_ids 給產生列印內容的函式
    content = generate_production_order_print_integrated(
        order=order,
        recipe_row=recipe_row,
        additional_recipe_rows=additional_recipe_rows,
        show_additional_ids=show_additional_ids
    )
    created_time = order.get("建立時間", "")

    html_template = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>生產單列印</title>
        <style>
            @page {{
                size: A5 landscape;
                margin: 10mm;
            }}
            body {{
                margin: 0;
            }}
            .title {{
                text-align: center;
                font-size: 24px;
                margin-bottom: -4px;
                font-family: Arial, Helvetica, sans-serif;
            }}
            .timestamp {{
                font-size: 12px;
                color: #000;
                text-align: center;
                margin-bottom: 2px;
                font-family: Arial, Helvetica, sans-serif;
                font-weight: normal;
            }}
            pre {{
                white-space: pre-wrap;
                font-family: 'Courier New', Courier, monospace;
                font-size: 22px;
                line-height: 1.4;
                margin-left: 25px;
                margin-top: 0px;
            }}
            b {{
                font-weight: normal;
            }}
        </style>
        <script>
            window.onload = function() {{
                window.print();
            }}
        </script>
    </head>
    <body>
        <div class="timestamp">{created_time}</div>
        <div class="title">生產單</div>
        <pre><code>{content}</code></pre>
    </body>
    </html>
    """

    return html_template

# ======== 共用儲存函式 =========
def save_df_to_sheet(ws, df):
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update("A1", values)

menu = st.session_state.menu  # 先從 session_state 取得目前選擇
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
    
    search = (st.session_state.search_customer or "").strip()
    
    if search:
        df_filtered = df[
            df["客戶編號"].str.contains(search, case=False, na=False) |
            df["客戶簡稱"].str.contains(search, case=False, na=False)
        ]
    else:
        df_filtered = df

    search_customer = st.session_state.get("search_customer")
    if isinstance(search_customer, str) and search_customer.strip() and df_filtered.empty:
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
    # === 載入「色粉管理」的色粉清單，建立 existing_powders ===
    def clean_powder_id(x):
        s = str(x).replace('\u3000', '').replace(' ', '').strip().upper()
        return s
    
    # 讀取色粉管理清單
    try:
        ws_powder = spreadsheet.worksheet("色粉管理")
        df_powders = pd.DataFrame(ws_powder.get_all_records())
        if "色粉編號" not in df_powders.columns:
            st.error("❌ 色粉管理表缺少『色粉編號』欄位")
            existing_powders = set()
        else:
            existing_powders = set(df_powders["色粉編號"].map(clean_powder_id).unique())
            
    except Exception as e:
        st.warning(f"⚠️ 無法載入色粉管理：{e}")
        existing_powders = set()
        
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

    import gspread
    from gspread.exceptions import WorksheetNotFound, APIError
    
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except WorksheetNotFound:
        try:
            ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)
        except APIError as e:
            st.error(f"❌ 無法建立工作表：{e}")
            st.stop()
            
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

    # 讀取原始資料(純字串)
    values = ws_recipe.get_all_values()
    if len(values) > 1:
        df_loaded = pd.DataFrame(values[1:], columns=values[0])
    else:
        df_loaded = pd.DataFrame(columns=columns)
    
    # 補齊缺少欄位
    for col in columns:
        if col not in df_loaded.columns:
            df_loaded[col] = ""
    
    # 清理配方編號（保持字串格式且不轉成數字）
    if "配方編號" in df_loaded.columns:
        df_loaded["配方編號"] = df_loaded["配方編號"].astype(str).map(clean_powder_id)
    
    st.session_state.df = df_loaded
    
    df = st.session_state.df
    
    # ===== 初始化欄位 =====
    import streamlit as st

    # 假設你已經有這個列表，是所有欄位名稱
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方",
        "色粉類別", "計量單位", "Pantone色號", "重要提醒", "比例1", "比例2", "比例3",
        "備註", "淨重", "淨重單位", "合計類別"
    ] + [f"色粉編號{i}" for i in range(1, 9)] + [f"色粉重量{i}" for i in range(1, 9)]
    
    # 初始化 session_state
    if "form_recipe" not in st.session_state or not st.session_state.form_recipe:
        st.session_state.form_recipe = {col: "" for col in columns}
        st.session_state.form_recipe["配方類別"] = "原始配方"
        st.session_state.form_recipe["狀態"] = "啟用"
        st.session_state.form_recipe["色粉類別"] = "配方"
        st.session_state.form_recipe["計量單位"] = "包"
        st.session_state.form_recipe["淨重單位"] = "g"
        st.session_state.form_recipe["合計類別"] = "無"
    if "num_powder_rows" not in st.session_state:
        st.session_state.num_powder_rows = 5
    
    fr = st.session_state.form_recipe
    
    st.subheader("➕ 新增 / 修改配方")
    
    with st.form("recipe_form"):
        # 基本欄位
        col1, col2, col3 = st.columns(3)
        with col1:
            fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="form_recipe_配方編號")
        with col2:
            fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="form_recipe_顏色")
        with col3:
            options = [""] + customer_options  
            cust_value = fr.get("客戶編號", "")
            
            # 防止 ValueError，如果值不存在於 options，預設選第一個
            index = options.index(cust_value) if cust_value in options else 0
            
            selected = st.selectbox(
                "客戶編號",
                options,
                index=index,
                key="form_recipe_selected_customer"
            )
    
            if " - " in selected:
                c_no, c_name = selected.split(" - ", 1)
            else:
                c_no, c_name = "", ""
    
            fr["客戶編號"] = c_no
            fr["客戶名稱"] = c_name
   
        # 配方類別、狀態、原始配方
        col4, col5, col6 = st.columns(3)
        with col4:
            options = ["原始配方", "附加配方"]
            current = fr.get("配方類別", options[0])
            if current not in options:
                current = options[0]
            fr["配方類別"] = st.selectbox("配方類別", options, index=options.index(current), key="form_recipe_配方類別")
        with col5:
            options = ["啟用", "停用"]
            current = fr.get("狀態", options[0])
            if current not in options:
                current = options[0]
            fr["狀態"] = st.selectbox("狀態", options, index=options.index(current), key="form_recipe_狀態")
        with col6:
            fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方", ""), key="form_recipe_原始配方")
    
        # 色粉類別、計量單位、Pantone 色號
        col7, col8, col9 = st.columns(3)
        with col7:
            options = ["配方", "色母", "色粉", "添加劑", "其他"]
            current = fr.get("色粉類別", options[0])
            if current not in options:
                current = options[0]
            fr["色粉類別"] = st.selectbox("色粉類別", options, index=options.index(current), key="form_recipe_色粉類別")
        with col8:
            options = ["包", "桶", "kg", "其他"]
            current = fr.get("計量單位", options[0])
            if current not in options:
                current = options[0]
            fr["計量單位"] = st.selectbox("計量單位", options, index=options.index(current), key="form_recipe_計量單位")
        with col9:
            fr["Pantone色號"] = st.text_input("Pantone色號", value=fr.get("Pantone色號", ""), key="form_recipe_Pantone色號")
    
        # 重要提醒、比例1-3
        fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒", ""), key="form_recipe_重要提醒")
        colr1, colon, colr2, colr3, unit = st.columns([2, 1, 2, 2, 1])
        with colr1:
            fr["比例1"] = st.text_input("", value=fr.get("比例1", ""), key="ratio1", label_visibility="collapsed")
        with colon:
            st.markdown(":", unsafe_allow_html=True)
        with colr2:
            fr["比例2"] = st.text_input("", value=fr.get("比例2", ""), key="ratio2", label_visibility="collapsed")
        with colr3:
            fr["比例3"] = st.text_input("", value=fr.get("比例3", ""), key="ratio3", label_visibility="collapsed")
        with unit:
            st.markdown("g/kg", unsafe_allow_html=True)
    
        # 備註
        fr["備註"] = st.text_area("備註", value=fr.get("備註", ""), key="form_recipe_備註")
    
        # 色粉淨重與單位
        col1, col2 = st.columns(2)
        with col1:
            fr["淨重"] = st.text_input("色粉淨重", value=fr.get("淨重", ""), key="form_recipe_淨重")
        with col2:
            options = ["g", "kg"]
            current = fr.get("淨重單位", options[0])
            if current not in options:
                current = options[0]
            fr["淨重單位"] = st.selectbox("單位", options, index=options.index(current), key="form_recipe_淨重單位")
    
        # 色粉設定多列
        st.markdown("### 色粉設定")
        for i in range(1, st.session_state.get("num_powder_rows", 5) + 1):
            c1, c2, c3, c4 = st.columns([1, 3, 3, 1])
            with c1:
                st.write(f"色粉{i}")
            with c2:
                fr[f"色粉編號{i}"] = st.text_input(f"色粉編號{i}", value=fr.get(f"色粉編號{i}", ""), key=f"form_recipe_色粉編號{i}")
            with c3:
                fr[f"色粉重量{i}"] = st.text_input(f"色粉重量{i}", value=fr.get(f"色粉重量{i}", ""), key=f"form_recipe_色粉重量{i}")
            with c4:
                st.markdown(fr.get("淨重單位", ""), unsafe_allow_html=True)
    
        # 合計類別與合計差額
        col1, col2 = st.columns(2)
        with col1:
            category_options = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
            default_raw = fr.get("合計類別", "無")
            default = "\u2002" if default_raw == "無" else default_raw
            if default not in category_options:
                default = category_options[0]
            fr["合計類別"] = st.selectbox("合計類別", category_options, index=category_options.index(default), key="form_recipe_合計類別")
        with col2:
            try:
                net = float(fr.get("淨重") or 0)
                total = sum(float(fr.get(f"色粉重量{i}") or 0) for i in range(1, 9))
                st.write(f"合計差額: {net - total:.2f} g/kg")
            except Exception:
                st.write("合計差額: 計算錯誤")
    
        # 按鈕區
        col1, col2 = st.columns([3, 2])
        with col1:
            submitted = st.form_submit_button("💾 儲存配方")
        with col2:
            add_powder = st.form_submit_button("➕ 新增色粉列")
        
        # 控制避免重複 rerun 的 flag
        if "add_powder_clicked" not in st.session_state:
            st.session_state.add_powder_clicked = False
        
        if add_powder and not st.session_state.add_powder_clicked:
            st.session_state.num_powder_rows = st.session_state.get("num_powder_rows", 5) + 1
            st.session_state.add_powder_clicked = True
            st.rerun()
        elif submitted:
            # 儲存邏輯示範
            st.success("配方已儲存！")
        else:
            # 其他情況重置 flag
            st.session_state.add_powder_clicked = False

    # === 表單提交後的處理邏輯（要在 form 區塊外） ===    
    existing_powders_str = {str(x).strip().upper() for x in existing_powders if str(x).strip() != ""}
   
    if submitted:
        missing_powders = []
        for i in range(1, st.session_state.num_powder_rows + 1):
            pid_raw = fr.get(f"色粉編號{i}", "")
            pid = clean_powder_id(pid_raw)
            if pid and pid not in existing_powders:
                missing_powders.append(pid_raw)
    
        if missing_powders:
            st.warning(f"⚠️ 以下色粉尚未建檔：{', '.join(missing_powders)}")
            st.stop()
    
        # 👉 儲存配方邏輯...
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
  
    # === 處理新增色粉列 ===
    if add_powder:
        if st.session_state.num_powder_rows < 8:
            st.session_state.num_powder_rows += 1
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

    # 按鈕事件判斷（form 外）
    if add_powder:
        st.session_state.num_powder_rows = st.session_state.get("num_powder_rows", 5) + 1
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
    # 若有輸入上方欄位且搜尋結果為空，顯示提示
    top_has_input = any([
        st.session_state.get("search_recipe_code_top"),
        st.session_state.get("search_customer_top"),
        st.session_state.get("search_pantone_top")
    ])
    if top_has_input and df_filtered.empty:
        st.info("❗ 查無符合條件的配方。")

    # 3. 唯一的主顯示區
    # --- 🔍 搜尋列區塊 ---
    
    st.markdown("---")  # 分隔線

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

    st.write(f"📌配方編號：{recipe_kw}　＆ 客戶名稱：{customer_kw}　＆ Pantone：{pantone_kw}")

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
    
    # ===== 篩選後筆數 + 每頁顯示筆數 =====
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"🧺 **篩選後筆數：** {df_filtered.shape[0]}")
    with col2:
        limit = st.selectbox(
            "",  # 不顯示文字
            options=[10, 20, 50, 100],
            index=0,
            key="limit_per_page"
        )
    
    # ===== 計算分頁 =====
    total_rows = df_filtered.shape[0]
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    if "page" not in st.session_state:
        st.session_state.page = 1
    if st.session_state.page > total_pages:
        st.session_state.page = total_pages  # 避免頁碼超過總頁數
    
    # ===== 分頁索引 =====
    start_idx = (st.session_state.page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx]
    
    # ===== 顯示表格 =====
    show_cols = ["配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方", "Pantone色號"]
    existing_cols = [c for c in show_cols if c in page_data.columns]
    
    if not page_data.empty:
        st.dataframe(page_data[existing_cols].reset_index(drop=True),
                     use_container_width=True,
                     hide_index=True)
    else:
        st.info("查無符合的配方（分頁結果）")
    
    # ===== 分頁控制列（按鈕 + 下拉頁碼）=====
    cols_page = st.columns([1, 1, 1, 2])
    with cols_page[0]:
        if st.button("首頁", key="first_page"):
            st.session_state.page = 1
            st.experimental_rerun()
    with cols_page[1]:
        if st.button("上一頁", key="prev_page") and st.session_state.page > 1:
            st.session_state.page -= 1
            st.experimental_rerun()
    with cols_page[2]:
        if st.button("下一頁", key="next_page") and st.session_state.page < total_pages:
            st.session_state.page += 1
            st.experimental_rerun()
    with cols_page[3]:
        selected_page = st.selectbox(
            "",  # 不顯示文字
            options=list(range(1, total_pages + 1)),
            index=st.session_state.page - 1,
            key="select_page"
        )
        if selected_page != st.session_state.page:
            st.session_state.page = selected_page
            st.experimental_rerun()
    
    st.caption(f"頁碼 {st.session_state.page} / {total_pages}，總筆數 {total_rows}")
    st.markdown("---")

    
    # 顯示上方搜尋沒有資料的提示
    top_has_input = any([
        st.session_state.get("search_recipe_code_top"),
        st.session_state.get("search_customer_top"),
        st.session_state.get("search_pantone_top")
    ])
    if top_has_input and df_filtered.empty:
        st.info("⚠️ 查無符合條件的配方（來自上方搜尋）")
    
    # --- 配方編號選擇 + 修改/刪除 ---
    code_list = page_data["配方編號"].dropna().tolist()
        
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

    # --- 生產單分頁 ----------------------------------------------------
elif menu == "生產單管理":
    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;
        font-weight: bold;
        color: #ff3366;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🚀生產單建立</div>', unsafe_allow_html=True)

    from pathlib import Path
    from datetime import datetime
    from datetime import datetime, timedelta
    import pandas as pd

    # 建立資料夾（若尚未存在）
    Path("data").mkdir(parents=True, exist_ok=True)

    order_file = Path("data/df_order.csv")

    # 清理函式：去除空白、全形空白，轉大寫
    def clean_powder_id(x):
        if pd.isna(x) or x == "":
            return ""
        return str(x).strip().replace('\u3000', '').replace(' ', '').upper()
    
    # 補足前導零（僅針對純數字且長度<4的字串）
    def fix_leading_zero(x):
        x = str(x).strip()
        if x.isdigit() and len(x) < 4:
            x = x.zfill(4)
        return x.upper()
        
    def normalize_search_text(text):
        return fix_leading_zero(clean_powder_id(text))
    
    # 先嘗試取得 Google Sheet 兩個工作表 ws_recipe、ws_order
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法載入工作表：{e}")
        st.stop()
    
    # ---------- 載入配方管理表 ----------
    try:
        records = ws_recipe.get_all_records()
        df_recipe = pd.DataFrame(records)
        df_recipe.columns = df_recipe.columns.str.strip()
        df_recipe.fillna("", inplace=True)
    
        # 清理主要欄位
        if "配方編號" in df_recipe.columns:
            df_recipe["配方編號"] = df_recipe["配方編號"].map(lambda x: fix_leading_zero(clean_powder_id(str(x))))
        if "客戶名稱" in df_recipe.columns:
            df_recipe["客戶名稱"] = df_recipe["客戶名稱"].map(clean_powder_id)
        if "原始配方" in df_recipe.columns:
            df_recipe["原始配方"] = df_recipe["原始配方"].map(clean_powder_id)
    
        # 建立標準化欄位
        if "原始配方_標準" not in df_recipe.columns:
            if "原始配方" in df_recipe.columns:
                df_recipe["原始配方_標準"] = df_recipe["原始配方"].map(lambda x: fix_leading_zero(str(x)))
            else:
                df_recipe["原始配方_標準"] = ""
    
        df_recipe["原始配方_標準"] = df_recipe["原始配方_標準"].astype(str)
        st.session_state.df_recipe = df_recipe
    
    except Exception as e:
        st.error(f"❌ 讀取『配方管理』工作表失敗：{e}")
        st.stop()
    
    # 載入生產單表
    try:
        existing_values = ws_order.get_all_values()
        if existing_values:
            df_order = pd.DataFrame(existing_values[1:], columns=existing_values[0]).astype(str)
        else:
            header = [
                "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "建立時間",
                "Pantone 色號", "計量單位", "原料",
                "包裝重量1", "包裝重量2", "包裝重量3", "包裝重量4",
                "包裝份數1", "包裝份數2", "包裝份數3", "包裝份數4",
                "重要提醒", "備註",
                "色粉編號1", "色粉編號2", "色粉編號3", "色粉編號4",
                "色粉編號5", "色粉編號6", "色粉編號7", "色粉編號8", "色粉合計",
                "合計類別"
            ]
            ws_order.append_row(header)
            df_order = pd.DataFrame(columns=header)
        st.session_state.df_order = df_order
    except Exception as e:
        if order_file.exists():
            st.warning("⚠️ 無法連線 Google Sheets，改用本地 CSV")
            df_order = pd.read_csv(order_file, dtype=str).fillna("")
            st.session_state.df_order = df_order
        else:
            st.error(f"❌ 無法讀取生產單資料：{e}")
            st.stop()
    
    df_recipe = st.session_state.df_recipe
    df_order = st.session_state.df_order.copy()
    
    # 轉換時間欄位與配方編號欄清理
    if "建立時間" in df_order.columns:
        df_order["建立時間"] = pd.to_datetime(df_order["建立時間"], errors="coerce")
    if "配方編號" in df_order.columns:
        df_order["配方編號"] = df_order["配方編號"].map(clean_powder_id)
    
    # 初始化 session_state 用的 key
    for key in ["order_page", "editing_order", "show_edit_panel", "new_order", "show_confirm_panel"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "order_page" else 1
    
    def format_option(r):
        label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
        if r.get("配方類別", "") == "附加配方":
            label += "（附加配方）"
        return label
    
    # 先定義清理函式
    def clean_powder_id(x):
        if pd.isna(x) or x == "":
            return ""
        return str(x).strip().upper()  # 去除空白+轉大寫
    
    # 載入配方管理表時做清理（載入區塊示範）
    try:
        records = ws_recipe.get_all_records()
        df_recipe = pd.DataFrame(records)
        df_recipe.columns = df_recipe.columns.str.strip()
        df_recipe.fillna("", inplace=True)
        if "配方編號" in df_recipe.columns:
            df_recipe["配方編號"] = df_recipe["配方編號"].astype(str).map(clean_powder_id)
        st.session_state.df_recipe = df_recipe
    except Exception as e:
        st.error(f"❌ 讀取『配方管理』工作表失敗：{e}")
        st.stop()
    
    df_recipe = st.session_state.df_recipe

    def clean_powder_id(x):
        if pd.isna(x) or x == "":
            return ""
        return str(x).strip().replace('\u3000', '').replace(' ', '').upper()
    
    def fix_leading_zero(x):
        x = str(x).strip()
        if x.isdigit() and len(x) < 4:
            x = x.zfill(4)
        return x.upper()
    
    def normalize_search_text(text):
        return fix_leading_zero(clean_powder_id(text))
    
    # Streamlit UI 搜尋表單==========================
    st.subheader("🔎 配方搜尋與新增生產單")

    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")
    
        # 資料預處理
        df_recipe["配方編號"] = df_recipe["配方編號"].astype(str)
        df_recipe["客戶名稱"] = df_recipe["客戶名稱"].astype(str)
        search_text = search_text.strip()
    
        if search_text:
            if exact:
                filtered = df_recipe[
                    (df_recipe["配方編號"] == search_text) | 
                    (df_recipe["客戶名稱"] == search_text)
                ]
            else:
                filtered = df_recipe[
                    df_recipe["配方編號"].str.contains(search_text, case=False, na=False) |
                    df_recipe["客戶名稱"].str.contains(search_text, case=False, na=False)
                ]
        else:
            filtered = df_recipe.copy()
    
        filtered = filtered.copy()  # 確保不修改原始 df
    
        # 產生選項
        if not filtered.empty:
            filtered["label"] = filtered.apply(format_option, axis=1)
            option_map = dict(zip(filtered["label"], filtered.to_dict(orient="records")))
            select_options = ["請選擇"] + list(option_map.keys())
        else:
            option_map = {}
            select_options = ["（無符合配方）"]
    
        # 單筆自動選取
        if len(option_map) == 1:
            selected_label = list(option_map.keys())[0]
            selected_row = option_map[selected_label]
            st.success(f"已自動選取：{selected_label}")
        else:
            selected_label = st.selectbox(
                "選擇配方",
                select_options,
                index=0,
                key="search_add_form_selected_recipe"
            )
            selected_row = None if selected_label in ("請選擇", "（無符合配方）") else option_map.get(selected_label)
    
    if add_btn:
        if selected_label in ("請選擇", "（無符合配方）") or not selected_row:
            st.warning("請先選擇有效配方")
        elif selected_row.get("狀態") == "停用":
            st.warning("⚠️ 此配方已停用，請勿使用")
            st.stop()
        else:
            # 初始化 order
            order = {}
            today_str = datetime.now().strftime("%Y%m%d")
            df_all_orders = st.session_state.df_order.copy()
            count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
            new_id = f"{today_str}-{count_today + 1:03}"
    
            # 寫入主配方欄位
            order["生產單號"] = new_id
            order["生產日期"] = datetime.now().strftime("%Y-%m-%d")
            order["建立時間"] = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
            order["配方編號"] = selected_row.get("配方編號", "")
            order["顏色"] = selected_row.get("顏色", "")
            order["客戶名稱"] = selected_row.get("客戶名稱", "")
            order["Pantone 色號"] = selected_row.get("Pantone色號", "")
            order["計量單位"] = selected_row.get("計量單位", "")
            order["備註"] = str(selected_row.get("備註", "")).strip()
            order["重要提醒"] = str(selected_row.get("重要提醒", "")).strip()
            order["合計類別"] = str(selected_row.get("合計類別", "")).strip()

            # ----------------- 附加配方 -----------------
            df_recipe_safe = st.session_state.df_recipe.copy()
            if "原始配方" not in df_recipe_safe.columns:
                df_recipe_safe["原始配方"] = ""
            df_recipe_safe["_原始配方標準"] = df_recipe_safe["原始配方"].map(lambda x: fix_leading_zero(clean_powder_id(str(x))))
            main_recipe_code = fix_leading_zero(clean_powder_id(order["配方編號"]))
    
            additional_recipes = df_recipe_safe[
                (df_recipe_safe["配方類別"] == "附加配方") &
                (df_recipe_safe["_原始配方標準"] == main_recipe_code)
            ]
    
            order["附加配方"] = [
                {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
                for _, row in additional_recipes.iterrows()
            ]
    
            # 存回 session_state，並顯示表單
            st.session_state.new_order = order
            st.session_state.recipe_row_cache = selected_row  # 保存主配方資料
            st.session_state.show_confirm_panel = True
    
            # ----------------- 附加配方（安全版） -----------------
            matched_additional = pd.DataFrame()  # 預設空 DataFrame
            recipe_id = order.get("配方編號", "").strip()
            if recipe_id:
                df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
                
                # 確保有原始配方欄位
                if "原始配方" not in df_recipe.columns:
                    df_recipe["原始配方"] = ""
                
                # 建立臨時標準化欄位，不改原始資料
                df_recipe["_原始配方標準"] = df_recipe["原始配方"].map(
                    lambda x: fix_leading_zero(clean_powder_id(str(x)))
                )
                
                # 標準化主配方編號
                main_recipe_code = fix_leading_zero(clean_powder_id(recipe_id))
                
                # 取出附加配方
                matched_additional = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["_原始配方標準"] == main_recipe_code)
                ]
            
            # 寫入 order
            order["附加配方"] = [
                {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
                for _, row in matched_additional.iterrows()
            ]
    
            # ----------------- 整合色粉編號與重量 -----------------
            all_colorants = []
            for i in range(1, 9):
                id_key = f"色粉編號{i}"
                wt_key = f"色粉重量{i}"
                id_val = selected_row.get(id_key, "")
                wt_val = selected_row.get(wt_key, "")
                if id_val or wt_val:
                    all_colorants.append((id_val, wt_val))
            for _, sub in matched_additional.iterrows():
                for i in range(1, 9):
                    id_key = f"色粉編號{i}"
                    wt_key = f"色粉重量{i}"
                    id_val = sub.get(id_key, "")
                    wt_val = sub.get(wt_key, "")
                    if id_val or wt_val:
                        all_colorants.append((id_val, wt_val))
    
            st.session_state.new_order = order
            st.rerun()
          
    # ---------- 新增後欄位填寫區塊 ----------
    if st.session_state.get("show_confirm_panel"):
    
        # 安全取得 session_state
        order = st.session_state.get("new_order", {})
        recipe_row = st.session_state.get("recipe_row_cache", {})
        unit = str(recipe_row.get("計量單位", "kg"))
    
        # 確保附加配方是 list
        additional_recipes = order.get("附加配方", [])
        if not isinstance(additional_recipes, list):
            additional_recipes = []
    
        # 補齊 order 欄位
        for key in ["生產單號", "配方編號", "顏色", "客戶名稱", "Pantone 色號", "計量單位", "備註", "重要提醒", "合計類別"]:
            order.setdefault(key, "")
    
        # 補齊主配方色粉欄位
        for i in range(1, 9):
            recipe_row.setdefault(f"色粉編號{i}", "")
            recipe_row.setdefault(f"色粉重量{i}", "")
    
        # 補齊附加配方欄位
        for add in additional_recipes:
            for i in range(1, 9):
                add.setdefault(f"色粉編號{i}", "")
                add.setdefault(f"色粉重量{i}", "")
            add.setdefault("淨重", 0)
            add.setdefault("淨重單位", "")
    
        # ---------- 列印 HTML（安全呼叫） ----------
        try:
            print_html = generate_production_order_print_integrated(
                order=order,
                recipe_row=recipe_row,
                additional_recipe_rows=additional_recipes,
                show_additional_ids=True
            )
        except Exception as e:
            st.error(f"❌ 產生列印內容失敗：{e}")
            print_html = ""
    
        st.markdown("---")
        st.subheader("新增生產單詳情填寫")
    
        # 不可編輯欄位
        c1, c2, c3, c4 = st.columns(4)
        c1.text_input("生產單號", value=str(order.get("生產單號", "")), disabled=True)
        c2.text_input("配方編號", value=str(order.get("配方編號", "")), disabled=True)
        c3.text_input("客戶編號", value=str(recipe_row.get("客戶編號", "")), disabled=True)
        c4.text_input("客戶名稱", value=str(order.get("客戶名稱", "")), disabled=True)
    
        # ---------- 表單 ----------
        with st.form("order_detail_form"):
            c5, c6, c7, c8 = st.columns(4)
            c5.text_input("計量單位", value=unit, disabled=True)
            color = c6.text_input("顏色", value=str(order.get("顏色", "")), key="form_color")
            pantone = c7.text_input("Pantone 色號", value=str(order.get("Pantone 色號", recipe_row.get("Pantone色號", ""))), key="form_pantone")
            raw_material = c8.text_input("原料", value=str(order.get("原料", "")), key="form_raw_material")
    
            # 重要提醒 / 合計類別 / 備註
            c9, c10 = st.columns(2)
            important_note = c9.text_input("重要提醒", value=str(order.get("重要提醒", "")), key="form_important_note")
            total_category = c10.text_input("合計類別", value=str(order.get("合計類別", "")), key="form_total_category")
            remark = st.text_area("備註", value=str(order.get("備註", "")), key="form_remark")
    
            # 包裝重量與份數
            st.markdown("**包裝重量與份數**")
            w_cols = st.columns(4)
            c_cols = st.columns(4)
            for i in range(1, 5):
                w_cols[i-1].text_input(f"包裝重量{i}", value=str(order.get(f"包裝重量{i}", "")), key=f"form_weight{i}")
                c_cols[i-1].text_input(f"包裝份數{i}", value=str(order.get(f"包裝份數{i}", "")), key=f"form_count{i}")
    
            # 主配方色粉
            st.markdown("### 色粉用量（編號與重量）")
            col_id, col_wt = st.columns(2)
            for i in range(1, 9):
                color_id = str(recipe_row.get(f"色粉編號{i}", "")).strip()
                color_wt = str(recipe_row.get(f"色粉重量{i}", "")).strip()
                if color_id or color_wt:
                    with col_id:
                        st.text_input(f"色粉編號{i}", value=color_id, disabled=True, key=f"form_main_color_id_{i}")
                    with col_wt:
                        st.text_input(f"色粉重量{i}", value=color_wt, disabled=True, key=f"form_main_color_weight_{i}")
    
            # 主配方淨重
            st.markdown(f"<div style='text-align:right; font-size:16px;'>🔢 配方淨重：{recipe_row.get('淨重','')} {recipe_row.get('淨重單位','')}</div>", unsafe_allow_html=True)
    
            # 附加配方色粉
            if additional_recipes:
                st.markdown("### 附加配方色粉用量（編號與重量）")
                for idx, add_recipe in enumerate(additional_recipes, 1):
                    st.markdown(f"#### 附加配方 {idx}")
                    col1, col2 = st.columns(2)
                    for i in range(1, 9):
                        color_id = str(add_recipe.get(f"色粉編號{i}", "")).strip()
                        color_wt = str(add_recipe.get(f"色粉重量{i}", "")).strip()
                        if color_id or color_wt:
                            with col1:
                                st.text_input(f"附加色粉編號_{idx}_{i}", value=color_id, disabled=True, key=f"form_add_color_id_{idx}_{i}")
                            with col2:
                                st.text_input(f"附加色粉重量_{idx}_{i}", value=color_wt, disabled=True, key=f"form_add_color_wt_{idx}_{i}")
    
                    # 附加配方淨重
                    total_net = float(add_recipe.get("淨重", 0) or 0)
                    unit_add = add_recipe.get("淨重單位", "")
                    st.markdown(f"<div style='text-align:right; font-size:16px;'>📦 附加配方淨重：{total_net:.2f} {unit_add}</div>", unsafe_allow_html=True)
    
            # ---------- Submit Button ----------
            submitted = st.form_submit_button("💾 儲存生產單")
    
        # ---------- 儲存資料到 session_state ----------
        if submitted:
            # 更新 order
            order.update({
                "顏色": st.session_state.get("form_color", ""),
                "Pantone 色號": st.session_state.get("form_pantone", ""),
                "原料": st.session_state.get("form_raw_material", ""),
                "重要提醒": st.session_state.get("form_important_note", ""),
                "合計類別": st.session_state.get("form_total_category", ""),
                "備註": st.session_state.get("form_remark", "")
            })
            for i in range(1, 5):
                order[f"包裝重量{i}"] = st.session_state.get(f"form_weight{i}", "")
                order[f"包裝份數{i}"] = st.session_state.get(f"form_count{i}", "")
    
            st.session_state["new_order"] = order
    
            # ---------- 寫入 Google Sheets ----------
            try:
                sheet_columns = [
                    "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "建立時間", 
                    "Pantone 色號", "計量單位", "原料", 
                    "包裝重量1", "包裝重量2", "包裝重量3", "包裝重量4", 
                    "包裝份數1", "包裝份數2", "包裝份數3", "包裝份數4", 
                    "備註", "合計類別", "淨重"
                ]
    
                cell = ws_order.find(order["生產單號"])
                values_to_write = [str(order.get(col, "")) for col in sheet_columns]
    
                if cell:
                    ws_order.update_row(cell.row, values_to_write)
                else:
                    ws_order.append_row(values_to_write)
    
                st.success(f"✅ 生產單 {order.get('生產單號','')} 已更新完成並寫入 Google Sheets")
            except Exception as e:
                st.error(f"Google Sheets 寫入錯誤：{e}")
    
        # ---------- 安全列印 HTML下載 ----------
        order = st.session_state.get("new_order", {})
        st.session_state.new_order = order  # 確保 session_state 有值
        
        # ---------- 下載列印 HTML ----------
        try:
            print_html = generate_production_order_print_integrated(
                order=order,
                recipe_row=st.session_state.get("recipe_row_cache", {}),
                additional_recipe_rows=order.get("附加配方", []),
                show_additional_ids=True
            )
        except Exception as e:
            st.error(f"❌ 產生列印內容失敗：{e}")
            print_html = ""
        
        st.download_button(
            label="📥 下載列印 HTML",
            data=str(print_html or "").encode("utf-8"),
            file_name=f"{order.get('生產單號','')}_print.html",
            mime="text/html"
        )
        
    # ---------- 生產單清單 + 修改 / 刪除 ----------
    st.markdown("---")
    st.subheader("📑 生產單記錄表")
                
    search_order = st.text_input("搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)", key="search_order_input_order_page", value="")
                
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
    
    cols_top = st.columns([5, 1])
    with cols_top[1]:
        limit = st.selectbox("每頁顯示筆數", [10, 20, 50, 75, 100], index=0, key="selectbox_order_limit")
    
    # 計算分頁資訊（依 limit）
    total_rows = len(df_filtered)
    total_pages = max((total_rows - 1) // limit + 1, 1)
    st.session_state.order_page = max(1, min(st.session_state.order_page, total_pages))
    start_idx = (st.session_state.order_page - 1) * limit
    page_data = df_filtered.iloc[start_idx:start_idx + limit].copy()
    page_data = page_data.sort_values(by="建立時間", ascending=False)
    
    # 產生選單與映射
    options = []
    code_to_id = {}
    for idx, row in page_data.iterrows():
        label = f"{row['生產單號']} / {row['配方編號']} / {row.get('顏色', '')} / {row.get('客戶名稱', '')}"
        options.append(label)
        code_to_id[label] = row["生產單號"]
    
    # 選單選擇（放左邊）
    with cols_top[0]:
        selected_label = st.selectbox("選擇生產單號", options, key="select_order_for_edit_from_list")
    
    # 選擇生產單後同步設定 session_state
    if selected_label:
        selected_order_code = code_to_id[selected_label]
        st.session_state.selected_code_edit = selected_order_code
    else:
        st.session_state.selected_code_edit = None
    
    # 計算出貨數量並加入新欄位
    if not page_data.empty:
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
    
        shipment_series = page_data.apply(calculate_shipment, axis=1)
        page_data["出貨數量"] = shipment_series
    
        # 顯示表格
        st.dataframe(
            page_data[["生產單號", "配方編號", "顏色", "客戶名稱", "出貨數量", "建立時間"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("查無符合的生產單")
    
    # 分頁控制列
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
    
    jump_page = cols_page[3].number_input(
        "",  # 不顯示文字
        min_value=1,
        max_value=total_pages,
        value=st.session_state.order_page,
        key="jump_page",
        label_visibility="collapsed"  # 隱藏標籤
    )
    if jump_page != st.session_state.order_page:
        st.session_state.order_page = jump_page
        st.rerun()
    
    st.caption(f"頁碼 {st.session_state.order_page} / {total_pages}，總筆數 {total_rows}")
    
    
    # ---------- 修改 / 刪除 / A5 下載三欄按鈕橫排 ----------
    # ===== 整合三欄按鈕 + 編輯面板 + A5 列印下載 =====
    cols_mod = st.columns([1, 1, 1])
    selected_code_edit = st.session_state.get("selected_code_edit", None)
    
    # ------------------ 清單列表 A5（色粉/色母處理） ------------------
    with cols_mod[0]:
        if selected_code_edit:
            order_row = df_order[df_order["生產單號"] == selected_code_edit]
            if not order_row.empty:
                order_dict = order_row.iloc[0].to_dict()
                recipe_rows = df_recipe[df_recipe["配方編號"] == order_dict["配方編號"]]
                if not recipe_rows.empty:
                    recipe_row = recipe_rows.iloc[0]
                    try:
                        # ✅ 使用完整 HTML 生成函式
                        html_data = generate_print_page_content(
                            order=order_dict,
                            recipe_row=recipe_row,
                            additional_recipe_rows=order_dict.get("附加配方", []),
                            show_additional_ids=True
                        )
                    except Exception as e:
                        st.error(f"❌ 產生列印內容失敗：{e}")
                        html_data = ""
        
        st.download_button(
            label="📥 下載清單列表 A5 HTML",
            data=str(html_data or "").encode("utf-8"),
            file_name=f"{selected_code_edit}_A5_列表列印.html" if selected_code_edit else "A5_列表列印.html",
            mime="text/html"
        )
    
    # ------------------ 修改按鈕 ------------------
    with cols_mod[1]:
        if st.button("✏️ 修改", key="edit_button_1") and selected_code_edit:
            row = df_order[df_order["生產單號"] == selected_code_edit]
            if not row.empty:
                st.session_state.editing_order = row.iloc[0].to_dict()
                st.session_state.show_edit_panel = True
            else:
                st.warning("找不到該筆生產單")
    
    # ------------------ 刪除按鈕 ------------------
    with cols_mod[2]:
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
            
            # 清理狀態
            st.session_state.pop("selected_code_edit", None)
            st.session_state.show_edit_panel = False
            st.session_state.editing_order = None
            st.experimental_rerun()
    
    # ------------------ 編輯面板 ------------------
    if st.session_state.get("show_edit_panel") and st.session_state.get("editing_order"):
        st.markdown("---")
        edit_order = st.session_state.editing_order
        st.subheader(f"✏️ 修改生產單 {edit_order['生產單號']}")
    
        # 客戶名稱 / 顏色
        new_customer = st.text_input("客戶名稱", value=edit_order.get("客戶名稱", ""), key="edit_customer_name")
        new_color = st.text_input("顏色", value=edit_order.get("顏色", ""), key="edit_color")
    
        # 包裝重量 1~4
        pack_weights_cols = st.columns(4)
        new_packing_weights = [
            pack_weights_cols[i].text_input(f"包裝重量{i+1}", value=edit_order.get(f"包裝重量{i+1}", ""), key=f"edit_packing_weight_{i+1}")
            for i in range(4)
        ]
    
        # 包裝份數 1~4
        pack_counts_cols = st.columns(4)
        new_packing_counts = [
            pack_counts_cols[i].text_input(f"包裝份數{i+1}", value=edit_order.get(f"包裝份數{i+1}", ""), key=f"edit_packing_count_{i+1}")
            for i in range(4)
        ]
    
        new_remark = st.text_area("備註", value=edit_order.get("備註", ""), key="edit_remark")
    
        # 取得對應配方資料
        recipe_id = edit_order.get("配方編號", "")
        recipe_rows = df_recipe[df_recipe["配方編號"] == recipe_id]
        if recipe_rows.empty:
            st.warning(f"找不到配方編號：{recipe_id}")
            st.stop()
        recipe_row = recipe_rows.iloc[0]
    
        st.download_button(
            label="📄 下載列印 HTML",
            data=preview_html.encode("utf-8"),
            file_name=f"{edit_order['生產單號']}_print.html",
            mime="text/html"
        )
    
        # 儲存 / 返回
        cols_edit = st.columns([1, 1])
        with cols_edit[0]:
            if st.button("儲存修改", key="save_edit_button"):
                idx_list = df_order.index[df_order["生產單號"] == edit_order["生產單號"]].tolist()
                if idx_list:
                    idx = idx_list[0]
                    # 更新本地 DataFrame
                    df_order.at[idx, "客戶名稱"] = new_customer
                    df_order.at[idx, "顏色"] = new_color
                    for i in range(4):
                        df_order.at[idx, f"包裝重量{i+1}"] = new_packing_weights[i]
                        df_order.at[idx, f"包裝份數{i+1}"] = new_packing_counts[i]
                    df_order.at[idx, "備註"] = new_remark
                    # 同步 Google Sheets
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
                    # 更新本地 CSV
                    os.makedirs(os.path.dirname(order_file), exist_ok=True)
                    df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
                    st.session_state.df_order = df_order
                    st.success("✅ 本地資料更新成功，修改已儲存")
                    st.experimental_rerun()
        with cols_edit[1]:
            if st.button("返回", key="return_button"):
                st.session_state.show_edit_panel = False
                st.session_state.editing_order = None
                st.experimental_rerun()

# ===== 匯入配方備份檔案 =====
if st.session_state.menu == "匯入備份":
    st.title("📥 匯入配方備份 Excel")
    
    def load_recipe_backup_excel(file):
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()
            df = df.dropna(how='all')
            df = df.fillna("")
    
            # 檢查必要欄位
            required_columns = ["配方編號", "顏色", "客戶編號", "色粉編號1"]
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                raise ValueError(f"缺少必要欄位：{missing}")
    
            return df
        except Exception as e:
            st.error(f"❌ 備份檔讀取失敗：{e}")
            return None
    
    uploaded_file = st.file_uploader("請上傳備份 Excel (.xlsx)", type=["xlsx"], key="upload_backup")
    if uploaded_file:
        df_uploaded = load_recipe_backup_excel(uploaded_file)
        if df_uploaded is not None:
            st.session_state.df_recipe = df_uploaded
            st.success("✅ 成功匯入備份檔！")
            st.dataframe(df_uploaded.head())

                
