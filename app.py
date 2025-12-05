# app.py - 方案 B：完整重構版（Element Plus 風格）

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import time

# ========== 頁面設定 ==========
st.set_page_config(
    page_title="佳咊配方管理系統",
    page_icon="🌈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 登入驗證 ==========
APP_PASSWORD = "'"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown(
        "<h3 style='text-align:center; color:#f0efa2;'>🔐 請輸入密碼</h3>",
        unsafe_allow_html=True
    )
    
    password_input = st.text_input("密碼：", type="password", key="login_password")
    
    if password_input == APP_PASSWORD:
        st.session_state.authenticated = True
        st.success("✅ 登入成功！請稍候...")
        time.sleep(0.8)
        st.rerun()
    elif password_input:
        st.error("❌ 密碼錯誤，請再試一次。")
    
    st.stop()

# ========== Google Sheets 連線 ==========
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

if "spreadsheet" not in st.session_state:
    try:
        st.session_state["spreadsheet"] = client.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"❗ 無法連線 Google Sheet：{e}")
        st.stop()

# ========== 側邊欄選單（Element Plus 風格）==========
st.markdown("""
<style>
/* 側邊欄樣式 */
[data-testid="stSidebar"] {
    background-color: #2c3e50;
}

[data-testid="stSidebar"] .css-1d391kg {
    padding-top: 1rem;
}

/* 側邊欄標題 */
[data-testid="stSidebar"] h1 {
    color: #ffffff;
    font-size: 20px;
    font-weight: bold;
    padding: 10px;
    margin-bottom: 10px;
}

/* Radio 按鈕容器 */
[data-testid="stSidebar"] .stRadio > div {
    background-color: transparent;
}

/* Radio 選項樣式 */
[data-testid="stSidebar"] .stRadio label {
    color: #ffffff !important;
    padding: 12px 16px;
    border-radius: 4px;
    cursor: pointer;
    display: block;
    transition: all 0.3s;
}

/* Radio 選項 hover */
[data-testid="stSidebar"] .stRadio label:hover {
    background-color: #34495e;
}

/* 選中的 Radio 選項 */
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] input:checked + div {
    background-color: transparent;
}

[data-testid="stSidebar"] .stRadio label:has(input:checked) {
    background-color: #34495e;
    color: #dbd818 !important;
    font-weight: bold;
}

/* 分隔線 */
[data-testid="stSidebar"] hr {
    border-color: #34495e;
    margin: 10px 0;
}

/* 子選單縮排 */
.submenu-item {
    padding-left: 30px !important;
    font-size: 14px;
}

/* 主選單圖標樣式 */
.menu-icon {
    margin-right: 8px;
}
</style>
""", unsafe_allow_html=True)

# 初始化選單狀態
if "menu" not in st.session_state:
    st.session_state.menu = "生產單管理"

# 定義選單選項（對應 Element Plus 結構）
menu_structure = {
    "主要功能": [
        "色粉管理",
        "客戶名單",
        "配方管理",
        "生產單管理",
    ],
    "查詢功能": [
        "Pantone色號表",
        "交叉查詢區",
    ],
    "其他功能": [
        "庫存區",
        "匯入備份",
    ]
}

# 平面化選單（用於 radio）
flat_menu = []
for category, items in menu_structure.items():
    flat_menu.extend(items)

with st.sidebar:
    st.markdown('<h1>🌈 佳咊配方管理系統</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # 使用 radio 建立選單
    selected = st.radio(
        "選擇功能",
        options=flat_menu,
        index=flat_menu.index(st.session_state.menu) if st.session_state.menu in flat_menu else 0,
        key="menu_radio",
        label_visibility="collapsed"
    )
    
    # 更新選單狀態
    if selected != st.session_state.menu:
        st.session_state.menu = selected
        st.rerun()
    
    st.markdown("---")
    
    # 系統資訊
    st.caption("系統版本：v2.0")
    st.caption("最後更新：2025-01-05")

# ========== 路由邏輯 ==========
menu = st.session_state.menu

# 匯入各功能模組
from utils.color import show_color_page
from utils.customer import show_customer_page
from utils.recipe import show_recipe_page
from utils.order import show_order_page
from utils.inventory import show_inventory_page
from utils.query import show_query_page

# 根據選單顯示對應頁面
if menu == "色粉管理":
    show_color_page()

elif menu == "客戶名單":
    show_customer_page()

elif menu == "配方管理":
    show_recipe_page()

elif menu == "生產單管理":
    show_order_page()

elif menu == "Pantone色號表":
    show_query_page(mode="pantone")

elif menu == "交叉查詢區":
    show_query_page(mode="cross")

elif menu == "庫存區":
    show_inventory_page()

elif menu == "匯入備份":
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📊 匯入備份</h2>',
        unsafe_allow_html=True
    )
    
    import pandas as pd
    
    def load_recipe_backup_excel(file):
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()
            df = df.dropna(how='all')
            df = df.fillna("")
            
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

else:
    st.warning(f"⚠️ 功能「{menu}」尚未開發")
