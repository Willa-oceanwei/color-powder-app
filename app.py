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
import uuid
from pathlib import Path        
from datetime import datetime

# ======== 🔐 簡易登入驗證區 ========
APP_PASSWORD = "'"  # ✅ 直接在程式中設定密碼

# 初始化登入狀態
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 尚未登入時，顯示登入介面
if not st.session_state.authenticated:
    st.markdown(
        "<h3 style='text-align:center; color:#f0efa2;'>👻 密碼咧 👻</h3>",
        unsafe_allow_html=True,
    )

    password_input = st.text_input("密碼：", type="password", key="login_password")

    # ✅ 支援按 Enter 或按鈕登入
    if password_input == APP_PASSWORD:
        st.session_state.authenticated = True
        st.success("✅ 登入成功！請稍候...")
        time.sleep(0.8)
        st.rerun()
    elif password_input != "":
        # 使用者輸入錯誤密碼時立即顯示錯誤
        st.error("❌ 密碼錯誤，請再試一次。")
        st.stop()

    # 尚未輸入密碼時停止執行
    st.stop()
    
# ======== 🎨 終極版自訂樣式（綠色主題 + 圓角下拉）========
def apply_modern_style():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --glass-bg: rgba(18, 18, 32, 0.62);
        --glass-border: rgba(255, 255, 255, 0.18);
        --text-main: #f5f1ff;
        --text-sub: #d7c9f7;
        --accent: #b188ff;
        --accent-2: #8d5bff;
    }

    * {
        font-family: 'Inter', 'Microsoft JhengHei', sans-serif;
    }

    .stApp {
        color: var(--text-main) !important;
        background:
 codex/add-fields-for-color-type-and-unit
            radial-gradient(circle at 18% 20%, rgba(162, 118, 255, 0.20), transparent 38%),
            radial-gradient(circle at 82% 15%, rgba(94, 196, 255, 0.14), transparent 34%),
            radial-gradient(circle at 70% 80%, rgba(215, 126, 255, 0.16), transparent 42%),
            linear-gradient(145deg, #120f24 0%, #1b1831 45%, #121629 100%);
        background-repeat: no-repeat;

            linear-gradient(120deg, rgba(8, 5, 20, 0.78), rgba(25, 12, 46, 0.72)),
            url('https://des13.com/images/2023/Branding_Website/Branding_Website35.webp');
        background-size: cover;
        background-position: center;
 main
        background-attachment: fixed;
    }

    .main .block-container {
        background: rgba(14, 12, 26, 0.55) !important;
        border: 1px solid var(--glass-border) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 18px;
        padding: 2rem;
        box-shadow: 0 16px 38px rgba(6, 5, 15, 0.5);
    }

    section[data-testid="stSidebar"] {
        background: rgba(10, 8, 22, 0.78) !important;
        border-right: 1px solid rgba(255,255,255,0.12);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }

    section[data-testid="stSidebar"] h1 {
        color: #f6efff;
        font-weight: 700;
        font-size: 22px;
        padding: 0 1rem;
        margin-bottom: 1.5rem;
    }

    section[data-testid="stSidebar"] div.stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.08) !important;
        color: var(--text-sub) !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        border-radius: 12px !important;
        padding: 0.65rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.25s ease !important;
        text-align: left !important;
        width: 100% !important;
        backdrop-filter: blur(6px);
    }

    section[data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {
        background: rgba(177, 136, 255, 0.28) !important;
        color: #ffffff !important;
        border-color: rgba(226, 204, 255, 0.55) !important;
    }

    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-2), var(--accent)) !important;
        color: #ffffff !important;
        border: 1px solid rgba(246, 234, 255, 0.65) !important;
        font-weight: 700 !important;
        box-shadow: 0 8px 20px rgba(58, 31, 125, 0.5) !important;
    }

    section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #7b47ff, #b188ff) !important;
        color: #ffffff !important;
    }

    .main div.stButton > button,
    form div.stButton > button,
    form button[type="submit"] {
        background: linear-gradient(135deg, var(--accent-2), var(--accent)) !important;
        color: #ffffff !important;
        border: 1px solid rgba(246, 234, 255, 0.65) !important;
        border-radius: 12px !important;
        padding: 0.58rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 6px 16px rgba(47, 28, 98, 0.35);
    }

    .main div.stButton > button:hover,
    form div.stButton > button:hover,
    form button[type="submit"]:hover {
        transform: translateY(-1px);
        background: linear-gradient(135deg, #6f42e9, #ac84ff) !important;
        border-color: rgba(255,255,255,0.85) !important;
    }

    div.stTextInput > div > div > input,
    div.stNumberInput > div > div > input,
    div.stTextArea > div > div > textarea {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 10px;
        color: #fff !important;
        padding: 0.6rem 0.75rem !important;
        transition: all 0.2s ease;
    }

    div.stTextInput > div > div > input:focus,
    div.stNumberInput > div > div > input:focus,
    div.stTextArea > div > div > textarea:focus {
        border-color: rgba(206, 170, 255, 0.95) !important;
        box-shadow: 0 0 0 2px rgba(177, 136, 255, 0.25) !important;
        outline: none !important;
    }

    div.stSelectbox div[data-baseweb="select"] > div {
        border-radius: 999px !important;
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        min-height: 40px !important;
        padding: 0.75rem !important;
        display: flex !important;
        align-items: center !important;
    }

    div.stSelectbox div[data-baseweb="select"] > div > div,
    div.stSelectbox svg {
        color: #f2e8ff !important;
    }

    div[data-baseweb="popover"] {
        border-radius: 18px !important;
        background: rgba(30, 18, 52, 0.95) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        box-shadow: 0 14px 32px rgba(8, 5, 20, 0.6) !important;
    }

    ul[role="listbox"] li {
        border-radius: 12px !important;
        background: transparent !important;
        color: #eee5ff !important;
    }

    ul[role="listbox"] li:hover {
        background: rgba(177,136,255,0.22) !important;
        color: #fff !important;
    }

    ul[role="listbox"] li[aria-selected="true"] {
        background: rgba(177,136,255,0.35) !important;
        color: #fff !important;
        font-weight: 600 !important;
    }

    button[data-testid="stTab"] p {
        color: #d8c6ff !important;
        font-weight: 600 !important;
    }

    button[data-testid="stTab"][aria-selected="true"] p {
        color: #ffffff !important;
        text-shadow: 0 1px 8px rgba(186, 145, 255, 0.8);
    }

    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background: linear-gradient(90deg, #7f4dff, #c09bff) !important;
        height: 3px !important;
        border-radius: 999px !important;
    }

    .stAlert {
        border-radius: 12px !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        background: rgba(24, 15, 44, 0.8) !important;
        color: #f7f2ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

apply_modern_style()
 
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

SHEET_CACHE_TTL_SECONDS = 120

def get_cached_worksheet(sheet_name):
    cache = st.session_state.setdefault("_ws_cache", {})
    if sheet_name in cache:
        return cache[sheet_name]
    ws = spreadsheet.worksheet(sheet_name)
    cache[sheet_name] = ws
    return ws

def get_cached_sheet_df(sheet_name, force_reload=False, ttl_seconds=SHEET_CACHE_TTL_SECONDS):
    now = datetime.now().timestamp()
    cache = st.session_state.setdefault("_sheet_df_cache", {})
    cached = cache.get(sheet_name)

    if (
        not force_reload
        and cached
        and now - cached.get("timestamp", 0) < ttl_seconds
    ):
        return cached["df"].copy()

    ws = get_cached_worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    cache[sheet_name] = {"timestamp": now, "df": df.copy()}
    return df


def get_cached_sheet_values(sheet_name, force_reload=False, ttl_seconds=SHEET_CACHE_TTL_SECONDS):
    now = datetime.now().timestamp()
    cache = st.session_state.setdefault("_sheet_values_cache", {})
    cached = cache.get(sheet_name)

    if (
        not force_reload
        and cached
        and now - cached.get("timestamp", 0) < ttl_seconds
    ):
        return [row[:] for row in cached["values"]]

    ws = get_cached_worksheet(sheet_name)
    values = ws.get_all_values()
    cache[sheet_name] = {"timestamp": now, "values": [row[:] for row in values]}
    return values

def invalidate_sheet_cache(sheet_name=None):
    if sheet_name is None:
        st.session_state.pop("_sheet_df_cache", None)
        st.session_state.pop("_ws_cache", None)
        st.session_state.pop("_sheet_values_cache", None)
        return

    st.session_state.get("_sheet_df_cache", {}).pop(sheet_name, None)
    st.session_state.get("_ws_cache", {}).pop(sheet_name, None)
    st.session_state.get("_sheet_values_cache", {}).pop(sheet_name, None)

# ======== Sidebar 修正 =========
import streamlit as st

menu_options = ["客戶名單", "配方管理", "生產單管理", "代工管理",
                "查詢區", "庫存區", "採購管理", "匯入備份"]

if "menu" not in st.session_state:
    st.session_state.menu = "生產單管理"

# 自訂 CSS：改按鈕字體大小
st.markdown("""
<style>
/* 將 Sidebar 內容往上推到極限安全值 */
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0px !important;
    margin-top: -18px !important;
}

/* 調整 Sidebar 標題距離 */
.sidebar h1 {
    margin-top: -10px !important;
}

/* Sidebar 標題字體大小（你原本的） */
.sidebar .css-1d391kg h1 {
    font-size: 24px !important;
}

/* Sidebar 按鈕字體大小 */
div.stButton > button {
    font-size: 14px !important;
    padding: 8px 12px !important;
    text-align: left;
}
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown('<h1 style="font-size:22px;">🪁 配方管理系統</h1>', unsafe_allow_html=True)

    for option in menu_options:
        is_active = st.session_state.menu == option

        if st.button(
            f"✅ {option}" if is_active else option,
            key=f"menu_{option}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            if not is_active:
                st.session_state.menu = option
                st.rerun()   # 🔥 關鍵：一次點擊立即更新
            
# ===== 調整整體主內容上方距離 =====
st.markdown("""
    <style>
    /* 調整整體主內容上方距離 */
    .block-container {
        padding-top: 0rem;
        margin-top: -20px;
    }
    </style>
""", unsafe_allow_html=True)

# ================= 共用 Google Sheet 穩定寫入工具 =================
def safe_append_row(ws, row_values):
    clean_row = ["" if v is None else str(v) for v in row_values]
    ws.append_row(clean_row, value_input_option="USER_ENTERED")

def safe_update_cell(ws, row, col, value):
    """
    穩定版單格更新（取代 update_cell）
    """
    body = {
        "valueInputOption": "USER_ENTERED",
        "data": [{
            "range": gspread.utils.rowcol_to_a1(row, col),
            "values": [[value]]
        }]
    }
    ws.spreadsheet.batch_update(body)

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

# ======== Helper Functions for Recipe Management =========
def clean_powder_id(x):
    """清理色粉ID，移除空白、全形空白，轉大寫"""
    if pd.isna(x) or x == "":
        return ""
    return str(x).strip().replace('\u3000', '').replace(' ', '').upper()

def fix_leading_zero(x):
    """補足前導零（僅針對純數字且長度<4的字串）"""
    x = str(x).strip()
    if x.isdigit() and len(x) < 4:
        x = x.zfill(4)
    return x.upper()

def normalize_search_text(text):
    """標準化搜尋文字"""
    return fix_leading_zero(clean_powder_id(text))

def safe_float_convert(value, default=0.0):
    """安全地將值轉換為浮點數"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int_convert(value, default=0):
    """安全地將值轉換為整數"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_str_convert(value, default=''):
    """安全地將值轉換為字符串"""
    if pd.isna(value) or value is None:
        return default
    return str(value).strip()

def safe_str(val):
    """安全字串轉換"""
    return "" if val is None else str(val)

def safe_float(val):
    """安全浮點數轉換"""
    try:
        return float(val)
    except:
        return 0

def fmt_num(val, digits=2):
    """格式化數字"""
    try:
        num = float(val)
    except (TypeError, ValueError):
        return "0"
    return f"{num:.{digits}f}".rstrip("0").rstrip(".")

def load_recipe(force_reload=False):
    """嘗試依序載入配方資料，來源：Google Sheet > CSV > 空 DataFrame"""
    try:
        df_loaded = get_cached_sheet_df("配方管理", force_reload=force_reload)
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

def generate_recipe_preview_text(order, recipe_row, show_additional_ids=True):
    """生成配方預覽文字（用於生產單）"""
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
    if "df_recipe" in st.session_state:
        df_recipe = st.session_state.df_recipe
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


def load_recipe_data():
    """從 Google Sheets 載入配方數據"""
    try:
        df_loaded = get_cached_sheet_df("配方管理")
        if df_loaded.empty:
            columns = [
                "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
                "原始配方", "色粉類別", "計量單位", "Pantone色號",
                "比例1", "比例2", "比例3", "淨重", "淨重單位",
                *[f"色粉編號{i}" for i in range(1, 9)],
                *[f"色粉重量{i}" for i in range(1, 9)],
                "合計類別", "重要提醒", "備註", "建檔時間"
            ]
            df_loaded = pd.DataFrame(columns=columns)
        
        for col in df_loaded.columns:
            if col not in df_loaded.columns:
                df_loaded[col] = ""
        
        if "配方編號" in df_loaded.columns:
            df_loaded["配方編號"] = df_loaded["配方編號"].astype(str).map(clean_powder_id)
        
        return df_loaded
    except Exception as e:
        st.error(f"載入配方數據時發生錯誤: {str(e)}")
        return pd.DataFrame()

# ======== 共用儲存函式 =========
def save_df_to_sheet(ws, df):
    """共用的 DataFrame 儲存函式"""
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.clear()
    ws.update("A1", values)
    invalidate_sheet_cache(ws.title)

    if ws.title == "庫存記錄":
        st.session_state.pop("stock_calc_time", None)

                
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
    
    # 配方資訊列（flex 平均分配 + 長文字自動撐開）
    recipe_id = recipe_row.get('配方編號', '')
    color = order.get('顏色', '')
    pantone = order.get('Pantone 色號', '').strip()

    # 有 Pantone 才印出
    pantone_part = (
        f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>Pantone：{pantone}</div>"
        if pantone else ""
    )

    # 固定欄位平均分配
    recipe_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>編號：<b>{recipe_id}</b></div>"
    color_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>顏色：{color}</div>"
    ratio_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>比例：{ratio} g/kg</div>"

    # 組合整行
    info_line = (
        f"<div style='display:flex; font-size:20px; font-family:Arial; align-items:center; gap:12px;'>"
        f"{recipe_part}{color_part}{ratio_part}{pantone_part}"
        f"</div>"
    )
    lines.append(info_line)
    # lines.append("")
    
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
            sub_total_type = (sub.get("合計類別", "") or "").strip()
            sub_net_weight = float(sub.get("淨重", 0) or 0)
            
            if sub_total_type == "" or sub_total_type == "無":
                sub_total_type_display = f"<b>{'='.ljust(powder_label_width)}</b>"
            
            elif category == "色母":
                sub_total_type_display = (
                    f"<b><span style='font-size:22px; display:inline-block; width:{powder_label_width}ch'>料</span></b>"
                )
            
            elif sub_total_type == "其他":
                sub_total_type_display = (
                    f"<span style='"
                    f"display:inline-block;"
                    f"width:{powder_label_width}ch;"
                    f"font-weight:bold;"
                    f"transform:scale(0.7);"
                    f"transform-origin:left center;"
                    f"'>其他</span>"
                )
            
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
    
    # ---------- 備註（自動判斷是否印出） ----------
    remark_text = order.get("備註", "").strip()
    if remark_text:  # 有輸入內容才印出
        lines.append("")
        lines.append("")  # 只在有備註時多留空行
        lines.append(f"備註 : {remark_text}")

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
    invalidate_sheet_cache(ws.title)

    if ws.title == "庫存記錄":
        st.session_state.pop("stock_calc_time", None)


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
                
#===「載入配方資料」的核心函式與初始化程式====
def load_recipe(force_reload=False):
        """嘗試依序載入配方資料，來源：Google Sheet > CSV > 空 DataFrame"""
        try:
            ws_recipe = get_cached_worksheet("配方管理")
            df_loaded = get_cached_sheet_df("配方管理", force_reload=force_reload)
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

# ------------------------------
menu = st.session_state.menu  # 先從 session_state 取得目前選擇

# ======== 色粉管理 =========
if menu == "色粉管理":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ===== 讀取工作表 =====
    worksheet = get_cached_worksheet("色粉管理")
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

    # form_color 現在一定是 dict，不會再報錯
    init_states(["form_color", "edit_color_index", "delete_color_index", "show_delete_color_confirm", "search_color"])

    for col in required_columns:
        st.session_state.form_color.setdefault(col, "")

    try:
        df = get_cached_sheet_df("色粉管理")
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
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818; margin:0 0 10px 0;">🪅新增色粉</h2>',
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
            
    st.markdown("---")
    
# ======== 客戶名單 =========
elif menu == "客戶名單":

    # ===== 縮小頁面空白 =====
    st.markdown("""
    <style>
    div.block-container { padding-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    # ===== 讀取或建立 Google Sheet =====
    try:
        ws_customer = get_cached_worksheet("客戶名單")
    except:
        ws_customer = spreadsheet.add_worksheet("客戶名單", rows=100, cols=10)

    columns = ["客戶編號", "客戶簡稱", "備註"]

    # ===== 初始化 session_state =====
    st.session_state.setdefault("form_customer", {col: "" for col in columns})
    init_states([
        "edit_customer_index",
        "delete_customer_index",
        "show_delete_customer_confirm",
        "search_customer"
    ])

    # ===== 載入資料 =====
    try:
        df = get_cached_sheet_df("客戶名單")
    except:
        df = pd.DataFrame(columns=columns)

    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    # =====================================================
    # 📝 新增 / 編輯 客戶
    # =====================================================
    st.markdown(
        '<h2 style="font-size:16px; font-family:Arial; color:#f1f5f2;">☑️ 新增客戶</h3>',
        unsafe_allow_html=True
    )
    
    with st.form("customer_form"):
        col1, col2 = st.columns(2)
        with col1:
            cid = st.text_input("客戶編號", st.session_state.form_customer.get("客戶編號", ""))
            cname = st.text_input("客戶簡稱", st.session_state.form_customer.get("客戶簡稱", ""))
        with col2:
            note = st.text_input("備註", st.session_state.form_customer.get("備註", ""))
    
        submit = st.form_submit_button("💾 儲存")
    
    if submit:
        new_data = {
            "客戶編號": cid.strip(),
            "客戶簡稱": cname.strip(),
            "備註": note.strip()
        }
    
        if not new_data["客戶編號"]:
            st.warning("⚠️ 請輸入客戶編號！")
        else:
            if st.session_state.edit_customer_index is not None:
                # 編輯模式
                idx = st.session_state.edit_customer_index
                for col in df.columns:
                    if col in new_data:
                        df.at[idx, col] = new_data[col]
                st.success("✅ 客戶已更新！")
                st.session_state.edit_customer_index = None
            else:
                # 新增模式
                if new_data["客戶編號"] in df["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在！")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    st.success("✅ 新增成功！")
    
            # 寫回 Google Sheet
            save_df_to_sheet(ws_customer, df)
    
            # 清空表單
            st.session_state.form_customer = {col: "" for col in df.columns}
    
            # 立即更新前端列表
            st.experimental_rerun()
    
    # =====================================================
    # 🗑️ 刪除確認
    # =====================================================
    if st.session_state.show_delete_customer_confirm:
        target_row = df.iloc[st.session_state.delete_customer_index]
        st.warning(f"⚠️ 確定要刪除 {target_row['客戶編號']} {target_row['客戶簡稱']}？")

        c1, c2 = st.columns(2)
        if c1.button("刪除"):
            df.drop(index=st.session_state.delete_customer_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_customer, df)
            st.session_state.show_delete_customer_confirm = False
            st.success("✅ 刪除成功！")
            st.rerun()

        if c2.button("取消"):
            st.session_state.show_delete_customer_confirm = False
            st.rerun()

    # =====================================================
    # 📋 客戶清單（搜尋 / 編輯 / 刪除）
    # =====================================================
    st.markdown('<h2 style="font-size:16px; font-family:Arial; color:#f1f5f2;">🛠️ 客戶修改 / 刪除</h3>', unsafe_allow_html=True)
    
    # 搜尋輸入
    keyword = st.text_input(
        "請輸入客戶編號或簡稱",
        st.session_state.get("search_customer", "")
    )
    st.session_state.search_customer = keyword.strip()
    
    # 預設顯示用資料
    df_filtered = pd.DataFrame()
    
    if keyword:
        df_filtered = df[
            df["客戶編號"].str.contains(keyword, case=False, na=False) |
            df["客戶簡稱"].str.contains(keyword, case=False, na=False)
        ]
    
        if df_filtered.empty:
            st.warning("❗ 查無符合的資料")
    
    # ===== 表格顯示 =====
    if not df_filtered.empty:
        st.dataframe(df_filtered[columns], use_container_width=True, hide_index=True)
    
        st.markdown("<hr style='margin-top:10px;margin-bottom:10px;'>", unsafe_allow_html=True)
    
        st.markdown(
            "<p style='font-size:14px; font-family:Arial; color:gray;'>🛈 請於上方新增欄位進行修改</p>",
            unsafe_allow_html=True
        )
    
        # --- 按鈕樣式 ---
        st.markdown("""
        <style>
        div.stButton > button {
            font-size:16px !important;
            padding:2px 8px !important;
            border-radius:8px;
            background-color:#333333 !important;
            color:white !important;
            border:1px solid #555555;
        }
        div.stButton > button:hover {
            background-color:#555555 !important;
            border-color:#dbd818 !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
        # ===== 列出清單（重點：index 對回原 df）=====
        for _, row in df_filtered.iterrows():
            real_idx = df.index[
                (df["客戶編號"] == row["客戶編號"]) &
                (df["客戶簡稱"] == row["客戶簡稱"])
            ][0]
    
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(
                    f"<div style='font-family:Arial;'>🔹 {row['客戶編號']}　{row['客戶簡稱']}</div>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("✏️ 改", key=f"edit_customer_{real_idx}"):
                    st.session_state.edit_customer_index = real_idx
                    st.session_state.form_customer = row.to_dict()
                    st.rerun()
            with c3:
                if st.button("🗑️ 刪", key=f"delete_customer_{real_idx}"):
                    st.session_state.delete_customer_index = real_idx
                    st.session_state.show_delete_customer_confirm = True
                    st.rerun()

#==========================================================
# ======== 配方管理分頁 =========
elif menu == "配方管理":

    st.markdown("""
    <style>
    div.block-container { padding-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    from pathlib import Path
    from datetime import datetime
    import pandas as pd

    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "重要提醒", "備註", "建檔時間"
    ]

    # ================================================================
    # 📌 資料載入：只有第一次進入、或寫入後才重新讀 Google Sheet
    # ================================================================
    def load_recipe_section_data():
        """重新從 Google Sheet 讀取配方管理所需的三張表"""

        # 1️⃣ 配方管理
        try:
            df_r = get_cached_sheet_df("配方管理", force_reload=True)
        except:
            df_r = pd.DataFrame(columns=columns)

        for col in columns:
            if col not in df_r.columns:
                df_r[col] = ""
        if "配方編號" in df_r.columns:
            df_r["配方編號"] = df_r["配方編號"].astype(str).map(clean_powder_id)

        # 2️⃣ 色粉管理
        try:
            df_p = get_cached_sheet_df("色粉管理", force_reload=True)
            if "色粉編號" not in df_p.columns:
                df_p = pd.DataFrame(columns=["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])
        except:
            df_p = pd.DataFrame(columns=["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])

        # 3️⃣ 客戶名單
        try:
            df_c = get_cached_sheet_df("客戶名單", force_reload=True)
        except:
            df_c = pd.DataFrame(columns=["客戶編號", "客戶簡稱"])

        st.session_state.df_recipe          = df_r
        st.session_state.df                 = df_r
        st.session_state.df_color           = df_p.astype(str)
        st.session_state._recipe_customers  = df_c
        st.session_state.recipe_data_loaded = True

    # ── 只有第一次進入、或寫入後重置旗標才重讀 ──
    if not st.session_state.get("recipe_data_loaded", False):
        load_recipe_section_data()

    # 取出 worksheet 物件（不耗 quota）
    try:
        ws_recipe = get_cached_worksheet("配方管理")
    except:
        try:
            ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)
        except:
            st.error("❌ 無法建立工作表")
            st.stop()

    # 取出 DataFrame（全程用 session_state，不重讀 Sheet）
    df           = st.session_state.df
    df_recipe    = st.session_state.df_recipe
    df_customers = st.session_state._recipe_customers
    df_powders   = st.session_state.df_color

    existing_powders     = set(df_powders["色粉編號"].map(clean_powder_id).unique()) \
                           if "色粉編號" in df_powders.columns else set()
    existing_powders_str = {str(x).strip().upper() for x in existing_powders if str(x).strip() != ""}

    customer_options = [
        "{} - {}".format(row["客戶編號"], row["客戶簡稱"])
        for _, row in df_customers.iterrows()
        if "客戶編號" in df_customers.columns and "客戶簡稱" in df_customers.columns
    ]

    # ================================================================
    # ✅ 共用：儲存配方到 Google Sheet（append 或 update 單列，不整表覆寫）
    # ================================================================
    def save_recipe_row(df_to_save, is_edit=False, edit_index=None):
        """
        新增用 append_row（1 次 API）
        修改用 update 單列（1 次 API）
        同時更新 session_state，不重讀整表
        """
        try:
            all_values = get_cached_sheet_values("配方管理")
            header     = all_values[0] if all_values else df_to_save.columns.tolist()
        except:
            header = df_to_save.columns.tolist()

        if is_edit and edit_index is not None:
            # 找到這筆配方在 Sheet 中的列號
            recipe_id = str(df_to_save.loc[edit_index, "配方編號"]).strip()
            target_row_idx = None
            if all_values:
                for i, row in enumerate(all_values[1:], start=2):
                    if row[0].strip() == recipe_id:
                        target_row_idx = i
                        break

            if target_row_idx:
                import gspread.utils as gu
                updated_row = [str(df_to_save.loc[edit_index].get(col, "")) for col in header]
                end_col = gu.rowcol_to_a1(target_row_idx, len(header)).rstrip("0123456789")
                ws_recipe.update(
                    f"A{target_row_idx}:{end_col}{target_row_idx}",
                    [updated_row]
                )
            else:
                # 找不到就 append（保險機制）
                new_row = [str(df_to_save.loc[edit_index].get(col, "")) for col in header]
                ws_recipe.append_row(new_row)
        else:
            # 新增：只 append 最後一列
            last_idx = df_to_save.index[-1]
            new_row  = [str(df_to_save.loc[last_idx].get(col, "")) for col in header]
            ws_recipe.append_row(new_row)

        # 同步 session_state
        invalidate_sheet_cache("配方管理")
        st.session_state.df        = df_to_save
        st.session_state.df_recipe = df_to_save

    # ================================================================
    # Tab 架構
    # ================================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 配方建立",
        "📜 配方記錄表",
        "👀 配方預覽/修改/刪除",
        "🪅 色粉管理",
        "👹 色母換算"
    ])

    # ============================================================
    # Tab 1：配方建立
    # ============================================================
    with tab1:

        if "form_recipe" not in st.session_state or not st.session_state.form_recipe:
            st.session_state.form_recipe = {col: "" for col in columns}
            st.session_state.form_recipe.update({
                "配方類別": "原始配方", "狀態": "啟用",
                "色粉類別": "配方",     "計量單位": "包",
                "淨重單位": "g",        "合計類別": "無"
            })
        if "num_powder_rows" not in st.session_state:
            st.session_state.num_powder_rows = 5

        fr = st.session_state.form_recipe

        with st.form("recipe_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="form_recipe_配方編號")
            with col2:
                fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="form_recipe_顏色")
            with col3:
                options = [""] + customer_options
                current = f"{fr.get('客戶編號','')} - {fr.get('客戶名稱','')}" if fr.get("客戶編號") else ""
                index   = options.index(current) if current in options else 0
                selected = st.selectbox("客戶編號", options, index=index, key="form_recipe_selected_customer")
                if selected and " - " in selected:
                    c_no, c_name = selected.split(" - ", 1)
                    fr["客戶編號"] = c_no.strip()
                    fr["客戶名稱"] = c_name.strip()

            col4, col5, col6 = st.columns(3)
            with col4:
                opts = ["原始配方", "附加配方"]
                cur  = fr.get("配方類別", opts[0])
                fr["配方類別"] = st.selectbox("配方類別", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_配方類別")
            with col5:
                opts = ["啟用", "停用"]
                cur  = fr.get("狀態", opts[0])
                fr["狀態"] = st.selectbox("狀態", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_狀態")
            with col6:
                fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方", ""), key="form_recipe_原始配方")

            col7, col8, col9 = st.columns(3)
            with col7:
                opts = ["配方", "色母", "色粉", "添加劑", "其他"]
                cur  = fr.get("色粉類別", opts[0])
                fr["色粉類別"] = st.selectbox("色粉類別", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_色粉類別")
            with col8:
                opts = ["包", "桶", "kg", "其他"]
                cur  = fr.get("計量單位", opts[0])
                fr["計量單位"] = st.selectbox("計量單位", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_計量單位")
            with col9:
                fr["Pantone色號"] = st.text_input("Pantone色號", value=fr.get("Pantone色號", ""), key="form_recipe_Pantone色號")

            fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒", ""), key="form_recipe_重要提醒")

            colr1, col_colon, colr2, colr3, col_unit = st.columns([2, 0.5, 2, 2, 1])
            with colr1:
                fr["比例1"] = st.text_input("", value=fr.get("比例1", ""), key="ratio1", label_visibility="collapsed")
            with col_colon:
                st.markdown("<div style='display:flex;justify-content:center;align-items:center;font-size:18px;font-weight:bold;height:36px;'>:</div>", unsafe_allow_html=True)
            with colr2:
                fr["比例2"] = st.text_input("", value=fr.get("比例2", ""), key="ratio2", label_visibility="collapsed")
            with colr3:
                fr["比例3"] = st.text_input("", value=fr.get("比例3", ""), key="ratio3", label_visibility="collapsed")
            with col_unit:
                st.markdown("<div style='display:flex;align-items:center;font-size:16px;height:36px;'>g/kg</div>", unsafe_allow_html=True)

            fr["備註"] = st.text_area("備註", value=fr.get("備註", ""), key="form_recipe_備註")

            col1, col2 = st.columns(2)
            with col1:
                fr["淨重"] = st.text_input("色粉淨重", value=fr.get("淨重", ""), key="form_recipe_淨重")
            with col2:
                opts = ["g", "kg"]
                cur  = fr.get("淨重單位", opts[0])
                fr["淨重單位"] = st.selectbox("單位", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_淨重單位")

            st.markdown("""
            <style>
            div.stTextInput > div > div > input { padding:2px 6px !important; height:36px !important; font-size:16px; }
            div.stTextInput { margin-top:0px !important; margin-bottom:0px !important; }
            </style>
            """, unsafe_allow_html=True)

            st.markdown("##### 色粉設定")
            for i in range(1, st.session_state.get("num_powder_rows", 5) + 1):
                c1, c2 = st.columns([2.5, 2.5])
                fr[f"色粉編號{i}"] = c1.text_input("", value=fr.get(f"色粉編號{i}", ""),
                    placeholder=f"色粉{i}編號", key=f"form_recipe_色粉編號{i}")
                fr[f"色粉重量{i}"] = c2.text_input("", value=fr.get(f"色粉重量{i}", ""),
                    placeholder="重量", key=f"form_recipe_色粉重量{i}")

            col1, col2 = st.columns(2)
            with col1:
                category_options = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
                default_raw = fr.get("合計類別", "無")
                default     = "\u2002" if default_raw == "無" else default_raw
                if default not in category_options:
                    default = category_options[0]
                fr["合計類別"] = st.selectbox("合計類別", category_options,
                    index=category_options.index(default), key="form_recipe_合計類別")
            with col2:
                try:
                    net   = float(fr.get("淨重") or 0)
                    total = sum(float(fr.get(f"色粉重量{i}") or 0) for i in range(1, 9))
                    st.write(f"合計差額: {net - total:.2f} g/kg")
                except:
                    st.write("合計差額: 計算錯誤")

            col1, col2 = st.columns([3, 2])
            with col1:
                submitted  = st.form_submit_button("💾 儲存配方")
            with col2:
                add_powder = st.form_submit_button("➕ 新增色粉列")

            if "add_powder_clicked" not in st.session_state:
                st.session_state.add_powder_clicked = False

        # ── 表單提交後處理 ──
        if submitted:
            missing_powders = []
            for i in range(1, st.session_state.num_powder_rows + 1):
                pid = clean_powder_id(fr.get(f"色粉編號{i}", ""))
                if pid and pid not in existing_powders_str:
                    missing_powders.append(fr.get(f"色粉編號{i}", ""))

            if missing_powders:
                st.warning(f"⚠️ 以下色粉尚未建檔：{', '.join(missing_powders)}")
            elif fr["配方編號"].strip() == "":
                st.warning("⚠️ 請輸入配方編號！")
            elif fr["配方類別"] == "附加配方" and fr["原始配方"].strip() == "":
                st.warning("⚠️ 附加配方必須填寫原始配方！")
            else:
                edit_idx = st.session_state.get("edit_recipe_index")
                if edit_idx is not None:
                    df.iloc[edit_idx] = pd.Series(fr, index=df.columns)
                    save_recipe_row(df, is_edit=True, edit_index=edit_idx)
                    st.toast(f"✅ 配方 {fr['配方編號']} 已更新！", icon="✏️")
                else:
                    if fr["配方編號"] in df["配方編號"].values:
                        st.warning("⚠️ 此配方編號已存在！")
                    else:
                        fr["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df = pd.concat([df, pd.DataFrame([fr])], ignore_index=True)
                        save_recipe_row(df, is_edit=False)
                        st.toast(f"✅ 新增配方 {fr['配方編號']} 成功！", icon="🎉")

                st.session_state.form_recipe     = {col: "" for col in columns}
                st.session_state.edit_recipe_index = None
                st.rerun()

        if add_powder and not st.session_state.add_powder_clicked:
            if st.session_state.num_powder_rows < 8:
                st.session_state.num_powder_rows += 1
            st.session_state.add_powder_clicked = True
            st.rerun()
        else:
            st.session_state.add_powder_clicked = False

    # ============================================================
    # Tab 2：配方記錄表
    # ============================================================
    with tab2:

        if df.empty:
            st.info("目前無資料")
            df_filtered = df.copy()
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                search_recipe  = st.text_input("配方編號", key="search_recipe_tab2")
            with col2:
                search_customer = st.text_input("客戶名稱或編號", key="search_customer_tab2")
            with col3:
                search_pantone  = st.text_input("Pantone色號", key="search_pantone_tab2")

            recipe_kw   = search_recipe.strip()
            customer_kw = search_customer.strip()
            pantone_kw  = search_pantone.strip()

            search_signature = f"{recipe_kw}|{customer_kw}|{pantone_kw}"
            if "last_search_signature_tab2" not in st.session_state:
                st.session_state.last_search_signature_tab2 = search_signature

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
            total_rows  = df_filtered.shape[0]

            if search_signature != st.session_state.last_search_signature_tab2:
                st.session_state.page_tab2 = 1
                if total_rows <= 5:
                    st.session_state.recipe_cols_tab2 = 1
                elif total_rows <= 20:
                    st.session_state.recipe_cols_tab2 = 2
                else:
                    st.session_state.recipe_cols_tab2 = 3
                st.session_state.last_search_signature_tab2 = search_signature

            if recipe_kw or customer_kw or pantone_kw:
                st.info(f"🔍 搜尋結果：共 {total_rows} 筆資料｜固定 {st.session_state.get('recipe_cols_tab2', 1)} 欄顯示")

            limit_options = [1, 5, 10, 20, 50, 100]
            if "limit_per_page_tab2" not in st.session_state:
                st.session_state.limit_per_page_tab2 = 1
            limit = st.session_state.limit_per_page_tab2

            if "last_limit_tab2" not in st.session_state:
                st.session_state.last_limit_tab2 = limit
            if st.session_state.last_limit_tab2 != st.session_state.limit_per_page_tab2:
                st.session_state.page_tab2      = 1
                st.session_state.last_limit_tab2 = st.session_state.limit_per_page_tab2

            total_pages = max((total_rows - 1) // limit + 1, 1)
            if "page_tab2" not in st.session_state:
                st.session_state.page_tab2 = 1
            if st.session_state.page_tab2 > total_pages:
                st.session_state.page_tab2 = total_pages

            start_idx = (st.session_state.page_tab2 - 1) * limit
            page_data = df_filtered.iloc[start_idx: start_idx + limit]

            show_cols    = ["配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方", "Pantone色號"]
            existing_cols = [c for c in show_cols if c in page_data.columns]

            if not page_data.empty:
                st.dataframe(page_data[existing_cols].reset_index(drop=True),
                             use_container_width=True, hide_index=True)
            else:
                if recipe_kw or customer_kw or pantone_kw:
                    st.info("查無符合的配方")

            cols_page = st.columns([1, 1, 1, 2, 1])
            with cols_page[0]:
                if st.button("🏠首頁", key="first_page_tab2"):
                    st.session_state.page_tab2 = 1; st.rerun()
            with cols_page[1]:
                if st.button("🔼上頁", key="prev_page_tab2") and st.session_state.page_tab2 > 1:
                    st.session_state.page_tab2 -= 1; st.rerun()
            with cols_page[2]:
                if st.button("🔽下頁", key="next_page_tab2") and st.session_state.page_tab2 < total_pages:
                    st.session_state.page_tab2 += 1; st.rerun()
            with cols_page[3]:
                jump_page = st.number_input("", min_value=1, max_value=total_pages,
                    value=st.session_state.page_tab2, key="jump_page_tab2", label_visibility="collapsed")
                if jump_page != st.session_state.page_tab2:
                    st.session_state.page_tab2 = jump_page
            with cols_page[4]:
                st.selectbox("", options=limit_options,
                    index=limit_options.index(limit), key="limit_per_page_tab2", label_visibility="collapsed")

            st.caption(f"頁碼 {st.session_state.page_tab2} / {total_pages}，總筆數 {total_rows}")

    # ============================================================
    # Tab 3：配方預覽/修改/刪除
    # ============================================================
    with tab3:

        if not df_recipe.empty and "配方編號" in df_recipe.columns:
            df_recipe["配方編號"] = df_recipe["配方編號"].fillna("").astype(str)

            if "select_recipe_code_page_tab3"  not in st.session_state:
                st.session_state["select_recipe_code_page_tab3"]  = ""
            if "editing_recipe_code"           not in st.session_state:
                st.session_state["editing_recipe_code"]           = None
            if "show_edit_recipe_panel"        not in st.session_state:
                st.session_state["show_edit_recipe_panel"]        = False
            if "show_delete_recipe_confirm"    not in st.session_state:
                st.session_state["show_delete_recipe_confirm"]    = False

            recipe_codes  = [""] + sorted(df_recipe["配方編號"].dropna().unique().tolist())
            selected_code = st.selectbox(
                "輸入配方", options=recipe_codes,
                index=recipe_codes.index(st.session_state["select_recipe_code_page_tab3"])
                      if st.session_state["select_recipe_code_page_tab3"] in recipe_codes else 0,
                format_func=lambda code: "" if code == "" else " | ".join(
                    df_recipe[df_recipe["配方編號"] == code][["配方編號", "顏色", "客戶名稱"]].iloc[0]
                ),
                key="select_recipe_code_page_tab3"
            )

            if st.session_state.get("editing_recipe_code") != selected_code:
                st.session_state.show_edit_recipe_panel     = False
                st.session_state.editing_recipe_code        = None
                st.session_state.show_delete_recipe_confirm = False

            if selected_code:
                df_selected = df_recipe[df_recipe["配方編號"] == selected_code]
                if not df_selected.empty:
                    recipe_row_preview  = df_selected.iloc[0].to_dict()
                    preview_text_recipe = generate_recipe_preview_text(
                        {"配方編號": recipe_row_preview.get("配方編號")},
                        recipe_row_preview
                    )
                    st.markdown(preview_text_recipe, unsafe_allow_html=True)

                    col_left, col_right = st.columns(2)
                    with col_left:
                        if st.button("✏️ 修改", key=f"edit_recipe_btn_tab3_{selected_code}"):
                            st.session_state.show_edit_recipe_panel = True
                            st.session_state.editing_recipe_code    = selected_code
                            st.rerun()
                    with col_right:
                        if st.button("🗑️ 刪除", key=f"delete_recipe_btn_tab3_{selected_code}"):
                            st.session_state.show_delete_recipe_confirm = True
                            st.session_state.delete_recipe_code         = selected_code

                    if st.session_state.get("show_delete_recipe_confirm", False):
                        code = st.session_state["delete_recipe_code"]
                        idx  = df_recipe[df_recipe["配方編號"] == code].index[0]
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ 是，刪除", key="confirm_delete_recipe_yes_tab3"):
                                st.session_state.select_recipe_code_page_tab3 = ""
                                df_recipe.drop(idx, inplace=True)
                                df_recipe.reset_index(drop=True, inplace=True)

                                # ✅ 整表覆寫只在刪除時用（無法 append）
                                ws_recipe.clear()
                                ws_recipe.update(
                                    "A1",
                                    [df_recipe.columns.tolist()] +
                                    df_recipe.fillna("").astype(str).values.tolist()
                                )
                                invalidate_sheet_cache("配方管理")
                                st.session_state.df_recipe = df_recipe
                                st.session_state.df        = df_recipe

                                st.success(f"✅ 已刪除 {code}")
                                st.session_state.show_delete_recipe_confirm = False
                                st.rerun()
                        with c2:
                            if st.button("取消", key="confirm_delete_recipe_no_tab3"):
                                st.session_state.show_delete_recipe_confirm = False
                                st.rerun()

            # ── 修改配方面板 ──
            if st.session_state.get("show_edit_recipe_panel") and st.session_state.get("editing_recipe_code"):
                st.markdown("---")
                code = st.session_state.editing_recipe_code
                idx  = df_recipe[df_recipe["配方編號"] == code].index[0]
                fr   = df_recipe.loc[idx].to_dict()

                with st.form(f"edit_recipe_form_tab3_{code}"):

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        fr["配方編號"] = st.text_input("配方編號", fr.get("配方編號", ""), key=f"edit_recipe_code_{code}")
                    with col2:
                        fr["顏色"] = st.text_input("顏色", fr.get("顏色", ""), key=f"edit_recipe_color_{code}")
                    with col3:
                        options  = [""] + customer_options
                        cust_id  = fr.get("客戶編號", "").strip()
                        cust_name = fr.get("客戶名稱", "").strip()
                        current  = f"{cust_id} - {cust_name}" if cust_id else ""
                        index_c  = options.index(current) if current in options else 0
                        selected = st.selectbox("客戶編號", options, index=index_c, key=f"edit_recipe_customer_{code}")
                        if " - " in selected:
                            fr["客戶編號"], fr["客戶名稱"] = selected.split(" - ", 1)

                    col4, col5, col6 = st.columns(3)
                    with col4:
                        opts_cat = ["原始配方", "附加配方"]
                        fr["配方類別"] = st.selectbox("配方類別", opts_cat,
                            index=opts_cat.index(fr.get("配方類別", opts_cat[0])),
                            key=f"edit_recipe_category_{code}")
                    with col5:
                        opts_st = ["啟用", "停用"]
                        fr["狀態"] = st.selectbox("狀態", opts_st,
                            index=opts_st.index(fr.get("狀態", opts_st[0])),
                            key=f"edit_recipe_status_{code}")
                    with col6:
                        fr["原始配方"] = st.text_input("原始配方", fr.get("原始配方", ""), key=f"edit_recipe_origin_{code}")

                    col7, col8 = st.columns(2)
                    with col7:
                        color_type_options = ["色粉", "色母"]
                        cur_ct = fr.get("色粉類別", color_type_options[0])
                        if cur_ct not in color_type_options:
                            cur_ct = color_type_options[0]
                        fr["色粉類別"] = st.selectbox("色粉類別", color_type_options,
                            index=color_type_options.index(cur_ct), key=f"edit_recipe_color_type_{code}")
                    with col8:
                        unit_options = ["包", "kg", "桶"]
                        cur_u = fr.get("計量單位", unit_options[0])
                        if cur_u not in unit_options:
                            cur_u = unit_options[0]
                        fr["計量單位"] = st.selectbox("計量單位", unit_options,
                            index=unit_options.index(cur_u), key=f"edit_recipe_unit_{code}")

                    fr["重要提醒"] = st.text_input("重要提醒", fr.get("重要提醒", ""), key=f"edit_recipe_note_{code}")

                    cols_ratio = st.columns([2, 0.3, 2, 2, 1])
                    fr["比例1"] = cols_ratio[0].text_input("", fr.get("比例1", ""), key=f"edit_ratio1_{code}")
                    cols_ratio[1].markdown(":", unsafe_allow_html=True)
                    fr["比例2"] = cols_ratio[2].text_input("", fr.get("比例2", ""), key=f"edit_ratio2_{code}")
                    fr["比例3"] = cols_ratio[3].text_input("", fr.get("比例3", ""), key=f"edit_ratio3_{code}")
                    cols_ratio[4].markdown("g/kg", unsafe_allow_html=True)

                    fr["備註"] = st.text_area("備註", fr.get("備註", ""), key=f"edit_recipe_remark_{code}")

                    st.markdown("#### 色粉設定")
                    existing_rows = max(5, sum(1 for i in range(1, 9) if fr.get(f"色粉編號{i}")))
                    num_rows = st.session_state.get("edit_num_powder_rows", existing_rows)
                    st.session_state["edit_num_powder_rows"] = num_rows

                    col_add, col_minus = st.columns(2)
                    with col_add:
                        if st.form_submit_button("➕ 增加色粉列"):
                            st.session_state.edit_num_powder_rows += 1; st.rerun()
                    with col_minus:
                        if st.form_submit_button("➖ 減少色粉列") and st.session_state.edit_num_powder_rows > 5:
                            st.session_state.edit_num_powder_rows -= 1; st.rerun()

                    for i in range(1, st.session_state.edit_num_powder_rows + 1):
                        c1, c2 = st.columns(2)
                        fr[f"色粉編號{i}"] = c1.text_input(f"色粉編號{i}", fr.get(f"色粉編號{i}", ""), key=f"edit_powder_code{i}_{code}")
                        fr[f"色粉重量{i}"] = c2.text_input(f"色粉重量{i}", fr.get(f"色粉重量{i}", ""), key=f"edit_powder_weight{i}_{code}")

                    cat_opts = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
                    default  = fr.get("合計類別", "\u2002")
                    fr["合計類別"] = st.selectbox("合計類別", cat_opts,
                        index=cat_opts.index(default if default in cat_opts else "\u2002"),
                        key=f"edit_recipe_total_category_{code}")

                    col_save, col_back = st.columns(2)
                    submitted_edit = col_save.form_submit_button("💾 儲存修改")
                    cancel         = col_back.form_submit_button("返回")

                    if submitted_edit:
                        for k, v in fr.items():
                            df_recipe.at[idx, k] = v

                        # ✅ 單列更新，不整表覆寫
                        try:
                            save_recipe_row(df_recipe, is_edit=True, edit_index=idx)
                            st.session_state.df_recipe = df_recipe
                            st.session_state.df        = df_recipe
                            st.success(f"✅ 配方 {fr['配方編號']} 已成功更新！")
                        except Exception as e:
                            st.error(f"❌ 儲存失敗：{e}")
                            st.stop()

                        st.session_state.show_edit_recipe_panel = False
                        st.session_state.editing_recipe_code    = None
                        st.session_state.pop("edit_num_powder_rows", None)
                        st.rerun()

                    if cancel:
                        st.session_state.show_edit_recipe_panel = False
                        st.session_state.editing_recipe_code    = None
                        st.session_state.pop("edit_num_powder_rows", None)
                        st.rerun()

    # ============================================================
    # Tab 4：色粉管理
    # ============================================================
    with tab4:

        REQUIRED_COLUMNS = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]

        # ── 使用 session_state 的 df_color，不重讀 Sheet ──
        if "df_color" not in st.session_state:
            st.session_state.df_color     = df_powders
            st.session_state.color_dirty  = False
            st.session_state.edit_color_index = None

        df_color = st.session_state.df_color
        for c in REQUIRED_COLUMNS:
            if c not in df_color.columns:
                df_color[c] = ""

        st.markdown('<h3 style="font-size:18px; color:#f1f5f2;">☑️ 新增 / 編輯色粉</h3>', unsafe_allow_html=True)

        if "form_color" not in st.session_state:
            st.session_state.form_color = {
                "色粉編號": "", "國際色號": "", "名稱": "",
                "色粉類別": "色粉", "包裝": "袋", "備註": ""
            }

        with st.form("color_form_tab4"):
            col1, col2 = st.columns(2)
            with col1:
                cid  = st.text_input("色粉編號",  st.session_state.form_color["色粉編號"])
                intl = st.text_input("國際色號",  st.session_state.form_color["國際色號"])
                name = st.text_input("名稱",       st.session_state.form_color["名稱"])
            with col2:
                ctype = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"],
                    index=["色粉", "色母", "添加劑"].index(st.session_state.form_color["色粉類別"]))
                pack  = st.selectbox("包裝", ["袋", "箱", "kg"],
                    index=["袋", "箱", "kg"].index(st.session_state.form_color["包裝"]))
                note  = st.text_input("備註", st.session_state.form_color["備註"])
            submit_color = st.form_submit_button("💾 新增 / 修改")

        if submit_color:
            new_row = {
                "色粉編號": cid.strip(), "國際色號": intl.strip(), "名稱": name.strip(),
                "色粉類別": ctype, "包裝": pack, "備註": note.strip()
            }
            if new_row["色粉編號"] == "":
                st.warning("⚠️ 請輸入色粉編號")
            else:
                ws_powder = get_cached_worksheet("色粉管理")
                if st.session_state.edit_color_index is not None:
                    idx_c = st.session_state.edit_color_index
                    for k in new_row:
                        df_color.at[idx_c, k] = new_row[k]

                    # ✅ 單列更新
                    try:
                        all_vals = get_cached_sheet_values("色粉管理")
                        header_c = all_vals[0] if all_vals else list(new_row.keys())
                        updated_c = [str(df_color.loc[idx_c].get(col, "")) for col in header_c]
                        import gspread.utils as gu
                        sheet_row = idx_c + 2
                        end_col_c = gu.rowcol_to_a1(sheet_row, len(header_c)).rstrip("0123456789")
                        ws_powder.update(f"A{sheet_row}:{end_col_c}{sheet_row}", [updated_c])
                        invalidate_sheet_cache("色粉管理")
                    except Exception as e:
                        st.error(f"❌ 更新色粉失敗：{e}")

                    st.success("✏️ 已更新色粉")
                    st.session_state.edit_color_index = None
                else:
                    if new_row["色粉編號"] in df_color["色粉編號"].values:
                        st.warning("⚠️ 此色粉編號已存在")
                    else:
                        df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                        # ✅ 只 append 新列
                        ws_powder.append_row([str(new_row.get(col, "")) for col in REQUIRED_COLUMNS])
                        invalidate_sheet_cache("色粉管理")
                        st.success("➕ 已新增色粉")

                st.session_state.df_color = df_color
                st.session_state.form_color = {
                    "色粉編號": "", "國際色號": "", "名稱": "",
                    "色粉類別": "色粉", "包裝": "袋", "備註": ""
                }
                st.rerun()

        st.markdown("---")
        st.markdown('<h3 style="font-size:18px; color:#b8d4c5;">🛠️ 色粉修改 / 刪除</h3>', unsafe_allow_html=True)

        keyword = st.text_input("輸入色粉編號 / 名稱 / 國際色號搜尋",
                                value=st.session_state.get("search_color_tab4", ""))
        st.session_state.search_color_tab4 = keyword.strip()

        if keyword:
            df_show = df_color[
                df_color["色粉編號"].str.contains(keyword, case=False, na=False) |
                df_color["名稱"].str.contains(keyword, case=False, na=False) |
                df_color["國際色號"].str.contains(keyword, case=False, na=False)
            ]
            if df_show.empty:
                st.info("⚠️ 查無符合的色粉")
            else:
                for i, row in df_show.iterrows():
                    c1, c2, c3 = st.columns([4, 1, 1])
                    with c1:
                        st.markdown(f"🔸 {row['色粉編號']}　{row['名稱']}")
                    with c2:
                        if st.button("✏️ 改", key=f"edit_color_{i}"):
                            st.session_state.form_color       = row.to_dict()
                            st.session_state.edit_color_index = i
                    with c3:
                        if st.button("🗑️ 刪", key=f"del_color_{i}"):
                            ws_powder = get_cached_worksheet("色粉管理")
                            # ✅ 刪除單列
                            try:
                                all_vals = get_cached_sheet_values("色粉管理")
                                target_id = str(row["色粉編號"]).strip()
                                for r_idx, r_row in enumerate(all_vals[1:], start=2):
                                    if r_row[0].strip() == target_id:
                                        ws_powder.delete_rows(r_idx)
                                        invalidate_sheet_cache("色粉管理")
                                        break
                            except Exception as e:
                                st.error(f"❌ 刪除色粉失敗：{e}")

                            st.session_state.df_color = df_color.drop(index=i).reset_index(drop=True)
                            st.session_state._tab4_need_rerun = True

        if st.session_state.get("_tab4_need_rerun", False):
            st.session_state._tab4_need_rerun = False
            st.rerun()

    # ============================================================
    # Tab 5：色母換算
    # ============================================================
    with tab5:

        st.markdown('<h3 style="font-size:18px; color:#f1f5f2;">👹 色母換算工具</h3>', unsafe_allow_html=True)

        for key, default in [
            ("master_batch_formula",       None),
            ("master_batch_ratio",         "50:1"),
            ("master_batch_additive",      "CA"),
            ("master_batch_total_qty",     100000.0),
            ("master_batch_material",      ""),
            ("master_batch_material_qty",  60000.0),
            ("master_batch_new_code",      ""),
            ("master_batch_selected_code", ""),
            ("master_batch_calculated",    None),
        ]:
            if key not in st.session_state:
                st.session_state[key] = default

        if st.session_state.master_batch_calculated is not None:
            if "additive_display" not in st.session_state.master_batch_calculated:
                st.session_state.master_batch_calculated = None

        st.markdown("**步驟 1：選擇原始配方**")

        if not df_recipe.empty:
            recipe_options = [""] + sorted(df_recipe["配方編號"].dropna().astype(str).unique().tolist())

            if st.session_state.master_batch_selected_code not in recipe_options:
                st.session_state.master_batch_selected_code = ""

            selected_recipe_code = st.selectbox(
                "配方編號", options=recipe_options,
                index=recipe_options.index(st.session_state.master_batch_selected_code),
                format_func=lambda code: "" if code == "" else " | ".join(
                    df_recipe[df_recipe["配方編號"] == code][["配方編號", "顏色", "客戶名稱"]].iloc[0].astype(str)
                ),
                key="master_batch_recipe_select"
            )
            st.session_state.master_batch_selected_code = selected_recipe_code

            if selected_recipe_code:
                recipe_data = df_recipe[df_recipe["配方編號"] == selected_recipe_code].iloc[0].to_dict()
                st.session_state.master_batch_formula = recipe_data

                st.markdown("**原始配方預覽**")
                info_parts = [f"編號：{recipe_data.get('配方編號', '')}",
                              f"顏色：{recipe_data.get('顏色', '')}"]
                if recipe_data.get("比例3"):
                    info_parts.append(f"比例：{recipe_data.get('比例3')}")
                info_parts.append(f"計量單位：{recipe_data.get('計量單位', '')}")
                if recipe_data.get("Pantone色號"):
                    info_parts.append(f"Pantone：{recipe_data.get('Pantone色號')}")
                st.markdown(f"<div style='font-size:16px;font-family:Arial;margin-bottom:10px;'>{' 　 '.join(info_parts)}</div>", unsafe_allow_html=True)

                preview_lines = []
                for i in range(1, 9):
                    pid = str(recipe_data.get(f"色粉編號{i}", "")).strip()
                    pwt = str(recipe_data.get(f"色粉重量{i}", "")).strip()
                    if pid and pwt:
                        preview_lines.append(f"{pid.ljust(12)}{pwt}")
                preview_lines.append("_" * 40)
                total_cat = recipe_data.get("合計類別", "").strip()
                net_wt    = str(recipe_data.get("淨重", "") or "").strip()
                if total_cat and total_cat != "無":
                    preview_lines.append(f"{total_cat.ljust(12)}{net_wt}")
                st.code("\n".join(preview_lines), language=None)

                st.markdown("---")

                with st.form("master_batch_form"):
                    st.markdown("**步驟 2：設定色母比例**")
                    ratio_options = ["12.5", "25:1", "50:1", "100:1"]
                    if st.session_state.master_batch_ratio not in ratio_options:
                        st.session_state.master_batch_ratio = "25:1"
                    ratio = st.selectbox("色母比例", ratio_options,
                        index=ratio_options.index(st.session_state.master_batch_ratio), key="ratio_select")

                    st.markdown("**步驟 3：選擇添加劑**")
                    additive_options = ["CA", "LA", "CP(增韌劑)"]
                    if st.session_state.master_batch_additive not in additive_options:
                        st.session_state.master_batch_additive = "CA"
                    additive = st.selectbox("添加劑", additive_options,
                        index=additive_options.index(st.session_state.master_batch_additive), key="additive_select")

                    st.markdown("**步驟 4：填寫合計資料**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        total_qty = st.number_input("總數量 (g)", min_value=0.0,
                            value=st.session_state.master_batch_total_qty, step=1000.0, key="total_quantity_input")
                    with col2:
                        material_code = st.text_input("料號", value=st.session_state.master_batch_material,
                            placeholder="例如：PE5100", key="material_input")
                    with col3:
                        material_qty = st.number_input("原料數量 (g)", min_value=0.0,
                            value=st.session_state.master_batch_material_qty, step=1000.0, key="material_quantity_input")

                    st.markdown("**步驟 5：新色母編號**")
                    new_code  = st.text_input("新色母編號", value=st.session_state.master_batch_new_code,
                        placeholder="例如：26820M", key="new_code_input")
                    calculate = st.form_submit_button("🧮 計算色母配方")

                if calculate:
                    st.session_state.master_batch_ratio        = ratio
                    st.session_state.master_batch_additive     = additive
                    st.session_state.master_batch_total_qty    = total_qty
                    st.session_state.master_batch_material     = material_code
                    st.session_state.master_batch_material_qty = material_qty
                    st.session_state.master_batch_new_code     = new_code

                    if total_qty <= 0:
                        st.warning("⚠️ 請填寫總數量"); st.stop()
                    if not material_code.strip():
                        st.warning("⚠️ 請填寫料號"); st.stop()
                    if material_qty <= 0:
                        st.warning("⚠️ 請填寫原料數量"); st.stop()
                    if not new_code.strip():
                        st.warning("⚠️ 請填寫新色母編號"); st.stop()

                    multiplier_map = {"12.5": 54, "25:1": 104, "50:1": 200, "100:1": 400}
                    multiplier = multiplier_map[ratio]

                    powder_data         = []
                    total_powder_weight = 0.0
                    for i in range(1, 9):
                        pid = str(recipe_data.get(f"色粉編號{i}", "")).strip()
                        pwt = str(recipe_data.get(f"色粉重量{i}", "")).strip()
                        if pid and pwt:
                            try:
                                ow = float(pwt)
                                nw = ow * multiplier
                                powder_data.append({"id": pid, "weight": nw})
                                total_powder_weight += nw
                            except:
                                pass

                    additive_qty     = total_qty - total_powder_weight - material_qty
                    additive_display = additive.replace("(增韌劑)", "")

                    if additive_qty < 0:
                        st.error(f"❌ 總數量不足！需至少：{total_powder_weight + material_qty:.2f}g"); st.stop()

                    calculated_total = total_powder_weight + additive_qty + material_qty

                    st.session_state.master_batch_calculated = {
                        "new_code": new_code, "powder_data": powder_data,
                        "additive": additive, "additive_display": additive_display,
                        "additive_qty": additive_qty, "material_code": material_code,
                        "material_qty": material_qty, "total_qty": total_qty,
                        "total_powder_weight": total_powder_weight,
                        "calculated_total": calculated_total,
                        "ratio": ratio, "recipe_data": recipe_data,
                        "selected_recipe_code": selected_recipe_code
                    }

                if st.session_state.master_batch_calculated is not None:
                    calc = st.session_state.master_batch_calculated
                    st.success("✅ 色母配方計算完成")
                    st.markdown("**色母配方預覽**")

                    info_parts = [f"編號：{calc['new_code']}",
                                  f"顏色：{calc['recipe_data'].get('顏色', '')}",
                                  f"比例：{calc['ratio']}"]
                    st.markdown(f"<div style='font-size:16px;font-family:Arial;margin-bottom:10px;'>{' 　 '.join(info_parts)}</div>", unsafe_allow_html=True)

                    table_html = "<table style='border-collapse:collapse;font-size:12px;line-height:1.4;'>"
                    table_html += "<tr><th>色粉編號</th><th>重量</th></tr>"
                    for item in calc["powder_data"]:
                        w = item["weight"]
                        w_str = f"{int(w)}" if w == int(w) else f"{w:.2f}"
                        table_html += f"<tr><td>{item['id']}</td><td style='text-align:right'>{w_str}</td></tr>"
                    aq = calc["additive_qty"]
                    aq_str = f"{int(aq)}" if aq == int(aq) else f"{aq:.2f}"
                    table_html += f"<tr><td>{calc['additive_display']}</td><td style='text-align:right'>{aq_str}</td></tr>"
                    mq = calc["material_qty"]
                    mq_str = f"{int(mq)}" if mq == int(mq) else f"{mq:.2f}"
                    table_html += f"<tr><td>{calc['material_code']}</td><td style='text-align:right'>{mq_str}</td></tr>"
                    table_html += "</table>"
                    st.markdown(table_html, unsafe_allow_html=True)
                    st.caption(f"✓ 色粉：{calc['total_powder_weight']:.2f}g + 添加劑：{calc['additive_qty']:.2f}g + 原料：{calc['material_qty']:.2f}g = {calc['calculated_total']:.2f}g")

                    def generate_master_batch_html(calc_data):
                        html_lines = [
                            f"編號：{calc_data['new_code']}　顏色：{calc_data['recipe_data'].get('顏色', '')}　比例：{calc_data['ratio']}",
                            ""
                        ]
                        for item in calc_data["powder_data"]:
                            w = item["weight"]
                            w_str = f"{int(w)}" if w == int(w) else f"{w:.2f}"
                            html_lines.append(f"{item['id'].ljust(12)}{w_str.rjust(8)}")
                        aq = calc_data["additive_qty"]
                        aq_str = f"{int(aq)}" if aq == int(aq) else f"{aq:.2f}"
                        html_lines.append(f"{calc_data['additive_display'].ljust(12)}{aq_str.rjust(8)}")
                        mq = calc_data["material_qty"]
                        mq_str = f"{int(mq)}" if mq == int(mq) else f"{mq:.2f}"
                        html_lines.append(f"{calc_data['material_code'].ljust(12)}{mq_str.rjust(8)}")
                        content = "<br>".join(html_lines)
                        return f"""<html><head><meta charset="utf-8"><title>色母配方列印</title>
                        <style>
                        @page {{ size: A6 landscape; margin: 10mm; }}
                        body {{ margin:0; font-family:'Courier New',Courier,monospace; font-size:24px; line-height:1.6; }}
                        pre {{ white-space:pre-wrap; margin-left:25px; margin-top:10px; }}
                        </style>
                        <script>window.onload=function(){{window.print();}}</script>
                        </head><body><pre>{content}</pre></body></html>"""

                    html_content = generate_master_batch_html(calc)

                    col_download, col_save = st.columns([2, 2])
                    with col_download:
                        st.download_button(
                            label="📥 下載 A6 列印 200%",
                            data=html_content.encode("utf-8"),
                            file_name=f"{calc['new_code']}_色母配方.html",
                            mime="text/html",
                            key="download_master_batch_html"
                        )
                    with col_save:
                        if st.button("💾 新增此配方到配方管理", key="save_master_batch_recipe"):
                            if calc["new_code"] in df_recipe["配方編號"].astype(str).values:
                                st.error(f"❌ 配方編號 {calc['new_code']} 已存在")
                            else:
                                try:
                                    ratio_parts = calc["ratio"].split(":")
                                    new_recipe = {
                                        "配方編號": calc["new_code"],
                                        "顏色":     calc["recipe_data"].get("顏色", ""),
                                        "客戶編號": calc["recipe_data"].get("客戶編號", ""),
                                        "客戶名稱": calc["recipe_data"].get("客戶名稱", ""),
                                        "配方類別": "原始配方", "狀態": "啟用", "原始配方": "",
                                        "色粉類別": "色母", "計量單位": "kg",
                                        "Pantone色號": calc["recipe_data"].get("Pantone色號", ""),
                                        "比例1": ratio_parts[0] if len(ratio_parts) > 0 else "",
                                        "比例2": ratio_parts[1] if len(ratio_parts) > 1 else "",
                                        "比例3": "",
                                        "淨重":     str(calc["total_qty"]), "淨重單位": "g",
                                        "合計類別": calc["material_code"],
                                        "重要提醒": f"色母換算自 {calc['selected_recipe_code']}",
                                        "備註":     calc["recipe_data"].get("備註", ""),
                                        "建檔時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    for i, item in enumerate(calc["powder_data"], 1):
                                        new_recipe[f"色粉編號{i}"] = item["id"]
                                        new_recipe[f"色粉重量{i}"] = str(item["weight"])
                                    next_i = len(calc["powder_data"]) + 1
                                    if next_i <= 8:
                                        new_recipe[f"色粉編號{next_i}"] = calc["additive_display"]
                                        new_recipe[f"色粉重量{next_i}"] = str(calc["additive_qty"])
                                    for i in range(1, 9):
                                        new_recipe.setdefault(f"色粉編號{i}", "")
                                        new_recipe.setdefault(f"色粉重量{i}", "")

                                    # ✅ 只 append 新列
                                    all_vals = get_cached_sheet_values("配方管理")
                                    existing_columns = all_vals[0] if all_vals else list(new_recipe.keys())
                                    new_row = [new_recipe.get(col, "") for col in existing_columns]
                                    ws_recipe.append_row(new_row)
                                    invalidate_sheet_cache("配方管理")

                                    df_recipe_new = pd.concat(
                                        [df_recipe, pd.DataFrame([new_recipe])], ignore_index=True
                                    )
                                    st.session_state.df_recipe = df_recipe_new
                                    st.session_state.df        = df_recipe_new
                                    st.success(f"✅ 配方 {calc['new_code']} 已新增！")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"❌ 新增失敗：{e}")
                                    import traceback
                                    st.code(traceback.format_exc())
        else:
            st.info("⚠️ 目前沒有配方資料，請先至「配方建立」新增配方")
    
# =============== Tab 架構結束 ===============                            
# --- 生產單分頁 ----------------------------------------------------
elif menu == "生產單管理":
    load_recipe(force_reload=True)
    
    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # st.markdown(
    #     '<h1 style="font-size:24px; font-family:Arial; color:#F9DC5C;">🛸 生產單管理</h1>',
    #     unsafe_allow_html=True
    # )

    from pathlib import Path
    from datetime import datetime, timedelta
    import pandas as pd
    import re
    import os

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
        ws_recipe = get_cached_worksheet("配方管理")
        ws_order = get_cached_worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法載入工作表：{e}")
        st.stop()
    
    # 載入配方管理表
    try:
        df_recipe = get_cached_sheet_df("配方管理")
        df_recipe.columns = df_recipe.columns.str.strip()
        df_recipe.fillna("", inplace=True)
    
        if "配方編號" in df_recipe.columns:
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
        df_order = get_cached_sheet_df("生產單")
        if not df_order.empty:
            df_order = df_order.astype(str)
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
            invalidate_sheet_cache("生產單")
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

    # ===== 完整初始化庫存（初始 + 進貨 - 已用） =====
    # ===== 庫存計算函式 =====
    def calculate_current_stock():
        """
        計算截至「今天」的實際庫存
        邏輯：與庫存區 calc_usage_for_stock() 完全一致
        """
        stock_dict = {}
        
        try:
            df_stock = get_cached_sheet_df("庫存記錄")
        except Exception as e:
            st.warning(f"⚠️ 無法讀取庫存記錄：{e}")
            return stock_dict
        
        if df_stock.empty:
            return stock_dict
        
        # ⚠️ 定義「今天」作為結束日
        today = pd.Timestamp.today().normalize()
        
        # 清理資料
        df_stock["類型"] = df_stock["類型"].astype(str).str.strip()
        df_stock["色粉編號"] = df_stock["色粉編號"].astype(str).str.strip()
        if "日期" in df_stock.columns:
            df_stock["日期"] = pd.to_datetime(df_stock["日期"], errors="coerce")
        
        # === 步驟 1：找出每個色粉的「最新初始庫存」及其日期 ===
        initial_stocks = {}
        
        for idx, row in df_stock.iterrows():
            if row["類型"] != "初始":
                continue
            
            pid = row.get("色粉編號", "")
            if not pid:
                continue
            
            try:
                qty = float(row.get("數量", 0))
            except:
                qty = 0.0
            
            if str(row.get("單位", "g")).lower() == "kg":
                qty *= 1000
            
            row_date = row.get("日期")
            if pd.isna(row_date):
                row_date = pd.Timestamp('2000-01-01')
            
            if pid not in initial_stocks:
                initial_stocks[pid] = {"qty": qty, "date": row_date}
            elif row_date > initial_stocks[pid]["date"]:
                initial_stocks[pid] = {"qty": qty, "date": row_date}
        
        for pid, data in initial_stocks.items():
            stock_dict[pid] = data["qty"]
        
        # === 步驟 2：累加「起算點 ~ 今天」的進貨 ===
        # 先取得所有進貨記錄的色粉，建立起算點
        df_in = df_stock[df_stock["類型"].astype(str).str.strip() == "進貨"].copy()
        for pid in df_in["色粉編號"].unique():
            if pid not in initial_stocks:
                # ✅ 找到該色粉最早的進貨日期作為起算點
                pid_in = df_in[df_in["色粉編號"] == pid]
                min_in_date = pid_in["日期"].min() if not pid_in.empty else pd.Timestamp('2000-01-01')
                initial_stocks[pid] = {"qty": 0.0, "date": min_in_date}
                stock_dict[pid] = 0.0
        
        for idx, row in df_stock.iterrows():
            if row["類型"] != "進貨":
                continue
            
            pid = row.get("色粉編號", "")
            if not pid:
                continue
            
            row_date = row.get("日期")
            
            # 檢查進貨日期是否在「起算點 ~ 今天」之間
            if pd.isna(row_date):
                should_add = True
            else:
                should_add = (
                    row_date >= initial_stocks[pid]["date"] and
                    row_date <= today
                )
            
            if should_add:
                try:
                    qty = float(row.get("數量", 0))
                except:
                    qty = 0.0
                
                if str(row.get("單位", "g")).lower() == "kg":
                    qty *= 1000
                
                stock_dict[pid] += qty
        
        # === 步驟 3：扣除「起算點 ~ 今天」的生產單用量 ===
        df_order_hist = st.session_state.get("df_order", pd.DataFrame()).copy()
        if df_order_hist.empty:
            return stock_dict
        
        if "生產日期" in df_order_hist.columns:
            df_order_hist["生產日期"] = pd.to_datetime(df_order_hist["生產日期"], errors="coerce")
        
        df_recipe_hist = st.session_state.get("df_recipe", pd.DataFrame()).copy()
        
        # ✅ 確保必要欄位存在
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        for c in powder_cols + ["配方編號", "配方類別", "原始配方"]:
            if c not in df_recipe_hist.columns:
                df_recipe_hist[c] = ""
        
        for _, order_hist in df_order_hist.iterrows():
            order_date = order_hist.get("生產日期")
            
            # ✅ 沒有日期的訂單直接跳過
            if pd.isna(order_date):
                continue
            
            recipe_id = str(order_hist.get("配方編號", "")).strip()
            if not recipe_id:
                continue
            
            # ✅ 關鍵修正：只處理「這張訂單的配方」，避免重複計算
            # 取得主配方與附加配方
            recipe_rows = []
            main_df = df_recipe_hist[df_recipe_hist["配方編號"].astype(str).str.strip() == recipe_id]
            if not main_df.empty:
                recipe_rows.append(main_df.iloc[0].to_dict())
            
            add_df = df_recipe_hist[
                (df_recipe_hist["配方類別"].astype(str).str.strip() == "附加配方") &
                (df_recipe_hist["原始配方"].astype(str).str.strip() == recipe_id)
            ]
            if not add_df.empty:
                recipe_rows.extend(add_df.to_dict("records"))
            
            # 計算包裝總量（kg）
            packs_total_kg = 0.0
            for j in range(1, 5):
                try:
                    w_val = float(order_hist.get(f"包裝重量{j}", 0) or 0)
                    n_val = float(order_hist.get(f"包裝份數{j}", 0) or 0)
                    packs_total_kg += w_val * n_val
                except:
                    pass
            
            if packs_total_kg <= 0:
                continue
            
            # ✅ 建立這張訂單已處理的色粉集合（避免重複扣除）
            processed_powders = set()
            
            # 逐配方計算用量
            for rec in recipe_rows:
                pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                
                for i, pid in enumerate(pvals, 1):
                    if not pid or pid.endswith(("01", "001", "0001")):
                        continue
                    
                    # ✅ 避免同一色粉在同一張訂單中重複扣除
                    if pid in processed_powders:
                        continue
                    
                    # ✅ 只處理有庫存記錄的色粉
                    if pid not in stock_dict:
                        continue
                    
                    # ✅ 檢查日期範圍（使用起算日期）
                    order_date_norm = order_date.normalize()
                    
                    # 取得起算日期
                    if pid in initial_stocks:
                        init_start_date = initial_stocks[pid]["date"].normalize()
                    else:
                        # 沒有初始庫存的色粉，使用最早的日期
                        init_start_date = pd.Timestamp('2000-01-01').normalize()
                    
                    if order_date_norm < init_start_date:
                        continue
                    if order_date_norm > today:
                        continue
                    
                    try:
                        ratio_g = float(rec.get(f"色粉重量{i}", 0) or 0)
                    except:
                        ratio_g = 0.0
                    
                    if ratio_g <= 0:
                        continue
                    
                    # ✅ 計算用量（g） = 色粉重量 * 包裝總量
                    total_used_g = ratio_g * packs_total_kg
                    
                    if pid in stock_dict:
                        stock_dict[pid] -= total_used_g
                        processed_powders.add(pid)  # ✅ 標記已處理
        
        return stock_dict
    
    # ⚡ 生產單頁：庫存重算節流（預設 3 分鐘）
    now = datetime.now()
    stock_recalc_interval_sec = 180
    last_calc_time = st.session_state.get("stock_calc_time")

    should_recalc_stock = (
        "last_final_stock" not in st.session_state
        or last_calc_time is None
        or not isinstance(last_calc_time, datetime)
        or (now - last_calc_time).total_seconds() > stock_recalc_interval_sec
    )

    if should_recalc_stock:
        # 讓既有 sheet TTL 快取先判斷是否需要打 API
        load_recipe(force_reload=False)
        st.session_state["last_final_stock"] = calculate_current_stock()
        st.session_state["stock_calc_time"] = now
    
    # ============================================================
    # 共用顯示函式（正式流程使用）
    # ============================================================
    def format_option(r):
        label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
        if r.get("配方類別", "") == "附加配方":
            label += "（附加配方）"
        return label

    def format_option_with_status(row):
        base = format_option(row)  # 你原本的顯示格式
        status = str(row.get("狀態", "")).strip()
        if status == "停用":
            return f"🚫 {base} 【停用】"
        return base
        
    DEBUG_MODE = False   # 平常 False，要查帳再打開
    if DEBUG_MODE:
        # ============================================================
        # 🐛 庫存計算除錯模式（可切換色粉）
        # ============================================================
        DEBUG_POWDER_ID = "CA"   # ⭐⭐⭐ 只要改這一行，例如 "CB"、"R12"
        
        if st.checkbox(
            f"🐛 顯示庫存計算除錯資訊（{DEBUG_POWDER_ID} 色粉）",
            value=False,
            key=f"debug_stock_{DEBUG_POWDER_ID}"
        ):
            st.markdown(f"### 📊 {DEBUG_POWDER_ID} 色粉庫存計算詳情")
        
            try:
                # ===== 讀取庫存記錄 =====
                ws_stock = get_cached_worksheet("庫存記錄")
                records = get_cached_sheet_df("庫存記錄").to_dict("records")
                df_stock_debug = pd.DataFrame(records)
        
                if not df_stock_debug.empty:
                    df_stock_debug["類型"] = df_stock_debug["類型"].astype(str).str.strip()
                    df_stock_debug["色粉編號"] = df_stock_debug["色粉編號"].astype(str).str.strip()
        
                    if "日期" in df_stock_debug.columns:
                        df_stock_debug["日期"] = pd.to_datetime(
                            df_stock_debug["日期"], errors="coerce"
                        )
        
                    df_powder = df_stock_debug[
                        df_stock_debug["色粉編號"] == DEBUG_POWDER_ID
                    ]
        
                    if not df_powder.empty:
                        st.markdown(f"**庫存記錄表中的 {DEBUG_POWDER_ID} 色粉：**")
                        st.dataframe(
                            df_powder[["類型", "日期", "數量", "單位", "備註"]],
                            use_container_width=True,
                            hide_index=True
                        )
        
                        # ===== 初始庫存 =====
                        df_init = df_powder[df_powder["類型"] == "初始"]
                        if not df_init.empty:
                            latest_init = df_init.sort_values("日期", ascending=False).iloc[0]
                            init_qty = float(latest_init["數量"])
        
                            if str(latest_init["單位"]).lower() == "kg":
                                init_qty *= 1000
        
                            st.info(
                                f"✅ 最新初始庫存：{init_qty} g（日期："
                                f"{latest_init['日期'].strftime('%Y/%m/%d') if pd.notna(latest_init['日期']) else '無日期'}）"
                            )
        
                        # ===== 進貨量 =====
                        df_in = df_powder[df_powder["類型"] == "進貨"]
                        if not df_in.empty:
                            total_in = 0
                            for _, row in df_in.iterrows():
                                qty = float(row["數量"])
                                if str(row["單位"]).lower() == "kg":
                                    qty *= 1000
                                total_in += qty
        
                            st.info(f"✅ 進貨總量：{total_in} g")
        
                    else:
                        st.warning(f"⚠️ 庫存記錄表中沒有 {DEBUG_POWDER_ID} 色粉的記錄")
        
                # ====================================================
                # 歷史生產單用量計算
                # ====================================================
                df_order_debug = st.session_state.get("df_order", pd.DataFrame()).copy()
                df_recipe_debug = st.session_state.get("df_recipe", pd.DataFrame()).copy()
        
                if not df_order_debug.empty and not df_recipe_debug.empty:
                    total_usage = 0
                    powder_orders = []
        
                    for _, order in df_order_debug.iterrows():
                        recipe_id = str(order.get("配方編號", "")).strip()
                        recipe_rows = df_recipe_debug[
                            df_recipe_debug["配方編號"] == recipe_id
                        ]
        
                        if recipe_rows.empty:
                            continue
        
                        recipe_row = recipe_rows.iloc[0]
        
                        for i in range(1, 9):
                            pid = str(recipe_row.get(f"色粉編號{i}", "")).strip()
        
                            if pid == DEBUG_POWDER_ID:
                                ratio_g = float(recipe_row.get(f"色粉重量{i}", 0))
                                order_usage = 0
        
                                for j in range(1, 5):
                                    w_val = float(order.get(f"包裝重量{j}", 0) or 0)
                                    n_val = float(order.get(f"包裝份數{j}", 0) or 0)
                                    order_usage += ratio_g * w_val * n_val
        
                                if order_usage > 0:
                                    total_usage += order_usage
                                    powder_orders.append({
                                        "生產單號": order.get("生產單號", ""),
                                        "生產日期": order.get("生產日期", ""),
                                        "用量(g)": order_usage
                                    })
        
                    if powder_orders:
                        st.markdown(f"**歷史生產單中的 {DEBUG_POWDER_ID} 用量：**")
                        df_orders = pd.DataFrame(powder_orders)
                        st.dataframe(df_orders, use_container_width=True, hide_index=True)
                        st.info(f"✅ 歷史用量總計：{total_usage} g")
        
                # ====================================================
                # 🔬 深度除錯：函式 vs 除錯計算
                # ====================================================
                st.markdown("---")
                st.markdown("### 🔬 深度除錯：函式計算 vs 除錯區塊計算")
        
                usage_with_date = 0
                usage_no_date = 0
                before_init_usage = 0
                after_init_usage = 0
        
                if not df_init.empty:
                    init_date = df_init.sort_values("日期", ascending=False).iloc[0]["日期"]
        
                    for _, order in df_order_debug.iterrows():
                        order_date = pd.to_datetime(
                            order.get("生產日期"),
                            errors="coerce"
                        )
                        recipe_id = str(order.get("配方編號", "")).strip()
        
                        recipe_rows = df_recipe_debug[
                            df_recipe_debug["配方編號"] == recipe_id
                        ]
                        if recipe_rows.empty:
                            continue
        
                        recipe_row = recipe_rows.iloc[0]
                        order_usage = 0
        
                        for i in range(1, 9):
                            pid = str(recipe_row.get(f"色粉編號{i}", "")).strip()
                            if pid == DEBUG_POWDER_ID:
                                ratio_g = float(recipe_row.get(f"色粉重量{i}", 0))
                                for j in range(1, 5):
                                    w_val = float(order.get(f"包裝重量{j}", 0) or 0)
                                    n_val = float(order.get(f"包裝份數{j}", 0) or 0)
                                    order_usage += ratio_g * w_val * n_val
        
                        if order_usage == 0:
                            continue
        
                        if pd.isna(order_date):
                            usage_no_date += order_usage
                        elif order_date < init_date:
                            before_init_usage += order_usage
                        else:
                            after_init_usage += order_usage
                            usage_with_date += order_usage
        
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(
                            f"**除錯區塊計算（有日期）**\n\n"
                            f"{usage_with_date / 1000:.2f} kg"
                        )
        
                    with col2:
                        final_stock = st.session_state.get(
                            "last_final_stock", {}
                        ).get(DEBUG_POWDER_ID, 0)
        
                        function_usage = 3000000 - final_stock
                        st.error(
                            f"**函式計算（calculate_current_stock）**\n\n"
                            f"{function_usage / 1000:.2f} kg"
                        )
        
                    st.markdown("**詳細分類：**")
                    st.write(f"- 無日期用量：{usage_no_date / 1000:.2f} kg")
                    st.write(f"- 起算點前用量：{before_init_usage / 1000:.2f} kg")
                    st.write(f"- 起算點後用量：{after_init_usage / 1000:.2f} kg")
                    st.write(
                        f"- **除錯總用量**："
                        f"{(usage_no_date + before_init_usage + after_init_usage) / 1000:.2f} kg"
                    )
        
                    diff = function_usage - usage_with_date
                    if abs(diff) > 100:
                        st.error(
                            f"🔴 **函式多扣除了 {diff / 1000:.2f} kg！**"
                        )
                        st.info("⚠️ 請檢查日期與起算點邏輯")
        
                final_stock = st.session_state.get(
                    "last_final_stock", {}
                ).get(DEBUG_POWDER_ID, 0)
        
                st.success(
                    f"🎯 **計算後的 {DEBUG_POWDER_ID} 庫存："
                    f"{final_stock / 1000:.2f} kg（{final_stock:.2f} g）**"
                )
        
            except Exception as e:
                st.error(f"❌ 除錯過程發生錯誤：{e}")
                import traceback
                st.code(traceback.format_exc())
    
       
        # 轉換時間欄位與配方編號欄清理
        if "建立時間" in df_order.columns:
            df_order["建立時間"] = pd.to_datetime(df_order["建立時間"], errors="coerce")
        if "配方編號" in df_order.columns:
            df_order["配方編號"] = df_order["配方編號"].map(clean_powder_id)
        
        # ✅ 修正：初始化 session_state（保留已存在的值）
        if "new_order" not in st.session_state:
            st.session_state["new_order"] = None
        if "show_confirm_panel" not in st.session_state:
            st.session_state["show_confirm_panel"] = False
        if "editing_order" not in st.session_state:
            st.session_state["editing_order"] = None
        if "show_edit_panel" not in st.session_state:
            st.session_state["show_edit_panel"] = False
        if "order_page" not in st.session_state:
            st.session_state["order_page"] = 1
            
    # =============== Tab 架構開始 ===============
    tab1, tab2, tab3 = st.tabs(["🛸 生產單建立", "📜 生產單記錄表", "👀 生產單預覽/修改/刪除"])
    # ============================================================
    # Tab 1: 生產單建立
    # ============================================================
    with tab1:
        # ================== Tab1 安全初始化 ==================
        # 確保控制旗標存在
        if "show_confirm_panel" not in st.session_state:
            st.session_state["show_confirm_panel"] = False
        if "new_order" not in st.session_state:
            st.session_state["new_order"] = None
        if "new_order_saved" not in st.session_state:
            st.session_state["new_order_saved"] = False

        # ===== Tab1 下載狀態初始化 =====
        if "downloaded_html_tab1" not in st.session_state:
            st.session_state["downloaded_html_tab1"] = False
        
        # 初始化表單欄位，避免 AttributeError
        for key in ["form_remark_tab1", "form_color_tab1", "form_pantone_tab1", "form_raw_material_tab1", "form_important_note_tab1", "form_total_category_tab1"]:
            if key not in st.session_state:
                st.session_state[key] = ""
        
        for i in range(1, 5):
            if f"form_weight{i}_tab1" not in st.session_state:
                st.session_state[f"form_weight{i}_tab1"] = ""
            if f"form_count{i}_tab1" not in st.session_state:
                st.session_state[f"form_count{i}_tab1"] = ""
        
        # 初始化 Tab1 使用的 local 變數
        show_confirm_panel = st.session_state["show_confirm_panel"]
        order = st.session_state["new_order"]

        # ===== 搜尋表單 =====
        with st.form("search_add_form", clear_on_submit=False):
            col1, col2, col3 = st.columns([4,1,1])
            with col1:
                search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text_tab1")
            with col2:
                exact = st.checkbox("精準搜", key="exact_search_tab1")
            with col3:
                add_btn = st.form_submit_button("➕ 新增")
        
        # ===== 處理搜尋結果（不污染原始 df_recipe）=====
        search_text_original = search_text.strip()
        search_text_normalized = fix_leading_zero(search_text_original)
        search_text_upper = search_text_original.upper()
        
        # 🔒 一律先 copy，搜尋只作用在 search_df
        search_df = df_recipe.copy()
        
        if search_text_normalized:
            # 建立「僅供搜尋使用」的標準化配方編號
            search_df["_配方編號標準"] = search_df["配方編號"].map(
                lambda x: fix_leading_zero(clean_powder_id(x))
            )
        
            if exact:
                filtered = search_df[
                    (search_df["_配方編號標準"] == search_text_normalized) |
                    (search_df["客戶名稱"].str.upper() == search_text_upper)
                ]
            else:
                filtered = search_df[
                    search_df["_配方編號標準"].str.contains(search_text_normalized, case=False, na=False) |
                    search_df["客戶名稱"].str.contains(search_text_original, case=False, na=False)
                ]
        
            # 搜尋結束後移除暫用欄位
            filtered = filtered.drop(columns=["_配方編號標準"], errors="ignore")
        
        else:
            # 沒輸入搜尋字 → 顯示全部（仍是 copy）
            filtered = search_df.copy()
    
        # 建立搜尋結果標籤與選項
        if not filtered.empty:
            filtered["label"] = filtered.apply(format_option_with_status, axis=1)
            option_map = dict(zip(filtered["label"], filtered.to_dict(orient="records")))
        else:
            option_map = {}
    
        # ===== 顯示選擇結果 =====
        if    not    option_map:
            st.warning("查無符合的配方")
            selected_row    =    None
            selected_label    =    None
            
        elif len(option_map) == 1:
            selected_label = list(option_map.keys())[0]
            selected_row = option_map[selected_label].copy()
        
            # 計算當天已有的單數，生成生產單號
            df_all_orders = st.session_state.df_order.copy()
            today_str = datetime.now().strftime("%Y%m%d")
            count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
            new_id = f"{today_str}-{count_today + 1:03}"
        
            # 自動建立 order
            order = {
                "生產單號": new_id,
                "生產日期": datetime.now().strftime("%Y-%m-%d"),
                "建立時間": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                "配方編號": selected_row.get("配方編號", ""),
                "顏色": selected_row.get("顏色", ""),
                "客戶名稱": selected_row.get("客戶名稱", ""),
                "Pantone 色號": selected_row.get("Pantone色號", ""),
                "計量單位": selected_row.get("計量單位", ""),
                "備註": str(selected_row.get("備註", "")).strip(),
                "重要提醒": str(selected_row.get("重要提醒", "")).strip(),
                "合計類別": str(selected_row.get("合計類別", "")).strip(),
                "色粉類別": selected_row.get("色粉類別", "").strip(),
            }
        
            st.session_state["new_order"] = order
            st.session_state["show_confirm_panel"] = True
        
            # 建立 recipe_row_cache
            st.session_state["recipe_row_cache"] = {k.strip(): ("" if v is None or pd.isna(v) else str(v)) for k, v in selected_row.items()}
        
            # 顯示選取訊息
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
                key="search_add_form_selected_recipe_tab1"
            )
            if selected_label == "請選擇":
                selected_row = None
            else:
                selected_row = option_map.get(selected_label)
        
        # === 處理「新增」按鈕 ===
        if add_btn:
            if selected_label is None or selected_label == "請選擇":
                st.warning("請先選擇有效配方")
            else:
                if selected_row.get("狀態") == "停用":
                    st.warning("⚠️ 此配方已停用，請勿使用")
                else:
                    order = {}
    
                    df_all_orders = st.session_state.df_order.copy()
                    today_str = datetime.now().strftime("%Y%m%d")
                    count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
                    new_id = f"{today_str}-{count_today + 1:03}"
    
                    main_recipe_code = selected_row.get("配方編號", "").strip()
                    df_recipe["配方類別"] = df_recipe["配方類別"].astype(str).str.strip()
                    df_recipe["原始配方"] = df_recipe["原始配方"].astype(str).str.strip()
                    附加配方 = df_recipe[
                        (df_recipe["配方類別"] == "附加配方") &
                        (df_recipe["原始配方"] == main_recipe_code)
                    ]
    
                    all_colorants = []
                    for i in range(1, 9):
                        id_key = f"色粉編號{i}"
                        wt_key = f"色粉重量{i}"
                        id_val = selected_row.get(id_key, "")
                        wt_val = selected_row.get(wt_key, "")
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
                    st.rerun()

        # ===== 顯示「新增後欄位填寫區塊」（必須在按鈕處理之外）=====
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
        
        show_confirm_panel = st.session_state.get("show_confirm_panel", False)

    # ===== 將配方欄位帶入 order =====
    for field in ["合計類別", "備註", "重要提醒"]:
        if field in recipe_row:
            order[field] = recipe_row.get(field, "")

    # ===== 處理附加配方 =====
    if recipe_id:

        # 📌 附加配方只查詢一次
        def get_additional_recipes(df, main_recipe_code):
            df = df.copy()
            df["配方類別"] = df["配方類別"].astype(str).str.strip()
            df["原始配方"] = df["原始配方"].astype(str).str.strip()
            main_code = str(main_recipe_code).strip()
            return df[
                (df["配方類別"] == "附加配方") &
                (df["原始配方"] == main_code)
            ]

        additional_recipes = get_additional_recipes(df_recipe, recipe_id)

        if additional_recipes.empty:
            order["附加配方"] = []

        else:
            st.markdown(
                f"<span style='font-size:14px; font-weight:bold;'>附加配方清單（共 {len(additional_recipes)} 筆）</span>",
                unsafe_allow_html=True
            )

            order["附加配方"] = [
                {
                    k.strip(): (
                        "" if v is None or pd.isna(v) else str(v)
                    )
                    for k, v in row.to_dict().items()
                }
                for _, row in additional_recipes.iterrows()
            ]

    else:
        order["附加配方"] = []
    
    st.session_state.new_order = order
    
    # ===== 顯示詳情填寫表單 =====
    if show_confirm_panel:
        
        # ✅【關鍵】第一次進入時，從配方帶入預設值
        if "recipe_init_done" not in st.session_state:
            order["備註"] = recipe_row.get("備註", "")
            order["重要提醒"] = recipe_row.get("重要提醒", "")
            order["合計類別"] = recipe_row.get("合計類別", "")
            st.session_state.recipe_init_done = True
            st.markdown("---")
            st.markdown("<span style='font-size:20px; font-weight:bold;'>新增生產單詳情填寫</span>", unsafe_allow_html=True)
            
        with st.form("order_detail_form_tab1"):
            c1, c2, c3, c4 = st.columns(4)
            c1.text_input("生產單號", value=order.get("生產單號", ""), disabled=True, key="form_order_no_tab1")
            c2.text_input("配方編號", value=order.get("配方編號", ""), disabled=True, key="form_recipe_id_tab1")
            c3.text_input("客戶編號", value=recipe_row.get("客戶編號", ""), disabled=True, key="form_cust_id_tab1")
            c4.text_input("客戶名稱", value=order.get("客戶名稱", ""), disabled=True, key="form_cust_name_tab1")
            
            c5, c6, c7, c8 = st.columns(4)
            c5.text_input("計量單位", value=recipe_row.get("計量單位", "kg"), disabled=True, key="form_unit_tab1")
            color = c6.text_input("顏色", value=order.get("顏色", ""), key="form_color_tab1")
            pantone = c7.text_input("Pantone 色號", value=order.get("Pantone 色號", recipe_row.get("Pantone色號", "")), key="form_pantone_tab1")
            raw_material = c8.text_input("原料", value=order.get("原料", ""), key="form_raw_material_tab1")
            
            # ===== 重要提醒 / 合計類別 / 比例（同一橫列）=====
            col_note, col_total, col_ratio = st.columns([0.5, 0.25, 0.25])
            
            with col_note:
                important_note = st.text_input(
                    "重要提醒",
                    value=order.get("重要提醒", ""),
                    key="form_important_note_tab1"
                )
            
            with col_total:
                total_category = st.text_input(
                    "合計類別",
                    value=order.get("合計類別", recipe_row.get("合計類別", "")),
                    disabled=True,
                    key="form_total_category_tab1"
                )
            
            with col_ratio:
                r1 = recipe_row.get("比例1", "")
                r2 = recipe_row.get("比例2", "")
                r3 = recipe_row.get("比例3", "")
            
                ratio_text = ""
                if r1 or r2 or r3:
                    ratio_text = ":".join([p for p in [r1, r2, r3] if p]) + " g/kg"
            
                st.text_input(
                    "比例",
                    value=ratio_text,
                    disabled=True,
                    key="form_ratio_tab1"
                )
            
            # ===== 備註（整行橫條）=====
            remark = st.text_area(
                "備註",
                value=order.get("備註", ""),
                height=100,
                key="form_remark_tab1"
            )
            
            st.markdown("**包裝重量與份數**")
            w_cols = st.columns(4)
            c_cols = st.columns(4)
            for i in range(1, 5):
                w_cols[i - 1].text_input(f"包裝重量{i}", value=order.get(f"包裝重量{i}", ""), key=f"form_weight{i}_tab1")
                c_cols[i - 1].text_input(f"包裝份數{i}", value=order.get(f"包裝份數{i}", ""), key=f"form_count{i}_tab1")
            
            st.markdown("###### 色粉用量（編號與重量）")
            id_col, wt_col = st.columns(2)
            for i in range(1, 9):
                color_id = recipe_row.get(f"色粉編號{i}", "").strip()
                color_wt = recipe_row.get(f"色粉重量{i}", "").strip()
                if color_id or color_wt:
                    id_col.text_input(f"色粉編號{i}", value=color_id, disabled=True, key=f"form_main_color_id_{i}_tab1")
                    wt_col.text_input(f"色粉重量{i}", value=color_wt, disabled=True, key=f"form_main_color_weight_{i}_tab1")
            
            additional_recipes = order.get("附加配方", [])
            if additional_recipes:
                st.markdown("###### 附加配方色粉用量（編號與重量）")
                for idx, r in enumerate(additional_recipes, 1):
                    st.markdown(f"附加配方 {idx}")
                    col1, col2 = st.columns(2)
                    for i in range(1, 9):
                        color_id = r.get(f"色粉編號{i}", "").strip()
                        color_wt = r.get(f"色粉重量{i}", "").strip()
                        if color_id or color_wt:
                            col1.text_input(f"附加色粉編號_{idx}_{i}", value=color_id, disabled=True, key=f"form_add_color_id_{idx}_{i}_tab1")
                            col2.text_input(f"附加色粉重量_{idx}_{i}", value=color_wt, disabled=True, key=f"form_add_color_wt_{idx}_{i}_tab1")
            
            col_submit1, col_submit2 = st.columns([1, 1])
            with col_submit1:
                submitted = st.form_submit_button("💾 僅儲存生產單")
            
            is_colorant = (recipe_row.get("色粉類別", "").strip() == "色母")
            with col_submit2:
                if is_colorant:
                    continue_to_oem = st.form_submit_button("✅ 儲存並轉代工管理")
                else:
                    continue_to_oem = False
            
            if submitted or continue_to_oem:
            
                # ===== 檢查是否至少有一個包裝 =====
                all_empty = True
                for i in range(1, 5):
                    weight = st.session_state.get(f"form_weight{i}_tab1", "").strip()
                    count  = st.session_state.get(f"form_count{i}_tab1", "").strip()
                    if weight or count:
                        all_empty = False
                        break
            
                if all_empty:
                    st.warning("⚠️ 請至少填寫一個包裝重量或包裝份數，才能儲存生產單！")
                    st.stop()
            
                # ===== 寫回 order（你原本的邏輯）=====
                order["顏色"] = st.session_state.form_color_tab1
                order["Pantone 色號"] = st.session_state.form_pantone_tab1
                order["料"] = st.session_state.form_raw_material_tab1
                order["備註"] = st.session_state.form_remark_tab1
                order["重要提醒"] = st.session_state.form_important_note_tab1
                order["合計類別"] = st.session_state.form_total_category_tab1
            
                order["比例1"] = recipe_row.get("比例1", "")
                order["比例2"] = recipe_row.get("比例2", "")
                order["比例3"] = recipe_row.get("比例3", "")
            
                for i in range(1, 5):
                    order[f"包裝重量{i}"] = st.session_state.get(f"form_weight{i}_tab1", "").strip()
                    order[f"包裝份數{i}"] = st.session_state.get(f"form_count{i}_tab1", "").strip()
            
                # =================================================
                # 🔒 Step 1：建立本次儲存內容快照（防重複）
                # =================================================
                current_snapshot = {
                    "顏色": order["顏色"],
                    "Pantone 色號": order["Pantone 色號"],
                    "原料": order["料"],
                    "備註": order["備註"],
                    "重要提醒": order["重要提醒"],
                    "合計類別": order["合計類別"],
                    "包裝": [
                        (
                            order.get(f"包裝重量{i}", ""),
                            order.get(f"包裝份數{i}", "")
                        )
                        for i in range(1, 5)
                    ]
                }
            
                # =================================================
                # 🛑 Step 2：若與上次儲存完全相同 → 阻止
                # =================================================
                last_snapshot = st.session_state.get("last_saved_order_snapshot")
                if last_snapshot == current_snapshot:
                    st.warning("⚠️ 此生產單內容未變更，已避免重複儲存")
                    st.stop()
            
                # ===== 你原本的色粉 / 淨重計算 =====
                raw_net_weight = recipe_row.get("淨重", 0)
                try:
                    net_weight = float(raw_net_weight)
                except:
                    net_weight = 0.0
            
                color_weight_list = []
                for i in range(1, 5):
                    w_str = st.session_state.get(f"form_weight{i}_tab1", "").strip()
                    weight = float(w_str) if w_str else 0.0
                    if weight > 0:
                        color_weight_list.append({
                            "項次": i,
                            "重量": weight,
                            "結果": net_weight * weight
                        })
            
                order["色粉合計清單"] = color_weight_list
                order["色粉合計類別"] = recipe_row.get("合計類別", "")
            
                # =================================================
                # ✅ Step 3：儲存成功後，記住這次內容
                # =================================================
                st.session_state.last_saved_order_snapshot = current_snapshot
            
                # 低庫存檢查
                # 📌 4️⃣ 低庫存檢查（統一與庫存區邏輯）
                # ============================================================

                last_stock = st.session_state.get("last_final_stock", {}).copy()
                alerts = []

                # 取得本張生產單的主配方與附加配方
                all_recipes_for_check = [recipe_row]
                if additional_recipes:
                    all_recipes_for_check.extend(additional_recipes)

                for rec in all_recipes_for_check:
                    for i in range(1, 9):
                        pid = str(rec.get(f"色粉編號{i}", "")).strip()
                        if not pid:
                            continue

                        # 排除尾碼 01 / 001 / 0001
                        if pid.endswith(("01", "001", "0001")):
                            continue

                        # 若該色粉沒有初始庫存，略過
                        if pid not in last_stock:
                            continue

                        # 取得色粉重量（每 kg 產品用量）
                        try:
                            ratio_g = float(rec.get(f"色粉重量{i}", 0))
                        except:
                            ratio_g = 0.0

                        # 計算用量：比例 * 包裝重量 * 包裝份數
                        total_used_g = 0
                        for j in range(1, 5):
                            try:
                                w_val = float(st.session_state.get(f"form_weight{j}", 0) or 0)
                                n_val = float(st.session_state.get(f"form_count{j}", 0) or 0)
                                total_used_g += ratio_g * w_val * n_val
                            except:
                                pass

                        # 扣庫存
                        last_stock_before = last_stock.get(pid, 0)
                        new_stock = last_stock_before - total_used_g
                        last_stock[pid] = new_stock

                        # 分級提醒
                        final_kg = new_stock / 1000
                        if final_kg < 0:
                            alerts.append(f"🔴 {pid} → 庫存不足（需 {abs(final_kg):.2f} kg）")
                        elif final_kg < 0.5:
                            alerts.append(f"🔴 {pid} → 僅剩 {final_kg:.2f} kg（嚴重不足）")
                        elif final_kg < 1:
                            alerts.append(f"🟠 {pid} → 僅剩 {final_kg:.2f} kg（請盡快補料）")
                        elif final_kg < 3:
                            alerts.append(f"🟡 {pid} → 僅剩 {final_kg:.2f} kg（偏低）")

                if alerts:
                    st.warning("💀 以下色粉庫存過低：\n" + "\n".join(alerts))

                st.session_state["last_final_stock"] = last_stock

                order_no = str(order.get("生產單號", "")).strip()

                try:
                    sheet_data = get_cached_sheet_df("生產單").to_dict("records")
                    rows_to_delete = []
                    
                    for idx, row in enumerate(sheet_data, start=2):
                        if str(row.get("生產單號", "")).strip() == order_no:
                            rows_to_delete.append(idx)
                
                    for r in reversed(rows_to_delete):
                        ws_order.delete_rows(r)
                
                except Exception as e:
                    st.error(f"❌ 刪除舊生產單失敗：{e}")
                
                try:
                    df_order = df_order[df_order["生產單號"].astype(str) != order_no]
                except:
                    pass
                
                try:
                    header = [col for col in df_order.columns if col and str(col).strip() != ""]
                    row_data = [str(order.get(col, "")).strip() if order.get(col) is not None else "" for col in header]
                    ws_order.append_row(row_data)
                    df_new = pd.DataFrame([order], columns=df_order.columns)
                    df_order = pd.concat([df_order, df_new], ignore_index=True)
                    df_order.to_csv("data/order.csv", index=False, encoding="utf-8-sig")
                    st.session_state.df_order = df_order
                    st.session_state.new_order_saved = True
                    st.success(f"✅ 生產單 {order['生產單號']} 已存！")
                    # ✅【防止重複儲存】只有真的寫入成功才記住
                    st.session_state.last_saved_order_snapshot = current_snapshot
                
                    if continue_to_oem:
                        oem_id = f"OEM{order['生產單號']}"
                
                        oem_qty = 0.0
                        for i in range(1, 5):
                            try:
                                w = float(order.get(f"包裝重量{i}", 0) or 0)
                                n = float(order.get(f"包裝份數{i}", 0) or 0)
                                oem_qty += w * 100 * n
                            except:
                                pass
                
                        try:
                            ws_oem = get_cached_worksheet("代工管理")
                        except:
                            ws_oem = spreadsheet.add_worksheet("代工管理", rows=100, cols=20)
                            ws_oem.append_row(["代工單號", "生產單號", "配方編號", "客戶名稱", 
                                                               "代工數量", "代工廠商", "備註", "狀態", "建立時間"])
                
                        oem_row = [
                            oem_id,
                            order['生產單號'],
                            order.get('配方編號', ''),
                            order.get('客戶名稱', ''),
                            oem_qty,
                            "",
                            "",
                            "🏭 在廠內",  # ⭐ 預設狀態
                            (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
                        ]
                        ws_oem.append_row(oem_row)
                
                        oem_msg = f"🎉 已建立代工單號：{oem_id}（{oem_qty} kg）\n💡 請至「代工管理」分頁編輯"
                        st.toast(oem_msg)
            
                except Exception as e:
                    st.error(f"❌ 寫入失敗：{e}")
                
        # 產生列印 HTML 按鈕
        show_ids = st.checkbox("列印時顯示附加配方編號", value=False, key="show_ids_tab1")
        print_html = generate_print_page_content(
            order=order,
            recipe_row=recipe_row,
            additional_recipe_rows=order.get("附加配方", []),
            show_additional_ids=show_ids
        )

        def mark_html_downloaded():
            st.session_state.downloaded_html_tab1 = True
                
        col1, col2, col3 = st.columns([3,1,3])
        with col1:           
            # ---------- 產生安全檔名 ----------
            raw_order_no = str(order.get("生產單號", "未命名")).strip()
            raw_recipe_no = str(recipe_row.get("配方編號", "無配方")).strip()
            
            def make_safe_filename(text):
                # 移除 Windows 不允許的字元
                text = re.sub(r'[\\/:*?"<>|]', '-', text)
                # 將多餘空白轉成單一底線
                text = re.sub(r'\s+', '_', text)
                return text
            
            safe_order_no = make_safe_filename(raw_order_no)
            safe_recipe_no = make_safe_filename(raw_recipe_no)
            
            file_name = f"{safe_order_no}_{safe_recipe_no}_列印.html"
            
            # ---------- 動態按鈕文字 ----------
            download_label = (
                "✅ 已下載 A5 HTML"
                if st.session_state.get("downloaded_html_tab1", False)
                else "📥 下載 A5 HTML"
            )
            
            # ---------- 下載按鈕 ----------
            st.download_button(
                label=download_label,
                data=print_html.encode("utf-8"),
                file_name=file_name,
                mime="text/html",
                key="download_html_tab1",
                disabled=not st.session_state.get("new_order_saved", False),
                on_click=mark_html_downloaded
            )
                
        with col3:
            if st.button("🔙 返回", key="back_button_tab1"):
                st.session_state.new_order = None
                st.session_state.show_confirm_panel = False
                st.session_state.new_order_saved = False
                st.session_state.downloaded_html_tab1 = False
                st.session_state.pop("recipe_init_done", None)
                st.rerun()
                        
    # ============================================================
    # Tab 2: 生產單記錄表（✅ 補上遺漏的預覽功能）
    # ============================================================
    with tab2:
            
        search_order = st.text_input(
            "搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)",
            key="search_order_input_tab2",
            value=""
        )
    
        if "order_page_tab2" not in st.session_state:
            st.session_state.order_page_tab2 = 1
    
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
    
        df_filtered["建立時間"] = pd.to_datetime(df_filtered["建立時間"], errors="coerce")
        df_filtered = df_filtered.sort_values(by="建立時間", ascending=False)
    
        if "selectbox_order_limit_tab2" not in st.session_state:
            st.session_state.selectbox_order_limit_tab2 = 5
    
        total_rows = len(df_filtered)
        limit = st.session_state.selectbox_order_limit_tab2
        total_pages = max((total_rows - 1) // limit + 1, 1)
    
        if st.session_state.order_page_tab2 > total_pages:
            st.session_state.order_page_tab2 = total_pages
    
        start_idx = (st.session_state.order_page_tab2 - 1) * limit
        end_idx = start_idx + limit
        page_data = df_filtered.iloc[start_idx:end_idx].copy()
    
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
    
            except Exception:
                return ""
    
        if not page_data.empty:
            page_data["出貨數量"] = page_data.apply(calculate_shipment, axis=1)
    
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
    
        cols_page = st.columns([2, 2, 2, 2, 2])
    
        with cols_page[0]:
            if st.button("🏠首頁", key="first_page_tab2"):
                st.session_state.order_page_tab2 = 1
                st.rerun()
    
        with cols_page[1]:
            if st.button("🔼上頁", key="prev_page_tab2") and st.session_state.order_page_tab2 > 1:
                st.session_state.order_page_tab2 -= 1
                st.rerun()
    
        with cols_page[2]:
            if st.button("🔽下頁", key="next_page_tab2") and st.session_state.order_page_tab2 < total_pages:
                st.session_state.order_page_tab2 += 1
                st.rerun()
    
        with cols_page[3]:
            jump_page = st.number_input(
                "",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.order_page_tab2,
                key="jump_page_tab2",
                label_visibility="collapsed"
            )
            if jump_page != st.session_state.order_page_tab2:
                st.session_state.order_page_tab2 = jump_page
                st.rerun()
    
        with cols_page[4]:
            options_list = [5, 10, 20, 50, 75, 100]
            current_limit = st.session_state.get("selectbox_order_limit_tab2", 5)
            if current_limit not in options_list:
                current_limit = 5
    
            new_limit = st.selectbox(
                label=" ",
                options=options_list,
                index=options_list.index(current_limit),
                key="selectbox_order_limit_tab2_widget",
                label_visibility="collapsed"
            )
    
            if new_limit != st.session_state.selectbox_order_limit_tab2:
                st.session_state.selectbox_order_limit_tab2 = new_limit
                st.session_state.order_page_tab2 = 1
                st.rerun()
    
        st.caption(f"頁碼 {st.session_state.order_page_tab2} / {total_pages}，總筆數 {total_rows}")

    # ============================================================
    # Tab 3: 生產單預覽/修改/刪除
    # ============================================================
    with tab3:
    
        # ===== 修改完成通知（一定要在 Tab 3 最上方）=====
        if st.session_state.get("edit_success_message"):
            st.toast(st.session_state.edit_success_message, icon="🎉")
            del st.session_state.edit_success_message
    
        def delete_order_by_id(ws, order_id):
            all_values = get_cached_sheet_df(ws.title).to_dict("records")
            df = pd.DataFrame(all_values)
    
            if df.empty:
                return False
    
            target_idx = df.index[df["生產單號"] == order_id].tolist()
            if not target_idx:
                return False
    
            row_number = target_idx[0] + 2
            ws.delete_rows(row_number)
            return True
    
        # ===== 刪除代工單函式 =====
        def delete_oem_by_order_id(ws_oem, order_id):
            all_values = get_cached_sheet_df("代工管理").to_dict("records")
            df = pd.DataFrame(all_values)
            if df.empty or "生產單號" not in df.columns:
                return 0
            target_idxs = df.index[df["生產單號"].astype(str) == str(order_id)].tolist()
            for idx in sorted(target_idxs, reverse=True):
                ws_oem.delete_rows(idx + 2)
            return len(target_idxs)
    
        # ===== 🔥 用 Form 包起來（搜尋 + 日期 + 選擇生產單）=====
        with st.form("search_order_form_tab3"):
            
            # 📅 日期區間選擇（新增）
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                search_date_start = st.date_input(
                    "生產日期（起）",
                    value=None,
                    key="search_date_start_tab3"
                )
            with col_date2:
                search_date_end = st.date_input(
                    "生產日期（迄）",
                    value=None,
                    key="search_date_end_tab3"
                )
            
            # 🔍 搜尋關鍵字
            search_order_tab3 = st.text_input(
                "搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)",
                key="search_order_input_tab3",
                value=""
            )
            
            # ✅ Form 提交按鈕
            submit_search = st.form_submit_button("🔍 搜尋")
    
        # ===== 只有按下搜尋才執行篩選 =====
        if submit_search or st.session_state.get("last_search_tab3_done", False):
            
            # 標記已搜尋過（避免 rerun 後消失）
            st.session_state.last_search_tab3_done = True
            
            # 📌 1. 關鍵字篩選
            if search_order_tab3.strip():
                mask = (
                    df_order["生產單號"].astype(str).str.contains(search_order_tab3, case=False, na=False) |
                    df_order["配方編號"].astype(str).str.contains(search_order_tab3, case=False, na=False) |
                    df_order["客戶名稱"].astype(str).str.contains(search_order_tab3, case=False, na=False) |
                    df_order["顏色"].astype(str).str.contains(search_order_tab3, case=False, na=False)
                )
                df_filtered_tab3 = df_order[mask].copy()
            else:
                df_filtered_tab3 = df_order.copy()
    
            # 📌 2. 日期篩選（新增）
            if "生產日期" in df_filtered_tab3.columns:
                df_filtered_tab3["生產日期"] = pd.to_datetime(df_filtered_tab3["生產日期"], errors="coerce")
                
                # 起始日期篩選
                if search_date_start:
                    df_filtered_tab3 = df_filtered_tab3[
                        df_filtered_tab3["生產日期"] >= pd.to_datetime(search_date_start)
                    ]
                
                # 結束日期篩選
                if search_date_end:
                    df_filtered_tab3 = df_filtered_tab3[
                        df_filtered_tab3["生產日期"] <= pd.to_datetime(search_date_end)
                    ]
    
            # 📌 3. 建立時間排序
            df_filtered_tab3["建立時間"] = pd.to_datetime(df_filtered_tab3["建立時間"], errors="coerce")
            df_filtered_tab3 = df_filtered_tab3.sort_values(by="建立時間", ascending=False)
    
            # ===== 📊 顯示搜尋結果表格（新增回來）=====
            if not df_filtered_tab3.empty:
                # 計算出貨數量函式
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
    
                    except Exception:
                        return ""
    
                # 新增出貨數量欄位
                df_display_tab3 = df_filtered_tab3.copy()
                df_display_tab3["出貨數量"] = df_display_tab3.apply(calculate_shipment, axis=1)
    
                # ===== 分頁控制：同一橫列，極簡版 =====
                col_ps, col_pg, col_info = st.columns([1.5, 1.5, 7])
                
                # 1️⃣ 每頁筆數
                with col_ps:
                    page_size = st.selectbox(
                        "",  # 不顯示 label
                        [5, 10, 20, 50, 100],  # 可調整，預設 5 筆
                        index=0,
                        key="tab3_page_size",
                        label_visibility="collapsed"
                    )
                
                # 2️⃣ 頁碼
                with col_pg:
                    page = st.number_input(
                        "",  # 不顯示 label
                        min_value=1,
                        max_value=max(1, (len(df_display_tab3)-1)//page_size + 1),
                        value=st.session_state.get("tab3_page_number", 1),
                        step=1,
                        key="tab3_page_number",
                        label_visibility="collapsed"
                    )
                
                # 3️⃣ 顯示總筆數與總頁數
                with col_info:
                    st.markdown(
                        f"<p style='font-size:13px; color:#9aa0a6; margin-top:0px;'>共 {len(df_display_tab3)} 筆 · {max(1, (len(df_display_tab3)-1)//page_size + 1)} 頁</p>",
                        unsafe_allow_html=True
                    )
                
                # ===== 計算分頁索引，安全處理 =====
                start_idx = min((page-1)*page_size, len(df_display_tab3))
                end_idx = min(start_idx + page_size, len(df_display_tab3))
                df_page = df_display_tab3.iloc[start_idx:end_idx]
                
                # ===== 顯示表格 =====
                if not df_page.empty and existing_cols:
                    st.dataframe(
                        df_page[existing_cols].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("⚠️ 沒有符合條件的生產單")
    
            # 📌 4. 下拉選單
            if not df_filtered_tab3.empty:
                df_filtered_tab3['配方編號'] = df_filtered_tab3['配方編號'].fillna('').astype(str)
    
                st.markdown("---")  # 分隔線
                st.markdown("**🔽 選擇生產單進行預覽/修改/刪除**")
    
                selected_index = st.selectbox(
                    "選擇生產單",
                    options=df_filtered_tab3.index,
                    format_func=lambda i: f"{df_filtered_tab3.at[i, '生產單號']} | {df_filtered_tab3.at[i, '配方編號']} | {df_filtered_tab3.at[i, '顏色']} | {df_filtered_tab3.at[i, '客戶名稱']}",
                    key="select_order_code_tab3",
                    index=0
                )
    
                selected_order = df_filtered_tab3.loc[selected_index]
                selected_code_edit = selected_order["生產單號"]
            else:
                selected_index, selected_order, selected_code_edit = None, None, None
    
        else:
            # st.info("💡 請輸入搜尋條件後按「🔍 搜尋」")
            selected_order = None
    
        def generate_order_preview_text_tab3(order, recipe_row, show_additional_ids=True):
            html_text = generate_production_order_print(
                order,
                recipe_row,
                additional_recipe_rows=None,
                show_additional_ids=show_additional_ids
            )
    
            main_code = str(order.get("配方編號", "")).strip()
            if main_code:
                additional_recipe_rows = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"].astype(str).str.strip() == main_code)
                ].to_dict("records")
            else:
                additional_recipe_rows = []
    
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
    
            def fmt_num_colorant(x: float) -> str:
                if abs(x - int(x)) < 1e-9:
                    return str(int(x))
                return f"{x:g}"
    
            # ===== 備註顯示（區分來源） =====
            order_note = str(order.get("備註", "")).strip()
            if order_note:
                html_text += f"【生產單備註】{order_note}<br><br>"
            
            category_colorant = str(recipe_row.get("色粉類別","")).strip()
            if category_colorant == "色母":
                pack_weights_display = [float(order.get(f"包裝重量{i}",0) or 0) for i in range(1,5)]
                pack_counts_display = [float(order.get(f"包裝份數{i}",0) or 0) for i in range(1,5)]
    
                pack_line = []
                for w, c in zip(pack_weights_display, pack_counts_display):
                    if w > 0 and c > 0:
                        val = int(w * 100)
                        pack_line.append(f"{val}K × {int(c)}")
    
                if pack_line:
                    html_text += " " * 14 + "  ".join(pack_line) + "<br>"
    
                colorant_weights = [float(recipe_row.get(f"色粉重量{i}",0) or 0) for i in range(1,9)]
                powder_ids = [str(recipe_row.get(f"色粉編號{i}","") or "").strip() for i in range(1,9)]
    
                number_col_width = 12
                for pid, wgt in zip(powder_ids, colorant_weights):
                    if pid and wgt > 0:
                        line = pid.ljust(6)
                        for w in pack_weights_display:
                            if w > 0:
                                val = wgt * w
                                line += fmt_num_colorant(val).rjust(number_col_width)
                        html_text += line + "<br>"
    
                total_colorant = float(recipe_row.get("淨重",0) or 0) - sum(colorant_weights)
                total_line_colorant = "料".ljust(12)
    
                col_widths = [5, 12, 12, 12]
    
                for idx, w in enumerate(pack_weights_display):
                    if w > 0:
                        val = total_colorant * w
                        width = col_widths[idx] if idx < len(col_widths) else 12
                        total_line_colorant += fmt_num_colorant(val).rjust(width)
    
                html_text += total_line_colorant + "<br>"
    
            text_with_newlines = html_text.replace("<br>", "\n")
            plain_text = re.sub(r"<.*?>", "", text_with_newlines)
            return "```\n" + plain_text.strip() + "\n```"
    
        if selected_order is not None:
            order_dict = selected_order.to_dict()
            order_dict = {k: "" if v is None or pd.isna(v) else str(v) for k, v in order_dict.items()}
    
            recipe_rows = df_recipe[df_recipe["配方編號"] == order_dict.get("配方編號", "")]
            recipe_row = recipe_rows.iloc[0].to_dict() if not recipe_rows.empty else {}
    
            show_ids_key = f"show_ids_checkbox_tab3_{selected_order['生產單號']}"
                        
            st.markdown("""
            <style>
            div[data-testid="stCheckbox"] label p {
                color: #888 !important;
                font-size: 0.9rem !important;
            }
            div[data-testid="stCheckbox"] input[type="checkbox"] {
                accent-color: #aaa !important;
            }
            </style>
            """, unsafe_allow_html=True)
                        
            show_ids = st.checkbox(
                "預覽時顯示附加配方編號",
                value=True,          # ✅ 只在第一次建立時當預設值
                key=show_ids_key     # ✅ 之後狀態由 Streamlit 自己記
            )
    
            preview_text = generate_order_preview_text_tab3(order_dict, recipe_row, show_additional_ids=show_ids)
    
            cols_preview_order = st.columns([6, 1.2])
            with cols_preview_order[0]:
                with st.expander("👀 生產單預覽", expanded=False):
                    st.markdown(preview_text, unsafe_allow_html=True)
    
            with cols_preview_order[1]:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ ", key="edit_order_btn_tab3"):
                        st.session_state["show_edit_panel"] = True
                        st.session_state["editing_order"] = order_dict
                with col_btn2:
                    if st.button("🗑️ ", key="delete_order_btn_tab3"):
                        st.session_state["delete_target_id"] = selected_code_edit
                        st.session_state["show_delete_confirm"] = True
    
            if st.session_state.get("show_delete_confirm", False):
                order_id = st.session_state.get("delete_target_id")
                order_label = order_id or "未指定生產單"
    
                st.warning(f"⚠️ 確定要刪除生產單？\n\n👉 {order_label}")
    
                c1, c2 = st.columns(2)
    
                if c1.button("✅ 是，刪除", key="confirm_delete_yes_tab3"):
                    if not order_id:
                        st.error("❌ 未指定要刪除的生產單 ID")
                    else:
                        order_id_str = str(order_id)
                        try:
                            # ===== 先刪代工單 =====
                            deleted_oem_count = 0
                            try:
                                ws_oem = get_cached_worksheet("代工管理")
                                deleted_oem_count = delete_oem_by_order_id(ws_oem, order_id_str)
                            except:
                                ws_oem = None
                
                            if deleted_oem_count > 0:
                                st.toast(f"🧹 已自動刪除 {deleted_oem_count} 筆對應代工單")
                
                            # ===== 再刪生產單 =====
                            deleted = delete_order_by_id(ws_order, order_id_str)
                
                            if deleted:
                                st.success(f"✅ 已刪除 {order_label}")
                            else:
                                st.error("❌ 找不到該生產單，刪除失敗")
                
                        except Exception as e:
                            st.error(f"❌ 刪除時發生錯誤：{e}")
                
                    st.session_state["show_delete_confirm"] = False
                    st.rerun()
           
        # ====== 修改面板（⚠️ 一定要在外層） ======
        if st.session_state.get("show_edit_panel") and st.session_state.get("editing_order"):
        
            st.markdown("---")
            st.markdown(
                f"<p style='font-size:18px; font-weight:bold; color:#fceca6;'>✏️ 修改生產單 {st.session_state.editing_order['生產單號']}</p>",
                unsafe_allow_html=True
            )
        
            st.caption("⚠️：『儲存修改』僅同步更新 Google Sheets 記錄；若需列印需先刪除原生產單後並重新建立新生產單。")
        
            order_no = st.session_state.editing_order["生產單號"]
        
            order_row = df_order[df_order["生產單號"] == order_no]
            if order_row.empty:
                st.warning(f"找不到生產單號：{order_no}")
                st.stop()
        
            order_dict = order_row.iloc[0].to_dict()
        
            recipe_id = order_dict.get("配方編號", "")
            recipe_rows = df_recipe[df_recipe["配方編號"] == recipe_id]
            if recipe_rows.empty:
                st.warning(f"找不到配方編號：{recipe_id}")
                st.stop()
        
            recipe_row = recipe_rows.iloc[0].to_dict()
        
            col_cust, col_color = st.columns(2)
            with col_cust:
                new_customer = st.text_input(
                    "客戶名稱",
                    value=order_dict.get("客戶名稱", ""),
                    key="edit_customer_name_tab3"
                )
            with col_color:
                new_color = st.text_input(
                    "顏色",
                    value=order_dict.get("顏色", ""),
                    key="edit_color_tab3"
                )
        
            pack_weights_cols = st.columns(4)
            new_packing_weights = []
            for i in range(1, 5):
                weight = pack_weights_cols[i - 1].text_input(
                    f"包裝重量{i}",
                    value=order_dict.get(f"包裝重量{i}", ""),
                    key=f"edit_packing_weight_tab3_{i}"
                )
                new_packing_weights.append(weight)
        
            pack_counts_cols = st.columns(4)
            new_packing_counts = []
            for i in range(1, 5):
                count = pack_counts_cols[i - 1].text_input(
                    f"包裝份數{i}",
                    value=order_dict.get(f"包裝份數{i}", ""),
                    key=f"edit_packing_count_tab3_{i}"
                )
                new_packing_counts.append(count)
        
            new_remark = st.text_area(
                "備註",
                value=order_dict.get("備註", ""),
                key="edit_remark_tab3"
            )
        
            cols_edit = st.columns([1, 1, 1])
        
            with cols_edit[0]:
                if st.button("💾 儲存修改", key="save_edit_button_tab3"):
                    
                    # ===== 更新 order_dict =====
                    order_dict["客戶名稱"] = new_customer
                    order_dict["顏色"] = new_color
                    order_dict["備註"] = new_remark
                    
                    for i in range(1, 5):
                        order_dict[f"包裝重量{i}"] = new_packing_weights[i-1]
                        order_dict[f"包裝份數{i}"] = new_packing_counts[i-1]
                    
                    # ===== 寫回 Google Sheet（簡化版）=====
                    try:
                        with st.spinner("正在儲存修改..."):
                            # 1️⃣ 找到該生產單在 Sheet 中的位置
                            all_values = get_cached_sheet_values("生產單")
                            header = all_values[0]
                            
                            target_row_idx = None
                            for idx, row in enumerate(all_values[1:], start=2):
                                if row[0] == order_no:
                                    target_row_idx = idx
                                    break
                            
                            if target_row_idx is None:
                                st.error(f"❌ 找不到生產單號 {order_no} 在 Google Sheet 中")
                                st.stop()
                            
                            # 2️⃣ 準備要更新的資料（按欄位順序）
                            updated_row = []
                            for col_name in header:
                                updated_row.append(str(order_dict.get(col_name, "")))
                            
                            # 3️⃣ 使用 gspread 內建函式轉換欄位範圍
                            import gspread.utils as utils
                            end_col = utils.rowcol_to_a1(target_row_idx, len(header)).replace(str(target_row_idx), "")
                            range_name = f"A{target_row_idx}:{end_col}{target_row_idx}"
                            
                            # 4️⃣ 一次更新整列
                            ws_order.update(range_name, [updated_row])
                            
                            # 5️⃣ 同步更新本地 df_order
                            mask = df_order["生產單號"] == order_no
                            for key, val in order_dict.items():
                                if key in df_order.columns:
                                    df_order.loc[mask, key] = val
                            
                            st.session_state.df_order = df_order
                            st.session_state.edit_success_message = f"✅ 生產單 {order_no} 修改完成"
                        
                    except Exception as e:
                        st.error(f"❌ 儲存失敗：{e}")
                        import traceback
                        st.code(traceback.format_exc())
                        st.stop()
                    
                    st.session_state.show_edit_panel = False
                    st.session_state.editing_order = None
                    st.rerun()
        
            with cols_edit[1]:
                if st.button("返回", key="return_button_tab3"):
                    st.session_state.show_edit_panel = False
                    st.session_state.editing_order = None
                    st.rerun()
 
# ======== 代工管理分頁 =========
if menu == "代工管理":

    st.markdown("""
    <style>
    div.block-container { padding-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    import pandas as pd
    from datetime import datetime

    # ================================================================
    # 📌 資料載入：只有第一次進入、或寫入後才重新讀 Google Sheet
    # ================================================================
    def load_oem_data():
        """重新從 Google Sheet 讀取代工三張表，存入 session_state"""
        try:
            ws_oem_ = get_cached_worksheet("代工管理")
            df_oem_ = get_cached_sheet_df("代工管理", force_reload=True)
        except:
            try:
                ws_oem_ = spreadsheet.add_worksheet("代工管理", rows=100, cols=20)
                ws_oem_.append_row(["代工單號", "生產單號", "配方編號", "客戶名稱",
                                    "代工數量", "代工廠商", "備註", "狀態", "建立時間"])
            except:
                pass
            df_oem_ = pd.DataFrame(columns=["代工單號", "生產單號", "配方編號", "客戶名稱",
                                             "代工數量", "代工廠商", "備註", "狀態", "建立時間"])

        try:
            ws_delivery_ = get_cached_worksheet("代工送達記錄")
            df_delivery_ = get_cached_sheet_df("代工送達記錄", force_reload=True)
        except:
            try:
                ws_delivery_ = spreadsheet.add_worksheet("代工送達記錄", rows=100, cols=10)
                ws_delivery_.append_row(["代工單號", "送達日期", "送達數量", "建立時間"])
            except:
                pass
            df_delivery_ = pd.DataFrame(columns=["代工單號", "送達日期", "送達數量", "建立時間"])

        try:
            ws_return_ = get_cached_worksheet("代工載回記錄")
            df_return_ = get_cached_sheet_df("代工載回記錄", force_reload=True)
        except:
            try:
                ws_return_ = spreadsheet.add_worksheet("代工載回記錄", rows=100, cols=10)
                ws_return_.append_row(["代工單號", "載回日期", "載回數量", "建立時間"])
            except:
                pass
            df_return_ = pd.DataFrame(columns=["代工單號", "載回日期", "載回數量", "建立時間"])

        # 補齊必要欄位
        for col in ["代工單號", "狀態"]:
            if col not in df_oem_.columns:
                df_oem_[col] = ""
        if "代工單號" not in df_delivery_.columns:
            df_delivery_["代工單號"] = ""
        if "代工單號" not in df_return_.columns:
            df_return_["代工單號"] = ""

        st.session_state.df_oem      = df_oem_
        st.session_state.df_delivery = df_delivery_
        st.session_state.df_return   = df_return_
        st.session_state.oem_data_loaded = True

    # ── 只有第一次進入時才讀 Sheet，rerun 時直接用 session_state ──
    if not st.session_state.get("oem_data_loaded", False):
        load_oem_data()

    # 取出工作表物件（worksheet 物件本身有 _ws_cache，不耗 quota）
    ws_oem      = get_cached_worksheet("代工管理")
    ws_delivery = get_cached_worksheet("代工送達記錄")
    ws_return   = get_cached_worksheet("代工載回記錄")

    # 取出 DataFrame（全程用 session_state，不重讀 Sheet）
    df_oem      = st.session_state.df_oem
    df_delivery = st.session_state.df_delivery
    df_return   = st.session_state.df_return

    # ================================================================
    # 共用輔助函式
    # ================================================================
    def tw_to_ad(d):
        d = str(d)
        if len(d) == 7:
            return str(int(d[:3]) + 1911) + d[3:]
        return d

    def update_oem_status(oem_no, new_status):
        """更新代工單狀態（單格寫入）並同步 session_state"""
        all_values = get_cached_sheet_values("代工管理")
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == oem_no:
                ws_oem.update_cell(idx, 8, new_status)
                break
        # 同步 session_state
        mask = st.session_state.df_oem["代工單號"] == oem_no
        st.session_state.df_oem.loc[mask, "狀態"] = new_status
        df_oem = st.session_state.df_oem  # 更新本地引用

    # ================================================================
    # Tab 分頁
    # ================================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 新增代工單",
        "✏️ 編輯代工",
        "📥 載回登入",
        "🆗 代工進度表",
        "🚚 代工歷程查詢"
    ])

    # ================================================================
    # Tab 1：新增代工單
    # ================================================================
    if "oem_saved" in st.session_state:
        st.toast(f"代工單 {st.session_state['oem_saved']} 建立成功！ 🎉")
        del st.session_state["oem_saved"]

    with tab1:
        st.markdown(
            '<div style="font-size:12px; color:#3dbcd1;">💡 可直接建立代工單，不需透過生產單轉單</div>',
            unsafe_allow_html=True
        )

        with st.form("create_oem_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_oem_id       = st.text_input("代工單號", placeholder="例如：OEM20251210-001")
                new_production_id = st.text_input("生產單號（選填）", placeholder="若有對應生產單請填寫")
                new_formula_id   = st.text_input("配方編號")
            with col2:
                new_customer  = st.text_input("客戶名稱")
                new_oem_qty   = st.number_input("代工數量 (kg)", min_value=0.0, value=0.0, step=1.0)
                new_vendor    = st.selectbox("代工廠商", ["", "弘旭", "良輝"])

            new_remark     = st.text_area("備註")
            submitted_new  = st.form_submit_button("💾 建立代工單")

        if submitted_new:
            if not new_oem_id.strip():
                st.error("❌ 請輸入代工單號")
            elif new_oem_id in df_oem.get("代工單號", pd.Series([])).values:
                st.error(f"❌ 代工單號 {new_oem_id} 已存在")
            elif new_oem_qty <= 0:
                st.error("❌ 代工數量必須大於 0")
            else:
                new_row_data = [
                    new_oem_id, new_production_id, new_formula_id,
                    new_customer, new_oem_qty, new_vendor, new_remark,
                    "🏭 在廠內",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
                ws_oem.append_row(new_row_data)

                # ✅ 直接更新 session_state，不重讀 Sheet
                new_df_row = pd.DataFrame([{
                    "代工單號": new_oem_id,
                    "生產單號": new_production_id,
                    "配方編號": new_formula_id,
                    "客戶名稱": new_customer,
                    "代工數量": new_oem_qty,
                    "代工廠商": new_vendor,
                    "備註":     new_remark,
                    "狀態":     "🏭 在廠內",
                    "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.df_oem = pd.concat(
                    [st.session_state.df_oem, new_df_row], ignore_index=True
                )
                st.session_state["oem_saved"] = new_oem_id
                st.rerun()

    # ================================================================
    # Tab 2：編輯代工
    # ================================================================
    with tab2:

        if "toast_message" in st.session_state:
            st.toast(
                st.session_state.toast_message["msg"],
                icon=st.session_state.toast_message.get("icon", "ℹ️")
            )
            del st.session_state.toast_message

        if not df_oem.empty:

            df_oem["狀態"] = df_oem["狀態"].astype(str).str.strip()
            df_oem["日期排序"] = df_oem["代工單號"].str.split("-").str[0].apply(tw_to_ad)
            df_oem["日期排序"] = pd.to_datetime(df_oem["日期排序"], errors="coerce")

            df_oem_active = df_oem[df_oem["狀態"] != "✅ 已結案"].copy()
            df_oem_active = df_oem_active.sort_values("日期排序", ascending=False)

            oem_options = [
                f"{row.get('客戶名稱','')} | {row.get('配方編號','')} | {row.get('代工數量',0)}kg | {row.get('代工廠商','')} | {row['代工單號']}"
                for _, row in df_oem_active.iterrows()
            ]

            if not oem_options:
                st.warning("⚠️ 目前沒有可編輯的代工單（全部已結案）")
            else:
                selected_option = st.selectbox("選擇代工單號", [""] + oem_options, key="select_oem_edit")

                if selected_option:
                    selected_oem = selected_option.split(" | ")[-1]

                    if ("oem_selected_row" not in st.session_state or
                            st.session_state.oem_selected_row.get("代工單號") != selected_oem):
                        oem_row = df_oem_active[df_oem_active["代工單號"] == selected_oem].iloc[0].to_dict()
                        st.session_state.oem_selected_row = oem_row

                    oem_row = st.session_state.oem_selected_row

                    col1, col2, col3 = st.columns(3)
                    col1.text_input("配方編號", value=oem_row.get("配方編號", ""), disabled=True)
                    col2.text_input("客戶名稱", value=oem_row.get("客戶名稱", ""), disabled=True)
                    col3.text_input("代工數量 (kg)", value=oem_row.get("代工數量", ""), disabled=True)

                    col4, col5 = st.columns([2, 1])
                    new_vendor = col4.selectbox(
                        "代工廠商", ["", "弘旭", "良輝"],
                        index=["", "弘旭", "良輝"].index(oem_row.get("代工廠商", ""))
                              if oem_row.get("代工廠商", "") in ["", "弘旭", "良輝"] else 0,
                        key="oem_vendor"
                    )
                    status_options = ["", "⏳ 未載回", "🏭 在廠內", "🔄 進行中", "✅ 已結案"]
                    current_status = oem_row.get("狀態", "")
                    status_index   = status_options.index(current_status) if current_status in status_options else 0
                    new_status     = col5.selectbox("狀態", status_options, index=status_index, key="oem_status")
                    new_remark     = st.text_area("備註", value=oem_row.get("備註", ""), key="oem_remark", height=120)

                    # 計算已送達 / 尚餘
                    df_this_delivery = df_delivery[df_delivery["代工單號"] == selected_oem] \
                        if "代工單號" in df_delivery.columns else pd.DataFrame()
                    total_delivered = df_this_delivery["送達數量"].astype(float).sum() \
                        if not df_this_delivery.empty else 0.0
                    oem_qty   = float(oem_row.get("代工數量", 0))
                    remaining = oem_qty - total_delivered

                    st.info(f"📦 已送達：{total_delivered} kg / 尚餘：{remaining} kg")

                    is_closed = oem_row.get("狀態") == "✅ 已結案"
                    if is_closed:
                        st.warning("⚠️ 此代工單已結案，禁止再修改")

                    b1, b2 = st.columns(2)

                    with b1:
                        if st.button("💾 更新代工資訊", key="update_oem_info"):
                            if is_closed:
                                st.error("❌ 已結案代工單不可修改")
                            else:
                                # ✅ 三欄合併成一次 API 寫入
                                all_values = get_cached_sheet_values("代工管理")
                                for idx, row in enumerate(all_values[1:], start=2):
                                    if row[0] == selected_oem:
                                        import gspread.utils as gu
                                        col_s = gu.rowcol_to_a1(idx, 6).rstrip("0123456789")
                                        col_e = gu.rowcol_to_a1(idx, 8).rstrip("0123456789")
                                        ws_oem.update(
                                            f"{col_s}{idx}:{col_e}{idx}",
                                            [[new_vendor, new_remark, new_status]]
                                        )
                                        break

                                # ✅ 同步 session_state，不重讀 Sheet
                                mask = st.session_state.df_oem["代工單號"] == selected_oem
                                st.session_state.df_oem.loc[mask, "代工廠商"] = new_vendor
                                st.session_state.df_oem.loc[mask, "備註"]     = new_remark
                                st.session_state.df_oem.loc[mask, "狀態"]     = new_status
                                st.session_state.oem_selected_row.update({
                                    "代工廠商": new_vendor,
                                    "備註":     new_remark,
                                    "狀態":     new_status
                                })
                                st.session_state.toast_message = {"msg": "代工資訊已更新", "icon": "💾"}
                                st.rerun()

                    with b2:
                        if st.button("🗑️ 刪除代工單", key="delete_oem"):
                            if is_closed:
                                st.error("❌ 已結案代工單不可刪除")
                            else:
                                st.session_state.show_delete_oem_confirm = True

                    if st.session_state.get("show_delete_oem_confirm", False):
                        st.warning(f"⚠️ 確定刪除 {oem_row['代工單號']}？")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("確認刪除", key="confirm_delete_oem"):
                                all_values = get_cached_sheet_values("代工管理")
                                for idx, row in enumerate(all_values[1:], start=2):
                                    if row[0] == oem_row["代工單號"]:
                                        ws_oem.delete_row(idx)
                                        break
                                # ✅ 同步 session_state
                                st.session_state.df_oem = st.session_state.df_oem[
                                    st.session_state.df_oem["代工單號"] != oem_row["代工單號"]
                                ].reset_index(drop=True)
                                st.session_state.toast_message = {"msg": "已刪除代工單", "icon": "🗑️"}
                                st.session_state.oem_selected_row = None
                                st.session_state.show_delete_oem_confirm = False
                                st.rerun()
                        with c2:
                            if st.button("取消", key="cancel_delete_oem"):
                                st.session_state.show_delete_oem_confirm = False

                    st.markdown("---")

                    # ── 新增送達 ──
                    col_d1, col_d2 = st.columns(2)
                    delivery_date = col_d1.date_input("送達日期", key="delivery_date")
                    delivery_qty  = col_d2.number_input(
                        "送達數量 (kg)", min_value=0.0, value=0.0, step=1.0, key="delivery_qty"
                    )

                    if st.button("➕ 新增送達", key="add_delivery"):
                        if remaining <= 0:
                            st.error("❌ 已全數送達，無法再新增送達紀錄")
                        elif delivery_qty <= 0:
                            st.warning("⚠️ 請輸入正確的送達數量")
                        elif delivery_qty > remaining:
                            st.error("❌ 送達數量不可超過尚餘數量")
                        else:
                            new_delivery_row = [
                                selected_oem,
                                delivery_date.strftime("%Y/%m/%d"),
                                delivery_qty,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ]
                            ws_delivery.append_row(new_delivery_row)

                            # ✅ 直接更新 session_state，不重讀 Sheet
                            new_del_df = pd.DataFrame([{
                                "代工單號": selected_oem,
                                "送達日期": delivery_date.strftime("%Y/%m/%d"),
                                "送達數量": delivery_qty,
                                "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }])
                            st.session_state.df_delivery = pd.concat(
                                [st.session_state.df_delivery, new_del_df], ignore_index=True
                            )

                            new_total_delivered = total_delivered + delivery_qty
                            new_remaining       = oem_qty - new_total_delivered

                            if new_remaining <= 0 and oem_row.get("狀態") != "✅ 已結案":
                                update_oem_status(selected_oem, "⏳ 未載回")
                                toast_msg = "📦 已全數送達，狀態自動轉為「未載回」"
                            else:
                                toast_msg = f"已新增送達：{delivery_date.strftime('%Y/%m/%d')} / {delivery_qty} kg"

                            st.session_state.toast_message = {"msg": toast_msg, "icon": "🚚"}
                            st.rerun()

        else:
            st.info("⚠️ 目前沒有代工單，請至「新增代工單」分頁建立")

    # ================================================================
    # Tab 3：載回登入
    # ================================================================
    with tab3:

        if st.session_state.get("toast_msg"):
            st.toast(st.session_state.toast_msg, icon=st.session_state.toast_icon)
            st.session_state.pop("toast_msg")
            st.session_state.pop("toast_icon")

        if df_oem.empty:
            st.info("⚠️ 目前沒有代工單")
        else:
            df_oem["日期排序"] = df_oem["代工單號"].str.split("-").str[0].apply(tw_to_ad)
            df_oem["日期排序"] = pd.to_datetime(df_oem["日期排序"], errors="coerce")

            df_oem_active = df_oem[df_oem["狀態"] != "✅ 已結案"].sort_values("日期排序", ascending=False)

            if df_oem_active.empty:
                st.warning("⚠️ 目前沒有可載回的代工單（全部已結案）")
            else:
                oem_options = [
                    f"{row['代工單號']} | {row.get('配方編號','')} | {row.get('客戶名稱','')} | {row.get('代工數量',0)}kg"
                    for _, row in df_oem_active.iterrows()
                ]
                selected_option = st.selectbox("選擇代工單號", [""] + oem_options, key="select_oem_return")

                if selected_option:
                    selected_oem = selected_option.split(" | ")[0]

                    oem_idx = df_oem[df_oem["代工單號"] == selected_oem].index[0]
                    oem_row = df_oem.loc[oem_idx]

                    total_qty = float(oem_row.get("代工數量", 0))

                    df_this_return  = df_return[df_return["代工單號"] == selected_oem]
                    total_returned  = df_this_return["載回數量"].astype(float).sum() \
                        if not df_this_return.empty else 0.0
                    remaining_qty   = total_qty - total_returned

                    col1, col2 = st.columns(2)
                    col1.text_input("配方編號",    value=oem_row.get("配方編號", ""),  disabled=True, key="oem_recipe_no_display")
                    col2.text_input("代工數量 (kg)", value=total_qty,                   disabled=True, key="oem_total_qty_display")
                    st.info(f"🚚 已載回：{total_returned} kg / 尚餘：{remaining_qty} kg")

                    if not df_this_return.empty:
                        st.dataframe(
                            df_this_return[["載回日期", "載回數量"]],
                            use_container_width=True, hide_index=True
                        )

                    st.markdown("---")

                    with st.form("return_form"):
                        col_r1, col_r2 = st.columns(2)
                        return_date = col_r1.date_input("載回日期", value=datetime.today(), key="return_date_input")
                        return_qty  = col_r2.number_input("載回數量 (kg)", min_value=0.0, step=1.0, key="return_qty_input")
                        submitted   = st.form_submit_button("➕ 新增載回")

                    if submitted:
                        if return_qty <= 0:
                            st.warning("⚠️ 請輸入載回數量")
                        else:
                            safe_append_row(ws_return, [
                                str(selected_oem),
                                return_date.strftime("%Y/%m/%d"),
                                str(return_qty),
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ])

                            # ✅ 直接更新 session_state，不重讀 Sheet
                            new_ret_df = pd.DataFrame([{
                                "代工單號": selected_oem,
                                "載回日期": return_date.strftime("%Y/%m/%d"),
                                "載回數量": return_qty,
                                "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }])
                            st.session_state.df_return = pd.concat(
                                [st.session_state.df_return, new_ret_df], ignore_index=True
                            )

                            new_total     = total_returned + return_qty
                            remaining_after = total_qty - new_total

                            if remaining_after <= 0 and total_qty > 0:
                                status_col_idx = int(df_oem.columns.get_loc("狀態")) + 1
                                ws_oem.update_cell(row=oem_idx + 2, col=status_col_idx, value="✅ 已結案")
                                # ✅ 同步 session_state
                                st.session_state.df_oem.loc[oem_idx, "狀態"] = "✅ 已結案"
                                st.session_state.toast_msg  = "🎉 載回完成，代工單已結案"
                                st.session_state.toast_icon = "✅"
                            else:
                                st.session_state.toast_msg  = "💾 載回資料已儲存"
                                st.session_state.toast_icon = "📦"

                            st.session_state["rerun_after_return_save"] = True

    if st.session_state.get("rerun_after_return_save", False):
        st.session_state["rerun_after_return_save"] = False
        st.rerun()

    # ================================================================
    # Tab 4：代工進度表
    # ================================================================
    with tab4:

        if not df_oem.empty:
            status_order_map = {
                "🏭 在廠內": 1,
                "⏳ 未載回": 2,
                "🔄 進行中": 3,
                "✅ 已結案": 4
            }

            progress_data = []

            for _, oem in df_oem.iterrows():
                oem_id = oem["代工單號"]

                df_this_delivery = df_delivery[df_delivery["代工單號"] == oem_id]
                delivery_text = ""
                if not df_this_delivery.empty:
                    delivery_text = "\n".join([
                        f"{row['送達日期']} ({row['送達數量']} kg)"
                        for _, row in df_this_delivery.iterrows()
                    ])

                df_this_return = df_return[df_return["代工單號"] == oem_id]
                return_text = ""
                if not df_this_return.empty:
                    return_text = "\n".join([
                        f"{row['載回日期']} ({row['載回數量']} kg)"
                        for _, row in df_this_return.iterrows()
                    ])

                total_qty      = float(oem.get("代工數量", 0))
                total_returned = df_this_return["載回數量"].astype(float).sum() \
                    if not df_this_return.empty else 0.0

                manual_status = str(oem.get("狀態", "")).strip()
                if manual_status:
                    status = manual_status
                else:
                    if total_returned >= total_qty and total_qty > 0:
                        status = "✅ 已結案"
                    elif total_returned > 0:
                        status = "🔄 進行中"
                    else:
                        status = "⏳ 未載回"

                progress_data.append({
                    "status_order":   status_order_map.get(status, 99),
                    "狀態":           status,
                    "代工單號":       oem_id,
                    "代工廠名稱":     oem.get("代工廠商", ""),
                    "配方編號":       oem.get("配方編號", ""),
                    "客戶名稱":       oem.get("客戶名稱", ""),
                    "代工數量":       f"{oem.get('代工數量', 0)} kg",
                    "送達日期及數量": delivery_text,
                    "載回日期及數量": return_text,
                    "建立時間":       oem.get("建立時間", "")
                })

            df_progress = pd.DataFrame(progress_data)

            show_open_only = st.checkbox("只顯示未結案代工單", value=True)
            if show_open_only:
                df_progress = df_progress[df_progress["狀態"] != "✅ 已結案"]

            search_text = st.text_input(
                "🔍 搜尋客戶名稱或配方編號",
                placeholder="輸入關鍵字（可搜尋客戶名稱 / 配方編號）"
            ).strip()

            if search_text:
                df_progress = df_progress[
                    df_progress["客戶名稱"].astype(str).str.contains(search_text, case=False, na=False) |
                    df_progress["配方編號"].astype(str).str.contains(search_text, case=False, na=False)
                ]

            if not df_progress.empty:
                df_progress = df_progress.sort_values(
                    by=["status_order", "建立時間"], ascending=[True, False]
                ).drop(columns=["status_order"])
                st.dataframe(df_progress, use_container_width=True, hide_index=True)
            else:
                st.info("目前沒有符合條件的代工單")

        else:
            st.info("⚠️ 目前沒有代工記錄")

    # ================================================================
    # Tab 5：代工歷程查詢
    # ================================================================
    with tab5:

        col1, col2 = st.columns(2)
        search_client = col1.text_input("客戶名稱", key="search_client_history")
        search_recipe = col2.text_input("配方編號", key="search_recipe_history")

        if not search_client and not search_recipe:
            st.info("請輸入客戶名稱或配方編號進行查詢")
        else:
            progress_data = []

            for _, oem in df_oem.iterrows():
                oem_id = oem.get("代工單號", "")
                status = oem.get("狀態", "")
                status_order = 0 if status != "✅ 已結案" else 1

                df_del = df_delivery[df_delivery["代工單號"] == oem_id] \
                    if "代工單號" in df_delivery.columns else pd.DataFrame()
                delivery_text = "\n".join([
                    f"{row['送達日期']} → {row['送達數量']} kg"
                    for _, row in df_del.iterrows()
                ]) if not df_del.empty else ""

                df_ret = df_return[df_return["代工單號"] == oem_id] \
                    if "代工單號" in df_return.columns else pd.DataFrame()
                return_text = "\n".join([
                    f"{row['載回日期']} → {row['載回數量']} kg"
                    for _, row in df_ret.iterrows()
                ]) if not df_ret.empty else ""

                progress_data.append({
                    "status_order": status_order,
                    "狀態":         status,
                    "代工單號":     oem_id,
                    "代工廠名稱":   oem.get("代工廠商", ""),
                    "配方編號":     oem.get("配方編號", ""),
                    "客戶名稱":     oem.get("客戶名稱", ""),
                    "代工數量":     f"{oem.get('代工數量', 0)} kg",
                    "送達日期及數量": delivery_text,
                    "載回日期及數量": return_text,
                    "建立時間":     oem.get("建立時間", "")
                })

            df_progress = pd.DataFrame(progress_data)

            if search_client:
                df_progress = df_progress[
                    df_progress["客戶名稱"].str.contains(search_client, case=False, na=False)
                ]
            if search_recipe:
                df_progress = df_progress[
                    df_progress["配方編號"].str.contains(search_recipe, case=False, na=False)
                ]

            if df_progress.empty:
                st.info("⚠️ 沒有符合條件的代工歷程")
            else:
                df_progress = df_progress.sort_values(
                    ["status_order", "建立時間"], ascending=[True, False]
                )
                df_display = df_progress.drop(columns=["status_order"]).copy()
                df_display["序號"] = range(1, len(df_display) + 1)
                cols = [c for c in df_display.columns if c != "序號"] + ["序號"]
                st.dataframe(df_display[cols].reset_index(drop=True), use_container_width=True)
            
               
# ======== 採購管理分頁 =========
elif menu == "採購管理":
    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    import pandas as pd
    from datetime import datetime, date

    # ===== 標題 =====
    # st.markdown(
    #     '<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">📥 採購管理</h1>',
    #     unsafe_allow_html=True
    # )

    # ===== Tab 分頁 =====
    tab1, tab2, tab3 = st.tabs(["📥 進貨新增", "🔍 進貨查詢", "🏢 供應商管理"])

    def get_or_create_worksheet(spreadsheet, title, rows=100, cols=10):
        try:
            return spreadsheet.worksheet(title)
        except Exception as e:
            try:
                return spreadsheet.add_worksheet(title, rows=rows, cols=cols)
            except Exception as e2:
                st.error(f"❌ 無法建立或取得工作表「{title}」")
                raise e2

    ws_stock = get_or_create_worksheet(spreadsheet, "庫存記錄", 100, 10)

    # ========== Tab 1：進貨新增（Form 版） ==========
    with tab1:
    
        # ✅ 讀取庫存記錄表（防 rerun）
        ws_stock = get_or_create_worksheet(spreadsheet, "庫存記錄", rows=100, cols=10)
        records = get_cached_sheet_df("庫存記錄").to_dict("records")
        if records:
            df_stock = pd.DataFrame(records)
        else:
            df_stock = pd.DataFrame(
                columns=["類型","色粉編號","日期","數量","單位","廠商編號","廠商名稱","備註"]
            )
    
        # 🔒 舊庫存補時間
        if "日期" in df_stock.columns:
            def fix_stock_datetime(x):
                try:
                    dt = pd.to_datetime(x, errors="coerce")
                    if pd.isna(dt):
                        return x
                    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                        return dt + pd.Timedelta(hours=9)
                    return dt
                except:
                    return x
            df_stock["日期"] = df_stock["日期"].apply(fix_stock_datetime)
    
        # 初始化 form_in_stock session_state
        if "form_in_stock" not in st.session_state:
            st.session_state.form_in_stock = {
                "色粉編號": "",
                "數量": 0.0,
                "單位": "g",
                "日期": datetime.today().date(),
                "廠商編號": "",
                "廠商名稱": "",
                "備註": ""
            }
    
        # ===== 使用 st.form =====
        with st.form("form_add_stock"):
            # --- 基本欄位 ---
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.form_in_stock["色粉編號"] = st.text_input(
                    "色粉編號", st.session_state.form_in_stock["色粉編號"]
                )
            with col2:
                st.session_state.form_in_stock["數量"] = st.number_input(
                    "數量", min_value=0.0, value=st.session_state.form_in_stock["數量"], step=1.0
                )
            with col3:
                st.session_state.form_in_stock["單位"] = st.selectbox(
                    "單位", ["g","kg"], index=["g","kg"].index(st.session_state.form_in_stock["單位"])
                )
            with col4:
                st.session_state.form_in_stock["日期"] = st.date_input(
                    "進貨日期", value=st.session_state.form_in_stock["日期"]
                )
    
            # --- 廠商欄位，下拉選單 + 自動帶出名稱 ---
            try:
                ws_supplier = get_cached_worksheet("供應商管理")
                df_supplier = get_cached_sheet_df("供應商管理").astype(str)
            except:
                df_supplier = pd.DataFrame(columns=["供應商編號", "供應商簡稱"])
            for col in ["供應商編號", "供應商簡稱"]:
                if col not in df_supplier.columns:
                    df_supplier[col] = ""
            supplier_name_map = df_supplier.set_index("供應商編號")["供應商簡稱"].to_dict()
            supplier_options = df_supplier["供應商編號"].tolist()
    
            col5, col6 = st.columns(2)
            with col5:
                selected_supplier = st.selectbox(
                    "廠商編號",
                    [""] + supplier_options,
                    key="form_supplier_select",
                    format_func=lambda x: f"{x} - {supplier_name_map.get(x,'')}" if x else ""
                )
    
            # ✅ 同步選單值到表單 state
            st.session_state.form_in_stock["廠商編號"] = selected_supplier
            st.session_state.form_in_stock["廠商名稱"] = supplier_name_map.get(selected_supplier, "")
    
            with col6:
                st.session_state.form_in_stock["廠商名稱"] = supplier_name_map.get(selected_supplier, "")
                st.text_input(
                    "廠商名稱",
                    value=st.session_state.form_in_stock["廠商名稱"],
                    disabled=True
                )
    
            # --- 備註欄 ---
            st.session_state.form_in_stock["備註"] = st.text_input(
                "備註", st.session_state.form_in_stock["備註"]
            )
    
            # --- 新增進貨按鈕 ---
            submitted = st.form_submit_button("新增進貨")
    
            if submitted:
                if not st.session_state.form_in_stock["色粉編號"].strip():
                    st.warning("⚠️ 請輸入色粉編號！")
                else:
                    new_row = {
                        "類型": "進貨",
                        "色粉編號": st.session_state.form_in_stock["色粉編號"].strip(),
                        "日期": st.session_state.form_in_stock["日期"].strftime("%Y/%m/%d"),
                        "數量": st.session_state.form_in_stock["數量"],
                        "單位": st.session_state.form_in_stock["單位"],
                        "廠商編號": st.session_state.form_in_stock["廠商編號"].strip(),
                        "廠商名稱": st.session_state.form_in_stock["廠商名稱"].strip(),
                        "備註": st.session_state.form_in_stock["備註"]
                    }
    
                    df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
    
                    # ✅ 寫回 Google Sheet
                    df_to_upload = df_stock.copy()
                    df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce")\
                                             .dt.strftime("%Y/%m/%d").fillna("")
                    df_to_upload = df_to_upload.astype(str)
                    ws_stock.clear()
                    ws_stock.update([df_to_upload.columns.tolist()] + df_to_upload.values.tolist())
    
                    # 清空表單
                    st.session_state.form_in_stock = {
                        "色粉編號": "",
                        "數量": 0.0,
                        "單位": "g",
                        "日期": datetime.today().date(),
                        "廠商編號": "",
                        "廠商名稱": "",
                        "備註": ""
                    }
    
                    st.success("✅ 進貨紀錄已新增")
                    st.toast(
                        f"進貨成功｜色粉 {new_row['色粉編號']}｜廠商 {new_row['廠商編號']}",
                        icon="✅"
                    )
    
                               
    # ========== Tab 2：進貨查詢 ==========
    with tab2:
              
        # 讀取庫存記錄表
        try:
            ws_stock = get_cached_worksheet("庫存記錄")
            df_stock = get_cached_sheet_df("庫存記錄")
        except:
            df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
        
        # --- 篩選欄位 ---
        col1, col2, col3 = st.columns(3)
        search_code = col1.text_input("色粉編號", key="in_search_code")
        search_start = col2.date_input("進貨日期(起)", key="in_search_start")
        search_end = col3.date_input("進貨日期(迄)", key="in_search_end")
        
        if st.button("查詢進貨", key="btn_search_in_v3"):
            df_result = df_stock[df_stock["類型"] == "進貨"].copy()
            
            # 1️⃣ 依色粉編號篩選
            if search_code.strip():
                df_result = df_result[df_result["色粉編號"].astype(str).str.contains(search_code.strip(), case=False)]
            
            # 2️⃣ 日期欄轉換格式
            df_result["日期_dt"] = pd.to_datetime(df_result["日期"], errors="coerce").dt.normalize()
            
            # 3️⃣ 判斷使用者是否真的有選日期
            today = pd.to_datetime("today").normalize()
            search_start_dt = pd.to_datetime(search_start).normalize() if search_start else None
            search_end_dt = pd.to_datetime(search_end).normalize() if search_end else None
            
            use_date_filter = (
                (search_start_dt is not None and search_start_dt != today) or
                (search_end_dt is not None and search_end_dt != today)
            )
            
            if use_date_filter:
                st.write("🔎 使用日期範圍：", search_start_dt, "～", search_end_dt)
                df_result = df_result[
                    (df_result["日期_dt"] >= search_start_dt) &
                    (df_result["日期_dt"] <= search_end_dt)
                ]
            else:
                st.markdown(
                    '<span style="color:gray; font-size:0.8em;">📅 未選日期 → 顯示所有進貨資料</span>',
                    unsafe_allow_html=True
                )
            
            # 4️⃣ 顯示結果
            if not df_result.empty:
                show_cols = {
                    "色粉編號": "色粉編號",
                    "廠商名稱": "供應商簡稱",
                    "日期_dt": "日期",
                    "數量": "數量",
                    "單位": "單位",
                    "備註": "備註"
                }
            
                # ✅ 若舊資料沒有廠商名稱欄位，補空值（避免 KeyError）
                if "廠商名稱" not in df_result.columns:
                    df_result["廠商名稱"] = ""
            
                df_display = df_result[list(show_cols.keys())].rename(columns=show_cols)
            
                # 🔄 自動轉換單位
                def format_quantity_unit(row):
                    qty = row["數量"]
                    unit = row["單位"].strip().lower()
                    if unit == "g" and qty >= 1000:
                        return pd.Series([qty / 1000, "kg"])
                    else:
                        return pd.Series([qty, row["單位"]])
            
                df_display[["數量", "單位"]] = df_display.apply(format_quantity_unit, axis=1)
                df_display["日期"] = df_display["日期"].dt.strftime("%Y/%m/%d")
            
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            else:
                st.info("ℹ️ 沒有符合條件的進貨資料")
    
    # ========== Tab 3：供應商管理 ==========
    with tab3:
    
        # ===== 讀取或建立 Google Sheet =====
        try:
            ws_supplier = get_cached_worksheet("供應商管理")
        except:
            ws_supplier = spreadsheet.add_worksheet("供應商管理", rows=100, cols=10)
    
        columns = ["供應商編號", "供應商簡稱", "備註"]
    
        # 安全初始化 form_supplier
        if "form_supplier" not in st.session_state or not isinstance(st.session_state.form_supplier, dict):
            st.session_state.form_supplier = {col: "" for col in columns}
    
        # 初始化其他 session_state
        init_states({
            "edit_supplier_id": None,
            "delete_supplier_index": None,
            "show_delete_supplier_confirm": False
        })
    
        # 讀取 Google Sheet 資料
        try:
            df = get_cached_sheet_df("供應商管理")
        except:
            df = pd.DataFrame(columns=columns)
        
        for col in columns:
            if col not in df.columns:
                df[col] = ""
    
        # ===== 計算下一個編號 =====
        import re
        
        def get_next_supplier_code(df, prefix="S", width=3):
            if df.empty or "供應商編號" not in df.columns:
                return f"{prefix}{str(1).zfill(width)}", None
        
            nums = []
        
            for code in df["供應商編號"].dropna():
                m = re.match(rf"{prefix}(\d+)", str(code))
                if m:
                    nums.append(int(m.group(1)))
        
            if not nums:
                return f"{prefix}{str(1).zfill(width)}", None
        
            max_num = max(nums)
            current_code = f"{prefix}{str(max_num).zfill(width)}"
            next_code = f"{prefix}{str(max_num + 1).zfill(width)}"
        
            return next_code, current_code
        
    
        next_code, current_code = get_next_supplier_code(df)
    
        if not st.session_state.get("edit_supplier_id"):
            if current_code:
                st.info(f"📌 目前已新增到：{current_code}　➡ 建議下一號：{next_code}")
            else:
                st.info(f"📌 尚無供應商資料，建議從：{next_code} 開始")
    
        # ===== 表單模式 =====
        with st.form("form_supplier_tab3"):
    
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.form_supplier["供應商編號"] = st.text_input(
                    "供應商編號",
                    st.session_state.form_supplier.get("供應商編號", "")
                )
    
                # 建議編號按鈕
                if not st.session_state.get("edit_supplier_id"):
                    if st.form_submit_button("⬇️ 使用建議編號", use_container_width=True):
                        st.session_state.form_supplier["供應商編號"] = next_code
                        st.rerun()
    
                st.session_state.form_supplier["供應商簡稱"] = st.text_input(
                    "供應商簡稱",
                    st.session_state.form_supplier.get("供應商簡稱", "")
                )
    
            with col2:
                st.session_state.form_supplier["備註"] = st.text_input(
                    "備註",
                    st.session_state.form_supplier.get("備註", ""),
                    key="form_supplier_note_tab3"
                )
    
            submit = st.form_submit_button("💾 儲存")
    
        if submit:
            new_data = st.session_state.form_supplier.copy()
            if not new_data["供應商編號"].strip():
                st.warning("⚠️ 請輸入供應商編號！")
                st.stop()
    
            edit_id = st.session_state.get("edit_supplier_id")
    
            if edit_id:  # 修改模式
                mask = df["供應商編號"] == edit_id
                if mask.any():
                    df.loc[mask, df.columns] = pd.Series(new_data)
                    st.success("✅ 供應商已更新！")
                else:
                    st.error("⚠️ 原供應商不存在，請重新選擇")
                    st.stop()
            else:  # 新增模式
                if new_data["供應商編號"] in df["供應商編號"].values:
                    st.warning("⚠️ 此供應商編號已存在！")
                    st.stop()
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                st.success("✅ 新增成功！")
    
            save_df_to_sheet(ws_supplier, df)
            st.session_state.form_supplier = {col: "" for col in columns}
            st.session_state.edit_supplier_id = None
            st.rerun()
    
        # ===== 刪除確認 =====
        if st.session_state.show_delete_supplier_confirm and st.session_state.delete_supplier_index in df.index:
            row = df.loc[st.session_state.delete_supplier_index]
            st.warning(f"⚠️ 確定要刪除 {row['供應商編號']} {row['供應商簡稱']}？")
            c1, c2 = st.columns(2)
            if c1.button("刪除", key="confirm_delete_supplier_tab3"):
                df.drop(index=st.session_state.delete_supplier_index, inplace=True)
                df.reset_index(drop=True, inplace=True)
                save_df_to_sheet(ws_supplier, df)
                st.success("✅ 刪除成功！")
                st.session_state.show_delete_supplier_confirm = False
                st.rerun()
            if c2.button("取消", key="cancel_delete_supplier_tab3"):
                st.session_state.show_delete_supplier_confirm = False
                st.rerun()
        
        st.markdown("---")
        
        # ===== 📋 供應商清單（搜尋後顯示表格與操作） =====
        st.markdown(
            '<h3 style="font-size:16px; font-family:Arial; color:#dbd818;">🛠️ 供應商修改/刪除</h3>',
            unsafe_allow_html=True
        )
        
        # 搜尋輸入框
        keyword = st.text_input("請輸入供應商編號或簡稱", st.session_state.get("search_supplier_keyword", ""))
        st.session_state.search_supplier_keyword = keyword.strip()
        
        # 預設空表格
        df_filtered = pd.DataFrame()
        
        # 只有輸入關鍵字才篩選
        if keyword:
            df_filtered = df[
                df["供應商編號"].str.contains(keyword, case=False, na=False) |
                df["供應商簡稱"].str.contains(keyword, case=False, na=False)
            ]
            
            # 僅在有輸入且結果為空時顯示警告
            if df_filtered.empty:
                st.warning("❗ 查無符合的資料")
        
        # ===== 📋 表格顯示搜尋結果 =====
        if not df_filtered.empty:
            st.dataframe(df_filtered[columns], use_container_width=True, hide_index=True)
            
            # ===== ✏️ 改 / 🗑️ 刪操作（表格下方） =====
            st.markdown("<hr style='margin-top:10px;margin-bottom:10px;'>", unsafe_allow_html=True)
            
            # 標題 + 灰色小字說明
            st.markdown(
                """
                <p style="font-size:14px; font-family:Arial; color:gray; margin-top:-8px;">
                    🛈 請於新增欄位修改
                </p>
                """,
                unsafe_allow_html=True
            )
            
            # --- 全域縮小 emoji 字體大小 ---
            st.markdown("""
                <style>
                div.stButton > button {
                    font-size:16px !important;
                    padding:2px 8px !important;
                    border-radius:8px;
                    background-color:#333333 !important;
                    color:white !important;
                    border:1px solid #555555;
                }
                div.stButton > button:hover {
                    background-color:#555555 !important;
                    border-color:#dbd818 !important;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # --- 列出供應商清單 ---
            for i, row in df_filtered.iterrows():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(
                        f"<div style='font-family:Arial;color:#FFFFFF;'>🔹 {row['供應商編號']}　{row['供應商簡稱']}</div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    if st.button("✏️ 改", key=f"edit_supplier_{i}"):
                        st.session_state.edit_supplier_index = i
                        st.session_state.form_supplier = row.to_dict()
                        st.rerun()
                with c3:
                    if st.button("🗑️ 刪", key=f"delete_supplier_{i}"):
                        st.session_state.delete_supplier_index = i
                        st.session_state.show_delete_supplier_confirm = True
                        st.rerun()

# ======== 交叉查詢分頁 =========
if "menu" not in st.session_state:
    st.session_state.menu = "查詢區"
# ======== 查詢區分頁（改為 Tab 架構）=========
elif menu == "查詢區":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    import pandas as pd

    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())

    # ===== 標題 =====
    # st.markdown(
    #     '<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">🔍 查詢區</h1>',
    #     unsafe_allow_html=True
    # )

    # ===== Tab 分頁 =====
    tab1, tab2, tab3, tab4 = st.tabs([
        "♻️ 依色粉編號查配方",
        "🧮 色粉用量查詢",
        "🍭 Pantone色號表",
        "🧪 樣品提交表"
    ])

    # ========== Tab 1：依色粉編號查配方 ==========
    with tab1:
    
        # 使用 form 包裹查詢欄位
        with st.form("form_cross_query"):
            cols = st.columns(5)
            input_vals = []
            for i in range(5):
                # 先用本地變數接收輸入，不直接綁定 session_state
                val = cols[i].text_input(f"色粉編號{i+1}", value="", key=f"cross_color_{i}")
                input_vals.append(val.strip())
    
            # Form 提交按鈕
            submit = st.form_submit_button("查詢配方")
    
        # form 提交後再處理
        if submit:
            # 收集非空值
            inputs = [v for v in input_vals if v]
    
            if not inputs:
                st.warning("⚠️ 請至少輸入一個色粉編號")
            else:
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

    # ========== Tab 2：色粉用量查詢 ==========
    with tab2:
    
        with st.form("form_powder_usage"):
            st.markdown("**🔍 色粉用量查詢**")
    
            # 四個色粉編號輸入框
            cols = st.columns(4)
            powder_inputs = []
            for i in range(4):
                val = cols[i].text_input(f"色粉編號{i+1}", key=f"usage_color_{i}")
                if val.strip():
                    powder_inputs.append(val.strip())
    
            # 日期區間選擇
            col1, col2 = st.columns(2)
            start_date = col1.date_input("開始日期", key="usage_start_date")
            end_date = col2.date_input("結束日期", key="usage_end_date")
    
            # 提交按鈕
            submit = st.form_submit_button("查詢用量")
    
        if submit and powder_inputs:
            results = []
            df_order_local = st.session_state.get("df_order", pd.DataFrame()).copy()
            df_recipe_local = st.session_state.get("df_recipe", pd.DataFrame()).copy()
    
            # 確保欄位存在，避免 KeyError
            powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
            for c in powder_cols + ["配方編號", "配方類別", "原始配方", "配方名稱", "顏色", "客戶名稱"]:
                if c not in df_recipe_local.columns:
                    df_recipe_local[c] = ""
    
            if "生產日期" in df_order_local.columns:
                df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
            else:
                df_order_local["生產日期"] = pd.NaT
    
            def format_usage(val):
                if val >= 1000:
                    kg = val / 1000
                    return f"{int(kg) if kg == int(kg) else round(kg,2)} kg"
                else:
                    return f"{int(val) if val == int(val) else round(val,2)} g"
    
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
    
            # ---- 以下原本計算邏輯照舊 ----
            for powder_id in powder_inputs:
                total_usage_g = 0.0
                monthly_usage = {}
    
                # 1) 先從配方管理找出「候選配方」
                if not df_recipe_local.empty:
                    mask = df_recipe_local[powder_cols].astype(str).apply(lambda row: powder_id in row.values, axis=1)
                    recipe_candidates = df_recipe_local[mask].copy()
                    candidate_ids = set(recipe_candidates["配方編號"].astype(str).tolist())
                else:
                    recipe_candidates = pd.DataFrame()
                    candidate_ids = set()
    
                # 2) 過濾生產單日期區間
                orders_in_range = df_order_local[
                    (df_order_local["生產日期"].notna()) &
                    (df_order_local["生產日期"] >= pd.to_datetime(start_date)) &
                    (df_order_local["生產日期"] <= pd.to_datetime(end_date))
                ]
    
                # 3) 計算用量
                for _, order in orders_in_range.iterrows():
                    order_recipe_id = str(order.get("配方編號", "")).strip()
                    if not order_recipe_id:
                        continue
    
                    recipe_rows = []
                    main_df = df_recipe_local[df_recipe_local["配方編號"].astype(str) == order_recipe_id]
                    if not main_df.empty:
                        recipe_rows.append(main_df.iloc[0].to_dict())
                    add_df = df_recipe_local[
                        (df_recipe_local["配方類別"] == "附加配方") &
                        (df_recipe_local["原始配方"].astype(str) == order_recipe_id)
                    ]
                    if not add_df.empty:
                        recipe_rows.extend(add_df.to_dict("records"))
    
                    order_total_for_powder = 0.0
                    sources_main = set()
                    sources_add = set()
    
                    packs_total = 0.0
                    for j in range(1, 5):
                        w_val = order.get(f"包裝重量{j}", 0)
                        n_val = order.get(f"包裝份數{j}", 0)
                        try: packs_total += float(w_val or 0) * float(n_val or 0)
                        except: pass
    
                    if packs_total <= 0: continue
    
                    for rec in recipe_rows:
                        rec_id = str(rec.get("配方編號", "")).strip()
                        if rec_id not in candidate_ids: continue
    
                        pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                        if powder_id not in pvals: continue
                        idx = pvals.index(powder_id) + 1
                        try: powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                        except: powder_weight = 0.0
                        if powder_weight <= 0: continue
    
                        contrib = powder_weight * packs_total
                        order_total_for_powder += contrib
                        disp_name = recipe_display_name(rec)
                        if str(rec.get("配方類別", "")).strip() == "附加配方":
                            sources_add.add(disp_name)
                        else:
                            sources_main.add(disp_name)
    
                    if order_total_for_powder <= 0: continue
    
                    od = order["生產日期"]
                    if pd.isna(od): continue
                    month_key = od.strftime("%Y/%m")
                    if month_key not in monthly_usage:
                        monthly_usage[month_key] = {"usage": 0.0, "main_recipes": set(), "additional_recipes": set()}
    
                    monthly_usage[month_key]["usage"] += order_total_for_powder
                    monthly_usage[month_key]["main_recipes"].update(sources_main)
                    monthly_usage[month_key]["additional_recipes"].update(sources_add)
                    total_usage_g += order_total_for_powder
    
                # 4) 輸出每月用量 & 總用量
                months_sorted = sorted(monthly_usage.keys())
                for month in months_sorted:
                    data = monthly_usage[month]
                    usage_g = data["usage"]
                    if usage_g <= 0: continue
                    per = pd.Period(month, freq="M")
                    month_start = per.start_time.date()
                    month_end = per.end_time.date()
                    disp_start = max(start_date, month_start)
                    disp_end = min(end_date, month_end)
                    date_disp = month if (disp_start == month_start and disp_end == month_end) else f"{disp_start.strftime('%Y/%m/%d')}~{disp_end.strftime('%m/%d')}"
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
                return [
                    'font-weight: bold; background-color: #333333; color: white' if s.name in df_usage.index and df_usage.loc[s.name, "來源區間"] == "總用量" and col in ["色粉編號", "來源區間", "月用量"] else ''
                    for col in s.index
                ]
    
            styled = df_usage.style.apply(highlight_total_row, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)
    
    # ========== Tab 3：Pantone色號表 ==========
    with tab3:
    
        # 讀取 Google Sheets
        try:
            ws_pantone = get_cached_worksheet("Pantone色號表")
        except:
            ws_pantone = spreadsheet.add_worksheet(title="Pantone色號表", rows=100, cols=4)
    
        df_pantone = get_cached_sheet_df("Pantone色號表")
    
        # 如果表格是空的，補上欄位名稱
        if df_pantone.empty:
            ws_pantone.clear()
            ws_pantone.append_row(["Pantone色號", "配方編號", "客戶名稱", "料號"])
            df_pantone = pd.DataFrame(columns=["Pantone色號", "配方編號", "客戶名稱", "料號"])
    
        # === 新增區塊（2 欄一列） ===
        st.markdown('<span style="color:#f1f5f2; font-weight:bold;">☑️ 新增 Pantone 記錄</span>', unsafe_allow_html=True)
        
        with st.form("add_pantone_tab"):
            col1, col2 = st.columns(2)
            with col1:
                pantone_code = st.text_input("Pantone 色號", key="pantone_code_tab")
            with col2:
                formula_id = st.text_input("配方編號", key="formula_id_tab")
    
            col3, col4 = st.columns(2)
            with col3:
                customer = st.text_input("客戶名稱", key="customer_tab")
            with col4:
                material_no = st.text_input("料號", key="material_no_tab")
    
            submitted = st.form_submit_button("➕ 新增")
    
            if submitted:
                if not pantone_code or not formula_id:
                    st.error("❌ Pantone 色號與配方編號必填")
                else:
                    if formula_id in df_recipe["配方編號"].astype(str).values:
                        st.warning(f"⚠️ 配方編號 {formula_id} 已存在於『配方管理』，不新增")
                    elif formula_id in df_pantone["配方編號"].astype(str).values:
                        st.error(f"❌ 配方編號 {formula_id} 已經在 Pantone 色號表裡")
                    else:
                        ws_pantone.append_row([pantone_code, formula_id, customer, material_no])
                        st.success(f"✅ 已新增：Pantone {pantone_code}（配方編號 {formula_id}）")
                        st.rerun()
    
        # ====== 統一顯示 Pantone 色號表函式 ======
        def show_pantone_table(df, title="Pantone 色號表"):
            if title:
                st.subheader(title)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                st.info("⚠️ 目前沒有資料")
                return
            df_reset = pd.DataFrame(df).reset_index(drop=True).astype(str)
            st.table(df_reset)
    
        # ======== 🔍 查詢 Pantone 色號 ========
        st.markdown('<span style="color:#f1f5f2; font-weight:bold;">🔍 查詢 Pantone 色號</span>', unsafe_allow_html=True)

        # 同一行：輸入框 + 搜尋模式
        c1, c2 = st.columns([2, 1])
        with c1:
            search_code = st.text_input("輸入 Pantone 色號", key="search_pantone_tab")
        with c2:
            search_mode = st.selectbox("", ["部分匹配", "精準匹配"], key="pantone_search_mode")
    
        # 使用者有輸入才顯示結果
        if search_code:
            if search_mode == "精準匹配":
                df_result_pantone = df_pantone[df_pantone["Pantone色號"].str.strip().str.lower() == search_code.strip().lower()]
            else:
                df_result_pantone = df_pantone[df_pantone["Pantone色號"].str.contains(search_code, case=False, na=False)]
    
            if not df_recipe.empty and "Pantone色號" in df_recipe.columns:
                if search_mode == "精準匹配":
                    df_result_recipe = df_recipe[df_recipe["Pantone色號"].str.strip().str.lower() == search_code.strip().lower()]
                else:
                    df_result_recipe = df_recipe[df_recipe["Pantone色號"].str.contains(search_code, case=False, na=False)]
            else:
                df_result_recipe = pd.DataFrame()
    
            if df_result_pantone.empty and df_result_recipe.empty:
                st.warning("查無符合的 Pantone 色號資料。")
            else:
                if not df_result_pantone.empty:
                    st.markdown(
                        '<div style="font-size:14px; font-family:Arial; color:#f0efa2; line-height:1.2; margin:2px 0; font-weight:bold;">📋 Pantone 對照表</div>',
                        unsafe_allow_html=True
                    )
                    show_pantone_table(df_result_pantone, title="")
    
                if not df_result_recipe.empty:
                    st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
                    st.markdown(
                        '<div style="font-size:14px; font-family:Arial; color:#f0efa2; line-height:1.2; margin:2px 0; font-weight:bold;">📋 配方管理</div>',
                        unsafe_allow_html=True
                    )
                    st.dataframe(
                        df_result_recipe[["配方編號", "顏色", "客戶名稱", "Pantone色號", "配方類別", "狀態"]].reset_index(drop=True),
                        use_container_width=True,
                    )
                    
    # ========== Tab 4：樣品記錄表 ==========
    from datetime import datetime, date
    
    # --- 日期安全轉換 ---
    def safe_date(v):
        try:
            if v in ["", None]:
                return datetime.today().date()
            if isinstance(v, pd.Timestamp):
                return v.date()
            if isinstance(v, datetime):
                return v.date()
            if isinstance(v, date):
                return v
            return pd.to_datetime(v).date()
        except:
            return datetime.today().date()
    
    with tab4:
    
        # ===== Sheet 讀取 =====
        try:
            ws_sample = get_cached_worksheet("樣品記錄")
        except:
            ws_sample = spreadsheet.add_worksheet("樣品記錄", rows=100, cols=10)
            ws_sample.append_row(["日期", "客戶名稱", "樣品編號", "樣品名稱", "樣品數量"])
            invalidate_sheet_cache("樣品記錄")
    
        try:
            df_sample = get_cached_sheet_df("樣品記錄")
        except:
            df_sample = pd.DataFrame()
    
        if df_sample.empty:
            df_sample = pd.DataFrame(columns=["日期", "客戶名稱", "樣品編號", "樣品名稱", "樣品數量"])
    
        # ===== session_state 初始化 =====
        if "form_sample" not in st.session_state:
            st.session_state.form_sample = {
                "日期": "",
                "客戶名稱": "",
                "樣品編號": "",
                "樣品名稱": "",
                "樣品數量": ""
            }
    
        # 初始化其他 session_state
        init_states({
            "edit_sample_index": None,
            "delete_sample_index": None,
            "show_delete_sample_confirm": False,
            "sample_search_triggered": False,
            "sample_filtered_df": pd.DataFrame(),
            "selected_sample_index": None
        })
    
        # ============================================================
        # 新增 / 修改 / 刪除 樣品（安全版）
        # ============================================================
        st.markdown(
            "<span style='color:#f1f5f2; font-weight:bold;'>☑️ 新增 / 修改 / 刪除 樣品</span>",
            unsafe_allow_html=True
        )
        
        # ===== 狀態初始化 =====
        if "sample_mode" not in st.session_state:
            st.session_state.sample_mode = "add"  # add / edit
        if "edit_sample_index" not in st.session_state:
            st.session_state.edit_sample_index = None
        if "form_sample" not in st.session_state:
            st.session_state.form_sample = {}
        if "last_selected_sample" not in st.session_state:
            st.session_state.last_selected_sample = None
        if "show_delete_sample_confirm" not in st.session_state:
            st.session_state.show_delete_sample_confirm = False
        if "delete_sample_index" not in st.session_state:
            st.session_state.delete_sample_index = None
        
        # ============================================================
        # 表單
        # ============================================================
        with st.form("form_sample_tab4"):
        
            c1, c2, c3 = st.columns(3)
        
            with c1:
                sample_date = st.date_input(
                    "日期",
                    value=safe_date(st.session_state.form_sample.get("日期")),
                    key="form_sample_date"
                )
        
            with c2:
                sample_customer = st.text_input(
                    "客戶名稱",
                    value=st.session_state.form_sample.get("客戶名稱", ""),
                    key="form_sample_customer"
                )
        
            with c3:
                sample_code = st.text_input(
                    "樣品編號",
                    value=st.session_state.form_sample.get("樣品編號", ""),
                    key="form_sample_code"
                )
        
            c4, c5 = st.columns(2)
        
            with c4:
                sample_name = st.text_input(
                    "樣品名稱",
                    value=st.session_state.form_sample.get("樣品名稱", ""),
                    key="form_sample_name"
                )
        
            with c5:
                sample_qty = st.text_input(
                    "樣品數量(g)",
                    value=st.session_state.form_sample.get("樣品數量", ""),
                    key="form_sample_qty"
                )
        
            submit = st.form_submit_button(
                "💾 儲存修改" if st.session_state.sample_mode == "edit" else "➕ 新增樣品"
            )
        
        # ============================================================
        # 儲存處理
        # ============================================================
        if submit:
            data = {
                "日期": sample_date,
                "客戶名稱": sample_customer.strip(),
                "樣品編號": sample_code.strip(),
                "樣品名稱": sample_name.strip(),
                "樣品數量": sample_qty.strip()
            }
        
            if not data["樣品編號"]:
                st.warning("⚠️ 請輸入樣品編號")
            else:
                if st.session_state.sample_mode == "edit":
                    # ===== 修改 =====
                    df_sample.loc[st.session_state.edit_sample_index] = data
                    st.success("✅ 樣品已更新")
                else:
                    # ===== 新增 =====
                    df_sample = pd.concat([df_sample, pd.DataFrame([data])], ignore_index=True)
                    st.success("✅ 新增完成")
        
                save_df_to_sheet(ws_sample, df_sample)
        
                # ===== 重置狀態 =====
                st.session_state.sample_mode = "add"
                st.session_state.edit_sample_index = None
                st.session_state.form_sample = {}
                st.session_state.last_selected_sample = None
        
                st.rerun()
        
        # ============================================================
        # 搜尋區
        # ============================================================
        st.markdown('<span style="color:#f1f5f2; font-weight:bold;">🔍 樣品記錄搜尋</span>', unsafe_allow_html=True)
        
        with st.form("sample_search_form"):
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                search_code = st.text_input("樣品編號")
            with s2:
                search_customer = st.text_input("客戶名稱")
            with s3:
                search_start = st.date_input("供樣日期（起）", value=None)
            with s4:
                search_end = st.date_input("供樣日期（迄）", value=None)
        
            do_search = st.form_submit_button("🔍 搜尋")
        
        if do_search:
            df_f = df_sample.copy()
        
            if search_code.strip():
                df_f = df_f[df_f["樣品編號"].astype(str).str.contains(search_code)]
        
            if search_customer.strip():
                df_f = df_f[df_f["客戶名稱"].astype(str).str.contains(search_customer)]
        
            if search_start:
                df_f = df_f[pd.to_datetime(df_f["日期"]) >= pd.to_datetime(search_start)]
        
            if search_end:
                df_f = df_f[pd.to_datetime(df_f["日期"]) <= pd.to_datetime(search_end)]
        
            st.session_state.sample_filtered_df = df_f.reset_index(drop=False)
            st.session_state.sample_search_triggered = True
        
        # ============================================================
        # 搜尋結果 → 選擇即進入「修改模式」 / 刪除
        # ============================================================
        if st.session_state.get("sample_search_triggered"):
            df_show = st.session_state.sample_filtered_df.copy()
        
            if df_show.empty:
                st.info("⚠️ 查無資料")
            else:
                options = [
                    f"{row['日期']}｜{row['樣品編號']}｜{row['樣品名稱']}"
                    for _, row in df_show.iterrows()
                ]
        
                selected = st.selectbox(
                    "選擇樣品以修改 / 刪除",
                    [""] + options,
                    index=0
                )
        
                # 只在「選擇改變時」才進入修改模式
                if selected and selected != st.session_state.last_selected_sample:
                    idx = options.index(selected)
                    real_index = df_show.iloc[idx]["index"]
        
                    st.session_state.sample_mode = "edit"
                    st.session_state.edit_sample_index = real_index
                    st.session_state.form_sample = df_sample.loc[real_index].to_dict()
                    st.session_state.last_selected_sample = selected
        
        # ============================================================
        # 刪除按鈕
        # ============================================================
        if st.session_state.sample_mode == "edit":
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ 刪除樣品"):
                    st.session_state.show_delete_sample_confirm = True
                    st.session_state.delete_sample_index = st.session_state.edit_sample_index
            with c2:
                st.write("")  # 空欄位保持對齊
        
        # ===== 刪除確認 =====
        if st.session_state.show_delete_sample_confirm and st.session_state.delete_sample_index is not None:
            r = df_sample.loc[st.session_state.delete_sample_index]
            st.warning(f"⚠️ 確定刪除 {r['樣品編號']} {r['樣品名稱']}？")
        
            c1, c2 = st.columns(2)
            with c1:
                if st.button("確認刪除"):
                    df_sample.drop(index=st.session_state.delete_sample_index, inplace=True)
                    df_sample.reset_index(drop=True, inplace=True)
                    save_df_to_sheet(ws_sample, df_sample)
                    st.session_state.show_delete_sample_confirm = False
                    st.session_state.edit_sample_index = None
                    st.session_state.form_sample = {}
                    st.session_state.sample_mode = "add"
                    st.session_state.last_selected_sample = None
                    st.rerun()
            with c2:
                if st.button("取消"):
                    st.session_state.show_delete_sample_confirm = False
                    st.rerun()
                    
# ======== 庫存區分頁 =========
elif menu == "庫存區":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    import pandas as pd
    from datetime import datetime, date
    import streamlit as st

    # 假設 client 已定義在更高層
    # 假設 df_recipe, df_order 已經從 session_state 載入
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())

    # 打開工作簿 & 工作表
    # ✅ 讀取庫存記錄表（改用 spreadsheet）
    try:
        ws_stock = get_cached_worksheet("庫存記錄")
        records = get_cached_sheet_df("庫存記錄").to_dict("records")
        if records:
            df_stock = pd.DataFrame(records)
        else:
            df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
    except:
        ws_stock = spreadsheet.add_worksheet("庫存記錄", rows=100, cols=10)
        ws_stock.append_row(["類型","色粉編號","日期","數量","單位","備註"])
        invalidate_sheet_cache("庫存記錄")
        df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])

    st.session_state.df_stock = df_stock

    # 工具：將 qty+unit 轉成 g
    def to_grams(qty, unit):
        try:
            q = float(qty or 0)
        except Exception:
            q = 0.0
        return q * 1000 if str(unit).lower() == "kg" else q

    # 顯示格式（g -> g 或 kg，保留小數）
    def format_usage(val_g):
        try:
            val = float(val_g or 0)
        except Exception:
            val = 0.0

        # kg 顯示
        if abs(val) >= 1000:
            kg = val / 1000.0
            return f"{kg:.2f} kg"

        # g 顯示（永遠保留 2 位）
        return f"{val:.2f} g"

    # ---------------- 計算用量函式 ----------------
    # ---------------- 計算用量函式（時間版） ----------------
    def calc_usage_for_stock(powder_id, df_order, df_recipe, start_dt, end_dt):
        total_usage_g = 0.0
    
        df_order_local = df_order.copy()
    
        # 必須有生產時間
        if "生產時間" not in df_order_local.columns:
            return 0.0
    
        df_order_local["生產時間"] = pd.to_datetime(
            df_order_local["生產時間"], errors="coerce"
        )
    
        # --- 1. 找到所有包含此色粉的配方 ---
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
    
        candidate_ids = set()
        if not df_recipe.empty:
            recipe_df_copy = df_recipe.copy()
            for c in powder_cols:
                if c not in recipe_df_copy.columns:
                    recipe_df_copy[c] = ""
    
            mask = recipe_df_copy[powder_cols].astype(str).apply(
                lambda row: powder_id in [s.strip() for s in row.values],
                axis=1
            )
            recipe_candidates = recipe_df_copy[mask].copy()
            candidate_ids = set(
                recipe_candidates["配方編號"].astype(str).str.strip().tolist()
            )
    
        if not candidate_ids:
            return 0.0
    
        # --- 2. 篩選「初始時間之後」的訂單（⭐ 核心） ---
        s_dt = pd.to_datetime(start_dt, errors="coerce")
        e_dt = pd.to_datetime(end_dt, errors="coerce")
    
        orders_in_range = df_order_local[
            (df_order_local["生產時間"].notna()) &
            (df_order_local["生產時間"] > s_dt) &
            (df_order_local["生產時間"] <= e_dt)
        ].copy()
    
        if orders_in_range.empty:
            return 0.0
    
        # --- 3. 逐張訂單計算用量 ---
        for _, order in orders_in_range.iterrows():
            order_recipe_id = str(order.get("配方編號", "")).strip()
            if not order_recipe_id:
                continue
    
            # 主配方 + 附加配方
            recipe_rows = []
    
            main_df = df_recipe[
                df_recipe["配方編號"].astype(str).str.strip() == order_recipe_id
            ]
            if not main_df.empty:
                recipe_rows.append(main_df.iloc[0].to_dict())
    
            if "配方類別" in df_recipe.columns and "原始配方" in df_recipe.columns:
                add_df = df_recipe[
                    (df_recipe["配方類別"].astype(str).str.strip() == "附加配方") &
                    (df_recipe["原始配方"].astype(str).str.strip() == order_recipe_id)
                ]
                if not add_df.empty:
                    recipe_rows.extend(add_df.to_dict("records"))
    
            # 計算包裝總量（kg）
            packs_total_kg = 0.0
            for j in range(1, 5):
                try:
                    packs_total_kg += float(order.get(f"包裝重量{j}", 0) or 0) * \
                                      float(order.get(f"包裝份數{j}", 0) or 0)
                except:
                    pass
    
            if packs_total_kg <= 0:
                continue
    
            # 計算色粉用量
            for rec in recipe_rows:
                pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                if powder_id not in pvals:
                    continue
    
                idx = pvals.index(powder_id) + 1
                try:
                    powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                except:
                    powder_weight = 0.0
    
                if powder_weight > 0:
                    total_usage_g += powder_weight * packs_total_kg
    
        return total_usage_g

    # ---------- 安全呼叫 Wrapper ----------
    def safe_calc_usage(pid, df_order, df_recipe, start_dt, end_dt):
        try:
            if pd.isna(start_dt) or pd.isna(end_dt) or start_dt > end_dt:
                return 0.0
            if df_order.empty or df_recipe.empty:
                return 0.0
            return calc_usage_for_stock(pid, df_order, df_recipe, start_dt, end_dt)
        except Exception as e:
            return 0.0

    # st.markdown('<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">🏭 庫存區</h1>', unsafe_allow_html=True)

    # ===== Tab 分頁 =====
    tab1, tab2, tab3, tab4 = st.tabs(["📦 初始庫存設定", "📊 庫存查詢", "🏆 色粉用量排行榜", "🧮 色粉用量查詢"])
    
    # ========== Tab 1：初始庫存設定 ==========
    with tab1:
    
        with st.form("form_ini_stock"):
            # 輸入欄位
            col1, col2, col3 = st.columns(3)
            ini_powder = col1.text_input("色粉編號", key="ini_color")
            ini_qty = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="ini_qty")
            ini_unit = col3.selectbox("單位", ["g", "kg"], key="ini_unit")
    
            # 日期與時間
            col4, col5 = st.columns(2)
            ini_date = col4.date_input("設定日期", value=datetime.today(), key="ini_date")
            ini_time = col5.time_input("設定時間", value=datetime.now().replace(microsecond=0).time(), key="ini_time")
    
            # 備註
            ini_note = st.text_input("備註", key="ini_note")
    
            # Form 提交按鈕
            submit = st.form_submit_button("💾 儲存初始庫存")
    
        if submit:
            # 防呆：檢查色粉編號
            if not ini_powder.strip():
                st.warning("⚠️ 請輸入色粉編號！")
                st.stop()
    
            powder_id = ini_powder.strip()
    
            # 防呆：數量轉 float
            try:
                qty_val = float(ini_qty)
            except:
                qty_val = 0.0
    
            # 組合成 datetime
            ini_datetime = pd.to_datetime(datetime.combine(ini_date, ini_time))
    
            # --- 刪掉舊的初始庫存（同色粉） ---
            df_stock = df_stock[~(
                (df_stock["類型"].astype(str).str.strip() == "初始") &
                (df_stock["色粉編號"].astype(str).str.strip() == powder_id)
            )]
    
            # --- 新增最新初始庫存 ---
            new_row = {
                "類型": "初始",
                "色粉編號": powder_id,
                "日期": ini_datetime,
                "數量": qty_val,
                "單位": ini_unit,
                "備註": ini_note
            }
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
    
            # --- 寫回 Google Sheet ---
            df_to_upload = df_stock.copy()
            df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce") \
                                          .dt.strftime("%Y/%m/%d %H:%M").fillna("")
    
            # gspread 安全清洗
            df_to_upload = df_to_upload.astype(object)
            df_to_upload = df_to_upload.where(pd.notnull(df_to_upload), "")
            df_to_upload = df_to_upload.applymap(lambda x: x.item() if hasattr(x, "item") else x)
    
            if ws_stock:
                ws_stock.clear()
                ws_stock.update([df_to_upload.columns.tolist()] + df_to_upload.values.tolist())
    
            # 同步 session_state
            st.session_state.df_stock = df_stock
    
            # 成功通知
            st.success(f"✅ 初始庫存已儲存\n色粉：{powder_id}\n數量：{qty_val} {ini_unit}")
    
    # ========== Tab 2：庫存查詢（Form 版） ==========
    with tab2:
    
        with st.form("form_stock_query"):
            # ===== 日期區間 =====
            col1, col2 = st.columns(2)
            query_start = col1.date_input("查詢起日", key="stock_start_query")
            query_end   = col2.date_input("查詢迄日", key="stock_end_query")
    
            # ===== 色粉 + 匹配模式 =====
            c_input, c_match = st.columns([3,1])
            with c_input:
                stock_powder = st.text_input("色粉編號", key="stock_powder")
            with c_match:
                match_mode = st.selectbox(
                    "匹配模式",
                    ["部分匹配", "精準匹配"],
                    index=0,
                    key="match_mode",
                    help="部分匹配：包含即可；精準匹配：必須完全相同"
                )
    
            # ===== 提交按鈕 =====
            submit = st.form_submit_button("計算庫存")
    
        # ===== 只有按下 submit 才計算 =====
        if submit:
            # 取值（確保來自 session_state）
            stock_powder = st.session_state.get("stock_powder", "").strip()
            match_mode   = st.session_state.get("match_mode", "部分匹配")
            query_start  = st.session_state.get("stock_start_query")
            query_end    = st.session_state.get("stock_end_query")
    
            # ---------- 前置處理 ----------
            df_stock_copy = df_stock.copy()
            df_stock_copy["日期"] = pd.to_datetime(df_stock_copy["日期"], errors="coerce").dt.normalize()
            df_stock_copy["日期時間"] = pd.to_datetime(df_stock_copy.get("日期時間", df_stock_copy["日期"]), errors="coerce")
            df_stock_copy["數量_g"] = df_stock_copy.apply(lambda r: to_grams(r["數量"], r["單位"]), axis=1)
            df_stock_copy["色粉編號"] = df_stock_copy["色粉編號"].astype(str).str.strip()
    
            df_order_copy = df_order.copy()
    
            # 取生產時間
            def get_order_datetime(row):
                if "生產時間" in row and pd.notna(row["生產時間"]):
                    return pd.to_datetime(row["生產時間"], errors="coerce")
                if "建立時間" in row and pd.notna(row["建立時間"]):
                    return pd.to_datetime(row["建立時間"], errors="coerce")
                if "生產日期" in row and pd.notna(row["生產日期"]):
                    dt = pd.to_datetime(row["生產日期"], errors="coerce")
                    if pd.notna(dt):
                        return dt + pd.Timedelta(hours=9)
                return pd.NaT
    
            df_order_copy["生產時間"] = df_order_copy.apply(get_order_datetime, axis=1)
    
            # ---------- 色粉清單 ----------
            stock_powder = stock_powder.strip()
            
            if stock_powder and match_mode == "精準匹配":
                # 👉 精準匹配：只查這一個
                all_pids = [stock_powder]
            
            else:
                # 👉 只有「部分匹配 / 未輸入」才建立完整清單
                all_pids_stock = (
                    df_stock_copy["色粉編號"].dropna().astype(str).str.strip().unique().tolist()
                    if not df_stock_copy.empty else []
                )
            
                all_pids_recipe = []
                if not df_recipe.empty:
                    for i in range(1, 9):
                        col = f"色粉編號{i}"
                        if col in df_recipe.columns:
                            all_pids_recipe.extend(
                                df_recipe[col].dropna().astype(str).str.strip().tolist()
                            )
            
                all_pids_all = sorted(set(all_pids_stock) | set(all_pids_recipe))
            
                if stock_powder:
                    all_pids = [
                        pid for pid in all_pids_all
                        if stock_powder.lower() in pid.lower()
                    ]
                    if not all_pids:
                        st.warning(f"⚠️ 查無與 '{stock_powder}' 相關的色粉記錄。")
                        st.stop()
                else:
                    all_pids = all_pids_all
            
    
            if not all_pids:
                st.warning("⚠️ 查無任何色粉記錄。")
                st.stop()
    
            # ---------- 時間區間 ----------
            today_dt = pd.Timestamp.now()
            start_dt = pd.to_datetime(query_start) if query_start else pd.Timestamp.min
            end_dt   = pd.to_datetime(query_end) + pd.Timedelta(hours=23, minutes=59, seconds=59) if query_end else today_dt
            if start_dt > end_dt:
                st.error("❌ 查詢起日不能晚於查詢迄日。")
                st.stop()
    
            # ---------- 核心計算 ----------
            def safe_format(x):
                try:
                    return format_usage(x)
                except:
                    return "0"
    
            if "last_final_stock" not in st.session_state:
                st.session_state["last_final_stock"] = {}
    
            stock_summary = []
    
            for pid in all_pids:
                df_pid = df_stock_copy[df_stock_copy["色粉編號"] == pid].copy()
    
                # (A) 最新期初
                df_ini = df_pid[df_pid["類型"].astype(str).str.strip() == "初始"]
                if not df_ini.empty:
                    latest_ini = df_ini.sort_values("日期時間", ascending=False).iloc[0]
                    ini_value = latest_ini["數量_g"]
                    ini_dt = latest_ini["日期時間"]
                    ini_note = f"期初來源：{ini_dt.strftime('%Y/%m/%d %H:%M')}"
                else:
                    ini_value = 0.0
                    ini_dt = pd.Timestamp.min
                    ini_note = "—"
    
                # (B) 區間進貨
                in_qty = df_pid[
                    (df_pid["類型"].astype(str).str.strip() == "進貨") &
                    (df_pid["日期時間"] > ini_dt) &
                    (df_pid["日期時間"] <= end_dt)
                ]["數量_g"].sum()
    
                # (C) 區間用量
                usage_qty = (
                    safe_calc_usage(pid, df_order_copy, df_recipe, ini_dt, end_dt)
                    if not df_order.empty and not df_recipe.empty
                    else 0.0
                )
    
                # 期末庫存
                final_g = ini_value + in_qty - usage_qty
                st.session_state["last_final_stock"][pid] = final_g
    
                # 過濾特例色粉
                if not str(pid).endswith(("01", "001", "0001")):
                    stock_summary.append({
                        "色粉編號": pid,
                        "期初庫存": safe_format(ini_value),
                        "區間進貨": safe_format(in_qty),
                        "區間用量": safe_format(usage_qty),
                        "期末庫存": safe_format(final_g),
                        "備註": ini_note,
                    })
    
            # ---------- 顯示結果 ----------
            df_result = pd.DataFrame(stock_summary)
            st.dataframe(df_result, use_container_width=True, hide_index=True)
            st.caption("ℹ️ 庫存僅扣除期初庫存儲存後之生產單（含當日）")
    
    
            st.caption(
                "🌟 期末庫存 = 期初庫存（時間點） + 其後進貨 − 其後用量（單位皆以 g 計算）"
            )

    # ========== Tab 3：色粉用量排行榜 ==========
    with tab3:
        # 日期區間選擇
        col1, col2 = st.columns(2)
        rank_start = col1.date_input("開始日期（排行榜）", key="rank_start_date")
        rank_end = col2.date_input("結束日期（排行榜）", key="rank_end_date")

        if st.button("生成排行榜", key="btn_powder_rank"):
            df_order_copy = df_order.copy()
            df_recipe_copy = df_recipe.copy()

            powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
            weight_cols = [f"色粉重量{i}" for i in range(1, 9)]
            for c in powder_cols + weight_cols + ["配方編號", "配方類別", "原始配方"]:
                if c not in df_recipe_copy.columns:
                    df_recipe_copy[c] = ""

            if "生產日期" in df_order_copy.columns:
                df_order_copy["生產日期"] = pd.to_datetime(df_order_copy["生產日期"], errors="coerce")
            else:
                df_order_copy["生產日期"] = pd.NaT

            # 過濾日期區間
            orders_in_range = df_order_copy[
                (df_order_copy["生產日期"].notna()) &
                (df_order_copy["生產日期"] >= pd.to_datetime(rank_start)) &
                (df_order_copy["生產日期"] <= pd.to_datetime(rank_end))
            ]

            pigment_usage = {}

            # 計算所有色粉用量
            for _, order in orders_in_range.iterrows():
                order_recipe_id = str(order.get("配方編號", "")).strip()
                if not order_recipe_id:
                    continue

                # 主配方 + 附加配方
                recipe_rows = []
                main_df = df_recipe_copy[df_recipe_copy["配方編號"].astype(str) == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
                add_df = df_recipe_copy[
                    (df_recipe_copy["配方類別"] == "附加配方") &
                    (df_recipe_copy["原始配方"].astype(str) == order_recipe_id)
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

            # 生成 DataFrame
            df_rank = pd.DataFrame([
                {"色粉編號": k, "總用量_g": v} for k, v in pigment_usage.items()
            ])

            # 排序
            df_rank = df_rank.sort_values("總用量_g", ascending=False).reset_index(drop=True)
            df_rank["總用量"] = df_rank["總用量_g"].map(format_usage)
            df_rank = df_rank[["色粉編號", "總用量"]]
            st.dataframe(df_rank, use_container_width=True, hide_index=True)

            # 下載 CSV
            csv = pd.DataFrame(list(pigment_usage.items()), columns=["色粉編號", "總用量(g)"]).to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="⬇️ 下載排行榜 CSV",
                data=csv,
                file_name=f"powder_rank_{rank_start}_{rank_end}.csv",
                mime="text/csv"
            )
    
    # ========== Tab 4：色粉用量查詢 ==========
    with tab4:
    
        with st.form("form_powder_usage"):
            st.markdown("**🔍 色粉用量查詢**")
    
            # 四個色粉編號輸入框
            cols = st.columns(4)
            powder_inputs = []
            for i in range(4):
                val = cols[i].text_input(f"色粉編號{i+1}", key=f"usage_color_{i}")
                if val.strip():
                    powder_inputs.append(val.strip())
    
            # 日期區間選擇
            col1, col2 = st.columns(2)
            start_date = col1.date_input("開始日期", key="usage_start_date")
            end_date = col2.date_input("結束日期", key="usage_end_date")
    
            # 提交按鈕
            submit = st.form_submit_button("查詢用量")
    
        if submit and powder_inputs:
            results = []
            df_order_local = st.session_state.get("df_order", pd.DataFrame()).copy()
            df_recipe_local = st.session_state.get("df_recipe", pd.DataFrame()).copy()
    
            # 確保欄位存在，避免 KeyError
            powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
            for c in powder_cols + ["配方編號", "配方類別", "原始配方", "配方名稱", "顏色", "客戶名稱"]:
                if c not in df_recipe_local.columns:
                    df_recipe_local[c] = ""
    
            if "生產日期" in df_order_local.columns:
                df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
            else:
                df_order_local["生產日期"] = pd.NaT
    
            def format_usage(val):
                if val >= 1000:
                    kg = val / 1000
                    return f"{int(kg) if kg == int(kg) else round(kg,2)} kg"
                else:
                    return f"{int(val) if val == int(val) else round(val,2)} g"
    
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
    
            # ---- 以下原本計算邏輯照舊 ----
            for powder_id in powder_inputs:
                total_usage_g = 0.0
                monthly_usage = {}
    
                # 1) 先從配方管理找出「候選配方」
                if not df_recipe_local.empty:
                    mask = df_recipe_local[powder_cols].astype(str).apply(lambda row: powder_id in row.values, axis=1)
                    recipe_candidates = df_recipe_local[mask].copy()
                    candidate_ids = set(recipe_candidates["配方編號"].astype(str).tolist())
                else:
                    recipe_candidates = pd.DataFrame()
                    candidate_ids = set()
    
                # 2) 過濾生產單日期區間
                orders_in_range = df_order_local[
                    (df_order_local["生產日期"].notna()) &
                    (df_order_local["生產日期"] >= pd.to_datetime(start_date)) &
                    (df_order_local["生產日期"] <= pd.to_datetime(end_date))
                ]
    
                # 3) 計算用量
                for _, order in orders_in_range.iterrows():
                    order_recipe_id = str(order.get("配方編號", "")).strip()
                    if not order_recipe_id:
                        continue
    
                    recipe_rows = []
                    main_df = df_recipe_local[df_recipe_local["配方編號"].astype(str) == order_recipe_id]
                    if not main_df.empty:
                        recipe_rows.append(main_df.iloc[0].to_dict())
                    add_df = df_recipe_local[
                        (df_recipe_local["配方類別"] == "附加配方") &
                        (df_recipe_local["原始配方"].astype(str) == order_recipe_id)
                    ]
                    if not add_df.empty:
                        recipe_rows.extend(add_df.to_dict("records"))
    
                    order_total_for_powder = 0.0
                    sources_main = set()
                    sources_add = set()
    
                    packs_total = 0.0
                    for j in range(1, 5):
                        w_val = order.get(f"包裝重量{j}", 0)
                        n_val = order.get(f"包裝份數{j}", 0)
                        try: packs_total += float(w_val or 0) * float(n_val or 0)
                        except: pass
    
                    if packs_total <= 0: continue
    
                    for rec in recipe_rows:
                        rec_id = str(rec.get("配方編號", "")).strip()
                        if rec_id not in candidate_ids: continue
    
                        pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                        if powder_id not in pvals: continue
                        idx = pvals.index(powder_id) + 1
                        try: powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                        except: powder_weight = 0.0
                        if powder_weight <= 0: continue
    
                        contrib = powder_weight * packs_total
                        order_total_for_powder += contrib
                        disp_name = recipe_display_name(rec)
                        if str(rec.get("配方類別", "")).strip() == "附加配方":
                            sources_add.add(disp_name)
                        else:
                            sources_main.add(disp_name)
    
                    if order_total_for_powder <= 0: continue
    
                    od = order["生產日期"]
                    if pd.isna(od): continue
                    month_key = od.strftime("%Y/%m")
                    if month_key not in monthly_usage:
                        monthly_usage[month_key] = {"usage": 0.0, "main_recipes": set(), "additional_recipes": set()}
    
                    monthly_usage[month_key]["usage"] += order_total_for_powder
                    monthly_usage[month_key]["main_recipes"].update(sources_main)
                    monthly_usage[month_key]["additional_recipes"].update(sources_add)
                    total_usage_g += order_total_for_powder
    
                # 4) 輸出每月用量 & 總用量
                months_sorted = sorted(monthly_usage.keys())
                for month in months_sorted:
                    data = monthly_usage[month]
                    usage_g = data["usage"]
                    if usage_g <= 0: continue
                    per = pd.Period(month, freq="M")
                    month_start = per.start_time.date()
                    month_end = per.end_time.date()
                    disp_start = max(start_date, month_start)
                    disp_end = min(end_date, month_end)
                    date_disp = month if (disp_start == month_start and disp_end == month_end) else f"{disp_start.strftime('%Y/%m/%d')}~{disp_end.strftime('%m/%d')}"
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
                return [
                    'font-weight: bold; background-color: #333333; color: white' if s.name in df_usage.index and df_usage.loc[s.name, "來源區間"] == "總用量" and col in ["色粉編號", "來源區間", "月用量"] else ''
                    for col in s.index
                ]
    
            styled = df_usage.style.apply(highlight_total_row, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

# ===== 匯入配方備份檔案 =====
if st.session_state.menu == "匯入備份":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 📌 標題
    # st.markdown(
    #     '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📊 匯入備份</h2>',
    #     unsafe_allow_html=True
    # )

    # 📌 前往收帳查詢系統
    st.markdown(
        """
        <a href="https://paylist.streamlit.app/" target="_blank">
            <div style="
                display:inline-block;
                padding:6px 12px;
                background:#dbd818;
                color:black;
                border-radius:6px;
                margin-bottom:10px;
            ">
                🔗 前往收帳查詢系統
            </div>
        </a>
        """,
        unsafe_allow_html=True
    )
  
    # ===== 讀取備份函式 =====
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

    # ===== 上傳檔案 =====
    uploaded_file = st.file_uploader("請上傳備份 Excel (.xlsx)", type=["xlsx"], key="upload_backup")

    if uploaded_file:
        df_uploaded = load_recipe_backup_excel(uploaded_file)
        if df_uploaded is not None:
            st.session_state.df_recipe = df_uploaded
            st.success("✅ 成功匯入備份檔！")
            st.dataframe(df_uploaded.head())
