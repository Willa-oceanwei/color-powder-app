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

# ======== 🎨 終極版自訂樣式（穩定版 Selectbox）========
# ======== 🎨 完整修正版樣式 ========
def apply_modern_style():
    st.markdown("""
    <style>
    /* ===== 全域字體 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', 'Microsoft JhengHei', sans-serif;
    }
    
    /* ===== 主背景統一 ===== */
    .stApp {
        background: #252538 !important;
    }
    
    .main .block-container {
        background: #252538 !important;
        padding: 2rem;
    }
    
    /* ===== Sidebar 樣式 ===== */
    section[data-testid="stSidebar"] {
        background: #1a1a2e !important;
        border-right: 1px solid rgba(249, 220, 92, 0.15);
    }
    
    section[data-testid="stSidebar"] h1 {
        color: #F9DC5C;
        font-weight: 700;
        font-size: 22px;
        padding: 0 1rem;
        margin-bottom: 1.5rem;
    }
    
    /* ===== Sidebar 未選中 ===== */
    section[data-testid="stSidebar"] div.stButton > button[kind="secondary"] {
        background: #252538 !important;
        color: #E8E8E8 !important;
        border: 1px solid rgba(249, 220, 92, 0.15) !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
        text-align: left !important;
        width: 100% !important;
    }
    
    /* Hover（未選中） */
    section[data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {
        background: #2d2d44 !important;
        color: #F9DC5C !important;
        border-color: rgba(249, 220, 92, 0.4) !important;
    }
    
    /* ===== 🔥 Sidebar 選中（填滿黃色）===== */
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #F9DC5C 0%, #E8C547 100%) !important;
        color: #1a1a2e !important;
        border: 1px solid #F9DC5C !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(249, 220, 92, 0.35) !important;
    }
    
    /* 選中狀態 hover 不變（避免閃爍） */
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #F9DC5C 0%, #E8C547 100%) !important;
        color: #1a1a2e !important;
    }
    
    /* ===== 🎯 移除 Sidebar 選中按鈕的勾勾 ===== */
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"]::before {
        content: none !important;
        display: none !important;
    }
    
    section[data-testid="stSidebar"] div.stButton > button svg {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] div.stButton > button span[data-testid="stMarkdownContainer"] {
        padding-left: 0 !important;
    }
    
    /* ===== 主內容區按鈕樣式 ===== */
    .main div.stButton > button {
        background: #1a1a2e !important;
        color: #E8E8E8 !important;
        border: 1px solid rgba(249, 220, 92, 0.2) !important;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .main div.stButton > button:hover {
        background: #F9DC5C !important;
        color: #1a1a2e !important;
        border-color: #F9DC5C !important;
        transform: translateY(-1px);
    }
    
    /* ===== 🔥 統一輸入框高度（50px）===== */
    div.stTextInput > div > div > input,
    div.stNumberInput > div > div > input,
    div.stTextArea > div > div > textarea,
    div.stDateInput > div > div > input {
        background: #2d2d44 !important;
        border: 1px solid rgba(249, 220, 92, 0.2) !important;
        border-radius: 6px;
        color: #E8E8E8 !important;
        padding: 0.6rem 0.75rem !important;
        min-height: 50px !important;
        height: 50px !important;
        transition: all 0.3s ease;
        box-sizing: border-box !important;
    }
    
    /* TextArea 例外（可多行） */
    div.stTextArea > div > div > textarea {
        min-height: 100px !important;
        height: auto !important;
    }
    
    /* 🔥 Focus 統一改黃色 */
    div.stTextInput > div > div > input:focus,
    div.stNumberInput > div > div > input:focus,
    div.stTextArea > div > div > textarea:focus,
    div.stDateInput > div > div > input:focus {
        border-color: #F9DC5C !important;
        box-shadow: 0 0 0 2px rgba(249, 220, 92, 0.2) !important;
        outline: none !important;
    }
    
    /* 🔥 移除 Streamlit 預設的紅色 focus ring */
    div.stTextInput > div > div > input:focus-visible,
    div.stNumberInput > div > div > input:focus-visible,
    div.stTextArea > div > div > textarea:focus-visible,
    div.stDateInput > div > div > input:focus-visible {
        outline: none !important;
        box-shadow: 0 0 0 2px rgba(249, 220, 92, 0.2) !important;
    }
    
    /* ===== 🎯 下拉選單統一高度為 50px ===== */
    div.stSelectbox > div > div {
        background: #2d2d44 !important;
        border: 1px solid rgba(249, 220, 92, 0.2) !important;
        border-radius: 6px !important;
        min-height: 50px !important;
        height: 50px !important;
        padding: 0 !important;
        transition: all 0.3s ease;
        box-sizing: border-box !important;
    }
    
    /* 🔥 下拉選單 Focus 也改黃色 */
    div.stSelectbox > div > div:focus-within {
        border-color: #F9DC5C !important;
        box-shadow: 0 0 0 2px rgba(249, 220, 92, 0.2) !important;
    }
    
    div.stSelectbox div[data-baseweb="select"] {
        background: #2d2d44 !important;
        min-height: 50px !important;
        height: 50px !important;
        border: none !important;
    }
    
    div.stSelectbox div[data-baseweb="select"] > div {
        background: #2d2d44 !important;
        min-height: 50px !important;
        height: 50px !important;
        padding: 0 0.75rem !important;
        display: flex !important;
        align-items: center !important;
        box-sizing: border-box !important;
    }
    
    div.stSelectbox div[data-baseweb="select"] > div > div {
        color: #E8E8E8 !important;
        line-height: 1.5 !important;
        padding: 0 !important;
        white-space: normal !important;
        overflow: visible !important;
    }
    
    div.stSelectbox svg {
        color: #E8E8E8 !important;
    }
    
    /* ===== 🎯 修正標籤位置（確保對齊）===== */
    div.stTextInput > label,
    div.stNumberInput > label,
    div.stSelectbox > label,
    div.stDateInput > label,
    div.stTextArea > label {
        color: #E8E8E8 !important;
        font-size: 0.875rem !important;
        margin-bottom: 0.5rem !important;
        display: block !important;
    }
    
    /* 彈出層 */
    div[data-baseweb="popover"] {
        background: #2d2d44 !important;
        border: 1px solid rgba(249, 220, 92, 0.3) !important;
        border-radius: 8px !important;
        margin-top: 4px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4) !important;
    }
    
    ul[role="listbox"] {
        background: #2d2d44 !important;
        padding: 0.5rem 0 !important;
        max-height: 400px !important;
        overflow-y: auto !important;
    }
    
    ul[role="listbox"] li {
        background: #2d2d44 !important;
        color: #E8E8E8 !important;
        padding: 1rem 1.2rem !important;
        min-height: 52px !important;
        line-height: 1.8 !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow: visible !important;
        display: flex !important;
        align-items: center !important;
        transition: all 0.2s ease !important;
    }
    
    ul[role="listbox"] li:hover {
        background: #3a3a52 !important;
        color: #F9DC5C !important;
    }
    
    ul[role="listbox"] li[aria-selected="true"] {
        background: rgba(249, 220, 92, 0.15) !important;
        color: #F9DC5C !important;
        font-weight: 600 !important;
    }
    
    div[data-baseweb="select"] span,
    ul[role="listbox"] li span,
    ul[role="listbox"] li div,
    ul[role="listbox"] li > * {
        color: inherit !important;
        white-space: normal !important;
        overflow: visible !important;
        line-height: 1.8 !important;
        max-width: 100% !important;
        overflow-wrap: break-word !important;
    }
    
    /* ===== Checkbox ===== */
    div.stCheckbox label {
        color: #E8E8E8 !important;
    }
    
    div.stCheckbox input[type="checkbox"] {
        accent-color: #F9DC5C !important;
    }
    
    div.stCheckbox input[type="checkbox"]:focus {
        outline: 2px solid rgba(249, 220, 92, 0.5) !important;
        outline-offset: 2px;
    }
    
    /* ===== 表格樣式 ===== */
    div.stDataFrame {
        background: #252538 !important;
        border-radius: 8px;
        border: 1px solid rgba(249, 220, 92, 0.15);
    }
    
    div.stDataFrame thead tr th {
        background: #1a1a2e !important;
        color: #F9DC5C !important;
        font-weight: 600;
        border-bottom: 2px solid rgba(249, 220, 92, 0.3) !important;
    }
    
    div.stDataFrame tbody tr {
        background: #252538 !important;
        color: #E8E8E8 !important;
    }
    
    div.stDataFrame tbody tr:hover {
        background: #2d2d44 !important;
    }
    
    /* ===== Tab 樣式 ===== */
    div[data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid rgba(249, 220, 92, 0.2) !important;
    }
    
    button[data-baseweb="tab"] {
        background: transparent !important;
        color: #A8A8B8 !important;
        border: none !important;
        border-bottom: 3px solid transparent !important;
        font-weight: 500;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s ease;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #F9DC5C !important;
        background: transparent !important;
        border-bottom-color: rgba(249, 220, 92, 0.3) !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #F9DC5C !important;
        background: transparent !important;
        border-bottom-color: #F9DC5C !important;
        font-weight: 600 !important;
    }
    
    div[data-baseweb="tab-panel"] {
        background: #252538 !important;
        padding: 1.5rem !important;
    }
    
    /* ===== Form ===== */
    form {
        background: rgba(26, 26, 46, 0.5) !important;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid rgba(249, 220, 92, 0.15);
    }
    
    /* ===== 標題 ===== */
    h1, h2, h3, h4, h5, h6 {
        color: #F9DC5C !important;
    }
    
    /* ===== 提示框 ===== */
    div.stAlert {
        background: rgba(249, 220, 92, 0.1) !important;
        border-left: 4px solid #F9DC5C !important;
        color: #E8E8E8 !important;
    }
    
    div.stSuccess {
        background: rgba(76, 175, 80, 0.1) !important;
        border-left-color: #4CAF50 !important;
    }
    
    div.stWarning {
        background: rgba(255, 152, 0, 0.1) !important;
        border-left-color: #FF9800 !important;
    }
    
    div.stError {
        background: rgba(244, 67, 54, 0.1) !important;
        border-left-color: #F44336 !important;
    }
    
    /* ===== 捲軸 ===== */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1a1a2e;
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(249, 220, 92, 0.3);
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(249, 220, 92, 0.5);
    }
    
    /* ===== Expander ===== */
    div.streamlit-expanderHeader {
        background: #2d2d44 !important;
        border: 1px solid rgba(249, 220, 92, 0.2) !important;
        border-radius: 6px;
        color: #E8E8E8 !important;
        transition: all 0.3s ease;
    }
    
    div.streamlit-expanderHeader:hover {
        background: #3a3a52 !important;
        border-color: #F9DC5C !important;
    }
    
    div.streamlit-expanderContent {
        background: #252538 !important;
        border: 1px solid rgba(249, 220, 92, 0.15);
        border-top: none;
    }
    
    /* ===== Code Block ===== */
    code {
        background: #1a1a2e !important;
        color: #F9DC5C !important;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
    }
    
    pre {
        background: #1a1a2e !important;
        border: 1px solid rgba(249, 220, 92, 0.2);
        border-radius: 6px;
        padding: 1rem;
    }
    
    /* ===== File Uploader ===== */
    div[data-testid="stFileUploader"] {
        background: #2d2d44 !important;
        border: 1px dashed rgba(249, 220, 92, 0.3) !important;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stFileUploader"]:hover {
        border-color: #F9DC5C !important;
        background: #3a3a52 !important;
    }
    
    /* ===== 下載按鈕 ===== */
    div.stDownloadButton > button {
        background: #1a1a2e !important;
        color: #F9DC5C !important;
        border: 1px solid rgba(249, 220, 92, 0.3) !important;
        transition: all 0.3s ease;
    }
    
    div.stDownloadButton > button:hover {
        background: #F9DC5C !important;
        color: #1a1a2e !important;
    }
    
    /* ===== 🔥 移除所有預設 Focus 樣式衝突 ===== */
    *:focus-visible {
        outline: none !important;
    }
    
    input:focus-visible,
    textarea:focus-visible,
    select:focus-visible,
    button:focus-visible {
        outline: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
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

menu_options = ["客戶名單", "配方管理", "生產單管理", 
                "查詢區", "庫存區", "代工管理", "採購管理", "匯入備份"]

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
    st.markdown('<h1 style="font-size:22px;">🌈配方管理系統</h1>', unsafe_allow_html=True)

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
        ws_recipe = spreadsheet.worksheet("配方管理")
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
        ws_recipe = spreadsheet.worksheet("配方管理")
        values = ws_recipe.get_all_values()
        if len(values) > 1:
            df_loaded = pd.DataFrame(values[1:], columns=values[0])
        else:
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
            ws_recipe = spreadsheet.worksheet("配方管理")
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
        ws_customer = spreadsheet.worksheet("客戶名單")
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
        df = pd.DataFrame(ws_customer.get_all_records())
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
        '<h2 style="font-size:16px; font-family:Arial; color:#dbd818;">🤖 新增 / 編輯客戶</h2>',
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
    st.markdown('<h2 style="font-size:16px; font-family:Arial; color:#dbd818;">🛠️ 客戶修改 / 刪除</h2>', unsafe_allow_html=True)
    
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
elif menu == "配方管理":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    from pathlib import Path
    from datetime import datetime
    import pandas as pd
    import streamlit as st

    # ------------------- 配方資料初始化 -------------------
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = load_recipe_data()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    # 統一使用 df_recipe
    df_recipe = st.session_state.df_recipe

    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "重要提醒", "備註", "建檔時間"
    ]

    # 載入 Google Sheet 工作表
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except:
        try:
            ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)
        except:
            st.error("❌ 無法建立工作表")
            st.stop()

    # 讀取原始資料
    values = ws_recipe.get_all_values()
    if len(values) > 1:
        df_loaded = pd.DataFrame(values[1:], columns=values[0])
    else:
        df_loaded = pd.DataFrame(columns=columns)
    
    # 補齊缺少欄位
    for col in columns:
        if col not in df_loaded.columns:
            df_loaded[col] = ""
    
    # 清理配方編號
    if "配方編號" in df_loaded.columns:
        df_loaded["配方編號"] = df_loaded["配方編號"].astype(str).map(clean_powder_id)
    
    st.session_state.df = df_loaded
    st.session_state.df_recipe = df_loaded  # ✅ 雙向同步
    df = st.session_state.df
    
    # === 載入「色粉管理」的色粉清單 ===
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
    
    # 載入客戶名單（提前載入，供所有 Tab 使用）
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customers = pd.DataFrame(ws_customer.get_all_records())
        customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]
    except:
        st.warning("⚠️ 無法載入客戶名單")
        customer_options = []

    # =============== Tab 架構開始 ===============
    st.markdown('<h1 style="font-size:24px; color:#F9DC5C;">🌈 配方管理</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📝 配方建立", "📊 配方記錄表", "👀 配方預覽/修改/刪除", "🪅 色粉管理"])
    
    # ============================================================
    # Tab 1: 配方建立
    # ============================================================
    with tab1:
        
        # ===== 初始化欄位 =====
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
            
        with st.form("recipe_form"):
            # 基本欄位
            col1, col2, col3 = st.columns(3)
            with col1:
                fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="form_recipe_配方編號")
            with col2:
                fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="form_recipe_顏色")
            with col3:
                options = [""] + customer_options
                current = f"{fr.get('客戶編號','')} - {fr.get('客戶名稱','')}" if fr.get("客戶編號") else ""
                index = options.index(current) if current in options else 0

                selected = st.selectbox(
                    "客戶編號",
                    options,
                    index=index,
                    key="form_recipe_selected_customer"
                )

                if selected and " - " in selected:
                    c_no, c_name = selected.split(" - ", 1)
                    fr["客戶編號"] = c_no.strip()
                    fr["客戶名稱"] = c_name.strip()
       
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
        
            # CSS：縮小輸入框高度及上下間距
            st.markdown("""
            <style>
            div.stTextInput > div > div > input {
                padding: 2px 6px !important;
                height: 36px !important;
                font-size: 16px;
            }
            div.stTextInput {
                margin-top: 0px !important;
                margin-bottom: 0px !important;
            }
            [data-testid="stVerticalBlock"] > div[style*="gap"] {
                gap: 0px !important;
                margin-bottom: 0px !important;
            }
            section[data-testid="stHorizontalBlock"] {
                padding-top: -2px !important;
                padding-bottom: -2px !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # 色粉設定多列
            st.markdown("##### 色粉設定")
            for i in range(1, st.session_state.get("num_powder_rows", 5) + 1):
                c1, c2 = st.columns([2.5, 2.5])
        
                fr[f"色粉編號{i}"] = c1.text_input(
                    "",  
                    value=fr.get(f"色粉編號{i}", ""), 
                    placeholder=f"色粉{i}編號",
                    key=f"form_recipe_色粉編號{i}"
                )
        
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
        
            # 儲存配方邏輯
            if fr["配方編號"].strip() == "":
                st.warning("⚠️ 請輸入配方編號！")
            elif fr["配方類別"] == "附加配方" and fr["原始配方"].strip() == "":
                st.warning("⚠️ 附加配方必須填寫原始配方！")
            else:
                if st.session_state.get("edit_recipe_index") is not None:
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
                    order_file = Path("data/df_recipe.csv")
                    order_file.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(order_file, index=False, encoding="utf-8-sig")
                except Exception as e:
                    st.error(f"❌ 儲存失敗：{e}")
                    st.stop()
        
                st.session_state.df = df
                st.session_state.df_recipe = df  # ✅ 雙向同步
                st.session_state.form_recipe = {col: "" for col in columns}
                st.session_state.edit_recipe_index = None
                st.rerun()
      
        # === 處理新增色粉列 ===
        if add_powder and not st.session_state.add_powder_clicked:
            st.session_state.num_powder_rows = st.session_state.get("num_powder_rows", 5) + 1
            st.session_state.add_powder_clicked = True
            st.rerun()
        elif submitted:
            # 儲存時重置 flag
            st.session_state.add_powder_clicked = False
        else:
            # 其他情況重置 flag
            st.session_state.add_powder_clicked = False
      
        # === 處理新增色粉列 ===
        if add_powder:
            if st.session_state.num_powder_rows < 8:
                st.session_state.num_powder_rows += 1
                st.rerun()

# ============================================================
    # ============================================================
    # Tab 2: 配方記錄表（穩定第一）
    # ============================================================
    with tab2:
    
        if df.empty:
            st.info("目前無資料")
            df_filtered = df.copy()
    
        else:
            # ===== 搜尋欄位 =====
            col1, col2, col3 = st.columns(3)
            with col1:
                search_recipe = st.text_input("配方編號", key="search_recipe_tab2")
            with col2:
                search_customer = st.text_input("客戶名稱或編號", key="search_customer_tab2")
            with col3:
                search_pantone = st.text_input("Pantone色號", key="search_pantone_tab2")
    
            recipe_kw = search_recipe.strip()
            customer_kw = search_customer.strip()
            pantone_kw = search_pantone.strip()
    
            # ===== 搜尋簽章（用來鎖版型）=====
            search_signature = f"{recipe_kw}|{customer_kw}|{pantone_kw}"
            if "last_search_signature_tab2" not in st.session_state:
                st.session_state.last_search_signature_tab2 = search_signature
    
            # ===== 篩選資料 =====
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
                mask &= df["Pantone色號"].astype(str).str.replace(" ", "").str.upper().str.contains(
                    pantone_kw_clean, na=False
                )
    
            df_filtered = df[mask]
    
            # ===== 分頁資料 =====
            total_rows = df_filtered.shape[0]
    
            # ===== 只在「搜尋改變」時決定欄位數 =====
            if search_signature != st.session_state.last_search_signature_tab2:
                st.session_state.page_tab2 = 1
    
                if total_rows <= 5:
                    st.session_state.recipe_cols_tab2 = 1
                elif total_rows <= 20:
                    st.session_state.recipe_cols_tab2 = 2
                else:
                    st.session_state.recipe_cols_tab2 = 3
    
                st.session_state.last_search_signature_tab2 = search_signature
    
            # ===== 搜尋結果提示 =====
            if recipe_kw or customer_kw or pantone_kw:
                st.info(
                    f"🔍 搜尋結果：共 {total_rows} 筆資料｜"
                    f"詳細資料固定為 {st.session_state.get('recipe_cols_tab2', 1)} 欄顯示"
                )
    
            # ===== 分頁設定 =====
            limit_options = [1, 5, 10, 20, 50, 100]
    
            # ⭐ 修正 1：只讀 state，不用 selectbox 回傳值
            if "limit_per_page_tab2" not in st.session_state:
                st.session_state.limit_per_page_tab2 = 1
    
            limit = st.session_state.limit_per_page_tab2
    
            # ⭐ 修正 2：偵測 limit 變更，立刻重置頁碼
            if "last_limit_tab2" not in st.session_state:
                st.session_state.last_limit_tab2 = limit
    
            if st.session_state.last_limit_tab2 != st.session_state.limit_per_page_tab2:
                st.session_state.page_tab2 = 1
                st.session_state.last_limit_tab2 = st.session_state.limit_per_page_tab2
    
            total_pages = max((total_rows - 1) // limit + 1, 1)
    
            if "page_tab2" not in st.session_state:
                st.session_state.page_tab2 = 1
    
            if st.session_state.page_tab2 > total_pages:
                st.session_state.page_tab2 = total_pages
    
            start_idx = (st.session_state.page_tab2 - 1) * limit
            end_idx = start_idx + limit
            page_data = df_filtered.iloc[start_idx:end_idx]
    
            # ===== 顯示表格 =====
            show_cols = ["配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方", "Pantone色號"]
            existing_cols = [c for c in show_cols if c in page_data.columns]
    
            if not page_data.empty:
                st.dataframe(
                    page_data[existing_cols].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True
                )
    
            else:
                if recipe_kw or customer_kw or pantone_kw:
                    st.info("查無符合的配方")
    
            # ===== 分頁控制列 =====
            cols_page = st.columns([1, 1, 1, 2, 1])
    
            with cols_page[0]:
                if st.button("🏠", key="first_page_tab2"):
                    st.session_state.page_tab2 = 1
                    st.rerun()
    
            with cols_page[1]:
                if st.button("🔼", key="prev_page_tab2") and st.session_state.page_tab2 > 1:
                    st.session_state.page_tab2 -= 1
                    st.rerun()
    
            with cols_page[2]:
                if st.button("🔽", key="next_page_tab2") and st.session_state.page_tab2 < total_pages:
                    st.session_state.page_tab2 += 1
                    st.rerun()
    
            with cols_page[3]:
                jump_page = st.number_input(
                    "",
                    min_value=1,
                    max_value=total_pages,
                    value=st.session_state.page_tab2,
                    key="jump_page_tab2",
                    label_visibility="collapsed"
                )
                if jump_page != st.session_state.page_tab2:
                    st.session_state.page_tab2 = jump_page
    
            with cols_page[4]:
                # ⭐ 修正 3：selectbox 只寫 state，不接回傳值
                st.selectbox(
                    "",
                    options=limit_options,
                    index=limit_options.index(limit),
                    key="limit_per_page_tab2",
                    label_visibility="collapsed"
                )
    
            st.caption(f"頁碼 {st.session_state.page_tab2} / {total_pages}，總筆數 {total_rows}")

# ============================================================
    # Tab 3: 配方預覽/修改/刪除
    # ============================================================
    with tab3:

        if not df_recipe.empty and "配方編號" in df_recipe.columns:
            df_recipe['配方編號'] = df_recipe['配方編號'].fillna('').astype(str)

            # 新增空白選項
            options = [None] + list(df_recipe.index)

            selected_index = st.selectbox(
                "輸入配方",
                options=options,
                format_func=lambda i: "" if i is None else f"{df_recipe.at[i, '配方編號']} | {df_recipe.at[i, '顏色']} | {df_recipe.at[i, '客戶名稱']}",
                key="select_recipe_code_page_tab3"
            )

            selected_code = df_recipe.at[selected_index, "配方編號"] if selected_index is not None else None
            
            if selected_code:
                df_selected = df_recipe[df_recipe["配方編號"] == selected_code]
                if not df_selected.empty:
                    recipe_row_preview = df_selected.iloc[0].to_dict()
                    preview_text_recipe = generate_recipe_preview_text(
                        {"配方編號": recipe_row_preview.get("配方編號")}, 
                        recipe_row_preview
                    )
                    st.markdown(preview_text_recipe, unsafe_allow_html=True)
            
                    # ✅ 生成兩欄放按鈕
                    col_left, col_right = st.columns(2)
                    with col_left:
                        if st.button("✏️ ", key=f"edit_recipe_btn_tab3_{selected_index}"):
                            st.session_state.show_edit_recipe_panel = True
                            st.session_state.editing_recipe_index = selected_index
                            st.rerun()
                    with col_right:
                        if st.button("🗑️ ", key=f"delete_recipe_btn_tab3_{selected_index}"):
                            st.session_state.show_delete_recipe_confirm = True
                            st.session_state.delete_recipe_index = selected_index

                # 刪除確認
                if st.session_state.get("show_delete_recipe_confirm", False):
                    idx = st.session_state["delete_recipe_index"]
                    recipe_label = df_recipe.at[idx, "配方編號"]
                    st.warning(f"⚠️ 確定要刪除配方？\n\n👉 {recipe_label}")

                    c1, c2 = st.columns(2)
                    if c1.button("✅ 是，刪除", key="confirm_delete_recipe_yes_tab3"):
                        df_recipe.drop(idx, inplace=True)
                        st.success(f"✅ 已刪除 {recipe_label}")
                        st.session_state.show_delete_recipe_confirm = False
                        st.rerun()
                    if c2.button("取消", key="confirm_delete_recipe_no_tab3"):
                        st.session_state.show_delete_recipe_confirm = False
                        st.rerun()

                # 修改配方面板
                if st.session_state.get("show_edit_recipe_panel") and st.session_state.get("editing_recipe_index") is not None:
                    st.markdown("---")
                    idx = st.session_state.editing_recipe_index
                    st.markdown(f"<p style='font-size:18px; font-weight:bold; color:#fceca6;'>✏️ 修改配方 {df_recipe.at[idx, '配方編號']}</p>", unsafe_allow_html=True)

                    fr = df_recipe.loc[idx].to_dict()

                    # 基本欄位
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="edit_recipe_code_tab3")
                    with col2:
                        fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="edit_recipe_color_tab3")
                    with col3:
                        options = [""] + customer_options
                        cust_id = fr.get("客戶編號", "").strip()
                        cust_name = fr.get("客戶名稱", "").strip()
                        current = f"{cust_id} - {cust_name}" if cust_id else ""
                        index = options.index(current) if current in options else 0
                        selected = st.selectbox("客戶編號", options, index=index, key="edit_recipe_selected_customer_tab3")
                        
                        if " - " in selected:
                            c_no, c_name = selected.split(" - ", 1)
                            fr["客戶編號"] = c_no
                            fr["客戶名稱"] = c_name

                    # 配方類別、狀態、原始配方
                    col4, col5, col6 = st.columns(3)
                    with col4:
                        options_cat = ["原始配方", "附加配方"]
                        current = fr.get("配方類別", options_cat[0])
                        fr["配方類別"] = st.selectbox("配方類別", options_cat, index=options_cat.index(current), key="edit_recipe_category_tab3")
                    with col5:
                        options_status = ["啟用", "停用"]
                        current = fr.get("狀態", options_status[0])
                        fr["狀態"] = st.selectbox("狀態", options_status, index=options_status.index(current), key="edit_recipe_status_tab3")
                    with col6:
                        fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方", ""), key="edit_recipe_origin_tab3")

                    # 色粉類別、計量單位、Pantone
                    col7, col8, col9, col10, col11 = st.columns(5)
                    with col7:
                        options_type = ["配方", "色母", "色粉", "添加劑", "其他"]
                        current = fr.get("色粉類別", options_type[0])
                        fr["色粉類別"] = st.selectbox("色粉類別", options_type, index=options_type.index(current), key="edit_recipe_powder_type_tab3")
                    with col8:
                        options_unit = ["包", "桶", "kg", "其他"]
                        current = fr.get("計量單位", options_unit[0])
                        fr["計量單位"] = st.selectbox("計量單位", options_unit, index=options_unit.index(current), key="edit_recipe_unit_tab3")
                    with col9:
                        fr["Pantone色號"] = st.text_input("Pantone色號", value=fr.get("Pantone色號", ""), key="edit_recipe_pantone_tab3")
                    with col10:
                        fr["淨重"] = st.text_input("色粉淨重", value=fr.get("淨重", ""), key="edit_recipe_net_weight_tab3")
                    with col11:
                        options = ["g", "kg"]
                        current = fr.get("淨重單位", options[0])
                        if current not in options:
                            current = options[0]
                        fr["淨重單位"] = st.selectbox("單位", options, index=options.index(current), key="edit_recipe_net_unit_tab3")

                    # 重要提醒、比例1-3、備註
                    fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒", ""), key="edit_recipe_note_tab3")

                    cols_ratio = st.columns([2, 0.3, 2, 2, 1])
                    with cols_ratio[0]:
                        fr["比例1"] = st.text_input("", value=fr.get("比例1", ""), key="edit_ratio1_tab3", label_visibility="collapsed")
                    with cols_ratio[1]:
                        st.markdown("<div style='text-align:center;font-size:18px;'>:</div>", unsafe_allow_html=True)
                    with cols_ratio[2]:
                        fr["比例2"] = st.text_input("", value=fr.get("比例2", ""), key="edit_ratio2_tab3", label_visibility="collapsed")
                    with cols_ratio[3]:
                        fr["比例3"] = st.text_input("", value=fr.get("比例3", ""), key="edit_ratio3_tab3", label_visibility="collapsed")
                    with cols_ratio[4]:
                        st.markdown("<div style='text-align:left;font-size:16px;'>g/kg</div>", unsafe_allow_html=True)
                    
                    fr["備註"] = st.text_area("備註", value=fr.get("備註", ""), key="edit_recipe_remark_tab3")

                    # 色粉設定
                    st.markdown("##### 色粉設定")
                    num_rows = max(5, sum(1 for i in range(1, 9) if fr.get(f"色粉編號{i}")))
                    for i in range(1, num_rows + 1):
                        c1, c2 = st.columns([2.5, 2.5])
                        fr[f"色粉編號{i}"] = c1.text_input("", value=fr.get(f"色粉編號{i}", ""), placeholder=f"色粉{i}編號", key=f"edit_recipe_powder_code_tab3_{i}")
                        fr[f"色粉重量{i}"] = c2.text_input("", value=fr.get(f"色粉重量{i}", ""), placeholder="重量", key=f"edit_recipe_powder_weight_tab3_{i}")
                    
                    # 合計類別
                    col1, col2 = st.columns(2)
                    category_options = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
                    default = str(fr.get("合計類別", "\u2002")).strip()
                    if default not in category_options:
                        default = "\u2002"
                    fr["合計類別"] = col1.selectbox("合計類別", category_options, index=category_options.index(default), key="edit_recipe_total_category_tab3")

                    # 儲存 / 返回
                    cols_edit = st.columns([1, 1])
                    
                    import traceback

                    with cols_edit[0]:
                        if st.button("💾 儲存修改", key="save_edit_recipe_btn_tab3"):
                            for k, v in fr.items():
                                df_recipe.at[idx, k] = v

                            try:
                                ws_recipe = spreadsheet.worksheet("配方管理")
                                header = ws_recipe.row_values(1)
                                if not header:
                                    st.error("❌ 試算表第一列（表頭）為空，無法寫入")
                                else:
                                    recipe_id = str(df_recipe.at[idx, "配方編號"]) if "配方編號" in df_recipe.columns else ""
                                    row_num = idx + 2

                                    if "配方編號" in header and recipe_id:
                                        id_col_index = header.index("配方編號") + 1
                                        col_vals = ws_recipe.col_values(id_col_index)
                                        try:
                                            found_list_index = col_vals.index(recipe_id)
                                            row_num = found_list_index + 1
                                        except ValueError:
                                            row_num = idx + 2

                                    values_row = [
                                        str(df_recipe.at[idx, col]) if (col in df_recipe.columns and pd.notna(df_recipe.at[idx, col])) else ""
                                        for col in header
                                    ]

                                    def colnum_to_letter(n):
                                        s = ""
                                        while n > 0:
                                            n, r = divmod(n - 1, 26)
                                            s = chr(65 + r) + s
                                        return s

                                    last_col_letter = colnum_to_letter(len(header))
                                    range_a1 = f"A{row_num}:{last_col_letter}{row_num}"
                                    ws_recipe.update(range_a1, [values_row])
                                    st.success("✅ 配方已更新並寫入 Google Sheet")

                            except Exception as e:
                                st.error(f"❌ 儲存到 Google Sheet 失敗：{type(e).__name__} {e}")
                                st.text(traceback.format_exc())

                                try:
                                    header_len = len(header) if 'header' in locals() else len(df_recipe.columns)
                                    last_col_num = header_len
                                    cell_list = ws_recipe.range(row_num, 1, row_num, last_col_num)
                                    for i, cell in enumerate(cell_list):
                                        cell.value = values_row[i] if i < len(values_row) else ""
                                    ws_recipe.update_cells(cell_list)
                                    st.success("✅ 備援寫入 (update_cells) 成功")
                                except Exception as e2:
                                    st.error(f"❌ 備援寫入也失敗：{type(e2).__name__} {e2}")
                                    st.text(traceback.format_exc())

                            st.session_state.show_edit_recipe_panel = False
                            st.rerun()

                    with cols_edit[1]:
                        if st.button("返回", key="return_edit_recipe_btn_tab3"):
                            st.session_state.show_edit_recipe_panel = False
                            st.rerun()

    # ========== Tab 4：色粉管理（前端狀態 → 批次寫回）==========
    with tab4:
    
        REQUIRED_COLUMNS = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    
        # ---------- 1️⃣ 初次進入才讀 Google Sheet ----------
        if "df_color" not in st.session_state:
            worksheet = spreadsheet.worksheet("色粉管理")
            try:
                df = pd.DataFrame(worksheet.get_all_records())
            except:
                df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    
            if df.empty:
                df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    
            for c in REQUIRED_COLUMNS:
                if c not in df.columns:
                    df[c] = ""
    
            st.session_state.df_color = df.astype(str)
            st.session_state.color_dirty = False
            st.session_state.edit_color_index = None
    
        df_color = st.session_state.df_color
    
        # ---------- 2️⃣ 新增 / 編輯色粉（只動前端） ----------
        st.markdown('<h3 style="font-size:18px; color:#dbd818;">➕ 新增 / 編輯色粉</h3>', unsafe_allow_html=True)
    
        if "form_color" not in st.session_state:
            st.session_state.form_color = {
                "色粉編號": "",
                "國際色號": "",
                "名稱": "",
                "色粉類別": "色粉",
                "包裝": "袋",
                "備註": ""
            }
    
        with st.form("color_form_tab4"):
            col1, col2 = st.columns(2)
            with col1:
                cid = st.text_input("色粉編號", st.session_state.form_color["色粉編號"])
                intl = st.text_input("國際色號", st.session_state.form_color["國際色號"])
                name = st.text_input("名稱", st.session_state.form_color["名稱"])
            with col2:
                ctype = st.selectbox("色粉類別", ["色粉", "色母", "添加劑"],
                                     index=["色粉", "色母", "添加劑"].index(st.session_state.form_color["色粉類別"]))
                pack = st.selectbox("包裝", ["袋", "箱", "kg"],
                                    index=["袋", "箱", "kg"].index(st.session_state.form_color["包裝"]))
                note = st.text_input("備註", st.session_state.form_color["備註"])
        
            submit = st.form_submit_button("💾 新增 / 修改")
        
        if submit:
            new_row = {
                "色粉編號": cid.strip(),
                "國際色號": intl.strip(),
                "名稱": name.strip(),
                "色粉類別": ctype,
                "包裝": pack,
                "備註": note.strip()
            }
        
            if new_row["色粉編號"] == "":
                st.warning("⚠️ 請輸入色粉編號")
            else:
                if st.session_state.edit_color_index is not None:
                    idx = st.session_state.edit_color_index
                    for k in new_row:
                        df_color.at[idx, k] = new_row[k]
                    st.success("✏️ 已更新並寫回 Google Sheet")
                    st.session_state.edit_color_index = None
                else:
                    if new_row["色粉編號"] in df_color["色粉編號"].values:
                        st.warning("⚠️ 此色粉編號已存在")
                    else:
                        df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("➕ 已新增並寫回 Google Sheet")
        
                # 直接寫回 Google Sheet
                worksheet = spreadsheet.worksheet("色粉管理")
                save_df_to_sheet(worksheet, df_color)
                st.session_state.df_color = df_color  # 更新 session_state
        
                # 清空表單
                st.session_state.form_color = {
                    "色粉編號": "",
                    "國際色號": "",
                    "名稱": "",
                    "色粉類別": "色粉",
                    "包裝": "袋",
                    "備註": ""
                }
        
                # 重跑，讓新增/修改的資料立即更新搜尋列表
                st.experimental_rerun()
        
        # ---------- 3️⃣ 搜尋 / 修改 / 刪除（只動前端） ----------
        st.markdown("---")
        st.markdown('<h3 style="font-size:18px; color:#dbd818;">🛠️ 色粉修改 / 刪除</h3>', unsafe_allow_html=True)
        
        keyword = st.text_input("輸入色粉編號 / 名稱 / 國際色號搜尋", value=st.session_state.get("search_color_tab4",""))
        st.session_state.search_color_tab4 = keyword.strip()
        
        # 只有有輸入關鍵字才列出結果
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
                            st.session_state.form_color = row.to_dict()
                            st.session_state.edit_color_index = i
                    with c3:
                        if st.button("🗑️ 刪", key=f"del_color_{i}"):
                            st.session_state.df_color = df_color.drop(index=i).reset_index(drop=True)
                            st.session_state.color_dirty = True
                            st.session_state._tab4_need_rerun = True
        
        # ---- Tab4 安全 rerun ----
        if st.session_state.get("_tab4_need_rerun", False):
            st.session_state._tab4_need_rerun = False
            st.rerun()
          
        # ---------- 4️⃣ 批次寫回 Google Sheet（唯一 API） ----------
        st.markdown("---")
    
        if st.session_state.color_dirty:
            st.warning("⚠️ 尚有變更尚未寫回 Google Sheet")
    
            if st.button("💾 套用變更（寫回 Google Sheet）"):
                worksheet = spreadsheet.worksheet("色粉管理")
                save_df_to_sheet(worksheet, st.session_state.df_color)
                st.session_state.color_dirty = False
                st.success("✅ 已全部寫回完成")
    

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
    
    st.markdown(
        '<h1 style="font-size:24px; font-family:Arial; color:#F9DC5C;">🛸 生產單管理</h1>',
        unsafe_allow_html=True
    )

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

    # ===== 完整初始化庫存（初始 + 進貨 - 已用） =====
    # ===== 庫存計算函式 =====
    def calculate_current_stock():
        """
        計算截至「今天」的實際庫存
        邏輯：與庫存區 calc_usage_for_stock() 完全一致
        """
        stock_dict = {}
        
        try:
            ws_stock = spreadsheet.worksheet("庫存記錄")
            records = ws_stock.get_all_records()
            df_stock = pd.DataFrame(records)
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
    
    # ⚠️ 每次進入「生產單管理」都重新計算最新庫存
    st.session_state["last_final_stock"] = calculate_current_stock()
    
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
                ws_stock = spreadsheet.worksheet("庫存記錄")
                records = ws_stock.get_all_records()
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
    tab1, tab2, tab3 = st.tabs(["🛸 生產單建立", "📊 生產單記錄表", "👀 生產單預覽/修改/刪除"])
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
        
        # ===== 處理搜尋結果 =====
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
        if not filtered.empty:
            filtered["label"] = filtered.apply(format_option_with_status, axis=1)
            option_map = dict(zip(filtered["label"], filtered.to_dict(orient="records")))
        else:
            option_map = {}
    
        # ===== 顯示選擇結果 =====
        #    =====    顯示選擇結果    =====
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
                all_empty = True
                            
                for i in range(1, 5):
                    weight = st.session_state.get(f"form_weight{i}_tab1", "").strip()
                    count  = st.session_state.get(f"form_count{i}_tab1", "").strip()
                    if weight or count:
                        all_empty = False
                        break  # ✅ 已經有填，不用再檢查後面
                            
                if all_empty:
                    st.warning("⚠️ 請至少填寫一個包裝重量或包裝份數，才能儲存生產單！")
                    st.stop()
                                
                order["顏色"] = st.session_state.form_color_tab1
                order["Pantone 色號"] = st.session_state.form_pantone_tab1
                order["料"] = st.session_state.form_raw_material_tab1
                order["備註"] = st.session_state.form_remark_tab1
                order["重要提醒"] = st.session_state.form_important_note_tab1
                order["合計類別"] = st.session_state.form_total_category_tab1
                # ===== 比例（來自配方，直接寫入訂單）=====
                order["比例1"] = recipe_row.get("比例1", "")
                order["比例2"] = recipe_row.get("比例2", "")
                order["比例3"] = recipe_row.get("比例3", "")    
                
                for i in range(1, 5):
                    order[f"包裝重量{i}"] = st.session_state.get(f"form_weight{i}_tab1", "").strip()
                    order[f"包裝份數{i}"] = st.session_state.get(f"form_count{i}_tab1", "").strip()
                
                for i in range(1, 9):
                    order[f"色粉編號{i}"] = recipe_row.get(f"色粉編號{i}", "")
                    order[f"色粉重量{i}"] = recipe_row.get(f"色粉重量{i}", "")
                
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
                        color_weight_list.append({"項次": i, "重量": weight, "結果": net_weight * weight})
                order["色粉合計清單"] = color_weight_list
                order["色粉合計類別"] = recipe_row.get("合計類別", "")
                
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
                    sheet_data = ws_order.get_all_records()
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
                            ws_oem = spreadsheet.worksheet("代工管理")
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
                
        col1, col2, col3 = st.columns([3,1,3])
        with col1:
            st.download_button(
                label="📥 下載 A5 HTML",
                data=print_html.encode("utf-8"),
                file_name=f"{order['生產單號']}_列印.html",
                mime="text/html",
                key="download_html_tab1",
                disabled=not st.session_state.get("new_order_saved", False)  # 未儲存前禁用
            )
                
        with col3:
            if st.button("🔙 返回", key="back_button_tab1"):
                st.session_state.new_order = None
                st.session_state.show_confirm_panel = False
                st.session_state.new_order_saved = False
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
            if st.button("🔼上一頁", key="prev_page_tab2") and st.session_state.order_page_tab2 > 1:
                st.session_state.order_page_tab2 -= 1
                st.rerun()
    
        with cols_page[2]:
            if st.button("🔽下一頁", key="next_page_tab2") and st.session_state.order_page_tab2 < total_pages:
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
    # Tab 3: 生產單修改/刪除（保持完整，無變更）
    # ============================================================
    with tab3:
    
        def delete_order_by_id(ws, order_id):
            all_values = ws.get_all_records()
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
            all_values = ws_oem.get_all_records()
            df = pd.DataFrame(all_values)
            if df.empty or "生產單號" not in df.columns:
                return 0
            target_idxs = df.index[df["生產單號"].astype(str) == str(order_id)].tolist()
            for idx in sorted(target_idxs, reverse=True):
                ws_oem.delete_rows(idx + 2)
            return len(target_idxs)
    
        search_order_tab3 = st.text_input(
            "搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)",
            key="search_order_input_tab3",
            value=""
        )
    
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
    
        df_filtered_tab3["建立時間"] = pd.to_datetime(df_filtered_tab3["建立時間"], errors="coerce")
        df_filtered_tab3 = df_filtered_tab3.sort_values(by="建立時間", ascending=False)
    
        if not df_filtered_tab3.empty:
            df_filtered_tab3['配方編號'] = df_filtered_tab3['配方編號'].fillna('').astype(str)
    
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
            st.info("⚠️ 沒有可選的生產單")
            selected_index, selected_order, selected_code_edit = None, None, None
    
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
            if show_ids_key not in st.session_state:
                st.session_state[show_ids_key] = True
                
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
                value=st.session_state[show_ids_key],
                key=show_ids_key
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
                                ws_oem = spreadsheet.worksheet("代工管理")
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
                
                st.caption("⚠️：『儲存修改』僅同步更新Google Sheets作記錄修正用；若需列印，請先刪除原生產單，並重新建立新生產單。")
                
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
                recipe_row = recipe_rows.iloc[0]
                
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
                        idx_list = df_order.index[df_order["生產單號"] == order_no].tolist()
                
                        if not idx_list:
                            st.error("⚠️ 找不到該筆生產單資料")
                            st.stop()
                
                        idx = idx_list[0]
                
                        df_order.at[idx, "客戶名稱"] = new_customer
                        df_order.at[idx, "顏色"] = new_color
                        for i in range(4):
                            df_order.at[idx, f"包裝重量{i + 1}"] = new_packing_weights[i]
                            df_order.at[idx, f"包裝份數{i + 1}"] = new_packing_counts[i]
                        df_order.at[idx, "備註"] = new_remark
                
                        try:
                            cell = ws_order.find(order_no)
                            if cell:
                                row_idx = cell.row
                                row_data = df_order.loc[idx].fillna("").astype(str).tolist()
                                last_col_letter = chr(65 + len(row_data) - 1)
                                ws_order.update(
                                    f"A{row_idx}:{last_col_letter}{row_idx}",
                                    [row_data]
                                )
                                st.success(f"✅ 生產單 {order_no} 已更新並同步！")
                            else:
                                st.warning("⚠️ Google Sheets 找不到該筆生產單，未更新")
                        except Exception as e:
                            st.error(f"Google Sheets 更新錯誤：{e}")
                
                        os.makedirs(os.path.dirname(order_file), exist_ok=True)
                        df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
                        st.session_state.df_order = df_order
                
                        st.success("✅ 本地資料更新成功，修改已儲存")
                        st.rerun()
                
                with cols_edit[1]:
                    if st.button("返回", key="return_button_tab3"):
                        st.session_state.show_edit_panel = False
                        st.session_state.editing_order = None
                        st.rerun()

# ======== 代工管理分頁 =========
if menu == "代工管理":
    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    import pandas as pd
    from datetime import datetime
    
    # ===== 標題 =====
    st.markdown('<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">🏭 代工管理</h1>', unsafe_allow_html=True)
    
    # ===== 讀取代工管理表 =====
    try:
        ws_oem = spreadsheet.worksheet("代工管理")
        df_oem = pd.DataFrame(ws_oem.get_all_records())
    except:
        ws_oem = spreadsheet.add_worksheet("代工管理", rows=100, cols=20)
        ws_oem.append_row(["代工單號", "生產單號", "配方編號", "客戶名稱", 
                          "代工數量", "代工廠商", "備註", "狀態", "建立時間"])
        df_oem = pd.DataFrame(columns=["代工單號", "生產單號", "配方編號", "客戶名稱", 
                                       "代工數量", "代工廠商", "備註", "狀態", "建立時間"])
    # 🔒 確保代工單號欄位一定存在（避免 KeyError）
    if "代工單號" not in df_oem.columns:
        df_oem["代工單號"] = ""
        
    
    # 確保狀態欄位存在
    if "狀態" not in df_oem.columns:
        df_oem["狀態"] = ""
    
    # ===== 讀取送達記錄表 =====
    try:
        ws_delivery = spreadsheet.worksheet("代工送達記錄")
        df_delivery = pd.DataFrame(ws_delivery.get_all_records())
    except:
        ws_delivery = spreadsheet.add_worksheet("代工送達記錄", rows=100, cols=10)
        ws_delivery.append_row(["代工單號", "送達日期", "送達數量", "建立時間"])
        df_delivery = pd.DataFrame(columns=["代工單號", "送達日期", "送達數量", "建立時間"])
    
    # ===== 讀取載回記錄表 =====
    try:
        ws_return = spreadsheet.worksheet("代工載回記錄")
        df_return = pd.DataFrame(ws_return.get_all_records())
    except:
        ws_return = spreadsheet.add_worksheet("代工載回記錄", rows=100, cols=10)
        ws_return.append_row(["代工單號", "載回日期", "載回數量", "建立時間"])
        df_return = pd.DataFrame(columns=["代工單號", "載回日期", "載回數量", "建立時間"])

    # 🔒 確保送達與載回表都有 "代工單號" 欄位，避免 KeyError
    if "代工單號" not in df_delivery.columns:
        df_delivery["代工單號"] = ""
    if "代工單號" not in df_return.columns:
        df_return["代工單號"] = ""

    
    # ===== Tab 分頁 =====
    tab1, tab2, tab3, tab4 = st.tabs(["➕ 新增代工單", "✏️ 編輯代工", "📥 載回登入", "📊 代工進度表"])
    
    # ========== Tab 1：新增代工單 ==========
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
                new_oem_id = st.text_input("代工單號", placeholder="例如：OEM20251210-001")
                new_production_id = st.text_input("生產單號（選填）", placeholder="若有對應生產單請填寫")
                new_formula_id = st.text_input("配方編號")
    
            with col2:
                new_customer = st.text_input("客戶名稱")
                new_oem_qty = st.number_input("代工數量 (kg)", min_value=0.0, value=0.0, step=1.0)
                new_vendor = st.selectbox("代工廠商", ["", "弘旭", "良輝"])
    
            new_remark = st.text_area("備註")
    
            submitted_new = st.form_submit_button("💾 建立代工單")
    
            if submitted_new:

                if not new_oem_id.strip():
                    st.error("❌ 請輸入代工單號")
                elif new_oem_id in df_oem.get("代工單號", []).values:
                    st.error(f"❌ 代工單號 {new_oem_id} 已存在")
                elif new_oem_qty <= 0:
                    st.error("❌ 代工數量必須大於 0")
                else:
                    new_row = [
                        new_oem_id,
                        new_production_id,
                        new_formula_id,
                        new_customer,
                        new_oem_qty,
                        new_vendor,
                        new_remark,
                        "🏭 在廠內",  # ⭐ 預設狀態
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]

                    ws_oem.append_row(new_row)

                    # 儲存成功後，將代工單號存進 session_state
                    st.session_state["oem_saved"] = new_oem_id  

                    st.rerun()

    # ========== Tab 2：編輯代工 ==========
    with tab2:
        if not df_oem.empty:
    
            # ---------- 建立日期排序欄位 ----------
            df_oem["狀態"] = df_oem["狀態"].astype(str).str.strip()
    
            def tw_to_ad(d):
                d = str(d)
                if len(d) == 7:
                    return str(int(d[:3]) + 1911) + d[3:]
                return d
    
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
    
                    # 如果 session_state 沒有這筆資料，才抓一次
                    if "oem_selected_row" not in st.session_state or st.session_state.oem_selected_row.get("代工單號") != selected_oem:
                        oem_row = df_oem_active[df_oem_active["代工單號"] == selected_oem].iloc[0].to_dict()
                        st.session_state.oem_selected_row = oem_row
    
                    oem_row = st.session_state.oem_selected_row
    
                    # ---------- 顯示基本資訊 ----------
                    col1, col2, col3 = st.columns(3)
                    col1.text_input("配方編號", value=oem_row.get("配方編號", ""), disabled=True)
                    col2.text_input("客戶名稱", value=oem_row.get("客戶名稱", ""), disabled=True)
                    col3.text_input("代工數量 (kg)", value=oem_row.get("代工數量", ""), disabled=True)
    
                    # ---------- 可編輯欄位 ----------
                    col4, col5 = st.columns([2,1])
                    new_vendor = col4.selectbox(
                        "代工廠商", ["", "弘旭", "良輝"],
                        index=["", "弘旭", "良輝"].index(oem_row.get("代工廠商", "")) if oem_row.get("代工廠商", "") in ["", "弘旭", "良輝"] else 0,
                        key="oem_vendor"
                    )
                    status_options = ["", "⏳ 未載回", "🏭 在廠內", "🔄 進行中", "✅ 已結案"]
                    current_status = oem_row.get("狀態", "")
                    status_index = status_options.index(current_status) if current_status in status_options else 0
                    new_status = col5.selectbox("狀態", status_options, index=status_index, key="oem_status")
                    new_remark = st.text_area("備註", value=oem_row.get("備註",""), key="oem_remark", height=120)
    
                    # ---------- 計算尚餘 ----------
                    df_this_delivery = df_delivery[df_delivery["代工單號"] == selected_oem] if "代工單號" in df_delivery.columns else pd.DataFrame()
                    total_delivered = df_this_delivery["送達數量"].astype(float).sum() if not df_this_delivery.empty else 0.0
                    oem_qty = float(oem_row.get("代工數量", 0))
                    remaining = oem_qty - total_delivered
                    st.info(f"📦 已送達：{total_delivered} kg / 尚餘：{remaining} kg")
    
                    # 禁用條件
                    disabled = remaining <= 0
                    if disabled:
                        st.warning("⚠️ 此代工單已全數送達，無法再編輯或新增送達紀錄")
    
                    # ---------- 更新 / 刪除按鈕 ----------
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("💾 更新代工資訊", key="update_oem_info") and not disabled:
                            all_values = ws_oem.get_all_values()
                            for idx, row in enumerate(all_values[1:], start=2):
                                if row[0] == selected_oem:
                                    ws_oem.update_cell(idx, 6, new_vendor)
                                    ws_oem.update_cell(idx, 7, new_remark)
                                    ws_oem.update_cell(idx, 8, new_status)
                                    st.success("✅ 代工資訊已更新")
                                    st.session_state.oem_selected_row.update({
                                        "代工廠商": new_vendor,
                                        "備註": new_remark,
                                        "狀態": new_status
                                    })
                                    break
    
                    with b2:
                        if st.button("🗑️ 刪除代工單", key="delete_oem"):
                            st.session_state.show_delete_oem_confirm = True
    
                    # ---------- 刪除確認 ----------
                    if st.session_state.get("show_delete_oem_confirm", False):
                        st.warning(f"⚠️ 確定刪除 {oem_row['代工單號']}？")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("確認刪除", key="confirm_delete_oem"):
                                all_values = ws_oem.get_all_values()
                                for idx, row in enumerate(all_values[1:], start=2):
                                    if row[0] == oem_row["代工單號"]:
                                        ws_oem.delete_row(idx)
                                        st.success("✅ 已刪除代工單")
                                        st.session_state.oem_selected_row = None
                                        st.session_state.show_delete_oem_confirm = False
                                        st.rerun()
                                        break
                        with c2:
                            if st.button("取消", key="cancel_delete_oem"):
                                st.session_state.show_delete_oem_confirm = False
    
                    st.markdown("---")
    
                    # ---------- 新增送達 ----------
                    col_d1, col_d2 = st.columns(2)
                    delivery_date = col_d1.date_input("送達日期", key="delivery_date")
                    delivery_qty = col_d2.number_input(
                        "送達數量 (kg)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        key="delivery_qty",
                        disabled=disabled
                    )
    
                    col_btn1, col_btn2 = st.columns([1, 3])
                    def update_oem_status(oem_no, new_status):
                        all_values = ws_oem.get_all_values()
                        for idx, row in enumerate(all_values[1:], start=2):
                            if row[0] == oem_no:
                                ws_oem.update_cell(idx, 8, new_status)
                                break
    
                    if col_btn1.button("➕ 新增送達", key="add_delivery") and not disabled:
                        if delivery_qty > 0:
                            # 寫入送達紀錄
                            new_record = [
                                selected_oem,
                                delivery_date.strftime("%Y/%m/%d"),
                                delivery_qty,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ]
                            ws_delivery.append_row(new_record)
    
                            # 重新計算尚餘
                            new_total_delivered = total_delivered + delivery_qty
                            new_remaining = oem_qty - new_total_delivered
    
                            # ✅ 尚餘為 0 → 自動轉為「未載回」
                            if new_remaining <= 0 and oem_row.get("狀態") != "✅ 已結案":
                                update_oem_status(selected_oem, "⏳ 未載回")
                                st.session_state.oem_selected_row["狀態"] = "⏳ 未載回"
                                st.toast("📦 已全數送達，狀態自動轉為「未載回」", icon="🚚")
    
                            st.success(f"✅ 已新增送達記錄：{delivery_date} / {delivery_qty} kg")
                            st.rerun()
                        else:
                            st.warning("⚠️ 請輸入送達數量")
    
        else:
            st.info("⚠️ 目前沒有代工單，請至「新增代工單」分頁建立") 

    # ================= Tab 3：載回登入 =================
    with tab3:
    
        # ===== Toast 顯示（跨 rerun 一次性）=====
        if "toast_msg" in st.session_state:
            st.toast(
                st.session_state.toast_msg,
                icon=st.session_state.toast_icon
            )
            del st.session_state.toast_msg
            del st.session_state.toast_icon
    
        if not df_oem.empty:
    
            # ---------- 建立日期排序欄位 ----------
            def tw_to_ad(d):
                d = str(d)
                if len(d) == 7:  # 民國年
                    return str(int(d[:3]) + 1911) + d[3:]
                return d
    
            df_oem["日期排序"] = df_oem["代工單號"].str.split("-").str[0].apply(tw_to_ad)
            df_oem["日期排序"] = pd.to_datetime(df_oem["日期排序"], errors="coerce")
    
            # ---------- 過濾未結案代工單 ----------
            df_oem_active = df_oem[df_oem["狀態"] != "✅ 已結案"]
            df_oem_active = df_oem_active.sort_values("日期排序", ascending=False)
    
            # ---------- 建立下拉選單 ----------
            oem_options = [
                f"{row['代工單號']} | {row.get('配方編號','')} | {row.get('客戶名稱','')} | {row.get('代工數量',0)}kg"
                for _, row in df_oem_active.iterrows()
            ]
    
            if not oem_options:
                st.warning("⚠️ 目前沒有可載回的代工單（全部已結案）")
    
            else:
                selected_option = st.selectbox(
                    "選擇代工單號",
                    [""] + oem_options,
                    key="select_oem_return"
                )
    
                if selected_option:
                    selected_oem_return = selected_option.split(" | ")[0]
    
                    # ⚠️ 一定用 df_oem 找 index（確保寫回 Sheet 正確）
                    oem_idx = df_oem[df_oem["代工單號"] == selected_oem_return].index[0]
                    oem_row_return = df_oem.loc[oem_idx]
    
                    # ---------- 數量計算 ----------
                    total_qty = float(oem_row_return.get("代工數量", 0))
    
                    df_this_return = df_return[df_return["代工單號"] == selected_oem_return]
                    total_returned = (
                        df_this_return["載回數量"].astype(float).sum()
                        if not df_this_return.empty else 0.0
                    )
    
                    remaining_return = total_qty - total_returned
    
                    # ---------- 狀態判斷 ----------
                    if total_returned >= total_qty and total_qty > 0:
                        status = "✅ 已結案"
                    elif total_returned > 0:
                        status = "🔄 進行中"
                    else:
                        status = "⏳ 未載回"
    
                    # ---------- 顯示基本資訊 ----------
                    col1, col2 = st.columns(2)
                    col1.text_input(
                        "配方編號",
                        value=oem_row_return.get("配方編號", ""),
                        disabled=True
                    )
                    col2.text_input(
                        "代工數量 (kg)",
                        value=oem_row_return.get("代工數量", ""),
                        disabled=True
                    )
    
                    # ---------- 已載回紀錄 ----------
                    if not df_this_return.empty:
                        st.dataframe(
                            df_this_return[["載回日期", "載回數量"]],
                            use_container_width=True,
                            hide_index=True
                        )
    
                    st.info(
                        f"🚚 已載回：{total_returned} kg / 尚餘：{remaining_return} kg"
                    )
    
                    # ---------- 輸入載回 ----------
                    col_r1, col_r2 = st.columns(2)
                    return_date = col_r1.date_input(
                        "載回日期",
                        key="return_date_input"
                    )
                    
                    return_qty = col_r2.number_input(
                        "載回數量 (kg)",
                        min_value=0.0,
                        step=1.0,
                        key="return_qty_input"
                    )
                    
                    # ---------- 新增載回 ----------
                    if st.button("➕ 新增載回"):
                        if return_qty <= 0:
                            st.warning("⚠️ 請輸入載回數量")
                        else:
                            # 寫入載回紀錄
                            ws_return.append_row([
                                selected_oem_return,
                                return_date.strftime("%Y/%m/%d"),
                                return_qty,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ])
    
                            new_total = total_returned + return_qty
    
                            # ---------- 是否結案 ----------
                            if new_total >= total_qty and total_qty > 0:
                                ws_oem.update_cell(
                                    oem_idx + 2,  # Sheet 實際列
                                    df_oem.columns.get_loc("狀態") + 1,
                                    "✅ 已結案"
                                )
                                st.session_state.toast_msg = "🎉 載回資料已儲存，代工單已結案"
                                st.session_state.toast_icon = "✅"
                            else:
                                st.session_state.toast_msg = "💾 載回資料已儲存"
                                st.session_state.toast_icon = "📦"
    
                            st.rerun()
    
        else:
            st.info("⚠️ 目前沒有代工單")

    # ========== Tab 4：代工進度表 ==========
    with tab4:
    
        if not df_oem.empty:
            progress_data = []
    
            # ===== 狀態排序權重（依你指定）=====
            status_order_map = {
                "🏭 在廠內": 1,
                "⏳ 未載回": 2,
                "🔄 進行中": 3,
                "✅ 已結案": 4
            }
    
            for _, oem in df_oem.iterrows():
                oem_id = oem["代工單號"]
    
                # ---------- 送達紀錄 ----------
                df_this_delivery = df_delivery[df_delivery["代工單號"] == oem_id]
                delivery_text = ""
                if not df_this_delivery.empty:
                    delivery_list = [
                        f"{row['送達日期']} ({row['送達數量']} kg)"
                        for _, row in df_this_delivery.iterrows()
                    ]
                    delivery_text = "\n".join(delivery_list)
    
                # ---------- 載回紀錄 ----------
                df_this_return = df_return[df_return["代工單號"] == oem_id]
                return_text = ""
                if not df_this_return.empty:
                    return_list = [
                        f"{row['載回日期']} ({row['載回數量']} kg)"
                        for _, row in df_this_return.iterrows()
                    ]
                    return_text = "\n".join(return_list)
    
                # ---------- 狀態判斷 ----------
                total_qty = float(oem.get("代工數量", 0))
                total_returned = (
                    df_this_return["載回數量"].astype(float).sum()
                    if not df_this_return.empty else 0.0
                )
    
                # 優先使用手動設定狀態
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
    
                # 狀態排序權重
                status_order = status_order_map.get(status, 99)
    
                progress_data.append({
                    "status_order": status_order,          # 只用來排序
                    "狀態": status,
                    "代工單號": oem_id,
                    "代工廠名稱": oem.get("代工廠商", ""),
                    "配方編號": oem.get("配方編號", ""),
                    "客戶名稱": oem.get("客戶名稱", ""),
                    "代工數量": f"{oem.get('代工數量', 0)} kg",
                    "送達日期及數量": delivery_text,
                    "載回日期及數量": return_text,
                    "建立時間": oem.get("建立時間", "")
                })
    
            # ---------- 組成 DataFrame ----------
            df_progress = pd.DataFrame(progress_data)
    
            # ---------- 只看未結案（預設開） ----------
            show_open_only = st.checkbox("只顯示未結案代工單", value=True)
    
            if show_open_only:
                df_progress = df_progress[df_progress["狀態"] != "✅ 已結案"]

            # ---------- 搜尋：客戶名稱 / 配方編號 ----------
            search_text = st.text_input(
                "🔍 搜尋客戶名稱或配方編號",
                placeholder="輸入關鍵字（可搜尋客戶名稱 / 配方編號）"
            ).strip()
            
            if search_text:
                df_progress = df_progress[
                    df_progress["客戶名稱"].astype(str).str.contains(search_text, case=False, na=False) |
                    df_progress["配方編號"].astype(str).str.contains(search_text, case=False, na=False)
                ]
    
            # ---------- 排序：狀態優先 → 建立時間新到舊 ----------
            if not df_progress.empty:
                df_progress = df_progress.sort_values(
                    by=["status_order", "建立時間"],
                    ascending=[True, False]
                )
    
                df_progress = df_progress.drop(columns=["status_order"])
    
                st.dataframe(
                    df_progress,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("目前沒有符合條件的代工單")
    
        else:
            st.info("⚠️ 目前沒有代工記錄")                                    
            
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
    st.markdown(
        '<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">📥 採購管理</h1>',
        unsafe_allow_html=True
    )

    # ===== Tab 分頁 =====
    tab1, tab2, tab3 = st.tabs(["📲 進貨新增", "🔍 進貨查詢", "🏢 供應商管理"])

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
        records = ws_stock.get_all_records()
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
                ws_supplier = spreadsheet.worksheet("供應商管理")
                df_supplier = pd.DataFrame(ws_supplier.get_all_records()).astype(str)
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
            ws_stock = spreadsheet.worksheet("庫存記錄")
            df_stock = pd.DataFrame(ws_stock.get_all_records())
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
            ws_supplier = spreadsheet.worksheet("供應商管理")
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
            df = pd.DataFrame(ws_supplier.get_all_records())
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
    st.markdown(
        '<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">🔍 查詢區</h1>',
        unsafe_allow_html=True
    )

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
        # ========== Tab 2：色粉用量查詢（使用 form 提交） ==========
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
        st.markdown("**➕ 新增 Pantone 記錄**")
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
    
        st.markdown("---")
    
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
        st.markdown("**🔍 查詢 Pantone 色號**")
    
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
            ws_sample = spreadsheet.worksheet("樣品記錄")
        except:
            ws_sample = spreadsheet.add_worksheet("樣品記錄", rows=100, cols=10)
            ws_sample.append_row(["日期", "客戶名稱", "樣品編號", "樣品名稱", "樣品數量"])
    
        try:
            df_sample = pd.DataFrame(ws_sample.get_all_records())
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
    
        # ===== 新增 / 修改 區 =====
        st.markdown("**➕ 新增 / 修改 樣品**")
    
        # 🔹 使用唯一 form name
        with st.form("form_sample_tab4"):
    
            c1, c2, c3 = st.columns(3)
            with c1:
                sample_date = st.date_input(
                    "日期",
                    value=safe_date(st.session_state.form_sample.get("日期")),
                    key="form_sample_tab4_date"
                )
            with c2:
                sample_customer = st.text_input(
                    "客戶名稱",
                    value=st.session_state.form_sample.get("客戶名稱", ""),
                    key="form_sample_tab4_customer"
                )
            with c3:
                sample_code = st.text_input(
                    "樣品編號",
                    value=st.session_state.form_sample.get("樣品編號", ""),
                    disabled=st.session_state.edit_sample_index is not None,
                    key="form_sample_tab4_code"
                )
    
            c4, c5 = st.columns(2)
            with c4:
                sample_name = st.text_input(
                    "樣品名稱",
                    value=st.session_state.form_sample.get("樣品名稱", ""),
                    key="form_sample_tab4_name"
                )
            with c5:
                sample_qty = st.text_input(
                    "樣品數量",
                    value=st.session_state.form_sample.get("樣品數量", ""),
                    key="form_sample_tab4_qty"
                )
    
            submit = st.form_submit_button("💾 儲存")
    
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
                if st.session_state.edit_sample_index is not None:
                    df_sample.loc[st.session_state.edit_sample_index] = data
                    st.success("✅ 樣品已更新")
                    st.session_state.edit_sample_index = None
                else:
                    df_sample = pd.concat([df_sample, pd.DataFrame([data])], ignore_index=True)
                    st.success("✅ 新增完成")
    
                # 寫回 Google Sheet
                save_df_to_sheet(ws_sample, df_sample)
    
                # 清空表單
                st.session_state.form_sample = {k: "" for k in st.session_state.form_sample}
    
                # 可在這裡觸發前端列表刷新
    
        # ===== 搜尋區（Enter 可觸發）=====
        st.markdown("**🔍 樣品記錄搜尋**")
    
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
    
            st.session_state.sample_filtered_df = df_f.reset_index(drop=True)
            st.session_state.sample_search_triggered = True
            st.session_state.selected_sample_index = None
    
        # ===== 搜尋結果（表格 + 單選）=====
        if st.session_state.sample_search_triggered:
            df_show = st.session_state.sample_filtered_df.copy()  # ← 重點：copy()
        
            # 🔥 只影響顯示：樣品編號轉成字串
            df_show["樣品編號"] = (
                df_show["樣品編號"]
                .astype(str)
                .str.replace(",", "")   # 防 6,590 這種格式
            )
        
            if df_show.empty:
                st.info("⚠️ 查無符合條件的樣品記錄")
            else:
                st.markdown("**📋 搜尋結果（選擇單筆以修改 / 刪除）**")
                with st.expander("點擊展開搜尋結果表格"):
                    st.dataframe(
                        df_show[["日期","樣品編號","樣品名稱","客戶名稱"]],
                        use_container_width=True,
                        hide_index=True
                    )
        
                options = [
                    f"{df_show.at[i,'日期']}｜{df_show.at[i,'樣品編號']}｜{df_show.at[i,'樣品名稱']}"
                    for i in df_show.index
                ]
        
                selected = st.selectbox("選擇樣品", [""] + options, key="select_sample")
                if selected:
                    idx = options.index(selected)
                    st.session_state.selected_sample_index = df_show.index[idx]
    
        # ===== 修改 / 刪除表單（選定後才出現）=====
        if st.session_state.selected_sample_index in df_sample.index:
            row = df_sample.loc[st.session_state.selected_sample_index]
            st.markdown("**✏️ 修改 / 🗑️ 刪除樣品**")
    
            c1, c2, c3 = st.columns(3)
            with c1:
                st.date_input("日期", value=pd.to_datetime(row["日期"]).date(), key="edit_date")
            with c2:
                st.text_input("客戶名稱", value=row["客戶名稱"], key="edit_customer")
            with c3:
                st.text_input("樣品編號", value=row["樣品編號"], key="edit_code")
    
            c4, c5 = st.columns(2)
            with c4:
                st.text_input("樣品名稱", value=row["樣品名稱"], key="edit_name")
            with c5:
                st.text_input("樣品數量", value=row["樣品數量"], key="edit_qty")
    
            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 儲存修改", key="save_edit"):
                    df_sample.at[st.session_state.selected_sample_index, "日期"] = st.session_state["edit_date"]
                    df_sample.at[st.session_state.selected_sample_index, "客戶名稱"] = st.session_state["edit_customer"]
                    df_sample.at[st.session_state.selected_sample_index, "樣品編號"] = st.session_state["edit_code"]
                    df_sample.at[st.session_state.selected_sample_index, "樣品名稱"] = st.session_state["edit_name"]
                    df_sample.at[st.session_state.selected_sample_index, "樣品數量"] = st.session_state["edit_qty"]
                    save_df_to_sheet(ws_sample, df_sample)
                    st.success("✅ 樣品已更新")
                    st.rerun()
            with b2:
                if st.button("🗑️ 刪除", key="delete_edit"):
                    st.session_state.delete_sample_index = st.session_state.selected_sample_index
                    st.session_state.show_delete_sample_confirm = True
    
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
                    st.session_state.selected_sample_index = None
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
        ws_stock = spreadsheet.worksheet("庫存記錄")
        records = ws_stock.get_all_records()
        if records:
            df_stock = pd.DataFrame(records)
        else:
            df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
    except:
        ws_stock = spreadsheet.add_worksheet("庫存記錄", rows=100, cols=10)
        ws_stock.append_row(["類型","色粉編號","日期","數量","單位","備註"])
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

    st.markdown('<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">🏭 庫存區</h1>', unsafe_allow_html=True)

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
    
    
    # ========== Tab 2：庫存查詢 ==========
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
            all_pids_stock = sorted(set(df_stock_copy["色粉編號"].tolist())) if not df_stock_copy.empty else []
    
            all_pids_recipe = []
            if not df_recipe.empty:
                for i in range(1, 9):
                    col = f"色粉編號{i}"
                    if col in df_recipe.columns:
                        all_pids_recipe.extend(df_recipe[col].astype(str).str.strip().tolist())
    
            all_pids_all = sorted(set(all_pids_stock) | set(p for p in all_pids_recipe if p))
    
            # 篩選匹配色粉
            all_pids = []
            if stock_powder:
                if match_mode == "部分匹配":
                    all_pids = [pid for pid in all_pids_all if stock_powder.lower() in pid.lower()]
                else:
                    all_pids = [pid for pid in all_pids_all if stock_powder.lower() == pid.lower()]
    
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
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📊 匯入備份</h2>',
        unsafe_allow_html=True
    )

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
