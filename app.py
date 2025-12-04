# app.py
import streamlit as st
from pathlib import Path
import importlib

# ======== 🔐 Google Sheet 初始化區 ========
import gspread
from google.oauth2.service_account import Credentials
import json

# 1️⃣ 從 secrets 讀取 gcp 金鑰
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ],
)

client = gspread.authorize(creds)

# 2️⃣ 讀取 Google 試算表 URL
if "spreadsheet" not in st.session_state:
    try:
        sheet_url = st.secrets["sheet_url"]
        st.session_state["spreadsheet"] = client.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"⚠️ 無法開啟 Google Sheet：{e}")
        st.stop()

spreadsheet = st.session_state["spreadsheet"]
# ======== 初始化完畢 ========

# widgets 样式微調（可自行調整）
st.set_page_config(layout="wide", page_title="佳咊配方管理系統")

st.markdown(
    """
    <style>
    /* 調整左側寬度、上方按鈕樣式等 */
    .top-nav .stButton>button{ margin-right:6px; }
    .left-menu .stButton>button{ text-align:left; width:100%; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- 初始化 session state ----
if "main_tab" not in st.session_state:
    st.session_state.main_tab = "配方管理"  # 預設主分類
if "left_item" not in st.session_state:
    st.session_state.left_item = "配方管理"  # 預設左側項目
if "quick_recipe" not in st.session_state:
    st.session_state.quick_recipe = False
if "quick_order" not in st.session_state:
    st.session_state.quick_order = False

# ---- 載入 utils 套件（會 import utils/*） ----
# 確保你的 utils 資料夾位置正確，且有 __init__.py
try:
    from utils import common, color, customer, recipe, order, schedule, query, inventory
except Exception as e:
    st.error(f"無法載入 utils 模組：{e}")
    st.stop()

# ---- 頂部主分類（水平） ----
st.markdown("<div class='top-nav'>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([2, 6, 1])
with col1:
    st.markdown("<h2 style='margin:0'>佳咊配方管理系統</h2>", unsafe_allow_html=True)
with col2:
    if st.button("配方管理", key="top_recipe"):
        st.session_state.main_tab = "配方管理"
    if st.button("生產單管理", key="top_order"):
        st.session_state.main_tab = "生產單管理"
with col3:
    # 快捷鈕區（配方 / 生產單）
    if st.button("🔎 配方快速"):
        st.session_state.quick_recipe = True
        st.session_state.main_tab = "配方管理"
        st.session_state.left_item = "配方管理"
    if st.button("🖨 生產單快速"):
        st.session_state.quick_order = True
        st.session_state.main_tab = "生產單管理"
        st.session_state.left_item = "生產單"
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# ---- 主體：左側功能樹 + 右側內容 ----
left_col, right_col = st.columns([1.2, 6], gap="small")

with left_col:
    st.markdown("<div class='left-menu'>", unsafe_allow_html=True)
    st.markdown("### 功能導航")

    # 依你指定的樹狀結構：上方是主分類（已由 top nav 決定），左側是功能樹
    # 使用按鈕（或 st.radio 也可），按下會設定 session_state.left_item
    if st.button("色粉管理", key="left_color"):
        st.session_state.left_item = "色粉管理"

    st.write("配方管理 ▾")
    if st.button("  ├ 色粉管理", key="left_recipe_color"):
        st.session_state.left_item = "配方-色粉管理"
    if st.button("  ├ 客戶名單", key="left_recipe_customer"):
        st.session_state.left_item = "配方-客戶名單"
    if st.button("  └ 配方管理", key="left_recipe_recipe"):
        st.session_state.left_item = "配方管理"

    st.write("生產單管理 ▾")
    if st.button("  ├ 生產單", key="left_order_order"):
        st.session_state.left_item = "生產單"
    if st.button("  └ 代工排程 (開發中)", key="left_order_schedule"):
        st.session_state.left_item = "代工排程"

    st.write("查詢 ▾")
    if st.button("  ├ Pantone 色號表", key="left_query_pantone"):
        st.session_state.left_item = "Pantone色號表"
    if st.button("  └ 交叉查詢", key="left_query_cross"):
        st.session_state.left_item = "交叉查詢"

    if st.button("庫存區", key="left_inventory"):
        st.session_state.left_item = "庫存區"

    if st.button("匯入備份（開發中）", key="left_import"):
        st.info("開發中")

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    st.markdown(f"### {st.session_state.main_tab} — {st.session_state.left_item}")

    # Routing: 根據 left_item 呼叫對應 utils 函式
    try:
        li = st.session_state.left_item
        # Map left_item -> utils function
        if li == "色粉管理":
            color.show_color_page()
        elif li == "配方管理":
            recipe.show_recipe_page()
        elif li == "配方-色粉管理":
            # 如果你想把色粉管理內嵌在配方頁，可改成呼叫 recipe.show_color_subpage()
            color.show_color_page()
        elif li == "配方-客戶名單":
            customer.show_customer_page()
        elif li == "生產單":
            order.show_order_page()
        elif li == "代工排程":
            schedule.show_schedule_page()
        elif li == "Pantone色號表":
            query.show_query_page(mode="pantone")
        elif li == "交叉查詢":
            query.show_query_page(mode="cross")
        elif li == "庫存區":
            inventory.show_inventory_page()
        else:
            # default / unknown
            st.info("選項尚未實作，或請從左側選單選擇。")
    except Exception as e:
        st.error(f"載入頁面時發生錯誤：{e}")
