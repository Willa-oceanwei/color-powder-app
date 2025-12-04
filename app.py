# app.py
import streamlit as st
import importlib
from pathlib import Path
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import traceback

# ---------- Page config ----------
st.set_page_config(layout="wide", page_title="佳咊配方管理系統", initial_sidebar_state="expanded")

# ---------- Basic CSS to mimic your HTML look ----------
st.markdown(
    """
    <style>
    /* Top nav */
    .top-nav { display:flex; align-items:center; gap:8px; padding:8px 12px; background:#2c3e50; color:white; }
    .top-nav h2 { margin:0; color: white; font-size:18px; }
    .top-nav .btn { background:#34495e; color:white; border-radius:6px; padding:6px 10px; margin-right:6px; border:none; }
    .top-nav .btn:hover { background:#3f5a72; }

    /* Left sidebar */
    .left-panel { background:#2c3e50; color:white; padding:12px; height:calc(100vh - 72px); overflow:auto; }
    .left-panel .section-title { color:#dbd818; font-weight:bold; margin-top:8px; margin-bottom:4px; }
    .left-panel .menu-button { width:100%; text-align:left; background:transparent; color:#ffffff; border:none; padding:6px 8px; border-radius:6px; }
    .left-panel .menu-button:hover { background:#3a4650; }
    .left-panel .sub-item { margin-left:12px; color:#ffffff; padding:4px 0; }
    .left-panel .collapsed { opacity:0.85; }

    /* Right content header */
    .content-header { padding:8px 0; font-size:18px; font-weight:bold; }

    /* Small helpers */
    .muted { color: #bbb; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Initialize session state ----------
if "main_tab" not in st.session_state:
    st.session_state.main_tab = "配方管理"  # 默认上方分頁
if "left_item" not in st.session_state:
    st.session_state.left_item = "配方管理"  # 默认左側項目
if "quick_recipe" not in st.session_state:
    st.session_state.quick_recipe = False
if "quick_order" not in st.session_state:
    st.session_state.quick_order = False
# collapse state for tree sections
if "collapse_recipe" not in st.session_state:
    st.session_state.collapse_recipe = False
if "collapse_order" not in st.session_state:
    st.session_state.collapse_order = False
if "collapse_query" not in st.session_state:
    st.session_state.collapse_query = False

# ---------- Safe spreadsheet loader ----------
spreadsheet = None
sheet_error_msg = None

def try_init_spreadsheet():
    global spreadsheet, sheet_error_msg
    if "spreadsheet" in st.session_state:
        spreadsheet = st.session_state.spreadsheet
        return

    # Try to get GCP service account from secrets
    try:
        if "gcp" in st.secrets and "gcp_service_account" in st.secrets["gcp"]:
            service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
            creds = Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
            client = gspread.authorize(creds)
            sheet_url = st.secrets.get("sheet_url") or st.secrets.get("SHEET_URL")
            if not sheet_url:
                sheet_error_msg = 'st.secrets 未提供 sheet_url（key "sheet_url"）。'
                return
            st.session_state["spreadsheet"] = client.open_by_url(sheet_url)
            spreadsheet = st.session_state["spreadsheet"]
            return
    except Exception as e:
        sheet_error_msg = f"無法使用 gcp 的 service account 連線：{type(e).__name__} {e}"
        # don't return yet; try fallback

    # Fallback: try sheet_url only (no creds) -> will fail but we handle gracefully
    try:
        sheet_url = st.secrets.get("sheet_url") or st.secrets.get("SHEET_URL")
        if not sheet_url:
            if sheet_error_msg is None:
                sheet_error_msg = 'st.secrets has no key "sheet_url" nor valid "gcp".'
            return
        # If you had a public sheet and used gspread without creds, still needs creds; just set message
        sheet_error_msg = '找到 sheet_url，但尚未提供授權（gcp service account）- 如需 Google Sheet 功能請設定 st.secrets["gcp"]["gcp_service_account"]'
        return
    except Exception as e:
        sheet_error_msg = f"嘗試使用 sheet_url 時發生錯誤：{e}"
        return

try_init_spreadsheet()

# ---------- Safe utils importer ----------
# expected utils modules: utils.common, utils.color, utils.recipe, utils.order, utils.customer, utils.query, utils.inventory, utils.schedule
utils = {}
utils_names = ["common", "color", "recipe", "order", "customer", "query", "inventory", "schedule"]
for name in utils_names:
    try:
        mod = importlib.import_module(f"utils.{name}")
        utils[name] = mod
    except Exception as e:
        utils[name] = None  # missing allowed
        # store small debug in session for user's diagnosis
        st.session_state.setdefault("utils_import_errors", {})[name] = str(e)

def safe_call(module_name, func_name, *args, **kwargs):
    mod = utils.get(module_name)
    if mod is None:
        st.info(f"模組 utils.{module_name} 未載入（或不存在），頁面為『開發中』。")
        return None
    func = getattr(mod, func_name, None)
    if func is None:
        st.info(f"utils.{module_name} 不含 {func_name} 函式（或尚未實作）。")
        return None
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"呼叫 {module_name}.{func_name} 發生錯誤：{type(e).__name__} {e}")
        st.text(traceback.format_exc())
        return None

# ---------- Top nav ----------
st.markdown("<div class='top-nav'>", unsafe_allow_html=True)
col_a, col_b, col_c = st.columns([2, 6, 2])

with col_a:
    st.markdown("<h2 style='margin:0; color:white;'>佳咊配方管理系統</h2>", unsafe_allow_html=True)

with col_b:
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("配方管理", key="top_recipe_btn"):
            st.session_state.main_tab = "配方管理"
            # set sensible left_item
            st.session_state.left_item = "配方管理"
    with c2:
        if st.button("生產單管理", key="top_order_btn"):
            st.session_state.main_tab = "生產單管理"
            st.session_state.left_item = "生產單"

with col_c:
    # 快捷鈕
    if st.button("🔎 配方快速", key="quick_recipe_btn"):
        st.session_state.quick_recipe = True
        st.session_state.main_tab = "配方管理"
        st.session_state.left_item = "配方管理"
    if st.button("🖨 生產單快速", key="quick_order_btn"):
        st.session_state.quick_order = True
        st.session_state.main_tab = "生產單管理"
        st.session_state.left_item = "生產單"

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<hr/>", unsafe_allow_html=True)

# ---------- Layout: left tree + right content ----------
left_col, right_col = st.columns([1.1, 6], gap="small")

with left_col:
    st.markdown("<div class='left-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>功能導航</div>", unsafe_allow_html=True)

    # Single top item: 色粉管理 (but you wanted it under 配方管理, so show as a top quick access)
    if st.button("色粉管理 (快速)", key="left_color_top"):
        st.session_state.left_item = "色粉管理"

    # 配方管理 section (collapsible)
    col_label = "配方管理"
    expand = st.session_state.collapse_recipe
    arrow = "▾" if expand else "▸"
    if st.button(f"{arrow} {col_label}", key="toggle_recipe"):
        st.session_state.collapse_recipe = not st.session_state.collapse_recipe

    if st.session_state.collapse_recipe:
        # subitems
        if st.button("  ├ 色粉管理", key="left_recipe_color"):
            st.session_state.left_item = "配方-色粉管理"
        if st.button("  ├ 客戶名單", key="left_recipe_customer"):
            st.session_state.left_item = "配方-客戶名單"
        if st.button("  └ 配方管理", key="left_recipe_recipe"):
            st.session_state.left_item = "配方管理"

    # 生產單管理 section (collapsible)
    col_label = "生產單管理"
    expand = st.session_state.collapse_order
    arrow = "▾" if expand else "▸"
    if st.button(f"{arrow} {col_label}", key="toggle_order"):
        st.session_state.collapse_order = not st.session_state.collapse_order

    if st.session_state.collapse_order:
        if st.button("  ├ 生產單", key="left_order_order"):
            st.session_state.left_item = "生產單"
        if st.button("  └ 代工排程（開發中）", key="left_order_schedule"):
            st.session_state.left_item = "代工排程"

    # 查詢 section
    col_label = "查詢"
    expand = st.session_state.collapse_query
    arrow = "▾" if expand else "▸"
    if st.button(f"{arrow} {col_label}", key="toggle_query"):
        st.session_state.collapse_query = not st.session_state.collapse_query

    if st.session_state.collapse_query:
        if st.button("  ├ Pantone 色號表", key="left_query_pantone"):
            st.session_state.left_item = "Pantone色號表"
        if st.button("  └ 交叉查詢", key="left_query_cross"):
            st.session_state.left_item = "交叉查詢"

    # 庫存、匯入備份
    if st.button("庫存區", key="left_inventory"):
        st.session_state.left_item = "庫存區"
    if st.button("匯入備份（開發中）", key="left_import"):
        st.info("匯入備份：開發中")

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    st.markdown(f"<div class='content-header'>{st.session_state.main_tab} — {st.session_state.left_item}</div>", unsafe_allow_html=True)

    # show helpful sheet status
    if spreadsheet is None:
        st.warning("⚠️ 無法取得 spreadsheet：" + (sheet_error_msg or "未設定。請在 st.secrets 添加 gcp 或 sheet_url。"))
        st.markdown("<div class='muted'>Google Sheet 功能暫時不可用；其餘 UI 可繼續操作（頁面顯示為『開發中』或讀取本地 CSV）。</div>", unsafe_allow_html=True)

    # ROUTING: map left_item -> utils functions
    li = st.session_state.left_item

    try:
        if li == "色粉管理" or li == "配方-色粉管理":
            # Prefer utils.color.show_color_page if present; else show recipe subpage if provided
            if utils.get("color"):
                safe_call("color", "show_color_page", spreadsheet)
            elif utils.get("recipe"):
                safe_call("recipe", "show_color_subpage", spreadsheet)
            else:
                st.info("色粉管理：開發中。")
        elif li == "配方管理":
            if utils.get("recipe"):
                safe_call("recipe", "show_recipe_page", spreadsheet)
            else:
                st.info("配方管理：開發中。")
        elif li == "配方-客戶名單":
            if utils.get("customer"):
                safe_call("customer", "show_customer_page", spreadsheet)
            else:
                st.info("客戶名單：開發中。")
        elif li == "生產單":
            if utils.get("order"):
                safe_call("order", "show_order_page", spreadsheet)
            else:
                st.info("生產單：開發中。")
        elif li == "代工排程":
            if utils.get("schedule"):
                safe_call("schedule", "show_schedule_page", spreadsheet)
            else:
                st.info("代工排程：開發中。")
        elif li == "Pantone色號表":
            if utils.get("query"):
                safe_call("query", "show_query_page", spreadsheet, mode="pantone")
            else:
                st.info("Pantone 色號表：開發中。")
        elif li == "交叉查詢":
            if utils.get("query"):
                safe_call("query", "show_query_page", spreadsheet, mode="cross")
            else:
                st.info("交叉查詢：開發中。")
        elif li == "庫存區":
            if utils.get("inventory"):
                safe_call("inventory", "show_inventory_page", spreadsheet)
            else:
                st.info("庫存區：開發中。")
        else:
            st.info("選項尚未實作或錯誤，請從左側選單選擇。")
    except Exception as e:
        st.error(f"載入頁面時發生錯誤：{type(e).__name__} {e}")
        st.text(traceback.format_exc())

# ---------- Footer / debug for missing utils (helpful) ----------
with st.expander("開發用：檢查 utils 載入狀態 / debug", expanded=False):
    st.write("已載入 modules：")
    for k, v in utils.items():
        status = "OK" if v else "MISSING"
        st.write(f"- utils.{k}: {status}")
    if "utils_import_errors" in st.session_state:
        st.write("載入錯誤摘要：")
        st.json(st.session_state["utils_import_errors"])
    st.write("spreadsheet:", "AVAILABLE" if spreadsheet else "UNAVAILABLE")
    if sheet_error_msg:
        st.write("sheet error:", sheet_error_msg)
