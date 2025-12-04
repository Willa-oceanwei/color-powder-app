import streamlit as st
import time
import json

# ==========================================
# 🔐 1. 簡易登入驗證
# ==========================================
APP_PASSWORD = "'"  # ← 你自己的密碼

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown(
        "<h3 style='text-align:center; color:#f0efa2;'>🔐 請輸入密碼</h3>",
        unsafe_allow_html=True,
    )

    pwd = st.text_input("密碼：", type="password", key="login_pw")

    if pwd == APP_PASSWORD:
        st.session_state.authenticated = True
        st.success("✅ 登入成功！")
        time.sleep(0.8)
        st.rerun()

    elif pwd != "":
        st.error("❌ 密碼錯誤！請再試一次")

    st.stop()  # 未登入無法進入系統


# ==========================================
# 🎨 2. Selectbox 美化（保留你的 CSS）
# ==========================================
st.markdown(
    """
    <style>
    .st-key-myselect [data-baseweb="option"][aria-selected="true"] {
        background-color: #999999 !important;
        color: black !important;
        font-weight: bold;
    }
    .st-key-myselect [data-baseweb="option"]:hover {
        background-color: #bbbbbb !important;
        color: black !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# 📌 3. Google Sheets 全域登入（由 utils 版本）
# ==========================================
from utils.common import get_spreadsheet

# 你的 Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"

if "spreadsheet" not in st.session_state:
    try:
        st.session_state.spreadsheet = get_spreadsheet("佳咊配方管理") \
            or get_spreadsheet(SHEET_URL)
    except Exception as e:
        st.error(f"❌ 無法連線至 Google Sheet：{e}")
        st.stop()

spreadsheet = st.session_state.spreadsheet  # 給子頁面使用



# ==========================================
# 📂 4. 左側選單（新版 ERP 版）
# ==========================================
menu = st.sidebar.selectbox(
    "功能選單",
    [
        "📦 色粉管理",
        "👥 客戶名單",
        "🧪 配方管理",
        "🧾 生產單管理",
        "🔍 交叉查詢區",
        "🎨 Pantone 色號表",
        "📊 庫存區",
        "⬆️ 匯入備份",
    ],
    key="myselect"
)


# ==========================================
# 🧩 5. 呼叫不同功能模組
# ==========================================
from utils import color, customer, recipe, order, query, inventory

if menu == "📦 色粉管理":
    color.render_color_page(spreadsheet)

elif menu == "👥 客戶名單":
    customer.render_customer_page(spreadsheet)

elif menu == "🧪 配方管理":
    recipe.render_recipe_page(spreadsheet)

elif menu == "🧾 生產單管理":
    order.render_order_page(spreadsheet)

elif menu == "🔍 交叉查詢區":
    query.render_query_page(spreadsheet)

elif menu == "🎨 Pantone 色號表":
    query.render_pantone_page(spreadsheet)

elif menu == "📊 庫存區":
    inventory.render_inventory_page(spreadsheet)

elif menu == "⬆️ 匯入備份":
    st.info("📁 匯入備份功能尚未完成")
