# app.py
import streamlit as st
import sys
from pathlib import Path

# 強制加入 utils 路徑
sys.path.append(str(Path(__file__).resolve().parent / "utils"))
sys.path.append(str(Path(__file__).resolve().parent))


st.set_page_config(page_title="佳咊配方管理系統", layout="wide")

# ==========================
#  0️⃣ 移除密碼機制避免空白頁面
# ==========================

# ==========================
#  1️⃣ 載入 utils 模組
# ==========================
try:
    from utils import common, color, customer, recipe, order, query, inventory, schedule
except Exception as e:
    st.error(f"❌ 無法載入 utils 模組：{e}")
    st.stop()

# ==========================
#  2️⃣ 初始化 session state
# ==========================
def init():
    if "main_tab" not in st.session_state:
        st.session_state.main_tab = "配方管理"

    if "left_item" not in st.session_state:
        st.session_state.left_item = "配方管理"

    if "quick_recipe" not in st.session_state:
        st.session_state.quick_recipe = False

    if "quick_order" not in st.session_state:
        st.session_state.quick_order = False

init()

# ==========================
#  3️⃣ 上方主導覽列（仿 ERP 外觀）
# ==========================
st.markdown("""
<style>
.top-nav button {
    margin-right: 8px;
}
.left-menu button {
    width: 100%;
    text-align: left !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='top-nav'>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([2, 6, 2])

with col1:
    st.markdown("<h2>佳咊配方管理系統</h2>", unsafe_allow_html=True)

with col2:
    if st.button("配方管理", key="top_recipe_btn"):
        st.session_state.main_tab = "配方管理"
        st.session_state.left_item = "配方管理"

    if st.button("生產單管理", key="top_order_btn"):
        st.session_state.main_tab = "生產單管理"
        st.session_state.left_item = "生產單"

with col3:
    if st.button("🔎 快速配方"):
        st.session_state.quick_recipe = True
        st.session_state.main_tab = "配方管理"
        st.session_state.left_item = "配方管理"

    if st.button("🖨 快速生產單"):
        st.session_state.quick_order = True
        st.session_state.main_tab = "生產單管理"
        st.session_state.left_item = "生產單"

st.markdown("</div><hr/>", unsafe_allow_html=True)

# ==========================
#  4️⃣ 左側樹狀功能選單
# ==========================
left_col, right_col = st.columns([1.3, 6], gap="small")

with left_col:
    st.markdown("### 功能導航")
    st.markdown("<div class='left-menu'>", unsafe_allow_html=True)

    # --- 色粉管理（獨立項）
    if st.button("色粉管理"):
        st.session_state.left_item = "色粉管理"

    # --- 配方管理 ---
    st.markdown("配方管理 ▾")
    if st.button("　├ 客戶名單"):
        st.session_state.left_item = "客戶名單"
    if st.button("　├ 色粉管理（子頁）"):
        st.session_state.left_item = "配方-色粉"
    if st.button("　└ 配方管理"):
        st.session_state.left_item = "配方管理"

    # --- 生產單管理 ---
    st.markdown("生產單管理 ▾")
    if st.button("　├ 生產單"):
        st.session_state.left_item = "生產單"
    if st.button("　└ 代工排程"):
        st.session_state.left_item = "代工排程"

    # --- 查詢 ---
    st.markdown("查詢 ▾")
    if st.button("　├ Pantone 色號表"):
        st.session_state.left_item = "Pantone色號表"
    if st.button("　└ 交叉查詢"):
        st.session_state.left_item = "交叉查詢"

    if st.button("庫存區"):
        st.session_state.left_item = "庫存區"

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================
#  5️⃣ 右側內容區域
# ==========================
with right_col:
    li = st.session_state.left_item

    if li == "色粉管理":
        color.show_color_page()

    elif li == "客戶名單":
        customer.show_customer_page()

    elif li == "配方管理":
        recipe.show_recipe_page()

    elif li == "配方-色粉":
        color.show_color_page()

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
        st.info("請從左側選擇一個功能。")
