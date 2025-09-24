# ===== app.py =====
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import json
import time
import base64
import re

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

menu_options = ["色粉管理", "客戶名單", "配方管理", "生產單管理", 
                "交叉查詢區", "Pantone色號表", "庫存區", "匯入備份"]

if "menu" not in st.session_state:
    st.session_state.menu = "生產單管理"

# 自訂 CSS：改按鈕字體大小
st.markdown("""
<style>
/* Sidebar 標題字體大小 */
.sidebar .css-1d391kg h1 {
    font-size: 24px !important;
}

/* Sidebar 按鈕字體大小 */
div.stButton > button {
    font-size: 14px !important;
    padding: 8px 12px !important;  /* 可調整上下左右間距 */
    text-align: left;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    # 標題
    st.markdown('<h1 style="font-size:22px;">🌈配方管理系統</h1>', unsafe_allow_html=True)

    for option in menu_options:
        label = f"✅ {option}" if st.session_state.menu == option else option
        if st.button(label, key=f"menu_{option}", use_container_width=True):
            st.session_state.menu = option


# ===== 在最上方定義函式 =====
def set_form_style():
    st.markdown("""
    <style>
    /* text_input placeholder */
    div.stTextInput > div > div > input::placeholder {
        color: #999999;
        font-size: 13px;
    }

    /* selectbox placeholder */
    div.stSelectbox > div > div > div.css-1wa3eu0-placeholder {
        color: #999999;
        font-size: 13px;
    }

    /* selectbox 選中後文字 */
    div.stSelectbox > div > div > div.css-1uccc91-singleValue {
        font-size: 14px;
        color: #000000;
    }
    </style>
    """, unsafe_allow_html=True)

# ===== 呼叫一次，套用全程式 =====
set_form_style()

# ===== 自訂函式：產生生產單列印格式 =====      
def generate_production_order_print(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}

    category = order.get("色粉類別", "").strip()  # 確保先賦值
    
    unit = recipe_row.get("計量單位", "kg")
    ratio = recipe_row.get("比例3", "")
    total_type = recipe_row.get("合計類別", "").strip()
    # ✅ 舊資料相容處理：「原料」統一轉成「料」
    if total_type == "原料":
        total_type = "料"
    
    powder_label_width = 12
    pack_col_width = 11
    number_col_width = 6
    column_offsets = [1, 5, 5, 5]
    total_offsets = [1.3, 5, 5, 5]
    
    packing_weights = [
        float(order.get(f"包裝重量{i}", 0)) if str(order.get(f"包裝重量{i}", "")).replace(".", "", 1).isdigit() else 0
        for i in range(1, 5)
    ]
    packing_counts = [
        float(order.get(f"包裝份數{i}", 0)) if str(order.get(f"包裝份數{i}", "")).replace(".", "", 1).isdigit() else 0
        for i in range(1, 5)
    ]

    # 這裡初始化 colorant_ids 和 colorant_weights
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
    
    # 合計列
    try:
        net_weight = float(recipe_row.get("淨重", 0))
    except:
        net_weight = 0.0
    
    lines = []
    lines.append("")
    
    # 配方資訊列
    recipe_id = recipe_row.get('配方編號', '')
    color = order.get('顏色', '')
    pantone = order.get('Pantone 色號', '')
    info_line = f"<span style='font-size:20px;'>編號：<b>{recipe_id:<8}</b>顏色：{color:<4}     比例：{ratio} g/kg   Pantone：{pantone}</span>"
    lines.append(info_line)
    lines.append("")
    
    # 包裝列
    pack_line = []
    for i in range(4):
        w = packing_weights[i]
        c = packing_counts[i]
        if w > 0 or c > 0:
            # 特例：色母類別 + w==1 時，強制 real_w=100
            if category == "色母":
                if w == 1:
                    unit_str = "100K"
                else:
                    real_w = w * 100
                    unit_str = f"{int(real_w)}K" if real_w == int(real_w) else f"{real_w:.1f}K"
            elif unit == "包":
                real_w = w * 25
                unit_str = f"{int(real_w)}K" if real_w == int(real_w) else f"{real_w:.1f}K"
            elif unit == "桶":
                real_w = w * 100
                unit_str = f"{int(real_w)}K" if real_w == int(real_w) else f"{real_w:.1f}K"
            else:
                real_w = w
                # 轉成字串後去掉多餘的 0 和小數點
                unit_str = f"{real_w:.2f}".rstrip("0").rstrip(".") + "kg"
        
            count_str = str(int(c)) if c == int(c) else str(c)
            text = f"{unit_str} × {count_str}"
            pack_line.append(f"{text:<{pack_col_width}}")
        
    packing_indent = " " * 14
    lines.append(f"<b>{packing_indent + ''.join(pack_line)}</b>")
                                    
    # 主配方色粉列
    for idx in range(8):
        c_id = colorant_ids[idx]
        c_weight = colorant_weights[idx]
        if not c_id:
            continue
        row = f"<b>{str(c_id or '').ljust(powder_label_width)}</b>"
        for i in range(4):
            val = c_weight * multipliers[i] if multipliers[i] > 0 else 0
            val_str = (
                str(int(val)) if val.is_integer() else f"{val:.3f}".rstrip('0').rstrip('.')
            ) if val else ""
            padding = " " * max(0, int(round(column_offsets[i])))
            # 數字用加 class 的 <b> 包起來
            row += padding + f"<b class='num'>{val_str:>{number_col_width}}</b>"
        lines.append(row)
        
    # 橫線：只有非色母類別才顯示
    category = (order.get("色粉類別") or "").strip()
    if category != "色母":
        lines.append("＿" * 28)
                    
    # 合計列
    total_offsets = [1, 5, 5, 5]  # 第一欄前空 2、第二欄前空 4、依此類推
    if total_type == "" or total_type == "無":
        total_type_display = f"<b>{'='.ljust(powder_label_width)}</b>"
    elif category == "色母":
        total_type_display = f"<b><span style='font-size:22px; display:inline-block; width:{powder_label_width}ch'>料</span></b>"
    else:
        total_type_display = f"<b>{total_type.ljust(powder_label_width)}</b>"
        
    total_line = total_type_display
        
    for i in range(4):
        result = 0
        if category == "色母":
            pigment_total = sum(colorant_weights)
            result = (net_weight - pigment_total) * multipliers[i] if multipliers[i] > 0 else 0
        else:
            result = net_weight * multipliers[i] if multipliers[i] > 0 else 0
        
        val_str = f"{result:.3f}".rstrip('0').rstrip('.') if result else ""
        padding = " " * max(0, int(round(total_offsets[i])))
        total_line += padding + f"<b class='num'>{val_str:>{number_col_width}}</b>"
        
    lines.append(total_line)
           
    # 多筆附加配方列印
    if additional_recipe_rows and isinstance(additional_recipe_rows, list):
        for idx, sub in enumerate(additional_recipe_rows, 1):
            lines.append("")
            if show_additional_ids:
                lines.append(f"附加配方 {idx}：{sub.get('配方編號', '')}")
            else:
                lines.append(f"附加配方 {idx}")
    
            add_ids = [sub.get(f"色粉編號{i+1}", "") for i in range(8)]
            add_weights = []
            for i in range(8):
                try:
                    val = float(sub.get(f"色粉重量{i+1}", 0) or 0)
                except:
                    val = 0.0
                add_weights.append(val)
    
            # 色粉列
            for i in range(8):
                c_id = add_ids[i]
                if not c_id:
                    continue
                row = c_id.ljust(powder_label_width)
                for j in range(4):
                    val = add_weights[i] * multipliers[j] if multipliers[j] > 0 else 0
                    val_str = (
                        str(int(val)) if val.is_integer() else f"{val:.3f}".rstrip('0').rstrip('.')
                    ) if val else ""
                    padding = " " * max(0, int(round(column_offsets[j])))
                    row += padding + f"<b>{val_str:>{number_col_width}}</b>"
                lines.append(row)

            # 橫線：加在附加配方合計列上方
            line_length = powder_label_width + sum([number_col_width + int(round(column_offsets[j])) for j in range(4)])
            lines.append("―" * line_length)
   
            # ✅ 合計列 (附加配方專用)
            sub_total_type = sub.get("合計類別", "")
            sub_net_weight = float(sub.get("淨重", 0) or 0)
            
            if sub_total_type == "" or sub_total_type == "無":
                sub_total_type_display = f"<b>{'='.ljust(powder_label_width)}</b>"
            elif category == "色母":
                sub_total_type_display = f"<b>{'料'.ljust(powder_label_width)}</b>"
            else:
                sub_total_type_display = f"<b>{sub_total_type.ljust(powder_label_width)}</b>"
            
            sub_total_line = sub_total_type_display
            for j in range(4):
                val = sub_net_weight * multipliers[j] if multipliers[j] > 0 else 0
                val_str = (
                    str(int(val)) if val.is_integer() else f"{val:.3f}".rstrip('0').rstrip('.')
                ) if val else ""
                padding = " " * max(0, int(round(column_offsets[j])))
                sub_total_line += padding + f"<b class='num'>{val_str:>{number_col_width}}</b>"
            
            lines.append(sub_total_line)

        
    lines.append("")
    lines.append("")  # 多加這一行，讓備註往下多空一行
    lines.append(f"備註 : {order.get('備註', '')}")
    
    return "<br>".join(lines)

# --------------- 新增：列印專用 HTML 生成函式 ---------------
def generate_print_page_content(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}

    # 如果只有一筆 dict，包成 list
    if additional_recipe_rows is not None and not isinstance(additional_recipe_rows, list):
        additional_recipe_rows = [additional_recipe_rows]

    # ✅ 傳入 show_additional_ids 給產生列印內容的函式
    content = generate_production_order_print(
        order,
        recipe_row,
        additional_recipe_rows,
        show_additional_ids=show_additional_ids  # 👈 新增參數
    )
    created_time = str(order.get("建立時間", "") or "")

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
                font-family: 'Courier New', Courier, monospace;
                font-size: 22px;
                line-height: 1.4;
            }
            .title {
                text-align: center;
                font-size: 24px;
                margin-bottom: -4px;
                font-family: Arial, Helvetica, sans-serif;
                font-weight: normal;
            }
            .timestamp {
                font-size: 20px;
                color: #000;
                text-align: center;
                margin-bottom: 2px;
                font-family: Arial, Helvetica, sans-serif;
                font-weight: normal;
            }
            pre {
                white-space: pre-wrap;
                margin-left: 25px;
                margin-top: 0px;
            }
            b.num {
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
        <pre>{content}</pre>
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

def init_states(keys):
    """
    初始化 session_state 中的變數
    - 如果 key 需要 dict，預設為 {}
    - 否則預設為 ""
    """
    dict_keys = {"form_color", "form_recipe", "order"}  # 這些一定要是 dict
    
    for k in keys:
        if k not in st.session_state:
            if k in dict_keys:
                st.session_state[k] = {}
            else:
                st.session_state[k] = ""
# ------------------------------
menu = st.session_state.menu  # 先從 session_state 取得目前選擇

# ======== 色粉管理 =========
if menu == "色粉管理":
    worksheet = spreadsheet.worksheet("色粉管理")
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

    # form_color 現在一定是 dict，不會再報錯
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
        font-size: 30px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #dbd818; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🎰色粉搜尋</h2>',
        unsafe_allow_html=True
    )
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

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">➕新增色粉</h2>',
        unsafe_allow_html=True
    )

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
                idx = st.session_state.edit_color_index
                for col in df.columns:
                    df.at[idx, col] = new_data.get(col, "")  # 保證每欄都有值
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data], columns=df.columns)], ignore_index=True)
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

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📋色粉清單</h2>',
        unsafe_allow_html=True
    )

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 3])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        with cols[5]:
            c1, c2 = st.columns(2, gap="small")
            if c1.button("✏️ 改", key=f"edit_color_{i}"):
                st.session_state.edit_color_index = i
                st.session_state.form_color = row.to_dict()
                st.rerun()
            if c2.button("🗑️ 刪", key=f"delete_color_{i}"):
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

    # 安全初始化 form_customer
    if "form_customer" not in st.session_state or not isinstance(st.session_state.form_customer, dict):
        st.session_state.form_customer = {}

    # 初始化其他 session_state 變數
    init_states(["edit_customer_index", "delete_customer_index", "show_delete_customer_confirm", "search_customer"])

    # 確保所有欄位都有 key
    for col in columns:
        st.session_state.form_customer.setdefault(col, "")

    # 載入 Google Sheet 資料
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
        font-size: 30px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #dbd818; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🗿客戶搜尋</h2>',
        unsafe_allow_html=True
    )
  
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

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">➕新增客戶</h2>',
        unsafe_allow_html=True
    )

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

    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📋 客戶清單</h2>',
        unsafe_allow_html=True
    )

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

    # ------------------- 配方資料初始化 -------------------
    # 初始化 session_state
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = pd.DataFrame()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    def load_recipe_data():
        """嘗試依序載入配方資料，來源：Google Sheet > CSV > 空 DataFrame"""
        try:
            ws_recipe = spreadsheet.worksheet("配方資料")
            df_loaded = pd.DataFrame(ws_recipe.get_all_records())
            if not df_loaded.empty:
                return df_loaded
        except Exception as e:
            st.warning(f"Google Sheet 載入失敗：{e}")
    
        # 回退 CSV
        order_file = Path("data/df_recipe.csv")
        if order_file.exists():
            try:
                df_csv = pd.read_csv(order_file)
                if not df_csv.empty:
                    return df_csv
            except Exception as e:
                st.error(f"CSV 載入失敗：{e}")
    
        # 都失敗時，回傳空 df
        return pd.DataFrame()
    
    # 統一使用 df_recipe
    df_recipe = st.session_state.df_recipe

    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "建檔時間"
    ]

    # 初始化 session_state 需要的變數
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

    # ✅ 如果還是空的，顯示提示
    if df_recipe.empty:
        st.error("⚠️ 配方資料尚未載入，請確認 Google Sheet 或 CSV 是否有資料")
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
        font-size: 22px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #F9DC5C; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    # 🎯 配方建立（加上 id 與跳轉按鈕）
    st.markdown("""
    <div id="recipe-create" style="display: flex; align-items: center; gap: 10px;">
        <div class="big-title">🎯配方建立</div>
        <a href="#recipe-table" style="
            background-color: var(--background-color);
            color: var(--text-color);
            padding:4px 10px;
            border-radius:6px;
            text-decoration:none;
            font-size:14px;
            font-family:Arial;
        ">⬇ 跳到記錄表</a>
    </div>
    """, unsafe_allow_html=True)
  
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
    # 初始化 session_state
    if "form_recipe" not in st.session_state:
        st.session_state.form_recipe = {col: "" for col in columns}
    if "edit_recipe_index" not in st.session_state:
        st.session_state.edit_recipe_index = None
    if "num_powder_rows" not in st.session_state:
        st.session_state.num_powder_rows = 5

    # 只有在「新增模式」才設定預設值
    if st.session_state.edit_recipe_index is None:
        if not st.session_state.form_recipe.get("配方類別"):
            st.session_state.form_recipe["配方類別"] = "原始配方"
        if not st.session_state.form_recipe.get("狀態"):
            st.session_state.form_recipe["狀態"] = "啟用"
        if not st.session_state.form_recipe.get("色粉類別"):
            st.session_state.form_recipe["色粉類別"] = "配方"
        if not st.session_state.form_recipe.get("計量單位"):
            st.session_state.form_recipe["計量單位"] = "包"
        if not st.session_state.form_recipe.get("淨重單位"):
            st.session_state.form_recipe["淨重單位"] = "g"
        if not st.session_state.form_recipe.get("合計類別"):
            st.session_state.form_recipe["合計類別"] = "無"

    fr = st.session_state.form_recipe
        
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
        colr1, col_colon, colr2, colr3, col_unit = st.columns([2, 0.5, 2, 2, 1])

        with colr1:
            fr["比例1"] = st.text_input(
                "", value=fr.get("比例1", ""), key="ratio1", label_visibility="collapsed"
            )

        with col_colon:
            st.markdown(
                """
                <div style="display:flex; justify-content:center; align-items:center;
                            font-size:18px; font-weight:bold; height:36px;">
                    :
                </div>
                """,
                unsafe_allow_html=True
            )

        with colr2:
            fr["比例2"] = st.text_input(
                "", value=fr.get("比例2", ""), key="ratio2", label_visibility="collapsed"
            )

        with colr3:
            fr["比例3"] = st.text_input(
                "", value=fr.get("比例3", ""), key="ratio3", label_visibility="collapsed"
            )

        with col_unit:
            st.markdown(
                """
                <div style="display:flex; justify-content:flex-start; align-items:center;
                            font-size:16px; height:36px;">
                    g/kg
                </div>
                """,
                unsafe_allow_html=True
            )
    
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
    
        # CSS：縮小輸入框高度及上下間距，並壓縮 columns 間距
        st.markdown("""
        <style>
        /* 調整輸入框高度與 padding */
        div.stTextInput > div > div > input {
            padding: 2px 6px !important;
            height: 36px !important;
            font-size: 16px;
        }

        /* 調整 text_input 外層 margin */
        div.stTextInput {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }

        /* 調整 columns row 的 gap */
        [data-testid="stVerticalBlock"] > div[style*="gap"] {
            gap: 0px !important;        /* 列間距 */
            margin-bottom: 0px !important;
        }

        /* 調整 columns 裡 row container padding */
        section[data-testid="stHorizontalBlock"] {
            padding-top: -2px !important;
            padding-bottom: -2px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # 色粉設定多列
        st.markdown("#### 色粉設定")
        fr = st.session_state.form_recipe
        for i in range(1, st.session_state.get("num_powder_rows", 5) + 1):
            c1, c2 = st.columns([2.5, 2.5])
    
            # 色粉編號
            fr[f"色粉編號{i}"] = c1.text_input(
                "",  
                value=fr.get(f"色粉編號{i}", ""), 
                placeholder=f"色粉{i}編號",
                key=f"form_recipe_色粉編號{i}"
            )
    
            # 色粉重量
            fr[f"色粉重量{i}"] = c2.text_input(
                "",  
                value=fr.get(f"色粉重量{i}", ""), 
                placeholder="重量",
                key=f"form_recipe_色粉重量{i}"
            )
    
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
                df.iloc[st.session_state.edit_recipe_index] = pd.Series(fr, index=df.columns)
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

    # 3. --- 🔍 搜尋列區塊 ---    
    # 📑 配方記錄表（加上跳轉回去的按鈕）
    st.markdown("---")  # 分隔線

    st.markdown("""
    <div id="recipe-table" style="display: flex; align-items: center; gap: 10px;">
        <h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📑配方記錄表</h2>
        <a href="#recipe-create" style="
            background-color: var(--background-color);  /* 跟隨亮/暗模式 */
            color: var(--text-color);                  /* 跟隨亮/暗模式 */
            padding:4px 10px;
            border-radius:6px;
            text-decoration:none;
            font-size:14px;
            font-family:Arial;
        ">⬆ 回頁首</a>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        search_recipe_bottom = st.text_input("配方編號", key="search_recipe_code_bottom")
    with col2:
        search_customer_bottom = st.text_input("客戶名稱或編號", key="search_customer_bottom")
    with col3:
        search_pantone_bottom = st.text_input("Pantone色號", key="search_pantone_bottom")

    # 先初始化 top 欄位變數
    recipe_kw = st.session_state.get("search_recipe_code_bottom", "").strip()
    customer_kw = st.session_state.get("search_customer_bottom", "").strip()
    pantone_kw = st.session_state.get("search_pantone_bottom", "").strip()

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
    
    # ===== 計算分頁 =====
    total_rows = df_filtered.shape[0]
    limit = st.session_state.get("limit_per_page", 5)
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    if "page" not in st.session_state:
        st.session_state.page = 1
    if st.session_state.page > total_pages:
        st.session_state.page = total_pages
    
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
    
    # ===== 分頁控制列（按鈕 + 輸入跳頁 + 每頁筆數）=====
    cols_page = st.columns([1, 1, 1, 2, 1])  # 五欄：首頁 / 上一頁 / 下一頁 / 跳頁 / 每頁筆數
    
    with cols_page[0]:
        if st.button("🏠首頁", key="first_page"):
            st.session_state.page = 1
            st.experimental_rerun()
    
    with cols_page[1]:
        if st.button("🔼上一頁", key="prev_page") and st.session_state.page > 1:
            st.session_state.page -= 1
            st.experimental_rerun()
    
    with cols_page[2]:
        if st.button("🔽下一頁", key="next_page") and st.session_state.page < total_pages:
            st.session_state.page += 1
            st.experimental_rerun()
    
    with cols_page[3]:
        # 輸入跳頁
        jump_page = st.number_input(
            "",  # 不顯示文字
            min_value=1,
            max_value=total_pages,
            value=st.session_state.page,
            key="jump_page",
            label_visibility="collapsed"  # 隱藏標籤，位置上移
        )
        if jump_page != st.session_state.page:
            st.session_state.page = jump_page
            st.experimental_rerun()
    
    with cols_page[4]:
        # 每頁顯示筆數選單
        limit = st.selectbox(
            "",
            options=[5, 10, 20, 50, 100],
            index=[5, 10, 20, 50, 100].index(st.session_state.get("limit_per_page", 5)),
            key="limit_per_page",
            label_visibility="collapsed"  # 隱藏標籤，減少上方空白
        )
    
    st.caption(f"頁碼 {st.session_state.page} / {total_pages}，總筆數 {total_rows}")

    st.markdown("---")  # 分隔線

    st.markdown(
        '<h2 style="font-size:20px; font-family:Arial; color:#dbd818;">🛠️ 配方修改/刪除</h2>',
        unsafe_allow_html=True
    )
    
    # --- 配方下拉 + 修改/刪除 + 預覽 ---
    from pathlib import Path
    import pandas as pd
    import streamlit as st
    
    # ---------- 安全轉換函式 ----------
    def safe_str(val):
        return "" if val is None else str(val)
    
    def safe_float(val):
        try:
            return float(val)
        except:
            return 0
    
    def fmt_num(val, digits=2):
        try:
            num = float(val)
        except (TypeError, ValueError):
            return "0"
    
        return f"{num:.{digits}f}".rstrip("0").rstrip(".")    
    # ---------- 函式：生成配方預覽 ----------
    def generate_recipe_preview_text(order, recipe_row, show_additional_ids=True):
        html_text = ""
        # 主配方基本資訊
        html_text += f"編號：{safe_str(recipe_row.get('配方編號'))}  "
        html_text += f"顏色：{safe_str(recipe_row.get('顏色'))}  "
        proportions = " / ".join([safe_str(recipe_row.get(f"比例{i}", "")) 
                                  for i in range(1,4) if safe_str(recipe_row.get(f"比例{i}", ""))])
        html_text += f"比例：{proportions}  "
        html_text += f"計量單位：{safe_str(recipe_row.get('計量單位',''))}  "
        html_text += f"Pantone：{safe_str(recipe_row.get('Pantone色號',''))}\n\n"
    
        # 主配方色粉列
        colorant_weights = [safe_float(recipe_row.get(f"色粉重量{i}",0)) for i in range(1,9)]
        powder_ids = [safe_str(recipe_row.get(f"色粉編號{i}","")) for i in range(1,9)]
        for pid, wgt in zip(powder_ids, colorant_weights):
            if pid and wgt > 0:
                html_text += pid.ljust(12) + fmt_num(wgt) + "\n"
    
        # 主配方合計列
        total_label = safe_str(recipe_row.get("合計類別","="))
        net_weight = safe_float(recipe_row.get("淨重",0))
        if net_weight > 0:
            html_text += "_"*40 + "\n"
            html_text += total_label.ljust(12) + fmt_num(net_weight) + "\n"
    
        # 備註列
        note = safe_str(recipe_row.get("備註"))
        if note:
            html_text += f"備註 : {note}\n"
    
        # 附加配方
        main_code = safe_str(order.get("配方編號",""))
        if main_code and not df_recipe.empty:
            additional_recipe_rows = df_recipe[
                (df_recipe["配方類別"]=="附加配方") &
                (df_recipe["原始配方"].astype(str).str.strip() == main_code)
            ].to_dict("records")
        else:
            additional_recipe_rows = []
    
        if additional_recipe_rows:
            html_text += "\n=== 附加配方 ===\n"
            for idx, sub in enumerate(additional_recipe_rows,1):
                if show_additional_ids:
                    html_text += f"附加配方 {idx}：{safe_str(sub.get('配方編號'))}\n"
                else:
                    html_text += f"附加配方 {idx}\n"
                sub_colorant_weights = [safe_float(sub.get(f"色粉重量{i}",0)) for i in range(1,9)]
                sub_powder_ids = [safe_str(sub.get(f"色粉編號{i}","")) for i in range(1,9)]
                for pid, wgt in zip(sub_powder_ids, sub_colorant_weights):
                    if pid and wgt > 0:
                        html_text += pid.ljust(12) + fmt_num(wgt) + "\n"
                total_label_sub = safe_str(sub.get("合計類別","=")) or "="
                net_sub = safe_float(sub.get("淨重",0))
                if net_sub > 0:
                    html_text += "_"*40 + "\n"
                    html_text += total_label_sub.ljust(12) + fmt_num(net_sub) + "\n"
    
        # 色母專用
        if safe_str(recipe_row.get("色粉類別"))=="色母":
            html_text += "\n色母專用預覽：\n"
            for pid, wgt in zip(powder_ids, colorant_weights):
                if pid and wgt > 0:
                    html_text += f"{pid.ljust(8)}{fmt_num(wgt).rjust(8)}\n"
            total_colorant = net_weight - sum(colorant_weights)
            if total_colorant > 0:
                category = safe_str(recipe_row.get("合計類別", "料"))
                html_text += f"{category.ljust(8)}{fmt_num(total_colorant).rjust(8)}\n"
    
        return "```\n" + html_text.strip() + "\n```"
    
    # ---------- 配方下拉選單 + 修改/刪除 + 預覽 ----------
    if not df_recipe.empty and "配方編號" in df_recipe.columns:
        df_recipe["配方編號"] = df_recipe["配方編號"].astype(str)

        # ---------- 自動選單邏輯 ----------
        default_index = None
        if 'df_filtered' in locals() and len(df_filtered) == 1:
            only_code = df_filtered.iloc[0]["配方編號"]
            default_index = df_recipe.index[df_recipe["配方編號"] == only_code][0]

        # ---------- 同一橫列 Columns ----------
        # ---------- 配方下拉選單 ----------
        selected_index = st.selectbox(
            "選擇配方",
            options=df_recipe.index,
            format_func=lambda i: f"{df_recipe.at[i, '配方編號']} | {df_recipe.at[i, '顏色']} | {df_recipe.at[i, '客戶名稱']}",
            key="select_recipe_code_page",
            index=df_recipe.index.get_loc(default_index) if default_index is not None else 0
        )

        selected_code = df_recipe.at[selected_index, "配方編號"] if selected_index is not None else None

        # ---------- 配方預覽 + 修改 / 刪除按鈕同一橫列 ----------
        if selected_code:
            recipe_row_preview = df_recipe.loc[selected_index].to_dict()
            preview_text_recipe = generate_recipe_preview_text(
                {"配方編號": recipe_row_preview.get("配方編號")},
                recipe_row_preview
            )

            cols_preview = st.columns([6, 0.7, 0.7])  # 預覽 + 修改 + 刪除
            with cols_preview[0]:
                auto_expand = False
                if 'df_filtered' in locals() and len(df_filtered) == 1:
                    auto_expand = True
                with st.expander("👀 配方預覽", expanded=auto_expand):
                    st.markdown(preview_text_recipe, unsafe_allow_html=True)

            with cols_preview[1]:
                if st.button("✏️ ", key="edit_btn"):
                    st.session_state.edit_recipe_index = selected_index
                    st.session_state.form_recipe = df_recipe.loc[selected_index].to_dict()
                    st.rerun()

            with cols_preview[2]:
                if st.button("🗑️ ", key="del_btn"):
                    st.session_state.delete_recipe_index = selected_index
                    st.session_state.show_delete_recipe_confirm = True
                    st.rerun()

        else:
            st.info("🟦 沒有可選的配方編號")

    # 頁面最下方手動載入按鈕
    st.markdown("---")
    if st.button("📥 重新載入配方資料"):
        st.session_state.df_recipe = load_recipe_data()
        st.success("配方資料已重新載入！")
        st.experimental_rerun()
        # 頁面最下方手動載入按鈕
        st.markdown("---")
        if st.button("📥 重新載入配方資料"):
            st.session_state.df_recipe = load_recipe_data()
            st.success("配方資料已重新載入！")
            st.experimental_rerun()  # 重新載入頁面，更新資料
            
    # --- 生產單分頁 ----------------------------------------------------
elif menu == "生產單管理":
    st.markdown("""
    <style>
    .big-title {
        font-size: 22px;
        font-weight: bold;
        color: #F9DC5C;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🛸生產單建立</div>', unsafe_allow_html=True)

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
    
    # 載入配方管理表
    try:
        records = ws_recipe.get_all_records()
        df_recipe = pd.DataFrame(records)
        df_recipe.columns = df_recipe.columns.str.strip()
        df_recipe.fillna("", inplace=True)
    
        if "配方編號" in df_recipe.columns:
            # 先清理再補零
            df_recipe["配方編號"] = df_recipe["配方編號"].map(lambda x: fix_leading_zero(clean_powder_id(x)))
        if "客戶名稱" in df_recipe.columns:
            df_recipe["客戶名稱"] = df_recipe["客戶名稱"].map(clean_powder_id)
        if "原始配方" in df_recipe.columns:
            df_recipe["原始配方"] = df_recipe["原始配方"].map(clean_powder_id)
    
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
    
    # Streamlit UI 搜尋表單
    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")
    
        search_text_original = search_text.strip()
        search_text_normalized = fix_leading_zero(search_text.strip())
        search_text_upper = search_text.strip().upper()
    
        if search_text_normalized:
            df_recipe["_配方編號標準"] = df_recipe["配方編號"].map(lambda x: fix_leading_zero(clean_powder_id(x)))
    
            if exact:
                filtered = df_recipe[
                    (df_recipe["_配方編號標準"] == search_text_normalized) |
                    (df_recipe["客戶名稱"].str.upper() == search_text_upper)
                ]
            else:
                filtered = df_recipe[
                    df_recipe["_配方編號標準"].str.contains(search_text_normalized, case=False, na=False) |
                    df_recipe["客戶名稱"].str.contains(search_text.strip(), case=False, na=False)
                ]
            filtered = filtered.copy()
            filtered.drop(columns=["_配方編號標準"], inplace=True)
        else:
            filtered = df_recipe.copy()
    
    # 建立搜尋結果標籤與選項
    def format_option(r):
        label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
        if r.get("配方類別", "") == "附加配方":
            label += "（附加配方）"
        return label
    
    if not filtered.empty:
        filtered["label"] = filtered.apply(format_option, axis=1)
        option_map = dict(zip(filtered["label"], filtered.to_dict(orient="records")))
    else:
        option_map = {}
    
    if not option_map:
        st.warning("查無符合的配方")
        selected_row = None
        selected_label = None
    elif len(option_map) == 1:
        selected_label = list(option_map.keys())[0]
        selected_row = option_map[selected_label].copy()  # 複製，避免修改原資料
    
        # 直接用搜尋結果的真實配方編號帶入，不用用輸入字串
        true_formula_id = selected_row["配方編號"]
        selected_row["配方編號_原始"] = true_formula_id
    
        # 顯示標籤（用真實配方編號）
        parts = selected_label.split(" | ", 1)
        if len(parts) > 1:
            display_label = f"{selected_row['配方編號']} | {parts[1]}"
        else:
            display_label = selected_row['配方編號']
    
        st.success(f"已自動選取：{display_label}")
    else:
        selected_label = st.selectbox(
            "選擇配方",
            ["請選擇"] + list(option_map.keys()),
            index=0,
            key="search_add_form_selected_recipe"
        )
        if selected_label == "請選擇":
            selected_row = None
        else:
            selected_row = option_map.get(selected_label)
    
    if add_btn:
        if selected_label is None or selected_label == "請選擇" or selected_label == "（無符合配方）":
            st.warning("請先選擇有效配方")
        else:
            if selected_row.get("狀態") == "停用":
                st.warning("⚠️ 此配方已停用，請勿使用")
                st.stop()
            else:
                # 取得或初始化新訂單物件
                order = st.session_state.get("new_order")
                if order is None or not isinstance(order, dict):
                    order = {}
    
                # 產生新的生產單號
                df_all_orders = st.session_state.df_order.copy()
                today_str = datetime.now().strftime("%Y%m%d")
                count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
                new_id = f"{today_str}-{count_today + 1:03}"
    
                # 查找附加配方
                main_recipe_code = selected_row.get("配方編號", "").strip()
                df_recipe["配方類別"] = df_recipe["配方類別"].astype(str).str.strip()
                df_recipe["原始配方"] = df_recipe["原始配方"].astype(str).str.strip()
                附加配方 = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"] == main_recipe_code)
                ]
    
                # 整合色粉：先加入主配方色粉
                all_colorants = []
                for i in range(1, 9):
                    id_key = f"色粉編號{i}"
                    wt_key = f"色粉重量{i}"
                    id_val = selected_row.get(id_key, "")
                    wt_val = selected_row.get(wt_key, "")
                    if id_val or wt_val:
                        all_colorants.append((id_val, wt_val))
    
                # 加入附加配方色粉
                for _, sub in 附加配方.iterrows():
                    for i in range(1, 9):
                        id_key = f"色粉編號{i}"
                        wt_key = f"色粉重量{i}"
                        id_val = sub.get(id_key, "")
                        wt_val = sub.get(wt_key, "")
                        if id_val or wt_val:
                            all_colorants.append((id_val, wt_val))
    
                # 設定訂單詳細資料（先更新其他欄位）
                order.update({
                    "生產單號": new_id,
                    "生產日期": datetime.now().strftime("%Y-%m-%d"),
                    "建立時間": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                    "配方編號": selected_row.get("配方編號", search_text_original),
                    "顏色": selected_row.get("顏色", ""),
                    "客戶名稱": selected_row.get("客戶名稱", ""),
                    "Pantone 色號": selected_row.get("Pantone色號", ""),
                    "計量單位": selected_row.get("計量單位", ""),
                    "備註": str(selected_row.get("備註", "")).strip(),
                    "重要提醒": str(selected_row.get("重要提醒", "")).strip(),
                    "合計類別": str(selected_row.get("合計類別", "")).strip(),
                    "色粉類別": selected_row.get("色粉類別", "").strip(),
                })
    
                # 用 all_colorants 填入色粉編號與重量欄位
                for i in range(1, 9):
                    id_key = f"色粉編號{i}"
                    wt_key = f"色粉重量{i}"
                    if i <= len(all_colorants):
                        id_val, wt_val = all_colorants[i-1]
                        order[id_key] = id_val
                        order[wt_key] = wt_val
                    else:
                        order[id_key] = ""
                        order[wt_key] = ""
    
                st.session_state["new_order"] = order
                st.session_state["show_confirm_panel"] = True
    
                # 重新執行應用（Streamlit 1.18+ 建議用 st.experimental_rerun）
                st.rerun()              
    
    # ---------- 新增後欄位填寫區塊 ----------
    # ===== 主流程頁面切換 =====
    page = st.session_state.get("page", "新增生產單")
    if page == "新增生產單":
        order = st.session_state.get("new_order")
        if order is None or not isinstance(order, dict):
            order = {}
    
        recipe_id_raw = order.get("配方編號", "").strip()

        recipe_id = fix_leading_zero(clean_powder_id(recipe_id_raw))
        
        matched = df_recipe[df_recipe["配方編號"].map(lambda x: fix_leading_zero(clean_powder_id(str(x)))) == recipe_id]
        
        if not matched.empty:
            recipe_row = matched.iloc[0].to_dict()
            recipe_row = {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in recipe_row.items()}
            st.session_state["recipe_row_cache"] = recipe_row
        else:
            recipe_row = {}
    
        # 這裡從 session_state 讀取 show_confirm_panel，避免被覆蓋
        show_confirm_panel = st.session_state.get("show_confirm_panel", False)
    
        # 強制帶入配方欄位值，避免原本 order 已有空字串導致沒更新
        for field in ["合計類別", "備註", "重要提醒"]:
            order[field] = recipe_row.get(field, "")
        
        # 只有 recipe_id 有值才處理附加配方邏輯
        if recipe_id:
            # ---------- 安全取得附加配方 ----------
            def get_additional_recipes(df, main_recipe_code):
                df = df.copy()
                df["配方類別"] = df["配方類別"].astype(str).str.strip()
                df["原始配方"] = df["原始配方"].astype(str).str.strip()
                main_code = str(main_recipe_code).strip()
                return df[(df["配方類別"] == "附加配方") & (df["原始配方"] == main_code)]
        
            additional_recipes = get_additional_recipes(df_recipe, recipe_id)
        
            if additional_recipes.empty:
                st.info("無附加配方")
                order["附加配方"] = []
            else:
                st.markdown(f"<span style='font-size:14px; font-weight:bold;'>附加配方清單（共 {len(additional_recipes)} 筆）</span>", unsafe_allow_html=True)
        
                for idx, row in additional_recipes.iterrows():
                    with st.expander(f"附加配方：{row.get('配方編號', '')} - {row.get('顏色', '')}"):
                        st.write(row)  # 可顯示完整欄位，也可以選擇只顯示必要欄位
        
                        # 分欄顯示色粉編號與色粉重量
                        col1, col2 = st.columns(2)
                        with col1:
                            color_ids = {f"色粉編號{i}": row.get(f"色粉編號{i}", "") for i in range(1, 9)}
                            st.write("色粉編號", color_ids)
                        with col2:
                            color_wts = {f"色粉重量{i}": row.get(f"色粉重量{i}", "") for i in range(1, 9)}
                            st.write("色粉重量", color_wts)
        
                # ---------- 寫入 order["附加配方"] ----------
                order["附加配方"] = [
                    {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
                    for _, row in additional_recipes.iterrows()
                ]
        else:
            order["附加配方"] = []  # 空配方時預設為空 list
 
                
        st.session_state.new_order = order
        st.session_state.show_confirm_panel = show_confirm_panel
            
        # 搜尋或配方存在時才顯示新增生產單表單
        if st.session_state.get("show_confirm_panel"):
            unit = recipe_row.get("計量單位", "kg") if recipe_row else "kg"
            print_html = generate_print_page_content(order, recipe_row, order.get("附加配方"))
        
            st.markdown("---")
            st.markdown("<span style='font-size:20px; font-weight:bold;'>新增生產單詳情填寫</span>", unsafe_allow_html=True)
        
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
                                
                # --- 主配方區塊 ---
                st.markdown("##### 色粉用量（編號與重量）")
                色粉編號欄, 色粉重量欄 = st.columns(2)
                for i in range(1, 9):
                    color_id = recipe_row.get(f"色粉編號{i}", "").strip()
                    color_wt = recipe_row.get(f"色粉重量{i}", "").strip()
                    if color_id or color_wt:  # ✅ 有內容才顯示
                        with 色粉編號欄:
                            st.text_input(f"色粉編號{i}", value=color_id, disabled=True, key=f"form_main_color_id_{i}")
                        with 色粉重量欄:
                            st.text_input(f"色粉重量{i}", value=color_wt, disabled=True, key=f"form_main_color_weight_{i}")
                
                # 顯示配方淨重
                st.markdown(
                    f"<div style='text-align:right; font-size:16px; margin-top:-10px;'>🔢 配方淨重：{recipe_row.get('淨重', '')} {recipe_row.get('淨重單位', '')}</div>",
                    unsafe_allow_html=True
                )

                # 顯示合計類別
                total_category = recipe_row.get("合計類別", "")
                if total_category:
                    st.markdown(
                        f"<div style='text-align:right; font-size:16px; font-weight:bold; margin-bottom:10px;'>合計: {total_category}</div>",
                        unsafe_allow_html=True
                    )
                
                # --- 附加配方區塊 ---
                附加配方清單 = order.get("附加配方", [])
                if 附加配方清單:
                    st.markdown("##### 附加配方色粉用量（編號與重量）")
                    for idx, 附加配方 in enumerate(附加配方清單, 1):
                        st.markdown(f"##### 附加配方 {idx}")
                        col1, col2 = st.columns(2)
                        for i in range(1, 9):
                            color_id = 附加配方.get(f"色粉編號{i}", "").strip()
                            color_wt = 附加配方.get(f"色粉重量{i}", "").strip()
                            if color_id or color_wt:  # ✅ 有內容才顯示
                                with col1:
                                    st.text_input(f"附加色粉編號_{idx}_{i}", value=color_id, disabled=True, key=f"form_add_color_id_{idx}_{i}")
                                with col2:
                                    st.text_input(f"附加色粉重量_{idx}_{i}", value=color_wt, disabled=True, key=f"form_add_color_wt_{idx}_{i}")
                
                        # 顯示附加配方淨重
                        try:
                            total_net = float(附加配方.get("淨重", 0))
                        except:
                            total_net = 0
                        unit = 附加配方.get("淨重單位", "")
                        st.markdown(
                            f"<div style='text-align:right; font-size:16px;'>📦 附加配方淨重：{total_net:.2f} {unit}</div>",
                            unsafe_allow_html=True
                        )
  
                submitted = st.form_submit_button("💾 儲存生產單")
        
            if submitted:
                order["顏色"] = st.session_state.form_color
                order["Pantone 色號"] = st.session_state.form_pantone
                order["料"] = st.session_state.form_raw_material
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
        
            # 產生列印 HTML 按鈕
            # ✅ 加入 checkbox 讓使用者決定是否顯示附加配方編號
            show_ids = st.checkbox("列印時顯示附加配方編號", value=False)
            
            # 產生列印 HTML
            print_html = generate_print_page_content(
                order=order,
                recipe_row=recipe_row,
                additional_recipe_rows=order.get("附加配方", []),
                show_additional_ids=show_ids
            )
            
            # 下載按鈕         
            col1, col2, col3 = st.columns([3, 1, 3])
            with col1:
                st.download_button(
                    label="📥 下載 A5 HTML",
                    data=print_html.encode("utf-8"),
                    file_name=f"{order['生產單號']}_列印.html",
                    mime="text/html"
                )
            
            with col3:
                if st.button("🔙 返回", key="back_button"):
                    st.session_state.new_order = None
                    st.session_state.show_confirm_panel = False
                    st.session_state.new_order_saved = False
                    st.rerun()
                            
    # ---------- 生產單清單 + 修改 / 刪除 ----------
    st.markdown("---")
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#F9DC5C;">📑 生產單記錄表</h2>',
        unsafe_allow_html=True
    )
    
    # 預先初始化
    order_dict = {}
    recipe_row = {}
    additional_recipe_rows = []
    selected_code_edit = None
    selected_label = None
    
    search_order = st.text_input(
        "搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)",
        key="search_order_input_order_page",
        value=""
    )
    
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
    else:
        df_filtered = df_order.copy()
    
    # 轉換建立時間並排序
    df_filtered["建立時間"] = pd.to_datetime(df_filtered["建立時間"], errors="coerce")
    df_filtered = df_filtered.sort_values(by="建立時間", ascending=False)
    
    # ---- limit 下拉選單要先定義（因為會影響 total_pages）----
    import re
    import streamlit as st
    import pandas as pd
    
    # ---- 初始化 limit 下拉選單（只用在下方分頁列） ----
    if "selectbox_order_limit" not in st.session_state:
        st.session_state.selectbox_order_limit = 5  # 預設每頁 5 筆
    
    # ===== 計算分頁 =====
    total_rows = len(df_filtered)
    limit = st.session_state.selectbox_order_limit
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    # 初始化或限制頁碼
    if "order_page" not in st.session_state:
        st.session_state.order_page = 1
    if st.session_state.order_page > total_pages:
        st.session_state.order_page = total_pages
    
    # ===== 分頁索引 =====
    start_idx = (st.session_state.order_page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx].copy()
    
    # ===== 定義 calculate_shipment 函式 =====
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
    
    # ===== 計算出貨數量 =====
    if not page_data.empty:
        page_data["出貨數量"] = page_data.apply(calculate_shipment, axis=1)
    
    # ===== 顯示表格 =====
    display_cols = ["生產單號", "配方編號", "顏色", "客戶名稱", "出貨數量", "建立時間"]
    existing_cols = [c for c in display_cols if c in page_data.columns]
    
    if not page_data.empty and existing_cols:
        st.dataframe(
            page_data[existing_cols].reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("查無符合的資料（分頁結果）")
    
    # ===== 分頁控制列（五個橫排） =====
    cols_page = st.columns([2, 2, 2, 2, 2])
    
    # 首頁
    with cols_page[0]:
        if st.button("🏠首頁", key="first_page"):
            st.session_state.order_page = 1
            st.experimental_rerun()
    
    # 上一頁
    with cols_page[1]:
        if st.button("🔼上一頁", key="prev_page") and st.session_state.order_page > 1:
            st.session_state.order_page -= 1
            st.experimental_rerun()
    
    # 下一頁
    with cols_page[2]:
        if st.button("🔽下一頁", key="next_page") and st.session_state.order_page < total_pages:
            st.session_state.order_page += 1
            st.rerun()
    
    # 輸入跳頁
    with cols_page[3]:
        jump_page = st.number_input(
            "",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.order_page,
            key="jump_page",
            label_visibility="collapsed"
        )
        if jump_page != st.session_state.order_page:
            st.session_state.order_page = jump_page
            st.rerun()
    
    # ------------------- 刪除生產單工具函式 -------------------
    def delete_order_by_id(ws, order_id):
        """直接刪除 Google Sheet 中的某一筆生產單"""
        all_values = ws.get_all_records()
        df = pd.DataFrame(all_values)
    
        if df.empty:
            return False
    
        # 找到目標列
        target_idx = df.index[df["生產單號"] == order_id].tolist()
        if not target_idx:
            return False
    
        # gspread 是 1-based row index，+2 是因為第1列是標題，第2列才是資料
        row_number = target_idx[0] + 2
        ws.delete_rows(row_number)
        return True
    
    
    # ------------------- 分頁數筆數選擇（下拉選單） -------------------
    with cols_page[4]:
        options_list = [5, 10, 20, 50, 75, 100]
        # 取得當前值，如果不在 options_list 裡就預設為 5
        current_limit = st.session_state.get("selectbox_order_limit", 5)
        if current_limit not in options_list:
            current_limit = 5
    
        new_limit = st.selectbox(
            label=" ",  # 空白標籤，不會占用高度
            options=options_list,
            index=options_list.index(current_limit),
            key="selectbox_order_limit",
            label_visibility="collapsed"
        )
    
        # 如果改變了每頁筆數，跳回首頁並刷新
        if new_limit != st.session_state.selectbox_order_limit:
            st.session_state.selectbox_order_limit = new_limit
            st.session_state.order_page = 1
            st.rerun()
    
    st.caption(f"頁碼 {st.session_state.order_page} / {total_pages}，總筆數 {total_rows}")
    st.markdown(" ")

    
    st.markdown("---")  # 分隔線
    
    # ------------------- 選擇生產單號 -------------------
    st.markdown(
        '<h2 style="font-size:20px; font-family:Arial; color:#F9DC5C;">🛠️ 生產單修改/刪除</h2>',
        unsafe_allow_html=True
    )

    options = []
    code_to_id = {}
    if not page_data.empty:
        for idx, row in page_data.iterrows():
            label = f"{row['生產單號']} / {row['配方編號']} / {row.get('顏色','')} / {row.get('客戶名稱','')}"
            options.append(label)
            code_to_id[label] = row["生產單號"]

    # ---------- 同一橫列 Columns ----------
    cols_top2 = st.columns([5, 0.7])  # 下拉 + 刪除按鈕
    with cols_top2[0]:
        selected_label = st.selectbox(
            "選擇生產單號",
            options or ["無資料"],
            key="select_order_for_edit_from_list"
        )
    
    # ------------------- 預覽函式 -------------------
    def generate_order_preview_text(order, recipe_row, show_additional_ids=True):
        # 1️⃣ 先生成主配方文字（不改 generate_production_order_print）
        html_text = generate_production_order_print(
            order,
            recipe_row,
            additional_recipe_rows=None,
            show_additional_ids=show_additional_ids
        )
    
        # 2️⃣ 取得附加配方（保留原本邏輯）
        main_code = str(order.get("配方編號", "")).strip()
        if main_code:
            additional_recipe_rows = df_recipe[
                (df_recipe["配方類別"] == "附加配方") &
                (df_recipe["原始配方"].astype(str).str.strip() == main_code)
            ].to_dict("records")
        else:
            additional_recipe_rows = []
    
        # 3️⃣ 附加配方顯示
        if additional_recipe_rows:
            powder_label_width = 12
            number_col_width = 7
            multipliers = []
            for j in range(1, 5):
                try:
                    w = float(order.get(f"包裝重量{j}", 0) or 0)
                except Exception:
                    w = 0
                if w > 0:
                    multipliers.append(w)
            if not multipliers:
                multipliers = [1.0]
    
            def fmt_num(x: float) -> str:
                if abs(x - int(x)) < 1e-9:
                    return str(int(x))
                return f"{x:g}"
    
            html_text += "<br>=== 附加配方 ===<br>"
    
            for idx, sub in enumerate(additional_recipe_rows, 1):
                if show_additional_ids:
                    html_text += f"附加配方 {idx}：{sub.get('配方編號','')}<br>"
                else:
                    html_text += f"附加配方 {idx}<br>"
    
                for i in range(1, 9):
                    c_id = str(sub.get(f"色粉編號{i}", "") or "").strip()
                    try:
                        base_w = float(sub.get(f"色粉重量{i}", 0) or 0)
                    except Exception:
                        base_w = 0.0
    
                    if c_id and base_w > 0:
                        cells = []
                        for m in multipliers:
                            val = base_w * m
                            cells.append(fmt_num(val).rjust(number_col_width))
                        row = c_id.ljust(powder_label_width) + "".join(cells)
                        html_text += row + "<br>"
    
                total_label = str(sub.get("合計類別", "=") or "=")
                try:
                    net = float(sub.get("淨重", 0) or 0)
                except Exception:
                    net = 0.0
                total_line = total_label.ljust(powder_label_width)
                for idx, m in enumerate(multipliers):
                    val = net * m
                    total_line += fmt_num(val).rjust(number_col_width)
                html_text += total_line + "<br>"
    
        # 4️⃣ 色母專用預覽（獨立變數，不影響其他邏輯）
        def fmt_num_colorant(x: float) -> str:
            if abs(x - int(x)) < 1e-9:
                return str(int(x))
            return f"{x:g}"

        # 備註列
        note_text = str(recipe_row.get("備註","")).strip()
        if note_text:
            html_text += f"備註 : {note_text}<br><br>"  # ✅ 這裡多加一個 <br> 空一行
    
        # 色母/色粉區（下方）排版
        category_colorant = str(recipe_row.get("色粉類別","")).strip()
        if category_colorant == "色母":
            # 包裝列（純顯示）
            pack_weights_display = [float(order.get(f"包裝重量{i}",0) or 0) for i in range(1,5)]
            pack_counts_display  = [float(order.get(f"包裝份數{i}",0) or 0) for i in range(1,5)]
            
            pack_line = []
            for w, c in zip(pack_weights_display, pack_counts_display):
                if w > 0 and c > 0:
                    val = int(w * 100)  # 基準值 100K
                    pack_line.append(f"{val}K × {int(c)}")
            
            if pack_line:
                html_text += " " * 14 + "  ".join(pack_line) + "<br>"
            
            # 色粉列
            colorant_weights = [float(recipe_row.get(f"色粉重量{i}",0) or 0) for i in range(1,9)]
            powder_ids = [str(recipe_row.get(f"色粉編號{i}","") or "").strip() for i in range(1,9)]
            
            number_col_width = 12  # 對齊寬度
            for pid, wgt in zip(powder_ids, colorant_weights):
                if pid and wgt > 0:
                    line = pid.ljust(6)
                    for w in pack_weights_display:
                        if w > 0:
                            val = wgt * w  # 色粉乘上包裝重量
                            line += str(int(val)).rjust(number_col_width)
                    html_text += line + "<br>"
            
            # 色母合計列
            total_colorant = float(recipe_row.get("淨重",0) or 0) - sum(colorant_weights)
            total_line_colorant = "料".ljust(12)
            
            # 自訂每欄寬度（第一欄偏左，第二欄偏右）
            col_widths = [5, 12, 12, 12]  # 可依實際欄位數調整
            
            for idx, w in enumerate(pack_weights_display):
                if w > 0:
                    val = total_colorant * w
                    width = col_widths[idx] if idx < len(col_widths) else 12
                    total_line_colorant += str(int(val)).rjust(width)
            
            html_text += total_line_colorant + "<br>"
    
        # 轉為純文字（保留對齊）
        text_with_newlines = html_text.replace("<br>", "\n")
        plain_text = re.sub(r"<.*?>", "", text_with_newlines)
        return "```\n" + plain_text.strip() + "\n```"
        
    # ------------------- 顯示預覽 -------------------
    if selected_label and selected_label != "無資料":
        selected_code_edit = code_to_id[selected_label]
        order_row = df_order[df_order["生產單號"] == selected_code_edit]

        if not order_row.empty:
            order_dict = order_row.iloc[0].to_dict()
            order_dict = {k: "" if v is None or pd.isna(v) else str(v) for k, v in order_dict.items()}

            recipe_rows = df_recipe[df_recipe["配方編號"] == order_dict.get("配方編號","")]
            recipe_row = recipe_rows.iloc[0].to_dict() if not recipe_rows.empty else {}

            # checkbox 狀態
            show_ids_key = f"show_ids_checkbox_{selected_code_edit}"
            if show_ids_key not in st.session_state:
                st.session_state[show_ids_key] = True

            show_ids = st.checkbox(
                "預覽時顯示附加配方編號",
                value=st.session_state[show_ids_key],
                key=show_ids_key
            )

            preview_text = generate_order_preview_text(order_dict, recipe_row, show_additional_ids=show_ids)

            # ---------- 同一橫排 Columns：左邊預覽，右邊刪除按鈕 ----------
            cols_preview_order = st.columns([6, 1.2])  # 右邊留寬一點
            with cols_preview_order[0]:
                with st.expander("👀 生產單預覽", expanded=False):
                    st.markdown(preview_text, unsafe_allow_html=True)

            with cols_preview_order[1]:
                col_btn1, col_btn2 = st.columns(2)  # 再切兩欄放「修改」和「刪除」
                with col_btn1:
                    if st.button("✏️ ", key="edit_order_btn"):
                        st.session_state["show_edit_panel"] = True
                        st.session_state["editing_order"] = order_dict
                        st.rerun()
                with col_btn2:
                    if st.button("🗑️ ", key="delete_order_btn"):
                        st.session_state["delete_target_id"] = selected_code_edit
                        st.session_state["delete_target_label"] = selected_label
                        st.session_state["show_delete_confirm"] = True

            # ------------------- 確認刪除 -------------------
            if st.session_state.get("show_delete_confirm", False):
                order_id = st.session_state["delete_target_id"]
                order_label = st.session_state.get("delete_target_label", order_id)
    
                st.warning(f"⚠️ 確定要刪除生產單？\n\n👉 {order_label}")
    
                c1, c2 = st.columns(2)
                if c1.button("✅ 是，刪除", key="confirm_delete_yes"):
                    deleted = delete_order_by_id(ws_orders, order_id)
                    if deleted:
                        st.success(f"✅ 已刪除 {order_label}")
                    else:
                        st.error("❌ 找不到該生產單，刪除失敗")
                    st.session_state["show_delete_confirm"] = False
                    st.rerun()
    
                if c2.button("取消", key="confirm_delete_no"):
                    st.session_state["show_delete_confirm"] = False
                    st.rerun()

    # 修改面板（如果有啟動）
    if st.session_state.get("show_edit_panel") and st.session_state.get("editing_order"):
        st.markdown("---")
        st.markdown(
            f"<p style='font-size:18px; font-weight:bold; color:#fceca6;'>✏️ 修改生產單 {st.session_state.editing_order['生產單號']}</p>",
            unsafe_allow_html=True
        )

        # 🔽 在這裡插入一行說明
        st.caption("⚠️：『儲存修改』僅同步更新Google Sheets作記錄修正用；若需列印，請先刪除原生產單，並重新建立新生產單。")
        
        order_no = st.session_state.editing_order["生產單號"]
        
        # 從 df_order 取得最新 row
        order_row = df_order[df_order["生產單號"] == order_no]
        if order_row.empty:
            st.warning(f"找不到生產單號：{order_no}")
            st.stop()
        order_dict = order_row.iloc[0].to_dict()  # 統一欄位格式
        
        # 取得對應配方資料
        recipe_id = order_dict.get("配方編號", "")
        recipe_rows = df_recipe[df_recipe["配方編號"] == recipe_id]
        if recipe_rows.empty:
            st.warning(f"找不到配方編號：{recipe_id}")
            st.stop()
        recipe_row = recipe_rows.iloc[0]
        
        # 表單編輯欄位
        col_cust, col_color = st.columns(2)  # 建立兩欄
        with col_cust:
            new_customer = st.text_input("客戶名稱", value=order_dict.get("客戶名稱", ""), key="edit_customer_name")
        with col_color:
            new_color = st.text_input("顏色", value=order_dict.get("顏色", ""), key="edit_color")
    
        # 包裝重量 1~4
        pack_weights_cols = st.columns(4)
        new_packing_weights = []
        for i in range(1, 5):
            weight = pack_weights_cols[i - 1].text_input(
                f"包裝重量{i}", value=order_dict.get(f"包裝重量{i}", ""), key=f"edit_packing_weight_{i}"
            )
            new_packing_weights.append(weight)
    
        # 包裝份數 1~4
        pack_counts_cols = st.columns(4)
        new_packing_counts = []
        for i in range(1, 5):
            count = pack_counts_cols[i - 1].text_input(
                f"包裝份數{i}", value=order_dict.get(f"包裝份數{i}", ""), key=f"edit_packing_count_{i}"
            )
            new_packing_counts.append(count)
    
        new_remark = st.text_area("備註", value=order_dict.get("備註", ""), key="edit_remark")
    
        
        cols_edit = st.columns([1, 1, 1])
    
        with cols_edit[0]:
            if st.button("💾 儲存修改", key="save_edit_button"):
                idx_list = df_order.index[df_order["生產單號"] == order_no].tolist()

                if idx_list:
                    idx = idx_list[0]

                    # === 更新本地 DataFrame ===
                    df_order.at[idx, "客戶名稱"] = new_customer
                    df_order.at[idx, "顏色"] = new_color
                    for i in range(4):
                        df_order.at[idx, f"包裝重量{i + 1}"] = new_packing_weights[i]
                        df_order.at[idx, f"包裝份數{i + 1}"] = new_packing_counts[i]
                    df_order.at[idx, "備註"] = new_remark

                    # === 同步更新 Google Sheets ===
                    try:
                        cell = ws_order.find(order_no)
                        if cell:
                            row_idx = cell.row
                            row_data = df_order.loc[idx].fillna("").astype(str).tolist()
                            last_col_letter = chr(65 + len(row_data) - 1)
                            ws_order.update(f"A{row_idx}:{last_col_letter}{row_idx}", [row_data])
                            st.success(f"✅ 生產單 {order_no} 已更新並同步！")
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
                st.rerun()

# ======== 交叉查詢分頁 =========
menu = st.session_state.get("menu", "色粉管理")  # 預設值可以自己改

if menu == "交叉查詢區":
    import pandas as pd

    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())

    # ---------------- 第一段：交叉查詢 ----------------
    st.markdown(
        '<h1 style="font-size:22px; font-family:Arial; color:#dbd818;">♻️ 依色粉編號查配方</h1>',
        unsafe_allow_html=True
    )

    # 輸入最多四個色粉編號
    cols = st.columns(5)
    inputs = []
    for i in range(5):
        val = cols[i].text_input(f"色粉編號{i+1}", key=f"cross_color_{i}")
        if val.strip():
            inputs.append(val.strip())

    if st.button("查詢配方", key="btn_cross_query") and inputs:
        # 篩選符合的配方
        mask = df_recipe.apply(
            lambda row: all(
                inp in row[[f"色粉編號{i}" for i in range(1, 9)]].astype(str).tolist() 
                for inp in inputs
            ),
            axis=1
        )
        matched = df_recipe[mask].copy()

        if matched.empty:
            st.warning("⚠️ 找不到符合的配方")
        else:
            results = []
            for _, recipe in matched.iterrows():
                # 找最近的生產日期
                orders = df_order[df_order["配方編號"].astype(str) == str(recipe["配方編號"])]
                last_date = pd.NaT
                if not orders.empty and "生產日期" in orders.columns:
                    orders["生產日期"] = pd.to_datetime(orders["生產日期"], errors="coerce")
                    last_date = orders["生產日期"].max()

                # 色粉組成
                powders = [
                    str(recipe[f"色粉編號{i}"]).strip()
                    for i in range(1, 9)
                    if str(recipe[f"色粉編號{i}"]).strip()
                ]
                powder_str = "、".join(powders)

                results.append({
                    "最後生產時間": last_date,
                    "配方編號": recipe["配方編號"],
                    "顏色": recipe["顏色"],
                    "客戶名稱": recipe["客戶名稱"],
                    "色粉組成": powder_str
                })

            df_result = pd.DataFrame(results)

            if not df_result.empty:
                # 按最後生產時間排序（由近到遠）
                df_result = df_result.sort_values(by="最後生產時間", ascending=False)

                # 格式化最後生產時間（避免 NaT 顯示成 NaT）
                df_result["最後生產時間"] = df_result["最後生產時間"].apply(
                    lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else ""
                )

            st.dataframe(df_result, use_container_width=True)

    st.markdown("---")  # 分隔線

    # ---------------- 第二段：色粉用量查詢 ----------------
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🧮 色粉用量查詢</h2>',
        unsafe_allow_html=True
    )

    # 四個色粉編號輸入框
    cols = st.columns(4)
    powder_inputs = []
    for i in range(4):
        val = cols[i].text_input(f"色粉編號{i+1}", key=f"usage_color_{i}")
        if val.strip():
            powder_inputs.append(val.strip())

    # ---- 日期區間選擇 ----
    col1, col2 = st.columns(2)
    start_date = col1.date_input("開始日期")
    end_date = col2.date_input("結束日期")

    def format_usage(val):
        if val >= 1000:
            kg = val / 1000
            # 若小數部分 = 0 就顯示整數
            if round(kg, 2) == int(kg):
                return f"{int(kg)} kg"
            else:
                return f"{kg:.2f} kg"
        else:
            if round(val, 2) == int(val):
                return f"{int(val)} g"
            else:
                return f"{val:.2f} g"

    if st.button("查詢用量", key="btn_powder_usage") and powder_inputs:
        results = []
        df_order = st.session_state.get("df_order", pd.DataFrame()).copy()
        df_recipe = st.session_state.get("df_recipe", pd.DataFrame()).copy()

        # 確保欄位存在，避免 KeyError
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        for c in powder_cols + ["配方編號", "配方類別", "原始配方", "配方名稱", "顏色", "客戶名稱"]:
            if c not in df_recipe.columns:
                df_recipe[c] = ""

        if "生產日期" in df_order.columns:
            df_order["生產日期"] = pd.to_datetime(df_order["生產日期"], errors="coerce")
        else:
            df_order["生產日期"] = pd.NaT

        # 小工具：將 recipe dict 轉成顯示名稱（若有配方名稱用配方名稱，否則用編號+顏色）
        def recipe_display_name(rec: dict) -> str:
            name = str(rec.get("配方名稱", "")).strip()
            if name:
                return name
            rid = str(rec.get("配方編號", "")).strip()
            color = str(rec.get("顏色", "")).strip()
            cust = str(rec.get("客戶名稱", "")).strip()
            if color or cust:
                parts = [p for p in [color, cust] if p]
                return f"{rid} ({' / '.join(parts)})"
            return rid

        for powder_id in powder_inputs:
            total_usage_g = 0.0
            monthly_usage = {}   # e.g. { 'YYYY/MM': { 'usage': float, 'main_recipes': set(), 'additional_recipes': set() } }

            # 1) 先從配方管理找出「候選配方」(任何一個色粉欄有包含此 powder_id)
            if not df_recipe.empty:
                mask = df_recipe[powder_cols].astype(str).apply(lambda row: powder_id in row.values, axis=1)
                recipe_candidates = df_recipe[mask].copy()
                candidate_ids = set(recipe_candidates["配方編號"].astype(str).tolist())
            else:
                recipe_candidates = pd.DataFrame()
                candidate_ids = set()

            # 2) 過濾生產單日期區間（只取有效日期）
            orders_in_range = df_order[
                (df_order["生產日期"].notna()) &
                (df_order["生產日期"] >= pd.to_datetime(start_date)) &
                (df_order["生產日期"] <= pd.to_datetime(end_date))
            ]

            # 3) 逐筆檢查訂單（保留原有過濾邏輯：只處理該訂單的主配方與其附加配方）
            for _, order in orders_in_range.iterrows():
                order_recipe_id = str(order.get("配方編號", "")).strip()
                if not order_recipe_id:
                    continue

                # 取得主配方（若存在）與其附加配方
                recipe_rows = []
                main_df = df_recipe[df_recipe["配方編號"].astype(str) == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
                add_df = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"].astype(str) == order_recipe_id)
                ]
                if not add_df.empty:
                    recipe_rows.extend(add_df.to_dict("records"))

                # 計算這張訂單中，該 powder_id 的用量（會檢查每個配方是否包含 powder_id，且該配方需在候選清單中）
                # 若同一張單多個配方包含 powder_id，會將各配方的貢獻加總
                order_total_for_powder = 0.0
                sources_main = set()
                sources_add = set()

                # 先算出該訂單的包裝總份 (= sum(pack_w * pack_n) )
                packs_total = 0.0
                for j in range(1, 5):
                    w_key = f"包裝重量{j}"
                    n_key = f"包裝份數{j}"
                    w_val = order[w_key] if w_key in order.index else 0
                    n_val = order[n_key] if n_key in order.index else 0
                    try:
                        pack_w = float(w_val or 0)
                    except (ValueError, TypeError):
                        pack_w = 0.0
                    try:
                        pack_n = float(n_val or 0)
                    except (ValueError, TypeError):
                        pack_n = 0.0
                    packs_total += pack_w * pack_n

                if packs_total <= 0:
                    # 如果這張訂單沒有實際包裝份數（皆為0），就跳過（因為不會產生用量）
                    continue

                for rec in recipe_rows:
                    rec_id = str(rec.get("配方編號", "")).strip()
                    # 只有當該配方在候選清單裡（也就是配方管理確認含該色粉）才計算
                    if rec_id not in candidate_ids:
                        continue

                    pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                    if powder_id not in pvals:
                        continue

                    idx = pvals.index(powder_id) + 1
                    try:
                        powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                    except (ValueError, TypeError):
                        powder_weight = 0.0

                    if powder_weight <= 0:
                        continue

                    # 用量 (g) = 色粉重量 * packs_total
                    contrib = powder_weight * packs_total
                    order_total_for_powder += contrib
                    # 記錄來源
                    disp_name = recipe_display_name(rec)
                    if str(rec.get("配方類別", "")).strip() == "附加配方":
                        sources_add.add(disp_name)
                    else:
                        sources_main.add(disp_name)

                if order_total_for_powder <= 0:
                    continue

                # 累計到月份
                od = order["生產日期"]
                if pd.isna(od):
                    continue
                month_key = od.strftime("%Y/%m")
                if month_key not in monthly_usage:
                    monthly_usage[month_key] = {"usage": 0.0, "main_recipes": set(), "additional_recipes": set()}

                monthly_usage[month_key]["usage"] += order_total_for_powder
                monthly_usage[month_key]["main_recipes"].update(sources_main)
                monthly_usage[month_key]["additional_recipes"].update(sources_add)
                total_usage_g += order_total_for_powder

            # 4) 輸出每月用量（日期區間使用輸入 start/end 與該月份交集，整月顯示 YYYY/MM，否則顯示 YYYY/MM/DD~MM/DD）
            #    只輸出用量>0 的月份
            months_sorted = sorted(monthly_usage.keys())
            for month in months_sorted:
                data = monthly_usage[month]
                usage_g = data["usage"]
                if usage_g <= 0:
                    continue

                # 利用 pd.Period 計算該月份的第一天/最後一天
                per = pd.Period(month, freq="M")
                month_start = per.start_time.date()
                month_end = per.end_time.date()
                disp_start = max(start_date, month_start)
                disp_end = min(end_date, month_end)

                if (disp_start == month_start) and (disp_end == month_end):
                    date_disp = month
                else:
                    date_disp = f"{disp_start.strftime('%Y/%m/%d')}~{disp_end.strftime('%m/%d')}"

                usage_disp = format_usage(usage_g)
                main_src = ", ".join(sorted(data["main_recipes"])) if data["main_recipes"] else ""
                add_src  = ", ".join(sorted(data["additional_recipes"])) if data["additional_recipes"] else ""

                results.append({
                    "色粉編號": powder_id,
                    "來源區間": date_disp,
                    "月用量": usage_disp,
                    "主配方來源": main_src,
                    "附加配方來源": add_src
                })

            # 5) 總用量（always append）
            total_disp = format_usage(total_usage_g)
            results.append({
                "色粉編號": powder_id,
                "來源區間": "總用量",
                "月用量": total_disp,
                "主配方來源": "",
                "附加配方來源": ""
            })

        df_usage = pd.DataFrame(results)

        def highlight_total_row(s):
            # 只有總用量那行才套用
            return [
                'font-weight: bold; background-color: #333333; color: white' if s.name in df_usage.index and df_usage.loc[s.name, "來源區間"] == "總用量" and col in ["色粉編號", "來源區間", "月用量"] else ''
                for col in s.index
            ]

        styled = df_usage.style.apply(highlight_total_row, axis=1)
        st.dataframe(styled, use_container_width=True)

    st.markdown("---")  # 分隔線

    # ---------------- 第三段：色粉用量排行榜 ----------------
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🏆 色粉用量排行榜</h2>',
        unsafe_allow_html=True
    )

    # 日期區間選擇
    col1, col2 = st.columns(2)
    rank_start = col1.date_input("開始日期（排行榜）")
    rank_end = col2.date_input("結束日期（排行榜）")

    def format_usage(val):
        """g -> kg/g，去除小數點多餘零"""
        if val >= 1000:
            kg = val / 1000
            if round(kg, 2) == int(kg):
                return f"{int(kg)} kg"
            else:
                return f"{kg:.2f} kg"
        else:
            if round(val, 2) == int(val):
                return f"{int(val)} g"
            else:
                return f"{val:.2f} g"

    if st.button("生成排行榜", key="btn_powder_rank"):
        df_order = st.session_state.get("df_order", pd.DataFrame()).copy()
        df_recipe = st.session_state.get("df_recipe", pd.DataFrame()).copy()

        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        weight_cols = [f"色粉重量{i}" for i in range(1, 9)]
        for c in powder_cols + weight_cols + ["配方編號", "配方類別", "原始配方"]:
            if c not in df_recipe.columns:
                df_recipe[c] = ""

        if "生產日期" in df_order.columns:
            df_order["生產日期"] = pd.to_datetime(df_order["生產日期"], errors="coerce")
        else:
            df_order["生產日期"] = pd.NaT

        # 過濾日期區間
        orders_in_range = df_order[
            (df_order["生產日期"].notna()) &
            (df_order["生產日期"] >= pd.to_datetime(rank_start)) &
            (df_order["生產日期"] <= pd.to_datetime(rank_end))
        ]

        pigment_usage = {}

        # 計算所有色粉用量
        for _, order in orders_in_range.iterrows():
            order_recipe_id = str(order.get("配方編號", "")).strip()
            if not order_recipe_id:
                continue

            # 主配方 + 附加配方
            recipe_rows = []
            main_df = df_recipe[df_recipe["配方編號"].astype(str) == order_recipe_id]
            if not main_df.empty:
                recipe_rows.append(main_df.iloc[0].to_dict())
            add_df = df_recipe[
                (df_recipe["配方類別"] == "附加配方") &
                (df_recipe["原始配方"].astype(str) == order_recipe_id)
            ]
            if not add_df.empty:
                recipe_rows.extend(add_df.to_dict("records"))

            # 包裝總份
            packs_total = 0.0
            for j in range(1, 5):
                w_key = f"包裝重量{j}"
                n_key = f"包裝份數{j}"
                w_val = order[w_key] if w_key in order.index else 0
                n_val = order[n_key] if n_key in order.index else 0
                try:
                    pack_w = float(w_val or 0)
                except (ValueError, TypeError):
                    pack_w = 0.0
                try:
                    pack_n = float(n_val or 0)
                except (ValueError, TypeError):
                    pack_n = 0.0
                packs_total += pack_w * pack_n

            if packs_total <= 0:
                continue

            # 計算各色粉用量
            for rec in recipe_rows:
                for i in range(1, 9):
                    pid = str(rec.get(f"色粉編號{i}", "")).strip()
                    try:
                        pw = float(rec.get(f"色粉重量{i}", 0) or 0)
                    except (ValueError, TypeError):
                        pw = 0.0

                    if pid and pw > 0:
                        contrib = pw * packs_total
                        pigment_usage[pid] = pigment_usage.get(pid, 0.0) + contrib

        # 生成 DataFrame（先保留純數字 g，用來排序）
        df_rank = pd.DataFrame([
            {"色粉編號": k, "總用量_g": v} for k, v in pigment_usage.items()
        ])

        # 先由高到低排序
        df_rank = df_rank.sort_values("總用量_g", ascending=False).reset_index(drop=True)
        # 再格式化成 g 或 kg 顯示
        df_rank["總用量"] = df_rank["總用量_g"].map(format_usage)
        # 只保留要顯示的欄位
        df_rank = df_rank[["色粉編號", "總用量"]]
        st.dataframe(df_rank, use_container_width=True)

        # 下載 CSV（原始數字）
        csv = pd.DataFrame(list(pigment_usage.items()), columns=["色粉編號", "總用量(g)"]).to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ 下載排行榜 CSV",
            data=csv,
            file_name=f"powder_rank_{rank_start}_{rank_end}.csv",
            mime="text/csv"
        )

# ======== Pantone色號分頁 =========
menu = st.session_state.get("menu", "色粉管理")  # 預設值可以自己改

if menu == "Pantone色號表":
    import streamlit as st
    import pandas as pd

    # 讀取 Google Sheets
    ws_pantone = spreadsheet.worksheet("Pantone色號表")
    df_pantone = pd.DataFrame(ws_pantone.get_all_records())

    ws_recipe = spreadsheet.worksheet("配方管理")
    df_recipe = pd.DataFrame(ws_recipe.get_all_records())

    st.markdown(
            '<h1 style="font-size:22px; font-family:Arial; color:#dbd818;">🍭 Pantone色號表</h1>',
            unsafe_allow_html=True
        )

    # 嘗試讀取 Pantone色號表
    try:
        ws_pantone = spreadsheet.worksheet("Pantone色號表")
    except:
        ws_pantone = spreadsheet.add_worksheet(title="Pantone色號表", rows=100, cols=4)

    df_pantone = pd.DataFrame(ws_pantone.get_all_records())

    # 如果表格是空的，補上欄位名稱
    if df_pantone.empty:
        ws_pantone.clear()
        ws_pantone.append_row(["Pantone色號", "配方編號", "客戶名稱", "料號"])
        df_pantone = pd.DataFrame(columns=["Pantone色號", "配方編號", "客戶名稱", "料號"])
    
    # === 新增區塊（2 欄一列） ===
    with st.form("add_pantone"):
        col1, col2 = st.columns(2)
        with col1:
            pantone_code = st.text_input("Pantone 色號")
        with col2:
            formula_id = st.text_input("配方編號")
        
        col3, col4 = st.columns(2)
        with col3:
            customer = st.text_input("客戶名稱")
        with col4:
            material_no = st.text_input("料號")
    
        # 按鈕必須在 form 內
        submitted = st.form_submit_button("➕ 新增")
    
        if submitted:
            if not pantone_code or not formula_id:
                st.error("❌ Pantone 色號與配方編號必填")
            else:
                # 單向檢查配方管理
                if formula_id in df_recipe["配方編號"].astype(str).values:
                    st.warning(f"⚠️ 配方編號 {formula_id} 已存在於『配方管理』，不新增")
                # 檢查 Pantone 色號表內是否重複
                elif formula_id in df_pantone["配方編號"].astype(str).values:
                    st.error(f"❌ 配方編號 {formula_id} 已經在 Pantone 色號表裡")
                else:
                    ws_pantone.append_row([pantone_code, formula_id, customer, material_no])
                    st.success(f"✅ 已新增：Pantone {pantone_code}（配方編號 {formula_id}）")
                    
    # ====== 全域函式 ======
    def show_pantone_table(df, title="Pantone 色號表"):
        """統一顯示 Pantone 色號表：去掉序號、文字左對齊"""
        st.subheader(title)
    
        # 如果 df 是 None 或不是 DataFrame，直接顯示空訊息
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            st.info("⚠️ 目前沒有資料")
            return
    
        # 轉成 DataFrame，重置 index，所有欄位轉字串
        df_reset = pd.DataFrame(df).reset_index(drop=True).astype(str)
    
        st.table(df_reset)

    # ======== Pantone色號查詢區塊 =========
    st.markdown(
        """
        <style>
        /* 查詢框下方距離縮小 */
        div.stTextInput {
            margin-bottom: 0.2rem !important;
        }
        /* 表格上方和下方距離縮小 */
        div[data-testid="stTable"] {
            margin-top: 0.2rem !important;
            margin-bottom: 0.2rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ====== 查詢區塊 ======
    st.markdown(
        '<h1 style="font-size:22px; font-family:Arial; color:#f0efa2;">🔍 查詢Pantone色號</h1>',
        unsafe_allow_html=True
    )

    # 查詢輸入框
    search_code = st.text_input("輸入 Pantone 色號進行查詢")

    # 控制是否顯示表格
    show_table = False

    # 使用者輸入查詢就顯示表格
    if search_code:
        show_table = True

    # 顯示表格（只有在 show_table=True 時）
    if show_table:
        if search_code:
            df_result = df_pantone[df_pantone["Pantone色號"].str.contains(search_code, case=False, na=False)]
            show_pantone_table(df_result, title="")
        else:
            show_pantone_table(df_pantone, title="")

# ======== 庫存區分頁 =========
menu = st.session_state.get("menu", "色粉管理")  # 預設值可以自己改

if menu == "庫存區":
    import pandas as pd
    from datetime import datetime

    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())

    # 打開工作簿 & 工作表
    sh = client.open("色粉管理")          # Google Sheet 名稱
    ws_stock = sh.worksheet("庫存記錄")    # 對應工作表名稱

    # ---------- 讀取資料 ----------
    records = ws_stock.get_all_records()
    if records:
        df_stock = pd.DataFrame(records)
    else:
        df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
    st.session_state.df_stock = df_stock

    # ================= 初始庫存設定 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📦 初始庫存設定</h2>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    ini_powder = col1.text_input("色粉編號", key="ini_color")
    ini_qty = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="ini_qty")
    ini_unit = col3.selectbox("單位", ["g", "kg"], key="ini_unit")
    ini_date = st.date_input("設定日期", value=datetime.today(), key="ini_date")
    ini_note = st.text_input("備註", key="ini_note")

    def to_grams(qty, unit):
        if unit.lower() == "kg":
            return qty * 1000
        return qty

    if st.button("儲存初始庫存", key="btn_save_ini"):
        if not ini_powder.strip():
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            if not df_stock.empty:
                exist_mask = (df_stock["類型"]=="初始") & (df_stock["色粉編號"]==ini_powder.strip())
            else:
                exist_mask = pd.Series([], dtype=bool)

            if exist_mask.any():
                if st.confirm(f"已有色粉 {ini_powder} 的初始庫存，是否覆蓋？", key="confirm_ini"):
                    df_stock.loc[exist_mask, ["日期","數量","單位","備註"]] = [ini_date, ini_qty, ini_unit, ini_note]
                else:
                    st.info("已取消覆蓋")
            else:
                new_row = {"類型":"初始",
                           "色粉編號":ini_powder.strip(),
                           "日期":ini_date,
                           "數量":ini_qty,
                           "單位":ini_unit,
                           "備註":ini_note}
                df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)

            # 寫回 Sheet
            df_to_upload = df_stock.copy()
            if "日期" in df_to_upload.columns:
                df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce").dt.strftime("%Y/%m/%d").fillna("")
            ws_stock.clear()
            ws_stock.update([df_to_upload.columns.values.tolist()] + df_to_upload.values.tolist())
            st.success("✅ 初始庫存已儲存")

    st.markdown("---")

    # ================= 進貨新增 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#18aadb;">📲 進貨新增</h2>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    in_powder = col1.text_input("色粉編號", key="in_color")
    in_qty = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="in_qty_add")
    in_unit = col3.selectbox("單位", ["g", "kg"], key="in_unit_add")
    in_date = col4.date_input("進貨日期", value=datetime.today(), key="in_date")
    in_note = st.text_input("備註", key="in_note")

    if st.button("新增進貨", key="btn_add_in"):
        if not in_powder.strip():
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            new_row = {"類型":"進貨",
                       "色粉編號":in_powder.strip(),
                       "日期":in_date,
                       "數量":in_qty,
                       "單位":in_unit,
                       "備註":in_note}
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)

            df_to_upload = df_stock.copy()
            if "日期" in df_to_upload.columns:
                df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce").dt.strftime("%Y/%m/%d").fillna("")
            ws_stock.clear()
            ws_stock.update([df_to_upload.columns.values.tolist()] + df_to_upload.values.tolist())
            st.success("✅ 進貨紀錄已新增")
    st.markdown("---")

    # ================= 進貨查詢 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🔍 進貨查詢</h2>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    search_code = col1.text_input("色粉編號", key="search_in_code")
    search_start = col2.date_input("進貨日期(起)", key="search_in_start")
    search_end = col3.date_input("進貨日期(迄)", key="search_in_end")

    if st.button("查詢進貨", key="btn_search_in"):
        df_result = df_stock[df_stock["類型"]=="進貨"].copy()
        if search_code.strip():
            df_result = df_result[df_result["色粉編號"].astype(str).str.contains(search_code.strip(), case=False)]
        if search_start and search_end:
            df_result = df_result[(pd.to_datetime(df_result["日期"]) >= pd.to_datetime(search_start)) &
                                  (pd.to_datetime(df_result["日期"]) <= pd.to_datetime(search_end))]
        if not df_result.empty:
            st.dataframe(df_result, use_container_width=True)
        else:
            st.info("ℹ️ 沒有符合條件的進貨資料")
    st.markdown("---")

    # ---------------- 庫存查詢 ----------------
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📊 庫存查詢</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    query_start = col1.date_input("查詢起日", key="stock_start")
    query_end = col2.date_input("查詢迄日", key="stock_end")
    stock_powder = st.text_input("色粉編號 (未輸入可查全部)", key="stock_powder")

    # --------- 庫存區模組 ---------
    # 工具：把 qty+unit 轉成 g
    def to_grams(qty, unit):
        try:
            q = float(qty or 0)
        except Exception:
            q = 0.0
        return q * 1000 if str(unit).lower() == "kg" else q

    # 顯示格式（g -> g 或 kg）
    def format_usage(val_g):
        try:
            val = float(val_g or 0)
        except Exception:
            val = 0.0
        if abs(val) >= 1000:
            kg = val / 1000.0
            return f"{kg:.2f} kg" if not float(int(kg)) == kg else f"{int(kg)} kg"
        else:
            return f"{int(round(val))} g" if float(int(val)) == val else f"{val:.2f} g"

    # 用量計算：套用你原本的「總用量算法」，回傳 total_usage_g (g)
    def calc_usage_for_stock(powder_id, df_order, df_recipe, start_date, end_date):
        total_usage_g = 0.0

        # 確保 df_order 的生產日期為 datetime
        df_order_local = df_order.copy()
        if "生產日期" in df_order_local.columns:
            df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
        else:
            # 沒有生產日期欄位則直接無用量
            return 0.0

        # 先找 candidate 配方（任何一個色粉欄位包含 powder_id）
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        if not df_recipe.empty:
            # 確保有色粉欄位（避免 KeyError）
            for c in powder_cols:
                if c not in df_recipe.columns:
                    df_recipe[c] = ""
            mask = df_recipe[powder_cols].astype(str).apply(lambda row: powder_id in row.values, axis=1)
            recipe_candidates = df_recipe[mask].copy()
            candidate_ids = set(recipe_candidates["配方編號"].astype(str).tolist())
        else:
            candidate_ids = set()

        # 篩選生產單在查詢期間的訂單 (包含 start/end)
        s_dt = pd.to_datetime(start_date)
        e_dt = pd.to_datetime(end_date)
        orders_in_range = df_order_local[
            (df_order_local["生產日期"].notna()) &
            (df_order_local["生產日期"] >= s_dt) &
            (df_order_local["生產日期"] <= e_dt)
        ]

        if orders_in_range.empty:
            return 0.0

        # 逐張訂單計算
        for _, order in orders_in_range.iterrows():
            order_recipe_id = str(order.get("配方編號", "")).strip()
            if not order_recipe_id:
                continue

            # 取主配方與其附加配方
            recipe_rows = []
            if "配方編號" in df_recipe.columns:
                main_df = df_recipe[df_recipe["配方編號"].astype(str) == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
            # 附加配方
            if "配方類別" in df_recipe.columns and "原始配方" in df_recipe.columns:
                add_df = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"].astype(str) == order_recipe_id)
                ]
                if not add_df.empty:
                    recipe_rows.extend(add_df.to_dict("records"))

            # 計算這張訂單的包裝總份 = sum(pack_w * pack_n)
            packs_total = 0.0
            for j in range(1, 5):
                w_key = f"包裝重量{j}"
                n_key = f"包裝份數{j}"
                w_val = order[w_key] if w_key in order.index else 0
                n_val = order[n_key] if n_key in order.index else 0
                try:
                    pack_w = float(w_val or 0)
                except (ValueError, TypeError):
                    pack_w = 0.0
                try:
                    pack_n = float(n_val or 0)
                except (ValueError, TypeError):
                    pack_n = 0.0
                packs_total += pack_w * pack_n

            if packs_total <= 0:
                continue

            # 檢查每個配方是否屬於 candidate_ids，並計算該配方對 powder 的貢獻
            order_total_for_powder = 0.0
            for rec in recipe_rows:
                rec_id = str(rec.get("配方編號", "")).strip()
                if rec_id not in candidate_ids:
                    continue

                # 取該配方所有色粉欄位，找出 powder_id 的索引
                pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                if powder_id not in pvals:
                    continue

                idx = pvals.index(powder_id) + 1
                try:
                    powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                except (ValueError, TypeError):
                    powder_weight = 0.0

                if powder_weight <= 0:
                    continue

                # 正確公式： 用量 (g) = 色粉重量 (g/kg) * packs_total (kg)
                contrib = powder_weight * packs_total
                order_total_for_powder += contrib

            # 累計
            total_usage_g += order_total_for_powder

        return total_usage_g

    # ---------------- 庫存查詢（主流程） ----------------
    s_dt = pd.to_datetime(query_start)
    e_dt = pd.to_datetime(query_end)

    # 初始化 session_state
    if "ini_dict" not in st.session_state:
        st.session_state["ini_dict"] = {}
    if "last_final_stock" not in st.session_state:
        st.session_state["last_final_stock"] = {}  # 紀錄上一期末庫存

    if st.button("計算庫存", key="btn_calc_stock"):
        df_stock_copy = df_stock.copy()

        # 基本防護
        for col in ["類型","色粉編號","日期","數量","單位","備註"]:
            if col not in df_stock_copy.columns:
                df_stock_copy[col] = ""

        # 日期與數量轉換
        df_stock_copy["日期"] = pd.to_datetime(df_stock_copy["日期"], errors="coerce")
        df_stock_copy["數量"] = pd.to_numeric(df_stock_copy["數量"], errors="coerce").fillna(0)
        df_stock_copy["數量_g"] = [to_grams(q, u) for q, u in zip(df_stock_copy["數量"], df_stock_copy["單位"])]

        # 篩選目標色粉
        if stock_powder.strip():
            df_stock_copy = df_stock_copy[df_stock_copy["色粉編號"].astype(str).str.contains(stock_powder.strip(), case=False)]

        # ---------- 計算期初庫存 ----------
        ini_dict = {}
        df_ini = df_stock_copy[df_stock_copy["類型"] == "初始"]

        for pid in df_stock_copy["色粉編號"].unique():
            pid = str(pid)
            df_pid_ini = df_ini[df_ini["色粉編號"].astype(str) == pid]

            if not df_pid_ini.empty:
                # 有初始紀錄
                ini_qty = df_pid_ini["數量_g"].sum()
            else:
                # 沒有初始紀錄，帶入上一期末庫存（如果有）
                ini_qty = st.session_state["last_final_stock"].get(pid, 0)
            ini_dict[pid] = ini_qty

        st.session_state["ini_dict"] = ini_dict

        # ---------- 核對期初庫存 ----------
        with st.expander("🔍 核對期初庫存 (可修改)", expanded=True):
            st.write("請確認各色粉的期初庫存 (g)，若不正確可直接修改：")
            updated_ini = {}
            for pid, qty in st.session_state["ini_dict"].items():
                new_qty = st.number_input(
                    f"{pid} 期初庫存 (g)",
                    value=float(qty),
                    step=1.0
                )
                updated_ini[pid] = new_qty
            if st.button("✅ 確認期初庫存"):
                st.session_state["ini_dict"] = updated_ini
                st.success("✅ 期初庫存已確認，開始計算區間庫存")

        # ---------- 計算區間庫存 ----------
        stock_summary = []
        for pid in df_stock_copy["色粉編號"].unique():
            pid = str(pid)
            df_pid = df_stock_copy[df_stock_copy["色粉編號"].astype(str) == pid]

            ini_qty_g = st.session_state["ini_dict"].get(pid, 0)
            interval_mask = (df_pid["日期"] >= s_dt) & (df_pid["日期"] <= e_dt)
            in_qty_g = df_pid[interval_mask & (df_pid["類型"] == "進貨")]["數量_g"].sum()
            usage_qty_g = calc_usage_for_stock(pid, df_order, df_recipe, s_dt, e_dt)
            final_g = ini_qty_g + in_qty_g - usage_qty_g

            # 更新上一期末庫存
            st.session_state["last_final_stock"][pid] = final_g

            stock_summary.append({
                "色粉編號": pid,
                "期初庫存": format_usage(ini_qty_g),
                "區間進貨": format_usage(in_qty_g),
                "區間用量": format_usage(usage_qty_g),
                "期末庫存": format_usage(final_g),
            })

        st.dataframe(pd.DataFrame(stock_summary), use_container_width=True)
        st.caption("🌟期末庫存 = 期初庫存 + 區間進貨 − 區間用量（單位皆以 g 計算，顯示自動轉換）")
           
# ===== 匯入配方備份檔案 =====
if st.session_state.menu == "匯入備份":
    st.markdown("""
    <style>
    .custom-title {
        font-size: 22px;      /* ← 改這裡調整大小 */
        font-weight: bold;     /* 粗體 */
        color: #F9DC5C;       /* 顏色，可改 */
        margin-bottom: 20px;  /* 底部間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="custom-title">📥 匯入配方備份 Excel</div>', unsafe_allow_html=True)
    
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

                
