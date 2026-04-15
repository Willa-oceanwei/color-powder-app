# ===== app.py =====
import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import time
import re
from pathlib import Path        
from datetime import datetime

st.set_page_config(
    page_title="配方管理系統",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    _, login_col, _ = st.columns([2, 3, 2])
    with login_col:
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
    
# ======== 🎨 ERP UI THEME (ENTERPRISE DARK) ========
# ======== 🚀 SaaS ERP UI (Notion + SAP Hybrid) ========
def apply_modern_style():
    import streamlit as st

    st.markdown("""
<style>

/* ===================================================
   🌌 GLOBAL
=================================================== */

.stApp, [data-testid="stAppViewContainer"]{
    background:#0a0a0a !important;
    font-family: 'Inter', 'DM Mono', sans-serif !important;
}

/* ===================================================
   🧭 SIDEBAR (SAP STYLE + NOTION CLEAN)
=================================================== */

[data-testid="stSidebar"]{
    background:#0b2f4a !important;
    min-width:200px !important;
    max-width:200px !important;
    padding-top:10px !important;
}

/* title */
.erp-title{
    font-size:15px;
    font-weight:700;
    color:#ffffff;
    margin-bottom:2px;
}

.erp-sub{
    font-size:10px;
    color:#9fb6cc;
    margin-bottom:12px;
}

/* group */
[data-testid="stSidebar"] .erp-group{
    font-size:9.5px;
    color:#e06b3a;
    letter-spacing:1.2px;
    margin:10px 0 4px 0;
}

/* sidebar buttons */
[data-testid="stSidebar"] div.stButton > button{
    background:transparent !important;
    color:#ffffff !important;
    border:0 !important;
    width:100%;
    text-align:left;
    font-size:13px;
    padding:6px 10px !important;
    border-radius:6px;
}

/* hover */
[data-testid="stSidebar"] div.stButton > button:hover{
    background:#124466 !important;
}

/* active */
[data-testid="stSidebar"] div.stButton > button[kind="primary"]{
    background:#c6582f !important;
    border-left:3px solid #ffb199 !important;
}

/* ===================================================
   🟦 MAIN LAYOUT
=================================================== */

.block-container{
    padding-top:18px;
    padding-left:22px;
    padding-right:22px;
}

/* ===================================================
   ⭐ LEVEL 1 TAB (SAP MODULE STYLE)
=================================================== */

div.block-container .stTabs [data-baseweb="tab-list"]{
    gap:6px;
    border-bottom:1px solid rgba(255,255,255,0.08);
}

/* tab */
div.block-container .stTabs [data-baseweb="tab-list"] > button{

    background:#0b2f4a !important;
    color:#cfd8e3 !important;

    padding:4px 16px !important;
    border-radius:8px 8px 0 0;

    font-size:13px;
    font-weight:600;

    border:1px solid rgba(255,255,255,0.06);

    transition:0.15s ease;

}

/* hover */
div.block-container .stTabs [data-baseweb="tab-list"] > button:hover{
    background:#124466 !important;
    color:#ffffff !important;
}

/* active */
div.block-container .stTabs [data-baseweb="tab-list"] > button[aria-selected="true"]{

    background:#c6582f !important;
    color:#ffffff !important;

    border-bottom:2px solid #0a0a0a !important;

    box-shadow:0 -2px 10px rgba(198,88,47,0.25);

}

/* ===================================================
   🟠 LEVEL 2 TAB (NOTION STYLE)
=================================================== */

div.block-container div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab-list"]{

    gap:14px;
    border-bottom:1px solid rgba(255,255,255,0.06);
    margin-top:8px;

}

/* tab */
div.block-container div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab-list"] > button{

    background:transparent !important;
    color:#9fb6cc !important;

    border:none !important;

    padding:2px 6px !important;
    font-size:12.5px;
    font-weight:500;

    border-radius:0;

}

/* hover */
div.block-container div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab-list"] > button:hover{
    color:#ff8a57 !important;
}

/* active */
div.block-container div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab-list"] > button[aria-selected="true"]{

    color:#ff8a57 !important;

    border-bottom:2px solid #ff8a57 !important;

    box-shadow:
        0 2px 6px rgba(255,138,87,0.55),
        0 0 14px rgba(255,138,87,0.45),
        0 0 24px rgba(255,138,87,0.35);

}

/* ===================================================
   🧾 INPUT (CLEAN ERP)
=================================================== */

input, textarea{
    background:#161616 !important;
    color:#ffffff !important;
    border:1px solid rgba(255,255,255,0.12) !important;
    border-radius:6px !important;
    font-family:'DM Mono', monospace !important;
}

/* ===================================================
   🔘 BUTTONS
=================================================== */

div.block-container .stButton > button{
    background:#0b2f4a !important;
    color:white !important;
    border-radius:6px !important;
    border:1px solid rgba(255,255,255,0.12) !important;
    font-weight:600 !important;
}

div.block-container .stButton > button:hover{
    background:#124466 !important;
}

div.block-container .stButton > button[kind="primary"]{
    background:#1a5a84 !important;
}

/* ===================================================
   📊 TABLE (ERP CLEAN GRID)
=================================================== */

div[data-testid="stDataFrame"]{
    border-radius:8px;
    overflow:hidden;
}

div[data-testid="stDataFrame"] table{
    width:100% !important;
    table-layout:fixed !important;
}

/* ===================================================
   📦 POPUP / SELECTBOX (NOTION STYLE)
=================================================== */

div[data-baseweb="popover"]{
    background:#1f2630 !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    border-radius:10px !important;
}

ul[role="listbox"] li{
    color:#d7e3ef !important;
}

ul[role="listbox"] li:hover{
    background:rgba(198,88,47,0.15) !important;
}

/* ===================================================
   ✨ FONT
=================================================== */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=DM+Mono:wght@300;400;500&display=swap');

</style>
""", unsafe_allow_html=True)
    
# ======== Sidebar Menu ========

def render_sidebar():
    import streamlit as st

    MENU_ITEMS = [
        {"group":"生產","key":"生產單管理","label":"生產單管理"},
        {"group":"生產","key":"配方管理","label":"配方管理"},
        {"group":"生產","key":"代工管理","label":"代工管理"},
        {"group":"倉儲","key":"庫存區","label":"庫存區"},
        {"group":"倉儲","key":"洗車廠庫存","label":"洗車廠庫存"},
        {"group":"倉儲","key":"採購管理","label":"採購管理"},
        {"group":"查詢","key":"查詢區","label":"查詢區"},
        {"group":"設定","key":"客戶名單","label":"客戶名單"},
        {"group":"設定","key":"匯入備份","label":"匯入備份"},
    ]

    if "menu" not in st.session_state:
        st.session_state.menu = "生產單管理"

    with st.sidebar:

        st.markdown("<div class='erp-title'>配方管理系統</div>", unsafe_allow_html=True)
        st.markdown("<div class='erp-sub'>v2.1 · ERP Edition</div>", unsafe_allow_html=True)

        current_group = None

        for item in MENU_ITEMS:

            if item["group"] != current_group:
                st.markdown(f"<div class='erp-group'>{item['group']}</div>", unsafe_allow_html=True)
                current_group = item["group"]

            if st.button(
                item["label"],
                key=item["key"],
                use_container_width=True,
                type="primary" if st.session_state.menu == item["key"] else "secondary"
            ):
                st.session_state.menu = item["key"]
                
#=======apply_arrow_nav()======

def apply_arrow_nav():
    import streamlit as st

    st.markdown("""
<script>
(function () {
  if (window._arrowNavBound) return;
  window._arrowNavBound = true;

  function getInputs() {
    return Array.from(
      document.querySelectorAll(
        'input:not([disabled]):not([readonly]), textarea:not([disabled])'
      )
    ).filter(el => el.offsetParent !== null);
  }

  function moveFocus(current, step) {
    const inputs = getInputs();
    const idx = inputs.indexOf(current);
    if (idx < 0) return;
    const next = inputs[idx + step];
    if (next) { next.focus(); if (next.select) next.select(); }
  }

  document.addEventListener('keydown', function(e) {
    const t = e.target;
    if (!(t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement)) return;
    if (t.disabled || t.readOnly) return;

    if (['ArrowDown','ArrowRight'].includes(e.key)) {
      e.preventDefault(); moveFocus(t, +1);
    }
    if (['ArrowUp','ArrowLeft'].includes(e.key)) {
      e.preventDefault(); moveFocus(t, -1);
    }
  }, true);
})();
</script>
""", unsafe_allow_html=True)

# ======== ENABLE ========

apply_modern_style()
apply_arrow_nav()
render_sidebar()


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

SHEET_CACHE_TTL_SECONDS = 300

def get_cached_worksheet(sheet_name):
    cache = st.session_state.setdefault("_ws_cache", {})
    if sheet_name in cache:
        return cache[sheet_name]
    ws = spreadsheet.worksheet(sheet_name)
    cache[sheet_name] = ws
    return ws

def _load_sheet_values_with_cache(sheet_name, force_reload=False, ttl_seconds=SHEET_CACHE_TTL_SECONDS):
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


def _set_sheet_values_cache(sheet_name, values):
    now = datetime.now().timestamp()
    st.session_state.setdefault("_sheet_values_cache", {})[sheet_name] = {
        "timestamp": now,
        "values": [row[:] for row in values],
    }
    st.session_state.get("_sheet_df_cache", {}).pop(sheet_name, None)


def get_cached_sheet_df(sheet_name, force_reload=False, ttl_seconds=SHEET_CACHE_TTL_SECONDS):
    values = _load_sheet_values_with_cache(
        sheet_name,
        force_reload=force_reload,
        ttl_seconds=ttl_seconds,
    )
    values_ts = st.session_state.get("_sheet_values_cache", {}).get(sheet_name, {}).get("timestamp", 0)
    df_cache = st.session_state.setdefault("_sheet_df_cache", {})
    df_cached = df_cache.get(sheet_name)
    if df_cached and df_cached.get("source_ts") == values_ts:
        return df_cached["df"].copy()

    if len(values) <= 1:
        df = pd.DataFrame(columns=values[0] if values else [])
    else:
        df = pd.DataFrame(values[1:], columns=values[0])

    df_cache[sheet_name] = {"source_ts": values_ts, "df": df.copy()}
    return df


def get_cached_sheet_values(sheet_name, force_reload=False, ttl_seconds=SHEET_CACHE_TTL_SECONDS):
    values = _load_sheet_values_with_cache(
        sheet_name,
        force_reload=force_reload,
        ttl_seconds=ttl_seconds,
    )
    return [row[:] for row in values]

def invalidate_sheet_cache(sheet_name=None):
    if sheet_name is None:
        st.session_state.pop("_sheet_df_cache", None)
        st.session_state.pop("_ws_cache", None)
        st.session_state.pop("_sheet_values_cache", None)
        return

    st.session_state.get("_sheet_df_cache", {}).pop(sheet_name, None)
    st.session_state.get("_ws_cache", {}).pop(sheet_name, None)
    st.session_state.get("_sheet_values_cache", {}).pop(sheet_name, None)


def clean_powder_id(x):
    """清理色粉ID，移除空白、全形空白，轉大寫"""
    if pd.isna(x) or x == "":
        return ""
    return str(x).strip().replace('\u3000', '').replace(' ', '').upper()



# 需要預載的 Sheet 對應表（Sheet名稱 → session_state key）
PRELOAD_SHEETS = {
    "配方管理": "df_recipe",
    "客戶名單": "_recipe_customers",
    "色粉管理": "df_color",
    "生產單": "df_order",
    "代工管理": "df_oem",
}


def preload_all_data(force=False):
    """
    一次性把所有常用 Sheet 載入 session_state。
    force=False（預設）：session_state 已有非空資料就跳過，不打 API。
    force=True：強制重讀（寫入後才用）。
    """
    for sheet_name, state_key in PRELOAD_SHEETS.items():
        if not force:
            existing = st.session_state.get(state_key)
            if isinstance(existing, pd.DataFrame) and not existing.empty:
                continue

        try:
            df = get_cached_sheet_df(sheet_name, force_reload=force)
        except Exception:
            df = pd.DataFrame()

        # 配方管理額外清理配方編號
        if sheet_name == "配方管理" and not df.empty and "配方編號" in df.columns:
            df["配方編號"] = df["配方編號"].astype(str).map(clean_powder_id)

        st.session_state[state_key] = df

    # 相容舊程式：配方管理同時會讀 st.session_state.df
    if "df_recipe" in st.session_state:
        st.session_state.df = st.session_state.df_recipe

    # 僅在配方管理所需資料齊備時，才標記已載入
    recipe_ready = all(
        key in st.session_state and isinstance(st.session_state.get(key), pd.DataFrame)
        for key in ["df_recipe", "df_color", "_recipe_customers"]
    )
    if recipe_ready:
        st.session_state.recipe_data_loaded = True

    # ⚠️ 代工管理還需要 df_delivery / df_return，這裡不要先設 oem_data_loaded
    # 讓代工分頁自己的 load_oem_data() 仍可正常建立完整資料
    # 讓各分頁舊版「已載入」旗標同步設好，避免它們自己重讀
    st.session_state.recipe_data_loaded = True
    st.session_state.oem_data_loaded = True

# ── App 第一次啟動時，執行一次預載 ──
if "app_data_loaded" not in st.session_state:
    with st.spinner("載入資料中..."):
        preload_all_data(force=False)
    st.session_state.app_data_loaded = True

# ── 若某分頁寫入後設了 need_reload_sheet，只重載那一張表 ──
if st.session_state.get("need_reload_sheet"):
    sheet_to_reload = st.session_state.pop("need_reload_sheet")
    state_key = PRELOAD_SHEETS.get(sheet_to_reload)
    if state_key:
        try:
            invalidate_sheet_cache(sheet_to_reload)
            df = get_cached_sheet_df(sheet_to_reload, force_reload=True)
            if sheet_to_reload == "配方管理" and not df.empty and "配方編號" in df.columns:
                df["配方編號"] = df["配方編號"].astype(str).map(clean_powder_id)
            st.session_state[state_key] = df
        except Exception:
            pass


# ======== ERP HTML Shell（僅替換畫面層，保留後端邏輯）=========
MENU_ITEMS = [
    {"key": "生產單管理", "label": "生產單管理", "group": "生產"},
    {"key": "配方管理", "label": "配方管理", "group": "生產"},
    {"key": "代工管理", "label": "代工管理", "group": "生產"},
    {"key": "庫存區", "label": "庫存區", "group": "倉儲"},
    {"key": "洗車廠庫存", "label": "洗車廠庫存", "group": "倉儲"},
    {"key": "採購管理", "label": "採購管理", "group": "倉儲"},
    {"key": "查詢區", "label": "查詢區", "group": "查詢"},
    {"key": "客戶名單", "label": "客戶名單", "group": "設定"},
    {"key": "匯入備份", "label": "匯入備份", "group": "設定"},
]

# ======== ERP Nav（sidebar 配色改為 #23272D，群組字改為 #bf6030）========
def render_erp_nav():
    import streamlit as st

    MENU_ITEMS = [
        {"key": "生產單管理", "label": "生產單管理", "group": "生產"},
        {"key": "配方管理",   "label": "配方管理",   "group": "生產"},
        {"key": "代工管理",   "label": "代工管理",   "group": "生產"},
        {"key": "庫存區",     "label": "庫存區",     "group": "倉儲"},
        {"key": "洗車廠庫存", "label": "洗車廠庫存", "group": "倉儲"},
        {"key": "採購管理",   "label": "採購管理",   "group": "倉儲"},
        {"key": "查詢區",     "label": "查詢區",     "group": "查詢"},
        {"key": "客戶名單",   "label": "客戶名單",   "group": "設定"},
        {"key": "匯入備份",   "label": "匯入備份",   "group": "設定"},
    ]

    groups = {}
    for item in MENU_ITEMS:
        groups.setdefault(item["group"], []).append(item)

    if "menu" not in st.session_state:
        st.session_state.menu = "生產單管理"
    render_erp_nav()          # ← 加這行來渲染 sidebar

    st.markdown(
        """
        <style>
        /* ── Sidebar 底色：#23272D ── */
        section[data-testid="stSidebar"] {
            min-width: 210px !important;
            max-width: 210px !important;
            background: #23272D !important;
            border-right: 1px solid rgba(255,255,255,0.08) !important;
        }

        section[data-testid="stSidebar"] .erp-title {
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            margin: 0 0 0.25rem 0;
            letter-spacing: 0.5px;
        }
        section[data-testid="stSidebar"] .erp-sub {
            font-size: 10px;
            color: #7fa8d1;
            margin-bottom: 0.8rem;
        }

        /* ── 群組字：偏紅橘 #bf6030 ── */
        section[data-testid="stSidebar"] .erp-group {
            color: #bf6030;
            font-size: 10px;
            letter-spacing: 0.8px;
            margin: 0.5rem 0 0.25rem 0.15rem;
        }

        section[data-testid="stSidebar"] div.stButton > button {
            border-radius: 2px !important;
            text-align: left !important;
            width: 100% !important;
            font-size: 12.5px !important;
            padding: 0.42rem 0.55rem !important;
            border-left: 3px solid transparent !important;
            background: transparent !important;
            color: #b8d0eb !important;
            border-top: 0 !important;
            border-right: 0 !important;
            border-bottom: 0 !important;
            box-shadow: none !important;
            transition: background 0.15s, color 0.15s;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover {
            background: #2d3540 !important;
            color: #ffffff !important;
            border-left-color: #3a8fd4 !important;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
            background: #2a3f5a !important;
            color: #ffffff !important;
            border-left-color: #4fa3e0 !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown('<div class="erp-title">配方管理系統</div>', unsafe_allow_html=True)
        st.markdown('<div class="erp-sub">v2.1 · ERP Edition</div>', unsafe_allow_html=True)

        for group_name, items in groups.items():
            st.markdown(f'<div class="erp-group">{group_name}</div>', unsafe_allow_html=True)
            for item in items:
                is_active = st.session_state.menu == item["key"]
                btn_kwargs = {
                    "key": f"menu_{item['key']}",
                    "use_container_width": True,
                }
                if is_active:
                    btn_kwargs["type"] = "primary"
        
                if st.button(item["label"], **btn_kwargs):
                    if not is_active:
                        st.session_state.menu = item["key"]
                        st.rerun()

    return st.session_state.menu

            
# ===== 調整整體主內容上方距離 =====
st.markdown("""
    <style>
    .block-container { margin-top: -0.4rem !important; }
    </style>
""", unsafe_allow_html=True)

# 重新套用主題，確保切換任何功能分頁後仍維持紫色主題樣式
apply_modern_style()

# ================= 共用 Google Sheet 穩定寫入工具 =================
def safe_append_row(ws, row_values):
    clean_row = ["" if v is None else str(v) for v in row_values]
    ws.append_row(clean_row, value_input_option="USER_ENTERED")
    cache = st.session_state.get("_sheet_values_cache", {}).get(ws.title)
    if cache and cache.get("values"):
        updated_values = [row[:] for row in cache["values"]]
        updated_values.append(clean_row)
        _set_sheet_values_cache(ws.title, updated_values)
    else:
        invalidate_sheet_cache(ws.title)

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

# ======== Helper Functions for Recipe Management =========
def fix_leading_zero(x):
    """補足前導零（僅針對純數字且長度<4的字串）"""
    x = str(x).strip()
    if x.isdigit() and len(x) < 4:
        x = x.zfill(4)
    return x.upper()

def normalize_search_text(text):
    """標準化搜尋文字"""
    return fix_leading_zero(clean_powder_id(text))

def split_search_keywords(raw_text):
    """拆解多條件關鍵字，支援逗號/頓號/分號/空白。"""
    text = str(raw_text or "").strip()
    if not text:
        return []
    return [t.strip() for t in re.split(r"[，,、;\s\n\t]+", text) if t.strip()]

def matches_all_keywords(target_text, keywords):
    """文字是否符合多條件 AND 關鍵字（不分大小寫）。"""
    if not keywords:
        return True
    haystack = str(target_text or "").lower()
    for kw in keywords:
        needle = str(kw or "").strip().lower()
        if needle and needle not in haystack:
            return False
    return True

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

def parse_pack_value(raw_val):
    """將包裝重量/份數轉為數值，容忍包含單位或符號的輸入（例如 30K、25kg、1,200）。"""
    if raw_val is None:
        return 0.0
    text = str(raw_val).strip()
    if not text:
        return 0.0
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except Exception:
        return 0.0

def calc_packs_total_kg(order_row):
    """依生產單包裝重量/份數，計算總包裝量（kg）。"""
    packs_total = 0.0
    for j in range(1, 5):
        packs_total += (
            parse_pack_value(order_row.get(f"包裝重量{j}", 0)) *
            parse_pack_value(order_row.get(f"包裝份數{j}", 0))
        )
    return packs_total

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

# ===== 自訂函式：產生生產單列印格式 =====      
def generate_production_order_print(
    order,
    recipe_row,
    additional_recipe_rows=None,
    show_additional_ids=True,
    include_remark=True
):
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
        else:
            pack_line.append(" " * pack_col_width)
        
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
    if include_remark and remark_text:  # 有輸入內容才印出
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
        show_additional_ids=show_additional_ids,  # 👈 新增參數
        include_remark=True
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
    _set_sheet_values_cache(ws.title, values)

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
    
if "menu" not in st.session_state:
    st.session_state.menu = "生產單管理"
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
            st.rerun()
    
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
        st.dataframe(
            df_filtered[columns],
            use_container_width=True,
            hide_index=True,
            height=420
        )
    
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
    from datetime import datetime, timedelta
    import pandas as pd

    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "代工轉換倍率",
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
    components.html(
        """
        <script>
        const storageKey = "recipe_mgmt_active_tab";
        const tabTexts = ["📝 配方建立", "📜 配方記錄表", "👀 配方預覽/修改/刪除", "🪅 色粉管理", "👹 色母換算"];

        function bindRecipeTabs() {
            const doc = window.parent.document;
            const allTabs = Array.from(doc.querySelectorAll('button[role="tab"]'));
            const targetTab = allTabs.find(btn => tabTexts.includes(btn.textContent.trim()));
            if (!targetTab) return false;

            const tablist = targetTab.closest('div[role="tablist"]');
            if (!tablist) return false;

            const tabs = Array.from(tablist.querySelectorAll('button[role="tab"]'));
            const savedIndex = parseInt(sessionStorage.getItem(storageKey), 10);
            if (!Number.isNaN(savedIndex) && tabs[savedIndex] && tabs[savedIndex].getAttribute('aria-selected') !== 'true') {
                tabs[savedIndex].click();
            }

            tabs.forEach((tab, idx) => {
                if (tab.dataset.recipePersistBound === '1') return;
                tab.dataset.recipePersistBound = '1';
                tab.addEventListener('click', () => sessionStorage.setItem(storageKey, String(idx)));
            });
            return true;
        }

        if (!bindRecipeTabs()) {
            const observer = new MutationObserver(() => {
                if (bindRecipeTabs()) observer.disconnect();
            });
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
        }
        </script>
        """,
        height=0,
    )

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
    
        # ===== 配方 toast 顯示（rerun 後觸發）=====
        if st.session_state.get("recipe_toast"):
            st.toast(
                st.session_state["recipe_toast"].get("msg", "已儲存"),
                icon=st.session_state["recipe_toast"].get("icon", "✅")
            )
            st.session_state.pop("recipe_toast", None)
    
        # ===== 表單初始化 =====
        if "form_recipe" not in st.session_state or not st.session_state.form_recipe:
            st.session_state.form_recipe = {col: "" for col in columns}
            st.session_state.form_recipe.update({
                "配方類別": "原始配方", "狀態": "啟用",
                "色粉類別": "配方", "計量單位": "包",
                "淨重單位": "g", "合計類別": "無"
            })
    
        if "num_powder_rows" not in st.session_state:
            st.session_state.num_powder_rows = 5
        if "add_powder_clicked" not in st.session_state:
            st.session_state.add_powder_clicked = False
    
        fr = st.session_state.form_recipe
    
        with st.form("recipe_form"):
            # ---------------- 基本資訊 ----------------
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號",""), key="form_recipe_配方編號")
            with col2:
                fr["顏色"] = st.text_input("顏色", value=fr.get("顏色",""), key="form_recipe_顏色")
            with col3:
                options = [""] + customer_options
                current = f"{fr.get('客戶編號','')} - {fr.get('客戶名稱','')}" if fr.get("客戶編號") else ""
                customer_filter_text = st.text_input(
                    "客戶下拉搜尋（可多條件）",
                    value="",
                    placeholder="例如：環瑩,27706",
                    key="form_recipe_customer_filter"
                )
                customer_keywords = split_search_keywords(customer_filter_text)
                filtered_customer_options = [""] + [
                    opt for opt in customer_options
                    if matches_all_keywords(opt, customer_keywords)
                ]
                if current and current not in filtered_customer_options:
                    filtered_customer_options.append(current)
                index = filtered_customer_options.index(current) if current in filtered_customer_options else 0
                selected = st.selectbox("客戶編號", filtered_customer_options, index=index, key="form_recipe_selected_customer")
                if selected and " - " in selected:
                    c_no, c_name = selected.split(" - ",1)
                    fr["客戶編號"] = c_no.strip()
                    fr["客戶名稱"] = c_name.strip()
            with col4:
                opts = ["原始配方","附加配方"]
                cur = fr.get("配方類別", opts[0])
                fr["配方類別"] = st.selectbox("配方類別", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_配方類別")

            # ---------------- 狀態/原始配方/色粉類別/計量單位 ----------------
            col5, col6, col7, col8 = st.columns(4)
            with col5:
                opts = ["啟用","停用"]
                cur = fr.get("狀態", opts[0])
                fr["狀態"] = st.selectbox("狀態", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_狀態")
            with col6:
                fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方",""), key="form_recipe_原始配方")
            with col7:
                opts = ["配方","色母","色粉","添加劑","其他"]
                cur = fr.get("色粉類別", opts[0])
                fr["色粉類別"] = st.selectbox("色粉類別", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_色粉類別")
            with col8:
                opts = ["包","桶","kg","其他"]
                cur = fr.get("計量單位", opts[0])
                fr["計量單位"] = st.selectbox("計量單位", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_計量單位")

            pantone_col, oem_ratio_col = st.columns(2)
            with pantone_col:
                fr["Pantone色號"] = st.text_input("Pantone色號", value=fr.get("Pantone色號",""), key="form_recipe_Pantone色號")
            with oem_ratio_col:
                fr["代工轉換倍率"] = st.number_input(
                    "代工轉換倍率（僅代工管理生效）",
                    min_value=0.01,
                    value=float(fr.get("代工轉換倍率", 1) or 1),
                    step=0.01,
                    key="form_recipe_oem_multiplier"
                )
    
            # ---------------- 重要提醒 ----------------
            fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒",""), key="form_recipe_重要提醒")
    
            # ---------------- 比例欄位 ----------------
            colr1, col_colon, colr2, colr3, col_unit = st.columns([2,0.5,2,2,1])
            with colr1: fr["比例1"] = st.text_input("", value=fr.get("比例1",""), key="ratio1", label_visibility="collapsed")
            with col_colon:
                st.markdown("<div style='display:flex;justify-content:center;align-items:center;font-size:18px;font-weight:bold;height:36px;'>:</div>", unsafe_allow_html=True)
            with colr2: fr["比例2"] = st.text_input("", value=fr.get("比例2",""), key="ratio2", label_visibility="collapsed")
            with colr3: fr["比例3"] = st.text_input("", value=fr.get("比例3",""), key="ratio3", label_visibility="collapsed")
            with col_unit:
                st.markdown("<div style='display:flex;align-items:center;font-size:16px;height:36px;'>g/kg</div>", unsafe_allow_html=True)
    
            # ---------------- 備註 ----------------
            fr["備註"] = st.text_area("備註", value=fr.get("備註",""), key="form_recipe_備註")
    
            # ---------------- 色粉淨重 ----------------
            col1, col2 = st.columns(2)
            with col1: fr["淨重"] = st.text_input("色粉淨重", value=fr.get("淨重",""), key="form_recipe_淨重")
            with col2:
                opts = ["g","kg"]
                cur = fr.get("淨重單位", opts[0])
                fr["淨重單位"] = st.selectbox("單位", opts, index=opts.index(cur) if cur in opts else 0, key="form_recipe_淨重單位")
    
            # ---------------- 色粉設定 ----------------
            st.markdown("##### 色粉設定")
            powder_cols = st.columns(st.session_state.num_powder_rows)
            for i, col in enumerate(powder_cols, start=1):
                fr[f"色粉編號{i}"] = col.text_input(
                    f"色粉編號{i}",
                    value=fr.get(f"色粉編號{i}",""),
                    key=f"form_recipe_色粉編號{i}"
                )
            powder_weight_cols = st.columns(st.session_state.num_powder_rows)
            for i, col in enumerate(powder_weight_cols, start=1):
                fr[f"色粉重量{i}"] = col.text_input(
                    f"色粉重量{i}",
                    value=fr.get(f"色粉重量{i}",""),
                    key=f"form_recipe_色粉重量{i}"
                )
    
            # ---------------- 合計類別與差額 ----------------
            col1, col2 = st.columns(2)
            with col1:
                category_options = ["LA","MA","S","CA","T9","料","\u2002","其他"]
                default_raw = fr.get("合計類別","無")
                default = "\u2002" if default_raw=="無" else default_raw
                if default not in category_options: default = category_options[0]
                fr["合計類別"] = st.selectbox("合計類別", category_options, index=category_options.index(default), key="form_recipe_合計類別")
            with col2:
                try:
                    net = float(fr.get("淨重") or 0)
                    total = sum(float(fr.get(f"色粉重量{i}") or 0) for i in range(1,9))
                    st.write(f"合計差額: {net - total:.2f} g/kg")
                except:
                    st.write("合計差額: 計算錯誤")
    
            # ---------------- 按鈕區 ----------------
            col1, col2 = st.columns([3,2])
            with col1:
                submitted  = st.form_submit_button("💾 儲存配方")
            with col2:
                add_powder = st.form_submit_button("➕ 新增色粉列")
    
            # ── 表單提交後處理 ──
            if submitted:
                missing_powders = []
                for i in range(1, st.session_state.num_powder_rows + 1):
                    pid = clean_powder_id(fr.get(f"色粉編號{i}",""))
                    if pid and pid not in existing_powders_str:
                        missing_powders.append(fr.get(f"色粉編號{i}",""))

                if missing_powders:
                    st.session_state.recipe_toast = {
                        "msg": f"新增失敗：以下色粉尚未建檔 {', '.join(missing_powders)}",
                        "icon": "⚠️"
                    }
                    st.rerun()
                elif fr["配方編號"].strip() == "":
                    st.warning("⚠️ 請輸入配方編號！")
                elif fr["配方類別"]=="附加配方" and fr["原始配方"].strip()=="":
                    st.warning("⚠️ 附加配方必須填寫原始配方！")
                else:
                    edit_idx = st.session_state.get("edit_recipe_index")
                    if edit_idx is not None:
                        df.iloc[edit_idx] = pd.Series(fr, index=df.columns)
                        save_recipe_row(df, is_edit=True, edit_index=edit_idx)
                        st.session_state.recipe_toast = {"msg": f"配方 {fr['配方編號']} 已更新！", "icon": "✏️"}
                    else:
                        new_recipe_code = clean_powder_id(fr["配方編號"])
                        existing_codes = set(df["配方編號"].astype(str).map(clean_powder_id))
                        if new_recipe_code in existing_codes:
                            st.session_state.recipe_toast = {"msg": f"❌ 配方編號 {fr['配方編號']} 已存在，請勿重覆新增", "icon": "🚫"}
                            st.rerun()
                        else:
                            fr["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df = pd.concat([df,pd.DataFrame([fr])], ignore_index=True)
                            save_recipe_row(df, is_edit=False)
                            st.session_state.recipe_toast = {"msg": f"新增配方 {fr['配方編號']} 成功！", "icon": "🎉"}
    
                    st.session_state.form_recipe       = {col:"" for col in columns}
                    st.session_state.edit_recipe_index = None
                    st.rerun()
    
            # ── 新增色粉列 ──
            if add_powder and not st.session_state.add_powder_clicked:
                if st.session_state.num_powder_rows < 8:
                    st.session_state.num_powder_rows += 1
                    st.session_state.recipe_toast = {"msg": "已新增一列色粉欄位", "icon": "➕"}
                else:
                    st.session_state.recipe_toast = {"msg": "色粉列已達上限（8 列）", "icon": "ℹ️"}
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

            df_filtered = df[mask].copy()
            if not df_filtered.empty:
                if "建檔時間" in df_filtered.columns:
                    df_filtered["_建檔時間_dt"] = pd.to_datetime(df_filtered["建檔時間"], errors="coerce")
                else:
                    df_filtered["_建檔時間_dt"] = pd.NaT
                df_filtered["_原始序"] = df_filtered.index
                df_filtered = df_filtered.sort_values(
                    by=["_建檔時間_dt", "_原始序"],
                    ascending=[False, False]
                ).drop(columns=["_建檔時間_dt", "_原始序"], errors="ignore")
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
        if st.session_state.get("recipe_tab3_toast"):
            st.toast(
                st.session_state["recipe_tab3_toast"].get("msg", ""),
                icon=st.session_state["recipe_tab3_toast"].get("icon", "ℹ️")
            )
            st.session_state.pop("recipe_tab3_toast", None)

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
            if "last_selected_recipe_code_tab3" not in st.session_state:
                st.session_state["last_selected_recipe_code_tab3"] = ""

            recipe_codes = [""] + sorted(df_recipe["配方編號"].dropna().unique().tolist())
            code_label_map = {
                code: "" if code == "" else " | ".join(
                    df_recipe[df_recipe["配方編號"] == code][["配方編號", "顏色", "客戶名稱"]].iloc[0].astype(str)
                )
                for code in recipe_codes
            }
            recipe_filter_text = st.text_input(
                "配方下拉搜尋（可多條件）",
                value="",
                placeholder="例如：27706,環瑩",
                key="recipe_code_filter_tab3"
            )
            recipe_filter_keywords = split_search_keywords(recipe_filter_text)
            filtered_recipe_codes = [
                code for code in recipe_codes
                if code == "" or matches_all_keywords(code_label_map.get(code, ""), recipe_filter_keywords)
            ]
            current_recipe_code = st.session_state["select_recipe_code_page_tab3"]
            if current_recipe_code and current_recipe_code not in filtered_recipe_codes:
                filtered_recipe_codes.append(current_recipe_code)

            selected_code = st.selectbox(
                "輸入配方", options=filtered_recipe_codes,
                index=filtered_recipe_codes.index(current_recipe_code) if current_recipe_code in filtered_recipe_codes else 0,
                format_func=lambda code: code_label_map.get(code, ""),
                key="select_recipe_code_page_tab3"
            )

            # 只在切換配方時重置面板，避免按下刪除確認時被立即清掉狀態
            if st.session_state.get("last_selected_recipe_code_tab3") != selected_code:
                st.session_state.show_edit_recipe_panel     = False
                st.session_state.editing_recipe_code        = None
                st.session_state.show_delete_recipe_confirm = False
                st.session_state["last_selected_recipe_code_tab3"] = selected_code

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
                                st.session_state.pop("select_recipe_code_page_tab3", None)
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
                                st.session_state["recipe_tab3_toast"] = {
                                    "msg": f"已刪除配方：{code}",
                                    "icon": "🗑️"
                                }
                                st.rerun()
                        with c2:
                            if st.button("取消", key="confirm_delete_recipe_no_tab3"):
                                st.session_state.show_delete_recipe_confirm = False
                                st.session_state["recipe_tab3_toast"] = {
                                    "msg": "已取消刪除配方",
                                    "icon": "↩️"
                                }
                                st.rerun()

            # ── 修改配方面板 ──
            if st.session_state.get("show_edit_recipe_panel") and st.session_state.get("editing_recipe_code"):
                st.markdown("---")
                code = st.session_state.editing_recipe_code
                idx  = df_recipe[df_recipe["配方編號"] == code].index[0]
                fr   = df_recipe.loc[idx].to_dict()

                with st.form(f"edit_recipe_form_tab3_{code}"):

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        fr["配方編號"] = st.text_input("配方編號", fr.get("配方編號", ""), key=f"edit_recipe_code_{code}")
                    with col2:
                        fr["顏色"] = st.text_input("顏色", fr.get("顏色", ""), key=f"edit_recipe_color_{code}")
                    with col3:
                        cust_id  = fr.get("客戶編號", "").strip()
                        cust_name = fr.get("客戶名稱", "").strip()
                        current  = f"{cust_id} - {cust_name}" if cust_id else ""
                        customer_filter_text_edit = st.text_input(
                            "客戶下拉搜尋（可多條件）",
                            value="",
                            placeholder="例如：環瑩,27706",
                            key=f"edit_recipe_customer_filter_{code}"
                        )
                        customer_keywords_edit = split_search_keywords(customer_filter_text_edit)
                        filtered_options = [""] + [
                            opt for opt in customer_options
                            if matches_all_keywords(opt, customer_keywords_edit)
                        ]
                        if current and current not in filtered_options:
                            filtered_options.append(current)
                        index_c = filtered_options.index(current) if current in filtered_options else 0
                        selected = st.selectbox("客戶編號", filtered_options, index=index_c, key=f"edit_recipe_customer_{code}")
                        if " - " in selected:
                            fr["客戶編號"], fr["客戶名稱"] = selected.split(" - ", 1)
                    with col4:
                        opts_cat = ["原始配方", "附加配方"]
                        fr["配方類別"] = st.selectbox("配方類別", opts_cat,
                            index=opts_cat.index(fr.get("配方類別", opts_cat[0])),
                            key=f"edit_recipe_category_{code}")

                    col5, col6, col7, col8 = st.columns(4)
                    with col5:
                        opts_st = ["啟用", "停用"]
                        fr["狀態"] = st.selectbox("狀態", opts_st,
                            index=opts_st.index(fr.get("狀態", opts_st[0])),
                            key=f"edit_recipe_status_{code}")
                    with col6:
                        fr["原始配方"] = st.text_input("原始配方", fr.get("原始配方", ""), key=f"edit_recipe_origin_{code}")

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

                    pantone_col, oem_ratio_col = st.columns(2)
                    with pantone_col:
                        fr["Pantone色號"] = st.text_input("Pantone色號", fr.get("Pantone色號", ""), key=f"edit_recipe_pantone_{code}")
                    with oem_ratio_col:
                        fr["代工轉換倍率"] = st.number_input(
                            "代工轉換倍率（僅代工管理生效）",
                            min_value=0.01,
                            value=float(fr.get("代工轉換倍率", 1) or 1),
                            step=0.01,
                            key=f"edit_recipe_oem_multiplier_{code}"
                        )

                    col_net, col_net_unit = st.columns(2)
                    with col_net:
                        fr["淨重"] = st.text_input("淨重", fr.get("淨重", ""), key=f"edit_recipe_net_weight_{code}")
                    with col_net_unit:
                        net_unit_options = ["g", "kg"]
                        cur_net_unit = fr.get("淨重單位", net_unit_options[0])
                        if cur_net_unit not in net_unit_options:
                            cur_net_unit = net_unit_options[0]
                        fr["淨重單位"] = st.selectbox("淨重單位", net_unit_options,
                            index=net_unit_options.index(cur_net_unit), key=f"edit_recipe_net_unit_{code}")

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

                    edit_powder_cols = st.columns(st.session_state.edit_num_powder_rows)
                    for i, col in enumerate(edit_powder_cols, start=1):
                        fr[f"色粉編號{i}"] = col.text_input(
                            f"色粉編號{i}",
                            fr.get(f"色粉編號{i}", ""),
                            key=f"edit_powder_code{i}_{code}"
                        )
                    edit_powder_weight_cols = st.columns(st.session_state.edit_num_powder_rows)
                    for i, col in enumerate(edit_powder_weight_cols, start=1):
                        fr[f"色粉重量{i}"] = col.text_input(
                            f"色粉重量{i}",
                            fr.get(f"色粉重量{i}", ""),
                            key=f"edit_powder_weight{i}_{code}"
                        )

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
                            st.session_state["recipe_tab3_toast"] = {
                                "msg": f"配方 {fr['配方編號']} 已更新",
                                "icon": "💾"
                            }
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
                        st.session_state["recipe_tab3_toast"] = {
                            "msg": "已取消配方修改",
                            "icon": "↩️"
                        }
                        st.rerun()

    # ============================================================
    # Tab 4：色粉管理
    # ============================================================
    with tab4:

        if "color_toast" not in st.session_state:
            st.session_state.color_toast = None

        # 顯示 toast（rerun 後）
        if st.session_state.get("color_toast"):
            st.toast(st.session_state.color_toast)
            st.session_state.color_toast = None

        if "edit_color_index" not in st.session_state:
            st.session_state.edit_color_index = None

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

        subtab_add_edit, subtab_modify_delete = st.tabs(["☑️ 新增 / 編輯色粉", "🛠️ 色粉修改 / 刪除"])

        with subtab_add_edit:
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

                        st.session_state.color_toast = "✏️ 已更新色粉"
                        st.session_state.edit_color_index = None
                    else:
                        if new_row["色粉編號"] in df_color["色粉編號"].values:
                            st.warning("⚠️ 此色粉編號已存在")
                        else:
                            df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                            # ✅ 只 append 新列
                            ws_powder.append_row([str(new_row.get(col, "")) for col in REQUIRED_COLUMNS])
                            invalidate_sheet_cache("色粉管理")
                            st.session_state.color_toast = "➕ 已新增色粉"

                    st.session_state.df_color = df_color
                    st.session_state.form_color = {
                        "色粉編號": "", "國際色號": "", "名稱": "",
                        "色粉類別": "色粉", "包裝": "袋", "備註": ""
                    }
                    st.rerun()

        with subtab_modify_delete:
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
                                st.session_state.color_toast = "🗑️ 已刪除色粉"
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
            recipe_option_labels = {
                code: "" if code == "" else " | ".join(
                    df_recipe[df_recipe["配方編號"] == code][["配方編號", "顏色", "客戶名稱"]].iloc[0].astype(str)
                )
                for code in recipe_options
            }

            if st.session_state.master_batch_selected_code not in recipe_options:
                st.session_state.master_batch_selected_code = ""

            master_filter_text = st.text_input(
                "配方下拉搜尋（可多條件）",
                value="",
                placeholder="例如：27706,環瑩",
                key="master_batch_recipe_filter"
            )
            master_filter_keywords = split_search_keywords(master_filter_text)
            filtered_recipe_options = [
                code for code in recipe_options
                if code == "" or matches_all_keywords(recipe_option_labels.get(code, ""), master_filter_keywords)
            ]
            current_master_code = st.session_state.master_batch_selected_code
            if current_master_code and current_master_code not in filtered_recipe_options:
                filtered_recipe_options.append(current_master_code)

            selected_recipe_code = st.selectbox(
                "配方編號", options=filtered_recipe_options,
                index=filtered_recipe_options.index(current_master_code) if current_master_code in filtered_recipe_options else 0,
                format_func=lambda code: recipe_option_labels.get(code, ""),
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

                preview_rows = []
                for i in range(1, 9):
                    pid = str(recipe_data.get(f"色粉編號{i}", "")).strip()
                    pwt = str(recipe_data.get(f"色粉重量{i}", "")).strip()
                    if pid and pwt:
                        preview_rows.append((pid, pwt))
                total_cat = recipe_data.get("合計類別", "").strip()
                net_wt    = str(recipe_data.get("淨重", "") or "").strip()
                if total_cat and total_cat != "無":
                    preview_rows.append((total_cat, net_wt))

                if preview_rows:
                    preview_df = pd.DataFrame(preview_rows, columns=["項目", "重量"])
                    st.dataframe(
                        preview_df,
                        use_container_width=False,
                        hide_index=True,
                        column_config={
                            "項目": st.column_config.TextColumn("項目", width="medium"),
                            "重量": st.column_config.TextColumn("重量", width="small"),
                        },
                    )

                st.markdown("---")

                with st.form("master_batch_form"):
                    st.markdown("**步驟 2：設定色母比例**")
                    ratio_options = ["12.5", "20:1", "25:1", "50:1", "100:1"]
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

                    multiplier_map = {"12.5": 54, "20:1": 84, "25:1": 104, "50:1": 200, "100:1": 400}
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

                    calc_rows = []
                    for item in calc["powder_data"]:
                        w = item["weight"]
                        w_str = f"{int(w)}" if w == int(w) else f"{w:.2f}"
                        calc_rows.append((item["id"], w_str))
                    aq = calc["additive_qty"]
                    aq_str = f"{int(aq)}" if aq == int(aq) else f"{aq:.2f}"
                    calc_rows.append((calc["additive_display"], aq_str))
                    mq = calc["material_qty"]
                    mq_str = f"{int(mq)}" if mq == int(mq) else f"{mq:.2f}"
                    calc_rows.append((calc["material_code"], mq_str))

                    calc_df = pd.DataFrame(calc_rows, columns=["色粉編號", "重量"])
                    st.dataframe(
                        calc_df,
                        use_container_width=False,
                        hide_index=True,
                        column_config={
                            "色粉編號": st.column_config.TextColumn("色粉編號", width="medium"),
                            "重量": st.column_config.TextColumn("重量", width="small"),
                        },
                    )
                    st.caption(f"✓ 色粉：{calc['total_powder_weight']:.2f}g + 添加劑：{calc['additive_qty']:.2f}g + 原料：{calc['material_qty']:.2f}g = {calc['calculated_total']:.2f}g")

                    def generate_master_batch_html(calc_data):
                        ratio_display = str(calc_data.get("ratio", "")).strip()
                        unit_hint_map = {
                            "12.5": "27K",
                            "20:1": "42K",
                            "25:1": "52K",
                            "50:1": "100K",
                            "100:1": "200K",
                        }
                        unit_hint = unit_hint_map.get(ratio_display, "")
                        html_lines = [
                            f"編號：{calc_data['new_code']}　顏色：{calc_data['recipe_data'].get('顏色', '')}　比例：{calc_data['ratio']}",
                            "",
                            f"{unit_hint:^20}" if unit_hint else "",
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
                            label="📥 下載 A5 列印 90%",
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

    # ✅ 優化：不再強制 force_reload，資料由預載層準備好
    # 萬一預載層未跑到（極少數情況），才補讀（用快取，不強制）
    if "df_recipe" not in st.session_state or \
       not isinstance(st.session_state.get("df_recipe"), pd.DataFrame) or \
       st.session_state.df_recipe.empty:
        load_recipe(force_reload=False)
    
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
            packs_total_kg = calc_packs_total_kg(order_hist)
            
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
            
    def generate_next_production_order_id():
        """依「當日最大流水號 + 1」產生生產單號，避免刪單後重複編號。"""
        today_str = datetime.now().strftime("%Y%m%d")
        id_pattern = re.compile(rf"^{today_str}-(\d+)$")

        max_seq = 0

        # 優先從最新 Sheet 讀取（避免 session_state 舊資料導致重號）
        try:
            latest_df = get_cached_sheet_df("生產單", force_reload=True)
        except Exception:
            latest_df = st.session_state.get("df_order", pd.DataFrame()).copy()

        if "生產單號" in latest_df.columns:
            for raw_id in latest_df["生產單號"].astype(str).tolist():
                m = id_pattern.match(raw_id.strip())
                if not m:
                    continue
                try:
                    max_seq = max(max_seq, int(m.group(1)))
                except Exception:
                    continue

        return f"{today_str}-{max_seq + 1:03d}"

    # =============== Tab 架構開始 ===============
    if st.session_state.get("order_toast"):
        st.toast(
            st.session_state["order_toast"].get("msg", ""),
            icon=st.session_state["order_toast"].get("icon", "ℹ️")
        )
        st.session_state.pop("order_toast", None)

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
        
            # 依當日最大流水號 +1 產生生產單號（避免刪單後重號）
            new_id = generate_next_production_order_id()
        
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
            recipe_dropdown_filter_text = st.text_input(
                "配方下拉搜尋（可多條件）",
                value="",
                placeholder="例如：27706,環瑩",
                key="search_add_form_dropdown_filter_tab1"
            )
            recipe_dropdown_keywords = split_search_keywords(recipe_dropdown_filter_text)
            filtered_option_labels = [
                label for label in option_map.keys()
                if matches_all_keywords(label, recipe_dropdown_keywords)
            ]
            selected_label = st.selectbox(
                "選擇配方",
                ["請選擇"] + filtered_option_labels,
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
    
                    new_id = generate_next_production_order_id()
    
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
            main_powders = []
            for i in range(1, 9):
                color_id = recipe_row.get(f"色粉編號{i}", "").strip()
                color_wt = recipe_row.get(f"色粉重量{i}", "").strip()
                if color_id or color_wt:
                    main_powders.append((i, color_id, color_wt))
            if main_powders:
                powder_cols = st.columns(len(main_powders))
                for col, (i, color_id, color_wt) in zip(powder_cols, main_powders):
                    col.text_input(f"色粉編號{i}", value=color_id, disabled=True, key=f"form_main_color_id_{i}_tab1")
                    col.text_input(f"色粉重量{i}", value=color_wt, disabled=True, key=f"form_main_color_weight_{i}_tab1")
            
            additional_recipes = order.get("附加配方", [])
            if additional_recipes:
                st.markdown("###### 附加配方色粉用量（編號與重量）")
                for idx, r in enumerate(additional_recipes, 1):
                    st.markdown(f"附加配方 {idx}")
                    add_powders = []
                    for i in range(1, 9):
                        color_id = r.get(f"色粉編號{i}", "").strip()
                        color_wt = r.get(f"色粉重量{i}", "").strip()
                        if color_id or color_wt:
                            add_powders.append((i, color_id, color_wt))
                    if add_powders:
                        add_cols = st.columns(len(add_powders))
                        for col, (i, color_id, color_wt) in zip(add_cols, add_powders):
                            col.text_input(f"附加色粉編號_{idx}_{i}", value=color_id, disabled=True, key=f"form_add_color_id_{idx}_{i}_tab1")
                            col.text_input(f"附加色粉重量_{idx}_{i}", value=color_wt, disabled=True, key=f"form_add_color_wt_{idx}_{i}_tab1")
            
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
                normalized_last_stock = {
                    str(k).strip().upper(): v for k, v in last_stock.items()
                }
                alerts = []

                # 取得本張生產單的主配方與附加配方
                all_recipes_for_check = [recipe_row]
                if additional_recipes:
                    all_recipes_for_check.extend(additional_recipes)

                def parse_numeric_input(raw_val):
                    """容忍 30K / 25kg / 1,200 等輸入格式。"""
                    if raw_val is None:
                        return 0.0
                    text = str(raw_val).strip()
                    if not text:
                        return 0.0
                    text = text.replace(",", "")
                    match = re.search(r"-?\d+(?:\.\d+)?", text)
                    if not match:
                        return 0.0
                    try:
                        return float(match.group(0))
                    except Exception:
                        return 0.0

                def _safe_float_local(value, default=0.0):
                    try:
                        return float(str(value).strip())
                    except Exception:
                        return default

                for rec in all_recipes_for_check:
                    for i in range(1, 9):
                        pid = str(rec.get(f"色粉編號{i}", "")).strip().upper()
                        if not pid:
                            continue

                        # 排除尾碼 01 / 001 / 0001
                        if pid.endswith(("01", "001", "0001")):
                            continue

                        # 若該色粉沒有初始庫存，略過
                        if pid not in normalized_last_stock:
                            continue

                        # 取得色粉重量（每 kg 產品用量）
                        try:
                            ratio_g = float(rec.get(f"色粉重量{i}", 0))
                        except:
                            ratio_g = 0.0

                        # 計算用量：比例 * 包裝重量 * 包裝份數
                        total_used_g = 0
                        for j in range(1, 5):
                            w_val = parse_numeric_input(
                                st.session_state.get(f"form_weight{j}_tab1", 0)
                            )
                            n_val = parse_numeric_input(
                                st.session_state.get(f"form_count{j}_tab1", 0)
                            )
                            total_used_g += ratio_g * w_val * n_val

                        # 扣庫存
                        last_stock_before = _safe_float_local(normalized_last_stock.get(pid, 0), 0.0)
                        new_stock = last_stock_before - total_used_g
                        normalized_last_stock[pid] = new_stock
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
                    # ⚠️ 修改後立即重存時，若吃到快取可能找不到舊單而重複 append
                    # 這裡強制重讀最新資料，確保先刪舊列再寫新列。
                    sheet_data = get_cached_sheet_df("生產單", force_reload=True).to_dict("records")
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
                    invalidate_sheet_cache("生產單")
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
                                                               "代工數量", "目標載回數量", "轉換倍率", "代工廠商", "備註", "狀態", "建立時間", "已交貨", "交貨備註"])

                        # 兼容舊版表頭：先補齊必要欄位，再按目前表頭順序組裝資料，避免欄位錯位
                        required_oem_headers = [
                            "代工單號", "生產單號", "配方編號", "客戶名稱",
                            "代工數量", "目標載回數量", "轉換倍率", "代工廠商", "備註", "狀態", "建立時間", "已交貨", "交貨備註"
                        ]
                        oem_headers = ws_oem.row_values(1)
                        if not oem_headers:
                            ws_oem.append_row(required_oem_headers)
                            oem_headers = required_oem_headers.copy()
                        else:
                            for h in required_oem_headers:
                                if h not in oem_headers:
                                    ws_oem.update_cell(1, len(oem_headers) + 1, h)
                                    oem_headers.append(h)

                        oem_row_dict = {
                            "代工單號": oem_id,
                            "生產單號": order['生產單號'],
                            "配方編號": order.get('配方編號', ''),
                            "客戶名稱": order.get('客戶名稱', ''),
                            "代工數量": oem_qty,
                            "目標載回數量": oem_qty,
                            "轉換倍率": 1,
                            "代工廠商": "",
                            "備註": "",
                            "狀態": "🏭 在廠內",
                            "建立時間": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                            "已交貨": "",
                            "交貨備註": ""
                        }
                        ws_oem.append_row([oem_row_dict.get(h, "") for h in oem_headers])
                
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
                return 0

            target_idx = df.index[df["生產單號"].astype(str) == str(order_id)].tolist()
            if not target_idx:
                return 0

            for idx in sorted(target_idx, reverse=True):
                ws.delete_rows(idx + 2)
            return len(target_idx)
    
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
    
                # ===== 分頁資料（控制元件改放到表格右下角）=====
                page_size = int(st.session_state.get("tab3_page_size", 10))
                if page_size <= 0:
                    page_size = 10
                    st.session_state["tab3_page_size"] = 10

                total_pages = max(1, (len(df_display_tab3) - 1) // page_size + 1)
                page = int(st.session_state.get("tab3_page_number", 1))
                page = max(1, min(page, total_pages))
                st.session_state["tab3_page_number"] = page

                # ===== 計算分頁索引，安全處理 =====
                start_idx = min((page - 1) * page_size, len(df_display_tab3))
                end_idx = min(start_idx + page_size, len(df_display_tab3))
                df_page = df_display_tab3.iloc[start_idx:end_idx]
                
                # ===== 顯示表格 =====
                if not df_page.empty and existing_cols:
                    st.dataframe(
                        df_page[existing_cols].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("""
                    <style>
                    .tab3-pager-note {
                        font-size: 12px;
                        color: #9aa0a6;
                        text-align: right;
                        margin-top: -2px;
                        margin-bottom: 4px;
                    }
                    </style>
                    """, unsafe_allow_html=True)

                    pager_left, pager_size_col, pager_page_col = st.columns([8.6, 1.0, 1.0], vertical_alignment="bottom")
                    with pager_left:
                        st.markdown(
                            f"<div class='tab3-pager-note'>共 {len(df_display_tab3)} 筆 · 第 {page}/{total_pages} 頁</div>",
                            unsafe_allow_html=True
                        )
                    with pager_size_col:
                        st.selectbox(
                            "每頁",
                            [5, 10, 20, 50, 100],
                            key="tab3_page_size",
                            label_visibility="collapsed"
                        )
                    with pager_page_col:
                        st.number_input(
                            "頁碼",
                            min_value=1,
                            max_value=total_pages,
                            step=1,
                            key="tab3_page_number",
                            label_visibility="collapsed"
                        )
                else:
                    st.info("⚠️ 沒有符合條件的生產單")
            else:
                st.warning("⚠️ 查無符合的生產單，請確認輸入的編號或篩選條件。")
    
            # 📌 4. 下拉選單
            if not df_filtered_tab3.empty:
                df_filtered_tab3['配方編號'] = df_filtered_tab3['配方編號'].fillna('').astype(str)

                st.markdown("---")  # 分隔線
                st.markdown("**🔽 選擇生產單進行預覽/修改/刪除**")

                order_dropdown_filter_text = st.text_input(
                    "生產單下拉搜尋（可多條件）",
                    value="",
                    placeholder="例如：環瑩,27706",
                    key="order_dropdown_filter_tab3"
                )
                order_dropdown_keywords = split_search_keywords(order_dropdown_filter_text)
                filtered_order_indices = [
                    i for i in df_filtered_tab3.index
                    if matches_all_keywords(
                        f"{df_filtered_tab3.at[i, '生產單號']} | {df_filtered_tab3.at[i, '配方編號']} | {df_filtered_tab3.at[i, '顏色']} | {df_filtered_tab3.at[i, '客戶名稱']}",
                        order_dropdown_keywords
                    )
                ]
                if not filtered_order_indices:
                    st.info("⚠️ 下拉選單無符合條件的生產單")
                    selected_index, selected_order, selected_code_edit = None, None, None
                else:
                    selected_index = st.selectbox(
                        "選擇生產單",
                        options=filtered_order_indices,
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
            category_colorant = str(recipe_row.get("色粉類別", "")).strip()

            # 色母預覽改用專用版型（保留正確的下方顯示樣式）
            if category_colorant == "色母":
                html_text = ""

                def fmt_num_colorant(x: float) -> str:
                    if abs(x - int(x)) < 1e-9:
                        return str(int(x))
                    return f"{x:g}"

                order_note = str(order.get("備註", "")).strip()
                if order_note:
                    html_text += f"【生產單備註】{order_note}<br><br>"

                pack_weights_display = [float(order.get(f"包裝重量{i}", 0) or 0) for i in range(1, 5)]
                pack_counts_display = [float(order.get(f"包裝份數{i}", 0) or 0) for i in range(1, 5)]

                id_col_width = 14
                value_col_width = 12
                active_pack_cols = []
                for w, c in zip(pack_weights_display, pack_counts_display):
                    if w > 0 and c > 0:
                        val = 100 if abs(w - 1.0) < 1e-9 else int(w * 100)
                        active_pack_cols.append(f"{val}K × {int(c)}")

                if active_pack_cols:
                    pack_line = (" " * id_col_width) + "".join(
                        f"{col:>{value_col_width}}" for col in active_pack_cols
                    )
                    html_text += pack_line + "<br>"

                colorant_weights = [float(recipe_row.get(f"色粉重量{i}", 0) or 0) for i in range(1, 9)]
                powder_ids = [str(recipe_row.get(f"色粉編號{i}", "") or "").strip() for i in range(1, 9)]

                for pid, wgt in zip(powder_ids, colorant_weights):
                    if pid and wgt > 0:
                        pid_display = pid[:id_col_width]
                        line = pid_display.ljust(id_col_width)
                        for w, c in zip(pack_weights_display, pack_counts_display):
                            if w > 0 and c > 0:
                                val = wgt * w
                                line += f"{fmt_num_colorant(val):>{value_col_width}}"
                        html_text += line + "<br>"

                total_colorant = float(recipe_row.get("淨重", 0) or 0) - sum(colorant_weights)
                total_line_colorant = "料".ljust(id_col_width)
                for w, c in zip(pack_weights_display, pack_counts_display):
                    if w > 0 and c > 0:
                        val = total_colorant * w
                        total_line_colorant += f"{fmt_num_colorant(val):>{value_col_width}}"

                html_text += total_line_colorant + "<br>"

                text_with_newlines = html_text.replace("<br>", "\n")
                plain_text = re.sub(r"<.*?>", "", text_with_newlines)
                return "```\n" + plain_text.strip() + "\n```"

            html_text = generate_production_order_print(
                order,
                recipe_row,
                additional_recipe_rows=None,
                show_additional_ids=show_additional_ids,
                include_remark=False
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
    
            # ===== 備註顯示（區分來源） =====
            order_note = str(order.get("備註", "")).strip()
            if order_note:
                html_text += f"【生產單備註】{order_note}<br><br>"

            text_with_newlines = html_text.replace("<br>", "\n")
            plain_text = re.sub(r"<.*?>", "", text_with_newlines)
            return "```\n" + plain_text.strip() + "\n```"
    
        if selected_order is not None:
            order_dict = selected_order.to_dict()
            order_dict = {k: "" if v is None or pd.isna(v) else str(v) for k, v in order_dict.items()}
    
            recipe_rows = df_recipe[df_recipe["配方編號"] == order_dict.get("配方編號", "")]
            recipe_row = recipe_rows.iloc[0].to_dict() if not recipe_rows.empty else {}
            current_order_no = str(selected_order.get("生產單號", "")).strip()
    
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
    
            preview_tab, manage_tab = st.tabs(["👀 預覽", "🛠️ 修改 / 刪除"])
    
            with preview_tab:
                head_col, opt_col = st.columns([6, 2])
                with head_col:
                    st.caption("下方為目前選擇生產單的完整列印預覽內容。")
                with opt_col:
                    if st.session_state.get("_show_ids_tab3_order_no") != current_order_no:
                        st.session_state["_show_ids_tab3_order_no"] = current_order_no
                        st.session_state["show_ids_mode_tab3"] = "顯示"
                    show_ids_mode = st.radio(
                        "附加配方編號",
                        options=["顯示", "不顯示"],
                        horizontal=True,
                        key="show_ids_mode_tab3"
                    )
                    show_ids = (show_ids_mode == "顯示")
    
                preview_text = generate_order_preview_text_tab3(
                    order_dict,
                    recipe_row,
                    show_additional_ids=show_ids
                )
                st.markdown(preview_text, unsafe_allow_html=True)

            with manage_tab:
                st.info(
                    f"目前選擇：{order_dict.get('生產單號','')}｜{order_dict.get('配方編號','')}｜"
                    f"{order_dict.get('顏色','')}｜{order_dict.get('客戶名稱','')}"
                )

            with manage_tab:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ 修改生產單", key="edit_order_btn_tab3"):
                        st.session_state["show_edit_panel"] = True
                        st.session_state["editing_order"] = order_dict
                with col_btn2:
                    if st.button("🗑️ 刪除生產單", key="delete_order_btn_tab3"):
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
                                deleted_count = delete_order_by_id(ws_order, order_id_str)

                                if deleted_count > 0:
                                    invalidate_sheet_cache("生產單")
                                    st.session_state.df_order = st.session_state.df_order[
                                        st.session_state.df_order["生產單號"].astype(str) != order_id_str
                                    ].copy()
                                    st.session_state["order_toast"] = {
                                        "msg": f"✅ 已刪除生產單 {order_label}",
                                        "icon": "🗑️"
                                    }
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
                            st.session_state["order_toast"] = {
                                "msg": f"✅ 生產單 {order_no} 修改完成",
                                "icon": "🎉"
                            }
                        
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
    from datetime import datetime, timedelta

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
                                    "代工數量", "目標載回數量", "轉換倍率", "代工廠商", "備註", "狀態", "建立時間", "已交貨", "交貨備註"])
            except:
                pass
            df_oem_ = pd.DataFrame(columns=["代工單號", "生產單號", "配方編號", "客戶名稱",
                                             "代工數量", "目標載回數量", "轉換倍率", "代工廠商", "備註", "狀態", "建立時間", "已交貨", "交貨備註"])

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
        for col in ["代工單號", "目標載回數量", "轉換倍率", "狀態", "已交貨", "交貨備註"]:
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
    # 也防禦舊 session：若旗標存在但必要資料缺漏，仍強制補載
    oem_keys_ready = all(k in st.session_state for k in ["df_oem", "df_delivery", "df_return"])
    if (not st.session_state.get("oem_data_loaded", False)) or (not oem_keys_ready):
        load_oem_data()

    # 取出工作表物件（worksheet 物件本身有 _ws_cache，不耗 quota）
    ws_oem      = get_cached_worksheet("代工管理")
    ws_delivery = get_cached_worksheet("代工送達記錄")
    ws_return   = get_cached_worksheet("代工載回記錄")

    # 若舊版工作表缺少交貨相關欄位，自動補上（只做一次）
    try:
        oem_headers = ws_oem.row_values(1)
        for col_name in ["目標載回數量", "轉換倍率", "已交貨", "交貨備註"]:
            if col_name not in oem_headers:
                ws_oem.update_cell(1, len(oem_headers) + 1, col_name)
                oem_headers.append(col_name)
    except:
        pass

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

    def _safe_float(value, default=0.0):
        try:
            return float(str(value).strip())
        except:
            return default

    def compute_oem_progress_status(oem_row, total_returned):
        target_qty = _safe_float(oem_row.get("目標載回數量", 0), 0.0)
        if target_qty <= 0:
            target_qty = _safe_float(oem_row.get("代工數量", 0), 0.0)

        if total_returned >= target_qty and target_qty > 0:
            return "✅ 已結案"
        if total_returned > 0:
            return "🔄 進行中"
        return "⏳ 未載回"

    def update_oem_status(oem_no, new_status):
        """更新代工單狀態（單格寫入）並同步 session_state"""
        status_col_idx = 8
        try:
            oem_headers = ws_oem.row_values(1)
            if "狀態" in oem_headers:
                status_col_idx = oem_headers.index("狀態") + 1
        except:
            pass
        all_values = get_cached_sheet_values("代工管理")
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == oem_no:
                ws_oem.update_cell(idx, status_col_idx, new_status)
                break
        # 同步 session_state
        mask = st.session_state.df_oem["代工單號"] == oem_no
        st.session_state.df_oem.loc[mask, "狀態"] = new_status

    def _parse_multi_search_keywords(raw_text):
        """將使用者輸入拆成多條件關鍵字（支援逗號、頓號、空白、分號、換行）。"""
        text = str(raw_text or "").strip()
        if not text:
            return []
        tokens = re.split(r"[，,、;\s\n\t]+", text)
        return [t.strip() for t in tokens if t and t.strip()]

    def _filter_df_by_keywords(df, keywords, searchable_cols):
        """
        多條件 AND 搜尋：
        - 每個 keyword 都必須在任一搜尋欄位命中
        - 若沒有 keyword，回傳原 df
        """
        if not keywords or df.empty:
            return df

        matched_df = df.copy()
        for kw in keywords:
            norm_kw = str(kw).lstrip("-").strip()
            per_kw_mask = pd.Series(False, index=matched_df.index)
            for col in searchable_cols:
                if col not in matched_df.columns:
                    continue
                per_kw_mask = per_kw_mask | matched_df[col].astype(str).str.contains(kw, case=False, na=False, regex=False)
                if norm_kw and norm_kw != kw:
                    per_kw_mask = per_kw_mask | matched_df[col].astype(str).str.lstrip("-").str.contains(norm_kw, case=False, na=False, regex=False)
            matched_df = matched_df[per_kw_mask]
            if matched_df.empty:
                break
        return matched_df

    def _build_oem_dropdown_label(row):
        """統一代工單下拉選單顯示格式，提升可讀性。"""
        oem_no = str(row.get("代工單號", "") or "").strip()
        recipe_no = str(row.get("配方編號", "") or "").strip()
        customer = str(row.get("客戶名稱", "") or "").strip()
        delivered = _safe_float(row.get("代工數量", 0), 0.0)
        target = _safe_float(row.get("目標載回數量", delivered), delivered)
        if target <= 0:
            target = delivered
        return f"{oem_no} | {recipe_no} | {customer} | 📦送{delivered:g} → 🎯應回{target:g}"

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
            row1_col1, row1_col2, row1_col3 = st.columns(3)
            with row1_col1:
                new_oem_id = st.text_input("代工單號", placeholder="例如：OEM20251210-001")
            with row1_col2:
                new_production_id = st.text_input("生產單號（選填）", placeholder="若有對應生產單請填寫")
            with row1_col3:
                new_formula_id = st.text_input("配方編號")

            row2_col1, row2_col2, row2_col3 = st.columns(3)
            with row2_col1:
                new_customer = st.text_input("客戶名稱")
            with row2_col2:
                new_oem_qty = st.number_input("代工數量 (kg)", min_value=0.0, value=0.0, step=1.0)
            with row2_col3:
                new_vendor = st.selectbox("代工廠商", ["", "弘旭", "良輝"])

            recipe_multiplier = 1.0
            try:
                df_recipe_for_oem = st.session_state.get("df_recipe", pd.DataFrame())
                matched = df_recipe_for_oem[
                    df_recipe_for_oem.get("配方編號", pd.Series(dtype=str)).astype(str).str.strip() == str(new_formula_id).strip()
                ]
                if not matched.empty:
                    recipe_multiplier = _safe_float(matched.iloc[0].get("代工轉換倍率", 1), 1.0)
            except:
                recipe_multiplier = 1.0
            if recipe_multiplier <= 0:
                recipe_multiplier = 1.0

            row3_col1, row3_col2 = st.columns(2)
            with row3_col1:
                new_multiplier = st.number_input("轉換倍率（僅代工管理）", min_value=0.01, value=float(recipe_multiplier), step=0.01)
            with row3_col2:
                new_target_qty = st.number_input(
                    "目標載回數量 (kg)",
                    min_value=0.0,
                    value=float(new_oem_qty * new_multiplier if new_oem_qty > 0 else 0.0),
                    step=1.0
                )

            new_remark     = st.text_area("備註")
            submitted_new  = st.form_submit_button("💾 建立代工單")

        if submitted_new:
            if not new_oem_id.strip():
                st.error("❌ 請輸入代工單號")
            elif new_oem_id in df_oem.get("代工單號", pd.Series([])).values:
                st.error(f"❌ 代工單號 {new_oem_id} 已存在")
            elif new_oem_qty <= 0:
                st.error("❌ 代工數量必須大於 0")
            elif new_target_qty <= 0:
                st.error("❌ 目標載回數量必須大於 0")
            else:
                new_row_data = [
                    new_oem_id, new_production_id, new_formula_id,
                    new_customer, new_oem_qty, new_target_qty, new_multiplier, new_vendor, new_remark,
                    "🏭 在廠內",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "",
                    ""
                ]
                ws_oem.append_row(new_row_data)

                # ✅ 直接更新 session_state，不重讀 Sheet
                new_df_row = pd.DataFrame([{
                    "代工單號": new_oem_id,
                    "生產單號": new_production_id,
                    "配方編號": new_formula_id,
                    "客戶名稱": new_customer,
                    "代工數量": new_oem_qty,
                    "目標載回數量": new_target_qty,
                    "轉換倍率": new_multiplier,
                    "代工廠商": new_vendor,
                    "備註":     new_remark,
                    "狀態":     "🏭 在廠內",
                    "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "已交貨":   "",
                    "交貨備註": ""
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

            oem_options = [_build_oem_dropdown_label(row) for _, row in df_oem_active.iterrows()]

            if not oem_options:
                st.warning("⚠️ 目前沒有可編輯的代工單（全部已結案）")
            else:
                selected_option = st.selectbox("選擇代工單號", [""] + oem_options, key="select_oem_edit")

                if selected_option:
                    selected_oem = selected_option.split(" | ")[0].strip()
                    selected_row_df = df_oem_active[df_oem_active["代工單號"] == selected_oem]
                    if selected_row_df.empty:
                        st.warning("⚠️ 找不到對應代工單資料，請重新整理")
                        st.stop()
                    oem_row = selected_row_df.iloc[0].to_dict()

                    # 🔁 切換代工單時重置編輯欄位，避免沿用上一筆資料
                    if st.session_state.get("oem_edit_selected_id") != selected_oem:
                        st.session_state.oem_edit_selected_id = selected_oem
                        st.session_state.oem_vendor = oem_row.get("代工廠商", "")
                        st.session_state.oem_status = oem_row.get("狀態", "")
                        st.session_state.oem_remark = oem_row.get("備註", "")
                        st.session_state.oem_multiplier = _safe_float(oem_row.get("轉換倍率", 1), 1.0)
                        st.session_state.oem_target_qty = _safe_float(
                            oem_row.get("目標載回數量", oem_row.get("代工數量", 0)),
                            _safe_float(oem_row.get("代工數量", 0), 0.0)
                        )
                        st.session_state.delivery_qty = 0.0

                    col1, col2, col3 = st.columns(3)
                    col1.text_input("配方編號", value=oem_row.get("配方編號", ""), disabled=True)
                    col2.text_input("客戶名稱", value=oem_row.get("客戶名稱", ""), disabled=True)
                    col3.text_input("代工數量 (kg)", value=oem_row.get("代工數量", ""), disabled=True)

                    col_target, col_ratio, col_vendor, col_status = st.columns([1, 1, 2, 1])
                    new_target_qty = col_target.number_input(
                        "目標載回數量 (kg)",
                        min_value=0.0,
                        step=1.0,
                        key="oem_target_qty"
                    )
                    new_multiplier = col_ratio.number_input(
                        "轉換倍率",
                        min_value=0.01,
                        step=0.01,
                        key="oem_multiplier"
                    )

                    new_vendor = col_vendor.selectbox(
                        "代工廠商", ["", "弘旭", "良輝"],
                        index=["", "弘旭", "良輝"].index(oem_row.get("代工廠商", ""))
                              if oem_row.get("代工廠商", "") in ["", "弘旭", "良輝"] else 0,
                        key="oem_vendor"
                    )
                    status_options = ["", "⏳ 未載回", "🏭 在廠內", "🔄 進行中", "✅ 已結案"]
                    current_status = oem_row.get("狀態", "")
                    status_index   = status_options.index(current_status) if current_status in status_options else 0
                    new_status     = col_status.selectbox("狀態", status_options, index=status_index, key="oem_status")
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

                    def persist_oem_info(vendor, remark, status, target_qty, multiplier):
                        all_values = get_cached_sheet_values("代工管理")
                        headers = all_values[0] if all_values else []
                        for idx, row in enumerate(all_values[1:], start=2):
                            if row[0] == selected_oem:
                                import gspread.utils as gu
                                vendor_col = headers.index("代工廠商") + 1 if "代工廠商" in headers else 6
                                remark_col = headers.index("備註") + 1 if "備註" in headers else 7
                                status_col = headers.index("狀態") + 1 if "狀態" in headers else 8
                                target_col = headers.index("目標載回數量") + 1 if "目標載回數量" in headers else 6
                                ratio_col = headers.index("轉換倍率") + 1 if "轉換倍率" in headers else 7
                                start_col = min(vendor_col, remark_col, status_col, target_col, ratio_col)
                                end_col = max(vendor_col, remark_col, status_col, target_col, ratio_col)
                                row_payload = [""] * (end_col - start_col + 1)
                                row_payload[vendor_col - start_col] = vendor
                                row_payload[remark_col - start_col] = remark
                                row_payload[status_col - start_col] = status
                                row_payload[target_col - start_col] = str(target_qty)
                                row_payload[ratio_col - start_col] = str(multiplier)
                                col_s = gu.rowcol_to_a1(idx, start_col).rstrip("0123456789")
                                col_e = gu.rowcol_to_a1(idx, end_col).rstrip("0123456789")
                                ws_oem.update(
                                    f"{col_s}{idx}:{col_e}{idx}",
                                    [row_payload]
                                )
                                break

                        mask = st.session_state.df_oem["代工單號"] == selected_oem
                        st.session_state.df_oem.loc[mask, "代工廠商"] = vendor
                        st.session_state.df_oem.loc[mask, "備註"] = remark
                        st.session_state.df_oem.loc[mask, "狀態"] = status
                        st.session_state.df_oem.loc[mask, "目標載回數量"] = target_qty
                        st.session_state.df_oem.loc[mask, "轉換倍率"] = multiplier

                    b1, b2, b3 = st.columns(3)

                    with b1:
                        if st.button("💾 更新代工資訊", key="update_oem_info"):
                            if is_closed:
                                st.error("❌ 已結案代工單不可修改")
                            elif new_target_qty <= 0:
                                st.error("❌ 目標載回數量必須大於 0")
                            else:
                                persist_oem_info(new_vendor, new_remark, new_status, new_target_qty, new_multiplier)
                                st.session_state.toast_message = {"msg": "代工資訊已更新", "icon": "💾"}
                                st.rerun()

                    with b2:
                        if st.button("🗑️ 刪除代工單", key="delete_oem"):
                            if is_closed:
                                st.error("❌ 已結案代工單不可刪除")
                            else:
                                st.session_state.show_delete_oem_confirm = True

                    with b3:
                        if st.button("✅ 手動結案（短收/特例）", key="force_close_oem"):
                            if is_closed:
                                st.warning("⚠️ 此代工單已結案")
                            else:
                                update_oem_status(selected_oem, "✅ 已結案")
                                st.session_state.toast_message = {"msg": "已手動結案（適用短收/特例）", "icon": "✅"}
                                st.rerun()

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
                                st.session_state.oem_edit_selected_id = None
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
                        vendor_changed = (
                            str(new_vendor).strip() != str(oem_row.get("代工廠商", "")).strip()
                            or str(new_remark).strip() != str(oem_row.get("備註", "")).strip()
                            or str(new_status).strip() != str(oem_row.get("狀態", "")).strip()
                            or float(new_target_qty) != _safe_float(oem_row.get("目標載回數量", oem_row.get("代工數量", 0)), 0.0)
                            or float(new_multiplier) != _safe_float(oem_row.get("轉換倍率", 1), 1.0)
                        )

                        if remaining <= 0 and delivery_qty > 0:
                            st.error("❌ 已全數送達，無法再新增送達紀錄")
                        elif delivery_qty <= 0 and vendor_changed:
                            if is_closed:
                                st.error("❌ 已結案代工單不可修改")
                            else:
                                persist_oem_info(new_vendor, new_remark, new_status, new_target_qty, new_multiplier)
                                st.session_state.toast_message = {"msg": "已更新代工廠商資訊（未新增送達）", "icon": "🏭"}
                                st.rerun()
                        elif delivery_qty <= 0:
                            st.warning("⚠️ 請輸入正確的送達數量")
                        elif delivery_qty > remaining:
                            st.error("❌ 送達數量不可超過尚餘數量")
                        else:
                            if vendor_changed and not is_closed:
                                persist_oem_info(new_vendor, new_remark, new_status, new_target_qty, new_multiplier)
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
                oem_options = [_build_oem_dropdown_label(row) for _, row in df_oem_active.iterrows()]
                selected_option = st.selectbox("選擇代工單號", [""] + oem_options, key="select_oem_return")

                if selected_option:
                    selected_oem = selected_option.split(" | ")[0].strip()

                    oem_idx = df_oem[df_oem["代工單號"] == selected_oem].index[0]
                    oem_row = df_oem.loc[oem_idx]

                    total_qty = float(oem_row.get("代工數量", 0))
                    target_qty = _safe_float(oem_row.get("目標載回數量", total_qty), total_qty)
                    if target_qty <= 0:
                        target_qty = total_qty

                    df_this_return  = df_return[df_return["代工單號"] == selected_oem]
                    total_returned  = df_this_return["載回數量"].astype(float).sum() \
                        if not df_this_return.empty else 0.0
                    remaining_qty   = target_qty - total_returned

                    col1, col2, col3 = st.columns(3)
                    col1.text_input("配方編號",    value=oem_row.get("配方編號", ""),  disabled=True, key="oem_recipe_no_display")
                    col2.text_input("代工數量 (kg)", value=total_qty, disabled=True, key="oem_total_qty_display")
                    col3.text_input("目標載回數量 (kg)", value=target_qty, disabled=True, key="oem_target_qty_display")
                    st.info(f"🚚 已載回：{total_returned} kg / 目標：{target_qty} kg / 尚餘：{remaining_qty} kg")

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

                            new_total = total_returned + return_qty
                            remaining_after = target_qty - new_total

                            if remaining_after <= 0 and target_qty > 0:
                                status_col_idx = int(df_oem.columns.get_loc("狀態")) + 1
                                ws_oem.update_cell(row=oem_idx + 2, col=status_col_idx, value="✅ 已結案")
                                # ✅ 同步 session_state
                                st.session_state.df_oem.loc[oem_idx, "狀態"] = "✅ 已結案"
                                if new_total > target_qty:
                                    over_qty = new_total - target_qty
                                    st.session_state.toast_msg = f"🎉 載回完成並超收 {over_qty:.2f} kg，代工單已結案"
                                else:
                                    st.session_state.toast_msg = "🎉 載回完成，代工單已結案"
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
                latest_return_date = pd.NaT
                if not df_this_return.empty:
                    return_text = "\n".join([
                        f"{row['載回日期']} ({row['載回數量']} kg)"
                        for _, row in df_this_return.iterrows()
                    ])
                    latest_return_date = pd.to_datetime(df_this_return["載回日期"], errors="coerce").max()

                total_qty      = float(oem.get("代工數量", 0))
                target_qty     = _safe_float(oem.get("目標載回數量", total_qty), total_qty)
                if target_qty <= 0:
                    target_qty = total_qty
                total_returned = df_this_return["載回數量"].astype(float).sum() \
                    if not df_this_return.empty else 0.0

                manual_status = str(oem.get("狀態", "")).strip()
                if manual_status:
                    status = manual_status
                else:
                    status = compute_oem_progress_status(oem, total_returned)

                variance_qty = total_returned - target_qty
                if variance_qty > 0:
                    variance_text = f"超收 {variance_qty:.2f} kg"
                elif variance_qty < 0:
                    variance_text = f"短收 {abs(variance_qty):.2f} kg"
                else:
                    variance_text = "剛好達標"

                progress_data.append({
                    "status_order":   status_order_map.get(status, 99),
                    "狀態":           status,
                    "代工單號":       oem_id,
                    "代工廠名稱":     oem.get("代工廠商", ""),
                    "配方編號":       oem.get("配方編號", ""),
                    "客戶名稱":       oem.get("客戶名稱", ""),
                    "代工數量":       f"{oem.get('代工數量', 0)} kg",
                    "目標載回":       f"{target_qty} kg",
                    "差異":           variance_text,
                    "送達日期及數量": delivery_text,
                    "載回日期及數量": return_text,
                    "建立時間":       oem.get("建立時間", ""),
                    "最近載回日期_sort": latest_return_date,
                    "已交貨":         oem.get("已交貨", ""),
                    "交貨備註":       oem.get("交貨備註", "")
                })

            df_progress_all = pd.DataFrame(progress_data)
            df_progress_all["建立時間_dt"] = pd.to_datetime(df_progress_all["建立時間"], errors="coerce")

            def _apply_tab4_filters(source_df, key_prefix):
                filtered_df = source_df.copy()
                search_text = st.text_input(
                    label="",
                    label_visibility="collapsed",
                    placeholder="輸入關鍵字（可逗號多條件，例如：環瑩,27706）",
                    key=f"{key_prefix}_search_text"
                ).strip()
                keywords = _parse_multi_search_keywords(search_text)
                if keywords:
                    filtered_df = _filter_df_by_keywords(
                        filtered_df,
                        keywords,
                        ["客戶名稱", "配方編號", "代工單號", "代工廠名稱"]
                    )

                use_date_filter = st.checkbox("啟用建立日期篩選", value=False, key=f"{key_prefix}_use_date_filter")
                if use_date_filter:
                    today_date = datetime.today().date()
                    default_start = today_date - timedelta(days=20)
                    default_end = today_date
                    dcol1, dcol2 = st.columns(2)
                    date_start = dcol1.date_input("建立日期起", value=default_start, key=f"{key_prefix}_start_date")
                    date_end = dcol2.date_input("建立日期迄", value=default_end, key=f"{key_prefix}_end_date")

                    if date_start > date_end:
                        st.warning("⚠️ 日期區間設定錯誤：起日不可大於迄日")
                        return filtered_df.iloc[0:0]

                    _ds = pd.Timestamp(date_start)
                    _de = pd.Timestamp(date_end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    filtered_df = filtered_df[
                        (
                            (filtered_df["建立時間_dt"] >= _ds) &
                            (filtered_df["建立時間_dt"] <= _de)
                        ) |
                        filtered_df["建立時間_dt"].isna()
                    ]

                return filtered_df

            open_tab, closed_tab = st.tabs([" 未結案代工單", " 已結案代工單"])

            with open_tab:
                df_progress_open = df_progress_all[df_progress_all["狀態"] != "✅ 已結案"].copy()
                df_progress_open = _apply_tab4_filters(df_progress_open, "oem_tab4_open")

                if not df_progress_open.empty:
                    df_progress_open["建立時間"] = df_progress_open["建立時間_dt"].dt.strftime("%Y-%m-%d").fillna("")
                    df_progress_open = df_progress_open.sort_values(
                        by=["status_order", "建立時間_dt"], ascending=[True, False]
                    ).drop(columns=["status_order", "已交貨", "交貨備註", "建立時間_dt", "最近載回日期_sort"], errors="ignore")
                    st.dataframe(df_progress_open, use_container_width=True, hide_index=True)
                else:
                    st.info("目前沒有符合條件的代工單")

            with closed_tab:
                
                df_closed = df_progress_all[df_progress_all["狀態"] == "✅ 已結案"].copy()
                df_closed = _apply_tab4_filters(df_closed, "oem_tab4_closed")
                df_closed = df_closed.sort_values(by="最近載回日期_sort", ascending=False, na_position="last")
                df_closed["建立時間"] = df_closed["建立時間_dt"].dt.strftime("%Y-%m-%d").fillna("")
                df_closed["已交貨"] = df_closed["已交貨"].astype(str).str.strip().isin(
                    ["是", "TRUE", "True", "1", "Y", "y", "✅"]
                )
                closed_cols = [
                    "狀態", "代工單號", "代工廠名稱", "配方編號", "客戶名稱",
                    "代工數量", "目標載回", "差異", "送達日期及數量", "載回日期及數量", "建立時間", "已交貨", "交貨備註"
                ]
                st.dataframe(
                    df_closed[closed_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "送達日期及數量": st.column_config.TextColumn("送達日期及數量", width="small"),
                        "載回日期及數量": st.column_config.TextColumn("載回日期及數量", width="small"),
                    }
                )

                st.markdown(
                    "<div style='font-size:16px; font-weight:600; color:#f4e8ff;'>📝 已結案交貨註記</div>",
                    unsafe_allow_html=True
                )
                closed_selector_options = []
                for _, row in df_closed.iterrows():
                    oem_no = str(row.get("代工單號", "") or "").strip()
                    recipe_no = str(row.get("配方編號", "") or "").strip()
                    customer_name = str(row.get("客戶名稱", "") or "").strip()
                    label = f"{oem_no}｜{recipe_no}｜{customer_name}"
                    closed_selector_options.append(
                        {"label": label, "代工單號": oem_no}
                    )

                if not closed_selector_options:
                    st.info("目前沒有已結案的代工單")
                else:
                    selected_closed_option = st.selectbox(
                        "選擇代工單（代工單號｜配方編號｜客戶名稱）",
                        closed_selector_options,
                        format_func=lambda x: x["label"],
                        key="oem_closed_delivery_target_id_tab4"
                    )
                    selected_closed_id = selected_closed_option["代工單號"]
                    selected_closed_row = df_closed[
                        df_closed["代工單號"].astype(str).str.strip() == str(selected_closed_id)
                    ].iloc[0]
                    delivered_default = bool(selected_closed_row.get("已交貨", False))
                    note_default = str(selected_closed_row.get("交貨備註", "") or "")

                    with st.form("oem_closed_delivery_form_tab4"):
                        marked_delivered = st.checkbox(
                            "已交貨",
                            value=delivered_default,
                            help="僅做註記，不影響其他流程"
                        )
                        delivery_note = st.text_input("交貨備註", value=note_default)
                        save_closed_delivery = st.form_submit_button("💾 儲存已結案交貨註記")

                    if save_closed_delivery:
                        all_values = get_cached_sheet_values("代工管理")
                        headers = all_values[0] if all_values else []
                        for col_name in ["已交貨", "交貨備註"]:
                            if col_name not in headers:
                                ws_oem.update_cell(1, len(headers) + 1, col_name)
                                headers.append(col_name)
                        delivery_col = headers.index("已交貨") + 1
                        delivery_note_col = headers.index("交貨備註") + 1

                        oem_row_map = {}
                        for idx, row in enumerate(all_values[1:], start=2):
                            if row and row[0]:
                                oem_row_map[str(row[0]).strip()] = idx

                        oem_no = str(selected_closed_id).strip()
                        sheet_value = "是" if bool(marked_delivered) else ""
                        delivery_note_value = str(delivery_note or "").strip()
                        target_row = oem_row_map.get(oem_no)

                        if target_row:
                            ws_oem.update_cell(target_row, delivery_col, sheet_value)
                            ws_oem.update_cell(target_row, delivery_note_col, delivery_note_value)
                            mask = st.session_state.df_oem["代工單號"] == oem_no
                            st.session_state.df_oem.loc[mask, "已交貨"] = sheet_value
                            st.session_state.df_oem.loc[mask, "交貨備註"] = delivery_note_value
                            st.success("✅ 已儲存 1 筆交貨註記")
                        else:
                            st.warning("⚠️ 找不到對應代工單，未更新資料")
                        st.rerun()

    # ================================================================
    # Tab 5：代工歷程查詢
    # ================================================================
    with tab5:

        col1, col2, col3 = st.columns(3)
        search_client = col1.text_input("客戶名稱", key="search_client_history")
        search_recipe = col2.text_input("配方編號", key="search_recipe_history")
        search_oem = col3.text_input("代工單號", key="search_oem_history")
        normalized_search_oem = search_oem.lstrip("-").strip()

        if not search_client and not search_recipe and not search_oem:
            st.info("請輸入客戶名稱、配方編號或代工單號進行查詢")
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
                    "建立時間":     oem.get("建立時間", ""),
                    "已交貨":       oem.get("已交貨", "")
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
            if search_oem:
                df_progress = df_progress[
                    df_progress["代工單號"].astype(str).str.contains(search_oem, case=False, na=False) |
                    df_progress["代工單號"].astype(str).str.lstrip("-").str.contains(normalized_search_oem, case=False, na=False)
                ]

            if df_progress.empty:
                st.info("⚠️ 沒有符合條件的代工歷程")
            else:
                df_progress["建立時間"] = pd.to_datetime(df_progress["建立時間"], errors="coerce")

            if df_progress.empty:
                st.info("⚠️ 沒有符合條件的代工歷程")
            else:
                df_progress = df_progress.sort_values(
                    ["status_order", "建立時間"], ascending=[True, False]
                )
                df_display = df_progress.drop(columns=["status_order"]).copy()
                df_display["建立時間"] = df_display["建立時間"].dt.strftime("%Y-%m-%d").fillna("")
                display_cols = [c for c in df_display.columns if c not in ["已交貨"]]
                st.dataframe(df_display[display_cols].reset_index(drop=True), use_container_width=True)
            
               
# ======== 採購管理分頁 =========
elif menu == "採購管理":
    import pandas as pd
    from datetime import datetime, date

    # ===== 標題 =====
    # st.markdown(
    #     '<h1 style="font-size:24px; font-family:Arial; color:#dbd818;">📥 採購管理</h1>',
    #     unsafe_allow_html=True
    # )

    # ===== Tab 分頁 =====
    tab1, tab2, tab3, tab4 = st.tabs(["📥 進貨新增", "🔍 進貨查詢", "✏️ 進貨編輯/刪除", "🏢 供應商管理"])

    def get_or_create_worksheet(spreadsheet, title, rows=100, cols=10):
        try:
            return spreadsheet.worksheet(title)
        except Exception:
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
                    invalidate_sheet_cache("庫存記錄")
                    st.session_state.stock_need_reload = True
    
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
                    qty = parse_pack_value(row.get("數量", 0))
                    unit_raw = str(row.get("單位", "") or "").strip()
                    unit = unit_raw.lower()
                    if unit == "g" and qty >= 1000:
                        return pd.Series([qty / 1000, "kg"])
                    else:
                        return pd.Series([qty, unit_raw])
            
                df_display[["數量", "單位"]] = df_display.apply(format_quantity_unit, axis=1)
                df_display["日期"] = df_display["日期"].dt.strftime("%Y/%m/%d")
            
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            else:
                st.info("ℹ️ 沒有符合條件的進貨資料")
    
    # ========== Tab 3：進貨編輯 / 刪除 ==========
    with tab3:
        try:
            ws_stock = get_cached_worksheet("庫存記錄")
            df_stock = get_cached_sheet_df("庫存記錄")
        except Exception:
            df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","廠商編號","廠商名稱","備註"])

        if df_stock.empty or "類型" not in df_stock.columns:
            st.info("目前沒有可編輯的進貨資料")
        else:
            df_in_edit = df_stock[df_stock["類型"].astype(str).str.strip() == "進貨"].copy().reset_index(drop=True)
            if df_in_edit.empty:
                st.info("目前沒有可編輯的進貨資料")
            else:
                df_in_edit["row_no"] = df_in_edit.index + 2
                record_options = df_in_edit.apply(
                    lambda r: f"列 {r['row_no']}｜{r.get('色粉編號','')}｜{r.get('日期','')}｜{r.get('數量','')} {r.get('單位','')}",
                    axis=1
                ).tolist()
                selected_record = st.selectbox("選擇進貨記錄", [""] + record_options, key="purchase_edit_record")

                if selected_record:
                    selected_idx = record_options.index(selected_record)
                    target_row = df_in_edit.iloc[selected_idx].to_dict()
                    sheet_idx = int(target_row["row_no"]) - 2

                    try:
                        edit_date = pd.to_datetime(target_row.get("日期", ""), errors="coerce").date()
                    except Exception:
                        edit_date = datetime.today().date()
                    if pd.isna(pd.to_datetime(target_row.get("日期", ""), errors="coerce")):
                        edit_date = datetime.today().date()

                    with st.form("purchase_edit_form"):
                        c1, c2, c3, c4 = st.columns(4)
                        edit_powder = c1.text_input("色粉編號", value=str(target_row.get("色粉編號", "")).strip())
                        edit_qty = c2.number_input(
                            "數量", min_value=0.0, value=float(pd.to_numeric(target_row.get("數量", 0), errors="coerce") or 0.0), step=1.0
                        )
                        edit_unit = c3.selectbox(
                            "單位", ["g", "kg"],
                            index=(["g", "kg"].index(str(target_row.get("單位", "g")).strip()) if str(target_row.get("單位", "g")).strip() in ["g", "kg"] else 0)
                        )
                        edit_in_date = c4.date_input("進貨日期", value=edit_date)

                        c5, c6 = st.columns(2)
                        edit_supplier_id = c5.text_input("廠商編號", value=str(target_row.get("廠商編號", "")).strip())
                        edit_supplier_name = c6.text_input("廠商名稱", value=str(target_row.get("廠商名稱", "")).strip())
                        edit_note = st.text_input("備註", value=str(target_row.get("備註", "")))

                        e1, e2 = st.columns(2)
                        submit_edit = e1.form_submit_button("💾 儲存進貨修改")
                        submit_delete = e2.form_submit_button("🗑️ 刪除此筆進貨")

                    if submit_edit:
                        if not edit_powder.strip():
                            st.warning("⚠️ 請輸入色粉編號！")
                        else:
                            df_stock.loc[sheet_idx, "類型"] = "進貨"
                            df_stock.loc[sheet_idx, "色粉編號"] = edit_powder.strip()
                            df_stock.loc[sheet_idx, "日期"] = edit_in_date.strftime("%Y/%m/%d")
                            df_stock.loc[sheet_idx, "數量"] = edit_qty
                            df_stock.loc[sheet_idx, "單位"] = edit_unit
                            df_stock.loc[sheet_idx, "廠商編號"] = edit_supplier_id.strip()
                            df_stock.loc[sheet_idx, "廠商名稱"] = edit_supplier_name.strip()
                            df_stock.loc[sheet_idx, "備註"] = edit_note

                            df_upload = df_stock.fillna("").astype(str)
                            ws_stock.clear()
                            ws_stock.update([df_upload.columns.tolist()] + df_upload.values.tolist())
                            invalidate_sheet_cache("庫存記錄")
                            st.session_state.stock_need_reload = True
                            st.success("✅ 進貨紀錄已更新")
                            st.toast(f"已更新進貨：{edit_powder.strip()}", icon="💾")
                            st.rerun()

                    if submit_delete:
                        df_stock = df_stock.drop(index=sheet_idx).reset_index(drop=True)
                        df_upload = df_stock.fillna("").astype(str)
                        ws_stock.clear()
                        ws_stock.update([df_upload.columns.tolist()] + df_upload.values.tolist())
                        invalidate_sheet_cache("庫存記錄")
                        st.session_state.stock_need_reload = True
                        st.success("✅ 已刪除進貨紀錄")
                        st.toast("已刪除進貨紀錄", icon="🗑️")
                        st.rerun()

    # ========== Tab 4：供應商管理 ==========
    with tab4:
    
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
    
        supplier_tab_form, supplier_tab_manage = st.tabs(["📝 新增 / 修改", "🛠️ 查詢 / 刪除"])

        with supplier_tab_form:
            # ===== 表單模式（欄位縮窄） =====
            with st.form("form_supplier_tab3"):
                col1, col2, col3, col4 = st.columns([1.1, 1.1, 1.6, 0.9])
                with col1:
                    st.session_state.form_supplier["供應商編號"] = st.text_input(
                        "供應商編號",
                        st.session_state.form_supplier.get("供應商編號", "")
                    )
                with col2:
                    st.session_state.form_supplier["供應商簡稱"] = st.text_input(
                        "供應商簡稱",
                        st.session_state.form_supplier.get("供應商簡稱", "")
                    )
                with col3:
                    st.session_state.form_supplier["備註"] = st.text_input(
                        "備註",
                        st.session_state.form_supplier.get("備註", ""),
                        key="form_supplier_note_tab3"
                    )
                with col4:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    use_next_code = st.form_submit_button("⬇️ 建議號", use_container_width=True)

                submit = st.form_submit_button("💾 儲存")

            if use_next_code and not st.session_state.get("edit_supplier_id"):
                st.session_state.form_supplier["供應商編號"] = next_code
                st.rerun()

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
        
        with supplier_tab_manage:
            st.markdown("---")
            st.markdown(
                '<h3 style="font-size:16px; font-family:Arial; color:#f6efff;">🛠️ 供應商修改/刪除</h3>',
                unsafe_allow_html=True
            )

            keyword = st.text_input("請輸入供應商編號或簡稱", st.session_state.get("search_supplier_keyword", ""))
            st.session_state.search_supplier_keyword = keyword.strip()
            df_filtered = pd.DataFrame()

            if keyword:
                df_filtered = df[
                    df["供應商編號"].str.contains(keyword, case=False, na=False) |
                    df["供應商簡稱"].str.contains(keyword, case=False, na=False)
                ]
                if df_filtered.empty:
                    st.warning("❗ 查無符合的資料")

            if not df_filtered.empty:
                st.dataframe(df_filtered[columns], use_container_width=True, hide_index=True)
                st.markdown("<hr style='margin-top:10px;margin-bottom:10px;'>", unsafe_allow_html=True)
                for i, row in df_filtered.iterrows():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(
                            f"<div style='font-family:Arial;color:#FFFFFF;'>🔹 {row['供應商編號']}　{row['供應商簡稱']}</div>",
                            unsafe_allow_html=True
                        )
                    with c2:
                        if st.button("✏️ 改", key=f"edit_supplier_{i}"):
                            st.session_state.edit_supplier_id = row["供應商編號"]
                            st.session_state.form_supplier = row.to_dict()
                            st.success("已帶入資料到「新增 / 修改」分頁，可直接儲存更新。")
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
                powder_kw = powder_id.strip().lower()
                total_usage_g = 0.0
                monthly_usage = {}
    
                # 1) 先從配方管理找出「候選配方」
                if not df_recipe_local.empty:
                    mask = df_recipe_local[powder_cols].astype(str).apply(
                        lambda row: any(powder_kw in str(v).strip().lower() for v in row.values),
                        axis=1
                    )
                    recipe_candidates = df_recipe_local[mask].copy()
                    candidate_ids = set(recipe_candidates["配方編號"].astype(str).tolist())
                else:
                    recipe_candidates = pd.DataFrame()
                    candidate_ids = set()
    
                # 2) 過濾生產單日期區間
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
                orders_in_range = df_order_local[
                    (df_order_local["生產日期"].notna()) &
                    (df_order_local["生產日期"] >= start_dt) &
                    (df_order_local["生產日期"] < end_dt)
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
    
                    packs_total = calc_packs_total_kg(order)
    
                    if packs_total <= 0: continue
    
                    for rec in recipe_rows:
                        rec_id = str(rec.get("配方編號", "")).strip()
        
                        # ── 合計類別命中 ──
                        rec_total_type = str(rec.get("合計類別", "")).strip()
                        if rec_total_type.upper() == powder_kw.upper():
                            try:
                                net_weight = float(rec.get("淨重", 0) or 0)
                            except Exception:
                                net_weight = 0.0
                            powder_sum = sum(
                                float(rec.get(f"色粉重量{i}", 0) or 0)
                                for i in range(1, 9)
                            )
                            remainder = net_weight - powder_sum
                            if remainder > 0:
                                contrib = remainder * packs_total
                                order_total_for_powder += contrib
                                disp_name = recipe_display_name(rec)
                                sources_main.add(disp_name)
                            continue  # 已處理，跳過下方一般色粉邏輯
        
                        if rec_id not in candidate_ids: continue
    
                        pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                        match_indexes = [
                            i for i, pval in enumerate(pvals, start=1)
                            if powder_kw in pval.lower()
                        ]
                        if not match_indexes:
                            continue

                        contrib = 0.0
                        for idx in match_indexes:
                            try:
                                powder_weight = float(rec.get(f"色粉重量{idx}", 0) or 0)
                            except Exception:
                                powder_weight = 0.0
                            if powder_weight > 0:
                                contrib += powder_weight * packs_total
                        if contrib <= 0:
                            continue

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
    
        pantone_tab_add, pantone_tab_search = st.tabs(["☑️ 新增記錄", "🔍 查詢 Pantone 色號"])

        with pantone_tab_add:
            with st.form("add_pantone_tab"):
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                with col1:
                    pantone_code = st.text_input("Pantone 色號", key="pantone_code_tab")
                with col2:
                    formula_id = st.text_input("配方編號", key="formula_id_tab")
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
    
        with pantone_tab_search:
            c1, c2 = st.columns([2, 1])
            with c1:
                search_code = st.text_input("輸入 Pantone 色號", key="search_pantone_tab")
            with c2:
                search_mode = st.selectbox("", ["部分匹配", "精準匹配"], key="pantone_search_mode")

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
        # 搜尋區 + 修改/刪除分頁
        # ============================================================
        st.markdown('<span style="color:#f1f5f2; font-weight:bold;">🔍 樣品記錄搜尋</span>', unsafe_allow_html=True)

        if "sample_search_code" not in st.session_state:
            st.session_state.sample_search_code = ""
        if "sample_search_customer" not in st.session_state:
            st.session_state.sample_search_customer = ""
        if "sample_search_start" not in st.session_state:
            st.session_state.sample_search_start = None
        if "sample_search_end" not in st.session_state:
            st.session_state.sample_search_end = None

        def filter_sample_records(df_raw, code_kw, customer_kw, start_dt, end_dt):
            df_f = df_raw.copy()

            if code_kw.strip():
                df_f = df_f[df_f["樣品編號"].astype(str).str.contains(code_kw.strip(), na=False)]

            if customer_kw.strip():
                df_f = df_f[df_f["客戶名稱"].astype(str).str.contains(customer_kw.strip(), na=False)]

            if start_dt is not None:
                df_f = df_f[pd.to_datetime(df_f["日期"], errors="coerce") >= pd.to_datetime(start_dt)]

            if end_dt is not None:
                df_f = df_f[pd.to_datetime(df_f["日期"], errors="coerce") <= pd.to_datetime(end_dt)]

            return df_f.reset_index(drop=False)

        with st.form("sample_search_form"):
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                search_code = st.text_input("樣品編號", value=st.session_state.sample_search_code)
            with s2:
                search_customer = st.text_input("客戶名稱", value=st.session_state.sample_search_customer)
            with s3:
                search_start = st.date_input("供樣日期（起）", value=st.session_state.sample_search_start)
            with s4:
                search_end = st.date_input("供樣日期（迄）", value=st.session_state.sample_search_end)

            do_search = st.form_submit_button("🔍 搜尋")

        if do_search:
            st.session_state.sample_search_code = search_code
            st.session_state.sample_search_customer = search_customer
            st.session_state.sample_search_start = search_start
            st.session_state.sample_search_end = search_end
            st.session_state.sample_filtered_df = filter_sample_records(
                df_sample,
                search_code,
                search_customer,
                search_start,
                search_end,
            )
            st.session_state.sample_search_triggered = True

        if st.session_state.get("sample_search_triggered", False):
            no_condition_input = (
                not str(st.session_state.get("sample_search_code", "")).strip()
                and not str(st.session_state.get("sample_search_customer", "")).strip()
                and st.session_state.get("sample_search_start") is None
                and st.session_state.get("sample_search_end") is None
            )
            if no_condition_input:
                st.session_state.sample_filtered_df = df_sample.reset_index(drop=False)

            df_show = st.session_state.sample_filtered_df.copy()
            st.caption(f"目前顯示 {len(df_show)} 筆樣品記錄")

            if df_show.empty:
                st.info("⚠️ 查無資料")
            else:
                st.dataframe(
                    df_show[["日期", "客戶名稱", "樣品編號", "樣品名稱", "樣品數量"]].reset_index(drop=True),
                    use_container_width=True
                )

                options = [
                    f"{row['日期']}｜{row['樣品編號']}｜{row['樣品名稱']}"
                    for _, row in df_show.iterrows()
                ]

                edit_tab, delete_tab = st.tabs(["✏️ 修改", "🗑️ 刪除"])

                with edit_tab:
                    selected_edit = st.selectbox(
                        "選擇要修改的樣品",
                        [""] + options,
                        index=0,
                        key="select_sample_for_edit_tab4",
                    )
                    if st.button("載入到上方表單", key="load_sample_to_form_tab4"):
                        if not selected_edit:
                            st.warning("⚠️ 請先選擇要修改的樣品")
                        else:
                            idx = options.index(selected_edit)
                            real_index = int(df_show.iloc[idx]["index"])
                            st.session_state.sample_mode = "edit"
                            st.session_state.edit_sample_index = real_index
                            st.session_state.form_sample = df_sample.loc[real_index].to_dict()
                            st.success("✅ 已載入資料，請到上方表單修改後按「💾 儲存修改」")
                            st.rerun()

                with delete_tab:
                    selected_delete = st.selectbox(
                        "選擇要刪除的樣品",
                        [""] + options,
                        index=0,
                        key="select_sample_for_delete_tab4",
                    )
                    if st.button("🗑️ 刪除選取樣品", key="delete_selected_sample_tab4"):
                        if not selected_delete:
                            st.warning("⚠️ 請先選擇要刪除的樣品")
                        else:
                            idx = options.index(selected_delete)
                            real_index = int(df_show.iloc[idx]["index"])
                            row = df_sample.loc[real_index]
                            df_sample.drop(index=real_index, inplace=True)
                            df_sample.reset_index(drop=True, inplace=True)
                            save_df_to_sheet(ws_sample, df_sample)
                            st.session_state.sample_filtered_df = df_sample.reset_index(drop=False)
                            st.session_state.sample_mode = "add"
                            st.session_state.edit_sample_index = None
                            st.session_state.form_sample = {}
                            st.success(f"✅ 已刪除樣品：{row['樣品編號']} {row['樣品名稱']}")
                            st.rerun()
        else:
            st.caption("請先設定條件後按「🔍 搜尋」；若條件留白再按搜尋，會顯示全部樣品記錄。")
                    
# ======== 庫存區分頁 =========
elif menu == "庫存區":

    st.markdown("""
    <style>
    div.block-container { padding-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    import pandas as pd
    from datetime import datetime, date
    import streamlit as st

    # ================================================================
    # ✅ 優化 1：df_recipe / df_order 全程用 session_state，不重讀
    # ================================================================
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order  = st.session_state.get("df_order",  pd.DataFrame())

    # ================================================================
    # ✅ 優化 2：ws_stock 只取一次，4 個 Tab 共用同一個物件
    # ================================================================
    try:
        ws_stock = get_cached_worksheet("庫存記錄")
    except Exception:
        ws_stock = spreadsheet.add_worksheet("庫存記錄", rows=100, cols=10)
        ws_stock.append_row(["類型", "色粉編號", "日期", "數量", "單位", "備註"])
        invalidate_sheet_cache("庫存記錄")

    # ================================================================
    # ✅ 優化 3：df_stock 用 TTL 快取，避免每次 rerun 都打 API
    #    只有「寫入成功後」才強制 force_reload=True
    # ================================================================
    if "stock_need_reload" not in st.session_state:
        st.session_state.stock_need_reload = False

    force_reload_stock = st.session_state.pop("stock_need_reload", False)

    try:
        records = get_cached_sheet_df("庫存記錄", force_reload=force_reload_stock).to_dict("records")
        df_stock = pd.DataFrame(records) if records else pd.DataFrame(
            columns=["類型", "色粉編號", "日期", "數量", "單位", "備註"]
        )
    except Exception:
        df_stock = pd.DataFrame(columns=["類型", "色粉編號", "日期", "數量", "單位", "備註"])

    st.session_state.df_stock = df_stock

    # ================================================================
    # 工具函式（不變，僅集中定義一次）
    # ================================================================
    def to_grams(qty, unit):
        try:
            q = float(qty or 0)
        except Exception:
            q = 0.0
        return q * 1000 if str(unit).lower() == "kg" else q

    def format_usage(val_g):
        try:
            val = float(val_g or 0)
        except Exception:
            val = 0.0
        def _trim_num(num):
            return f"{num:.2f}".rstrip("0").rstrip(".")

        if abs(val) >= 1000:
            return f"{_trim_num(val / 1000)} kg"
        return f"{_trim_num(val)} g"

    def calc_usage_for_stock(powder_id, df_order, df_recipe, start_dt, end_dt):
        """計算指定色粉在 (start_dt, end_dt] 區間的生產用量（g）
        
        修正：除了搜尋色粉編號欄位外，也處理「合計類別」== powder_id 的情況
        合計類別用量 = (淨重 - 所有色粉重量合計) × 包裝總量
        """
        total_usage_g = 0.0
        df_order_local = df_order.copy()

        def normalize_recipe_id(raw_val):
            return fix_leading_zero(clean_powder_id(str(raw_val or "")))
    
        if "生產時間" not in df_order_local.columns:
            return 0.0
    
        df_order_local["生產時間"] = pd.to_datetime(df_order_local["生產時間"], errors="coerce")
    
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        powder_weight_cols = [f"色粉重量{i}" for i in range(1, 9)]
    
        for c in powder_cols + powder_weight_cols:
            if c not in df_order_local.columns:
                df_order_local[c] = ""
    
        candidate_ids = set()
        candidate_total_ids = set()  # 合計類別為 powder_id 的配方
    
        if not df_recipe.empty:
            recipe_df_copy = df_recipe.copy()
            for c in powder_cols:
                if c not in recipe_df_copy.columns:
                    recipe_df_copy[c] = ""
    
            # 一般色粉欄位搜尋
            mask = recipe_df_copy[powder_cols].astype(str).apply(
                lambda row: powder_id in [s.strip() for s in row.values], axis=1
            )
            candidate_ids = set(
                recipe_df_copy[mask]["配方編號"].map(normalize_recipe_id).tolist()
            )
    
            # 合計類別搜尋（LA/T9/料 等）
            if "合計類別" in recipe_df_copy.columns and "淨重" in recipe_df_copy.columns:
                mask_total = recipe_df_copy["合計類別"].astype(str).str.strip().str.upper() == powder_id.upper()
                candidate_total_ids = set(
                    recipe_df_copy[mask_total]["配方編號"].map(normalize_recipe_id).tolist()
                )
    
        if not candidate_ids and not candidate_total_ids:
            return 0.0
    
        s_dt = pd.to_datetime(start_dt, errors="coerce")
        e_dt = pd.to_datetime(end_dt,   errors="coerce")
    
        orders_in_range = df_order_local[
            df_order_local["生產時間"].notna() &
            (df_order_local["生產時間"] > s_dt) &
            (df_order_local["生產時間"] <= e_dt)
        ]
    
        for _, order in orders_in_range.iterrows():
            packs_total_kg = calc_packs_total_kg(order)
    
            if packs_total_kg <= 0:
                continue
    
            order_recipe_id = normalize_recipe_id(order.get("配方編號", ""))
            if not order_recipe_id:
                continue
    
            # 取得主配方與附加配方
            recipe_rows = []
            if not df_recipe.empty:
                recipe_norm = df_recipe["配方編號"].map(normalize_recipe_id)
                main_df = df_recipe[recipe_norm == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
                if "配方類別" in df_recipe.columns and "原始配方" in df_recipe.columns:
                    base_norm = df_recipe["原始配方"].map(normalize_recipe_id)
                    add_df = df_recipe[
                        (df_recipe["配方類別"].astype(str).str.strip() == "附加配方") &
                        (base_norm == order_recipe_id)
                    ]
                    if not add_df.empty:
                        recipe_rows.extend(add_df.to_dict("records"))
    
            for rec in recipe_rows:
                rec_id = normalize_recipe_id(rec.get("配方編號", ""))
    
                # ── 一般色粉欄位命中 ──
                if rec_id in candidate_ids:
                    pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                    if powder_id in pvals:
                        idx = pvals.index(powder_id) + 1
                        try:
                            pw = float(rec.get(f"色粉重量{idx}", 0) or 0)
                        except Exception:
                            pw = 0.0
                        if pw > 0:
                            total_usage_g += pw * packs_total_kg
    
                # ── 合計類別命中：用量 = (淨重 - 色粉合計) × 包裝 ──
                if rec_id in candidate_total_ids:
                    rec_total_type = str(rec.get("合計類別", "")).strip()
                    if rec_total_type.upper() == powder_id.upper():
                        try:
                            net_weight = float(rec.get("淨重", 0) or 0)
                        except Exception:
                            net_weight = 0.0
                        powder_sum = 0.0
                        for i in range(1, 9):
                            try:
                                powder_sum += float(rec.get(f"色粉重量{i}", 0) or 0)
                            except Exception:
                                pass
                        remainder = net_weight - powder_sum
                        if remainder > 0:
                            total_usage_g += remainder * packs_total_kg
    
        return total_usage_g

    def safe_calc_usage(pid, df_order, df_recipe, start_dt, end_dt):
        try:
            if pd.isna(start_dt) or pd.isna(end_dt) or start_dt > end_dt:
                return 0.0
            if df_order.empty or df_recipe.empty:
                return 0.0
            return calc_usage_for_stock(pid, df_order, df_recipe, start_dt, end_dt)
        except Exception:
            return 0.0

    def build_stock_summary(stock_powder="", match_mode="部分匹配", query_start=None, query_end=None, category_filter=None):
        """依條件計算庫存摘要（單位 g），可依色粉類別過濾。"""
        df_stock_copy = df_stock.copy()

        def parse_stock_datetime_series(series):
            if series is None:
                return pd.Series(pd.NaT, index=df_stock_copy.index)

            def parse_one(val):
                if pd.isna(val):
                    return pd.NaT

                if isinstance(val, (datetime, pd.Timestamp)):
                    return pd.to_datetime(val, errors="coerce")
                if isinstance(val, date):
                    return pd.Timestamp(val)

                text = str(val).strip()
                if not text:
                    return pd.NaT

                parsed = pd.to_datetime(text, errors="coerce")
                if pd.notna(parsed):
                    return parsed

                numeric_serial = pd.to_numeric(text, errors="coerce")
                if pd.notna(numeric_serial):
                    return pd.to_datetime("1899-12-30") + pd.to_timedelta(numeric_serial, unit="D")

                for fmt in (
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d %H:%M",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y/%m/%d",
                    "%Y-%m-%d",
                ):
                    try:
                        return pd.to_datetime(datetime.strptime(text, fmt))
                    except Exception:
                        continue

                return pd.NaT

            return series.apply(parse_one)

        raw_date_source = df_stock_copy["日期"] if "日期" in df_stock_copy.columns else None
        raw_datetime_source = df_stock_copy["日期時間"] if "日期時間" in df_stock_copy.columns else None

        # 保留原始輸入，避免後續僅靠 Timestamp(00:00:00) 無法判斷是否有「明確填寫時間」
        if raw_date_source is not None:
            df_stock_copy["_raw_日期"] = raw_date_source
        else:
            df_stock_copy["_raw_日期"] = ""

        if raw_datetime_source is not None:
            df_stock_copy["_raw_日期時間"] = raw_datetime_source
        else:
            df_stock_copy["_raw_日期時間"] = ""

        raw_date_dt = parse_stock_datetime_series(raw_date_source)
        raw_datetime_dt = parse_stock_datetime_series(raw_datetime_source)
        df_stock_copy["日期時間"] = raw_datetime_dt.combine_first(raw_date_dt)
        df_stock_copy["日期"] = raw_date_dt.dt.normalize()
        df_stock_copy["數量_g"] = df_stock_copy.apply(lambda r: to_grams(r["數量"], r["單位"]), axis=1)
        df_stock_copy["色粉編號"] = df_stock_copy["色粉編號"].astype(str).str.strip()

        df_order_copy = df_order.copy()

        def get_order_datetime(row):
            # 優先用「生產日期」，其次才是生產時間/建立時間
            if "生產日期" in row and pd.notna(row["生產日期"]):
                dt = pd.to_datetime(row["生產日期"], errors="coerce")
                if pd.notna(dt):
                    return dt + pd.Timedelta(hours=12)

            for col_name in ["生產時間", "建立時間"]:
                if col_name in row and pd.notna(row[col_name]):
                    dt = pd.to_datetime(row[col_name], errors="coerce")
                    if pd.notna(dt):
                        return dt
            return pd.NaT

        if not df_order_copy.empty:
            df_order_copy["生產時間"] = df_order_copy.apply(get_order_datetime, axis=1)

        allowed_ids = None
        if category_filter:
            df_color_local = st.session_state.get("df_color", pd.DataFrame()).copy()
            if df_color_local.empty or "色粉編號" not in df_color_local.columns or "色粉類別" not in df_color_local.columns:
                return None, f"⚠️ 缺少色粉管理資料，無法過濾「{category_filter}」類別。"
            allowed_ids = set(
                df_color_local[
                    df_color_local["色粉類別"].astype(str).str.strip() == category_filter
                ]["色粉編號"].astype(str).str.strip().tolist()
            )

        if stock_powder and match_mode == "精準匹配":
            all_pids = [stock_powder]
        else:
            pids_from_stock = (
                df_stock_copy["色粉編號"].dropna().unique().tolist()
                if not df_stock_copy.empty else []
            )
            pids_from_recipe = []
            if not df_recipe.empty:
                for i in range(1, 9):
                    col_name = f"色粉編號{i}"
                    if col_name in df_recipe.columns:
                        pids_from_recipe.extend(
                            df_recipe[col_name].dropna().astype(str).str.strip().tolist()
                        )

            all_pids_all = sorted(set(pids_from_stock) | set(pids_from_recipe))

            if stock_powder:
                all_pids = [p for p in all_pids_all if stock_powder.lower() in p.lower()]
            else:
                all_pids = all_pids_all

        if allowed_ids is not None:
            all_pids = [p for p in all_pids if p in allowed_ids]

        if not all_pids:
            return [], "⚠️ 查無符合條件的庫存記錄。"

        today_end_dt = pd.Timestamp.today().normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        start_dt = pd.to_datetime(query_start).normalize() if query_start else pd.Timestamp.min
        end_dt = (pd.to_datetime(query_end).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
                  if query_end else today_end_dt)
        if start_dt > end_dt:
            return None, "❌ 查詢起日不能晚於查詢迄日。"

        if "last_final_stock" not in st.session_state:
            st.session_state["last_final_stock"] = {}

        stock_summary = []
        for pid in all_pids:
            df_pid = df_stock_copy[df_stock_copy["色粉編號"] == pid]

            df_ini = df_pid[df_pid["類型"].astype(str).str.strip() == "初始"]
            if not df_ini.empty:
                latest_ini = df_ini.sort_values("日期時間", ascending=False).iloc[0]
                ini_value = latest_ini["數量_g"]
                ini_dt = latest_ini["日期時間"]
                if pd.isna(ini_dt) and "日期" in latest_ini and pd.notna(latest_ini["日期"]):
                    ini_dt = pd.to_datetime(latest_ini["日期"], errors="coerce")
                if pd.notna(ini_dt):
                    # ✅ 業務規則：期初庫存採「日期」語意，不採時間點語意
                    # 代表該日清點結束後的期初基準，扣料自次日開始
                    ini_note = f"期初來源：{ini_dt.strftime('%Y/%m/%d')}"
                else:
                    ini_note = "期初來源：未提供日期"
            else:
                ini_value = 0.0
                ini_dt = pd.NaT
                ini_note = "—"

            if pd.notna(ini_dt):
                ini_effective_start_dt = ini_dt.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
            else:
                ini_effective_start_dt = ini_dt

            calc_start_dt = max(start_dt, ini_effective_start_dt) if pd.notna(ini_effective_start_dt) else start_dt

            purchase_types = {"進貨", "新增庫存"}
            in_qty = df_pid[
                (df_pid["類型"].astype(str).str.strip().isin(purchase_types)) &
                (df_pid["日期時間"] > calc_start_dt) &
                (df_pid["日期時間"] <= end_dt)
            ]["數量_g"].sum()

            usage_qty = (
                safe_calc_usage(pid, df_order_copy, df_recipe, calc_start_dt, end_dt)
                if not df_order.empty and not df_recipe.empty else 0.0
            )

            final_g = ini_value + in_qty - usage_qty
            st.session_state["last_final_stock"][pid] = final_g

            stock_summary.append({
                "色粉編號": pid,
                "期初庫存": format_usage(ini_value),
                "區間進貨": format_usage(in_qty),
                "區間用量": format_usage(usage_qty),
                "期末庫存": format_usage(final_g),
                "備註": ini_note,
            })

        return stock_summary, None

    # ================================================================
    # Tab 分頁
    # ================================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 初始庫存設定",
        "📊 庫存查詢",
        "🏆 色粉用量排行榜",
        "🧮 色粉用量查詢",
        "🧴 色母庫存查詢"
    ])

    # ====================================================================
    # Tab 1：初始庫存設定
    # ====================================================================
    # ✅ 優化重點：
    #   舊做法：整表 clear() + update()  → 每次 2 次 API（大量 quota）
    #   新做法：
    #     1. 用 get_cached_sheet_values 找出舊初始記錄的列號
    #     2. 用 delete_rows 逐列刪除（1 次 API / 列）
    #     3. 用 append_row 新增一列（1 次 API）
    #   總計：最多 2 次 API，原本最多 N+2 次
    # ====================================================================
    with tab1:

        with st.form("form_ini_stock"):
            col1, col2, col3 = st.columns(3)
            ini_powder = col1.text_input("色粉編號", key="ini_color")
            ini_qty    = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="ini_qty")
            ini_unit   = col3.selectbox("單位", ["g", "kg"], key="ini_unit")

            ini_date = st.date_input("設定日期", value=datetime.today(), key="ini_date")

            ini_note  = st.text_input("備註", key="ini_note")
            submit_t1 = st.form_submit_button("💾 儲存初始庫存")

        if submit_t1:
            if not ini_powder.strip():
                st.warning("⚠️ 請輸入色粉編號！")
                st.stop()

            powder_id  = ini_powder.strip()
            try:
                qty_val = float(ini_qty)
            except Exception:
                qty_val = 0.0

            confirm_key = f"_confirm_zero_stock_{powder_id}"
            pending_confirm_key = "_pending_zero_stock_confirm"
            if qty_val == 0 and st.session_state.get(pending_confirm_key) != confirm_key:
                st.session_state[pending_confirm_key] = confirm_key
                st.warning("⚠️ 數量為 0，請再次按下「💾 儲存初始庫存」確認要儲存。")
                st.stop()
            st.session_state.pop(pending_confirm_key, None)

            # 期初庫存採「日期語意」，寫入日期字串即可（不再要求時間欄位）
            ini_datetime = ini_date.strftime("%Y/%m/%d")

            # ── 步驟 1：找出舊的「初始」列（從快取取，不多打 API）──
            try:
                all_values = get_cached_sheet_values("庫存記錄")
                header = all_values[0] if all_values else []

                # 找出欄位索引
                try:
                    type_col_idx  = header.index("類型")
                    pid_col_idx   = header.index("色粉編號")
                except ValueError:
                    type_col_idx, pid_col_idx = 0, 1

                rows_to_delete = []
                for i, row in enumerate(all_values[1:], start=2):
                    if (len(row) > type_col_idx and row[type_col_idx].strip() == "初始" and
                            len(row) > pid_col_idx and row[pid_col_idx].strip() == powder_id):
                        rows_to_delete.append(i)

                # ── 步驟 2：由後往前刪，避免列號偏移 ──
                for row_num in reversed(rows_to_delete):
                    ws_stock.delete_rows(row_num)

            except Exception as e:
                st.warning(f"⚠️ 無法刪除舊初始庫存：{e}")

            # ── 步驟 3：append 一列新資料（1 次 API）──
            new_row_values = [
                "初始",
                powder_id,
                ini_datetime,
                str(qty_val),
                ini_unit,
                ini_note
            ]
            ws_stock.append_row(new_row_values, value_input_option="RAW")

            # ── 步驟 4：讓下次讀取強制 reload ──
            invalidate_sheet_cache("庫存記錄")
            st.session_state.stock_need_reload = True
            st.session_state.pop("stock_calc_time", None)   # 讓生產單頁的庫存也重算

            st.success(f"✅ 初始庫存已儲存　色粉：{powder_id}　數量：{qty_val} {ini_unit}")
            st.toast(f"✅ 初始庫存儲存成功：{powder_id}", icon="📦")
            st.rerun()

    # ====================================================================
    # Tab 2：庫存查詢
    # ====================================================================
    # ✅ 優化重點：
    #   1. 只有按下「計算庫存」才執行 API / 計算
    #   2. 結果快取到 session_state["stock_query_result"]
    #   3. 相同查詢條件（簽名）不重算，直接顯示快取結果
    # ====================================================================
    with tab2:
        def normalize_stock_query_error(err_msg):
            """將各種錯誤型態轉成可安全顯示的文字，避免 Streamlit 再次誤判型態。"""
            if isinstance(err_msg, str):
                err_text_local = err_msg
            elif isinstance(err_msg, BaseException):
                err_text_local = f"{type(err_msg).__name__}: {err_msg}"
            elif isinstance(err_msg, dict):
                err_text_local = "；".join(
                    f"{k}={v}" for k, v in err_msg.items()
                )
            elif isinstance(err_msg, (list, tuple, set)):
                parts = [str(x).strip() for x in err_msg if str(x).strip()]
                err_text_local = "；".join(parts)
            else:
                try:
                    err_text_local = str(err_msg)
                except Exception:
                    err_text_local = repr(err_msg)

            if not isinstance(err_text_local, str):
                err_text_local = str(err_text_local)

            err_text_local = err_text_local.replace("\x00", "").strip()
            if not err_text_local:
                err_text_local = "庫存查詢失敗，請稍後再試。"
            return err_text_local

        use_date_range_key = "stock_use_date_range"
        use_date_range = st.checkbox(
            "使用日期區間",
            value=st.session_state.get(use_date_range_key, False),
            key=f"{use_date_range_key}_cb",
        )
        st.session_state[use_date_range_key] = use_date_range

        with st.form("form_stock_query"):
            col1, col2 = st.columns(2)
            query_start = col1.date_input("查詢起日", key="stock_start_query", disabled=not use_date_range)
            query_end   = col2.date_input("查詢迄日", key="stock_end_query", disabled=not use_date_range)

            c_input, c_match = st.columns([3, 1])
            with c_input:
                stock_powder = c_input.text_input("色粉編號", key="stock_powder")
            with c_match:
                match_mode = st.selectbox(
                    "匹配模式", ["部分匹配", "精準匹配"],
                    index=0, key="match_mode"
                )

            submit_t2 = st.form_submit_button("計算庫存")

        if not use_date_range:
            st.caption("ℹ️ 未使用日期區間：預設查詢從期初庫存（若無期初則從最早資料）到今天的庫存。")

        effective_query_start = query_start if use_date_range else None
        effective_query_end = query_end if use_date_range else None

        # ── 計算簽名（避免重複計算）──
        query_signature = f"{use_date_range}|{effective_query_start}|{effective_query_end}|{st.session_state.get('stock_powder','')}|{st.session_state.get('match_mode','')}"

        if submit_t2:
            stock_summary, err_msg = build_stock_summary(
                stock_powder=st.session_state.get("stock_powder", "").strip(),
                match_mode=st.session_state.get("match_mode", "部分匹配"),
                query_start=effective_query_start,
                query_end=effective_query_end,
            )
            if err_msg:
                err_text = normalize_stock_query_error(err_msg)
                if err_text.startswith("⚠️"):
                    st.warning(err_text)
                else:
                    st.error(err_text)
                # 錯誤狀態不再灌空列表，避免下方「查無資料」提示重複顯示一次
                st.session_state["stock_query_result"] = None
            else:
                st.session_state["stock_query_result"] = stock_summary
                st.session_state["stock_query_signature"] = query_signature

        # ── 顯示（快取結果，不重算）──
        cached_result = st.session_state.get("stock_query_result")
        if cached_result is not None:
            if not cached_result:  # 空列表 / 無資料
                st.info("查無符合條件的庫存資料。")
            else:
                df_result = pd.DataFrame(cached_result)
                if df_result.empty:
                    st.info("查無符合條件的庫存資料。")
                else:
                    st.dataframe(
                        df_result,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "備註": st.column_config.TextColumn(width="large"),
                        },
                    )
                    st.caption("ℹ️ 庫存扣除從期初日期次日開始的生產單（期初日期當天不扣料）")
                    st.caption("🌟 期末庫存 = 期初庫存 + 其後進貨 − 其後用量（單位皆以 g 計算）")

   
    # ====================================================================
    # Tab 5：色母庫存查詢（修復版）
    # ====================================================================
    with tab5:
        st.caption("ℹ️ 不選擇日期區間時，會顯示截至今日的累積庫存。")

        # checkbox 放在 form 外才能即時控制 disabled
        use_date_range = st.checkbox(
            "使用日期區間",
            value=st.session_state.get("_tab5_use_date_range", False),
            key="_tab5_use_date_range_cb"
        )
        st.session_state["_tab5_use_date_range"] = use_date_range

        with st.form("form_master_stock_query"):
            col1, col2 = st.columns(2)
            master_start = col1.date_input(
                "查詢起日", key="master_stock_start",
                disabled=not use_date_range
            )
            master_end = col2.date_input(
                "查詢迄日", key="master_stock_end",
                disabled=not use_date_range
            )

            c_input, c_match = st.columns([3, 1])
            with c_input:
                master_powder = st.text_input("色母編號（留空=全部）", key="master_powder")
            with c_match:
                master_match_mode = st.selectbox(
                    "匹配模式", ["部分匹配", "精準匹配"],
                    index=0, key="master_match_mode"
                )

            b1, b2 = st.columns(2)
            submit_master_query = b1.form_submit_button("計算色母庫存")
            submit_master_all   = b2.form_submit_button("顯示全部色母")

        if submit_master_query or submit_master_all:

            # ★ 核心修復：不勾選時強制 None，不用 date_input 的預設值
            query_start = master_start if use_date_range else None
            query_end   = master_end   if use_date_range else None

            powder_keyword = "" if submit_master_all else master_powder.strip()

            # ── Step 1: 色母編號清單 ──
            df_color_local = st.session_state.get("df_color", pd.DataFrame()).copy()

            if (df_color_local.empty
                    or "色粉編號"  not in df_color_local.columns
                    or "色粉類別" not in df_color_local.columns):
                st.warning("⚠️ 缺少色粉管理資料，請先至「色粉管理」建立色母資料。")
                st.stop()

            master_ids_all = set(
                df_color_local[
                    df_color_local["色粉類別"].astype(str).str.strip() == "色母"
                ]["色粉編號"].astype(str).str.strip().tolist()
            )

            if not master_ids_all:
                st.warning("⚠️ 色粉管理中沒有「色母」類別的資料。")
                st.stop()

            if powder_keyword:
                if master_match_mode == "精準匹配":
                    master_ids_filtered = {p for p in master_ids_all if p == powder_keyword}
                else:
                    master_ids_filtered = {
                        p for p in master_ids_all if powder_keyword.upper() in p.upper()
                    }
            else:
                master_ids_filtered = master_ids_all

            if not master_ids_filtered:
                st.warning(f"⚠️ 找不到符合「{powder_keyword}」的色母編號。")
                st.stop()

            # ── Step 2: 生產單 ──
            df_order_local = st.session_state.get("df_order", pd.DataFrame()).copy()

            if not df_order_local.empty:
                df_order_local["生產日期_dt"] = pd.to_datetime(
                    df_order_local.get("生產日期", pd.Series(dtype=str)),
                    errors="coerce"
                ).dt.normalize()

            # ── Step 3: 配方管理 ──
            df_recipe_local = st.session_state.get("df_recipe", pd.DataFrame()).copy()

            for c in [f"色粉編號{i}" for i in range(1, 9)] + \
                     [f"色粉重量{i}" for i in range(1, 9)] + \
                     ["配方編號", "配方類別", "原始配方"]:
                if c not in df_recipe_local.columns:
                    df_recipe_local[c] = ""

            def normalize_recipe_id(raw_val):
                return fix_leading_zero(clean_powder_id(str(raw_val or "")))

            # ── Step 4: 建立「配方 → 含哪些色母及用量」快取 ──
            # key = 配方編號（附加配方用原始配方ID）
            recipe_powder_map = {}

            for _, rec in df_recipe_local.iterrows():
                rid = str(rec.get("配方編號", "")).strip()
                if not rid:
                    continue
                cat = str(rec.get("配方類別", "")).strip()
                key_rid = str(rec.get("原始配方", "")).strip() if cat == "附加配方" else rid
                key_rid = normalize_recipe_id(key_rid)
                if not key_rid:
                    continue

                for i in range(1, 9):
                    pid = str(rec.get(f"色粉編號{i}", "")).strip()
                    if not pid or pid not in master_ids_all:
                        continue
                    try:
                        pw = float(rec.get(f"色粉重量{i}", 0) or 0)
                    except Exception:
                        pw = 0.0
                    if pw > 0:
                        recipe_powder_map.setdefault(key_rid, []).append((pid, pw))

            # ── Step 5: 預計算每張生產單的色母用量 ──
            # (date_dt, pid, usage_g)
            order_usage_records = []

            if not df_order_local.empty:
                for _, order in df_order_local.iterrows():
                    order_date_dt = order.get("生產日期_dt")
                    if pd.isna(order_date_dt):
                        order_date_dt = pd.to_datetime(order.get("建立時間", ""), errors="coerce")
                        if pd.isna(order_date_dt):
                            continue
                        order_date_dt = order_date_dt.normalize()

                    recipe_id = normalize_recipe_id(order.get("配方編號", ""))
                    if not recipe_id or recipe_id not in recipe_powder_map:
                        continue

                    packs_total_kg = calc_packs_total_kg(order)

                    if packs_total_kg <= 0:
                        continue

                    pid_usage = {}
                    for pid, pw in recipe_powder_map[recipe_id]:
                        pid_usage[pid] = pid_usage.get(pid, 0.0) + pw * packs_total_kg

                    for pid, usage_g in pid_usage.items():
                        if usage_g > 0:
                            order_usage_records.append((order_date_dt, pid, usage_g))

            # ── Step 6: 庫存記錄 ──
            try:
                df_stock_local = get_cached_sheet_df("庫存記錄").copy()
            except Exception:
                df_stock_local = pd.DataFrame()

            if not df_stock_local.empty:
                raw_date  = pd.to_datetime(
                    df_stock_local.get("日期",    pd.Series(dtype=str)), errors="coerce"
                )
                raw_dtime = pd.to_datetime(
                    df_stock_local.get("日期時間", pd.Series(dtype=str)), errors="coerce"
                )
                df_stock_local["日期_dt"]  = raw_dtime.combine_first(raw_date)
                df_stock_local["數量_g"]   = df_stock_local.apply(
                    lambda r: to_grams(r.get("數量", 0), r.get("單位", "g")), axis=1
                )
                df_stock_local["色粉編號"] = df_stock_local["色粉編號"].astype(str).str.strip()
                df_stock_local["類型"] = df_stock_local.get("類型", "").astype(str).str.strip()

            # ── Step 7: 逐色母計算 ──
            today_dt = pd.Timestamp.today().normalize()

            # ★ 查詢結束點：有指定用指定日，否則用今天
            range_end_global = pd.Timestamp(query_end).normalize() if query_end else today_dt

            stock_summary = []

            for pid in sorted(master_ids_filtered):

                # 7a. 期初庫存
                ini_value = 0.0
                ini_dt    = pd.Timestamp.min
                ini_note  = "無期初記錄"

                if not df_stock_local.empty:
                    df_pid = df_stock_local[df_stock_local["色粉編號"] == pid]
                    df_ini = df_pid[df_pid["類型"].astype(str).str.strip() == "初始"]
                    if not df_ini.empty:
                        latest_ini = df_ini.sort_values("日期_dt", ascending=False).iloc[0]
                        ini_value  = latest_ini["數量_g"]
                        ini_dt_raw = latest_ini["日期_dt"]
                        ini_dt     = ini_dt_raw if pd.notna(ini_dt_raw) else pd.Timestamp.min
                        ini_remark = str(latest_ini.get("備註", "")).strip()
                        if ini_dt != pd.Timestamp.min:
                            ini_note = f"期初：{ini_dt.strftime('%Y/%m/%d')}"
                        else:
                            raw_str  = str(latest_ini.get("日期", "")).strip()
                            ini_note = f"期初：{raw_str[:10]}" if raw_str else "期初：—"
                        if ini_remark:
                            ini_note = f"{ini_note} | {ini_remark}"
                else:
                    df_pid = pd.DataFrame()

                # 7b. 計算起點與結束點
                # ─────────────────────────────────────────────────────
                # 有期初記錄：
                #   range_start = max(期初日, 查詢起日)
                #   若期初日 > 查詢結束日 → 期初庫存=0、進貨=0、用量=0、期末=0
                # 無期初記錄：
                #   range_start = 查詢起日（無指定則不限）
                #   期初庫存 = 0，但進貨與用量照常計算，期末可為負
                # ─────────────────────────────────────────────────────
                ini_dt_norm = ini_dt.normalize() if ini_dt != pd.Timestamp.min else pd.Timestamp.min
                has_ini = (ini_dt_norm != pd.Timestamp.min)

                range_end = range_end_global

                # qs_dt = 查詢起日（含當天）；ini_dt_norm = 期初日（嚴格大於）
                qs_dt = pd.Timestamp(query_start).normalize() if query_start else None

                if has_ini and ini_dt_norm > range_end:
                    # 期初日在查詢結束後 → 整段為 0
                    stock_summary.append({
                        "色母編號": pid,
                        "期初庫存": format_usage(0),
                        "區間進貨": format_usage(0),
                        "區間用量": format_usage(0),
                        "期末庫存": format_usage(0),
                        "備註": f"期初（{ini_dt.strftime('%Y/%m/%d')}）在查詢區間結束後",
                    })
                    continue

                # 7c. 進貨量
                # 嚴格大於期初日（避免重算期初當天）AND 大於等於查詢起日（含當天）
                in_qty = 0.0
                if not df_pid.empty:
                    purchase_types = {"進貨", "新增庫存"}
                    mask_in = df_pid["類型"].astype(str).str.strip().isin(purchase_types)
                    if has_ini:
                        mask_in &= df_pid["日期_dt"].dt.normalize() > ini_dt_norm
                    if qs_dt is not None:
                        mask_in &= df_pid["日期_dt"].dt.normalize() >= qs_dt
                    mask_in &= df_pid["日期_dt"].dt.normalize() <= range_end
                    in_qty = df_pid[mask_in]["數量_g"].sum()

                # 7d. 生產用量
                # 嚴格大於期初日 AND 大於等於查詢起日（含當天）
                usage_qty = 0.0
                for rec_date, rec_pid, rec_usage in order_usage_records:
                    if rec_pid != pid:
                        continue
                    if has_ini and rec_date <= ini_dt_norm:
                        continue
                    if qs_dt is not None and rec_date < qs_dt:
                        continue
                    if rec_date > range_end:
                        continue
                    usage_qty += rec_usage

                # 7e. 期末庫存
                final_g = ini_value + in_qty - usage_qty
                st.session_state.setdefault("last_final_stock", {})[pid] = final_g

                stock_summary.append({
                    "色母編號": pid,
                    "期初庫存": format_usage(ini_value),
                    "區間進貨": format_usage(in_qty),
                    "區間用量": format_usage(usage_qty),
                    "期末庫存": format_usage(final_g),
                    "備註":     ini_note,
                })

            st.session_state["master_stock_query_result"] = stock_summary

        # ── 顯示結果 ──
        cached = st.session_state.get("master_stock_query_result")
        if cached is not None:
            df_result = pd.DataFrame(cached)
            if df_result.empty:
                st.info("⚠️ 查無符合條件的色母庫存資料。")
            else:
                st.dataframe(
                    df_result,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "色母編號": st.column_config.TextColumn("色母編號", width="medium"),
                        "期初庫存": st.column_config.TextColumn("期初庫存", width="small"),
                        "區間進貨": st.column_config.TextColumn("區間進貨", width="small"),
                        "區間用量": st.column_config.TextColumn("區間用量", width="small"),
                        "期末庫存": st.column_config.TextColumn("期末庫存", width="small"),
                        "備註":     st.column_config.TextColumn("備註",     width="medium"),
                    },
                )
                st.caption("🌟 條件：色粉管理「色粉類別」= 色母")
                st.caption("📅 期末庫存 = 期初庫存 + 期初後進貨 − 期初後用量")
                if use_date_range:
                    st.caption(f"📅 查詢區間：{master_start} ～ {master_end}")
                else:
                    st.caption("📅 未指定日期區間，計算截至今日的累積庫存")

    # ====================================================================
    # Tab 3：色粉用量排行榜
    # ====================================================================
    # ✅ 優化重點：
    #   1. 全程使用 session_state 的 df_order / df_recipe，不重讀 Sheet
    #   2. 排行結果快取到 session_state["rank_result"]，相同條件不重算
    # ====================================================================
    with tab3:

        col1, col2 = st.columns(2)
        rank_start = col1.date_input("開始日期（排行榜）", key="rank_start_date")
        rank_end   = col2.date_input("結束日期（排行榜）", key="rank_end_date")

        if st.button("生成排行榜", key="btn_powder_rank"):

            rank_signature = f"{rank_start}|{rank_end}"
            if st.session_state.get("rank_signature") == rank_signature and \
               st.session_state.get("rank_result") is not None:
                # 相同條件 → 直接跳到顯示（不重算）
                pass
            else:
                # ── 純記憶體計算，不打 API ──
                df_order_copy  = df_order.copy()
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

                orders_in_range = df_order_copy[
                    df_order_copy["生產日期"].notna() &
                    (df_order_copy["生產日期"] >= pd.to_datetime(rank_start)) &
                    (df_order_copy["生產日期"] <= pd.to_datetime(rank_end))
                ]

                pigment_usage = {}

                for _, order in orders_in_range.iterrows():
                    order_recipe_id = str(order.get("配方編號", "")).strip()
                    if not order_recipe_id:
                        continue

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

                    packs_total = calc_packs_total_kg(order)

                    if packs_total <= 0:
                        continue

                    for rec in recipe_rows:
                        for i in range(1, 9):
                            pid = str(rec.get(f"色粉編號{i}", "")).strip()
                            try:
                                pw = float(rec.get(f"色粉重量{i}", 0) or 0)
                            except Exception:
                                pw = 0.0
                            if pid and pw > 0:
                                pigment_usage[pid] = pigment_usage.get(pid, 0.0) + pw * packs_total

                df_rank = pd.DataFrame([
                    {"色粉編號": k, "總用量_g": v} for k, v in pigment_usage.items()
                ])
                if not df_rank.empty:
                    df_rank = df_rank.sort_values("總用量_g", ascending=False).reset_index(drop=True)
                    df_rank["總用量"] = df_rank["總用量_g"].map(format_usage)
                    df_rank = df_rank[["色粉編號", "總用量"]]

                # 快取
                st.session_state["rank_result"]    = df_rank
                st.session_state["rank_signature"] = rank_signature
                st.session_state["rank_pigment"]   = pigment_usage

        # ── 顯示（快取）──
        df_rank = st.session_state.get("rank_result")
        pigment_usage = st.session_state.get("rank_pigment", {})

        if df_rank is not None:
            if not df_rank.empty:
                st.dataframe(df_rank, use_container_width=True, hide_index=True)
                csv = pd.DataFrame(
                    list(pigment_usage.items()), columns=["色粉編號", "總用量(g)"]
                ).to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="⬇️ 下載排行榜 CSV",
                    data=csv,
                    file_name=f"powder_rank_{st.session_state.get('rank_start_date')}_{st.session_state.get('rank_end_date')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("⚠️ 查無用量資料")

    # ====================================================================
    # Tab 4：色粉用量查詢
    # ====================================================================
    # ✅ 優化重點：
    #   1. 全程使用 session_state 的 df_order / df_recipe，不重讀 Sheet
    #   2. 結果快取到 session_state["tab4_usage_result"]，相同條件不重算
    # ====================================================================
    with tab4:

        with st.form("form_powder_usage"):
            st.markdown("**🔍 色粉用量查詢**")

            cols = st.columns(4)
            powder_inputs_raw = []
            for i in range(4):
                val = cols[i].text_input(f"色粉編號{i+1}", key=f"usage_color_{i}")
                if val.strip():
                    powder_inputs_raw.append(val.strip())

            col1, col2 = st.columns(2)
            start_date = col1.date_input("開始日期", key="usage_start_date")
            end_date   = col2.date_input("結束日期",  key="usage_end_date")

            submit_t4 = st.form_submit_button("查詢用量")

        if submit_t4:
            powder_inputs = powder_inputs_raw  # 已在 form 內收集

            if not powder_inputs:
                st.warning("⚠️ 請至少輸入一個色粉編號")
                st.stop()

            t4_signature = f"{'|'.join(powder_inputs)}|{start_date}|{end_date}"
            if (st.session_state.get("tab4_signature") == t4_signature and
                    st.session_state.get("tab4_usage_result") is not None):
                pass  # 相同條件 → 直接顯示快取
            else:
                results = []
                # ── 純記憶體計算，不打 API ──
                df_order_local  = df_order.copy()
                df_recipe_local = df_recipe.copy()

                powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
                for c in powder_cols + ["配方編號", "配方類別", "原始配方", "配方名稱", "顏色", "客戶名稱"]:
                    if c not in df_recipe_local.columns:
                        df_recipe_local[c] = ""

                if "生產日期" in df_order_local.columns:
                    df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
                else:
                    df_order_local["生產日期"] = pd.NaT

                def recipe_display_name(rec):
                    name = str(rec.get("配方名稱", "")).strip()
                    if name:
                        return name
                    rid   = str(rec.get("配方編號", "")).strip()
                    color = str(rec.get("顏色",     "")).strip()
                    cust  = str(rec.get("客戶名稱", "")).strip()
                    if color or cust:
                        return f"{rid} ({' / '.join([p for p in [color, cust] if p])})"
                    return rid

                for powder_id in powder_inputs:
                    powder_kw = powder_id.strip().lower()
                    total_usage_g = 0.0
                    monthly_usage = {}

                    # 候選配方
                    if not df_recipe_local.empty:
                        mask = df_recipe_local[powder_cols].astype(str).apply(
                            lambda row: any(powder_kw in str(v).strip().lower() for v in row.values),
                            axis=1
                        )
                        candidate_ids = set(df_recipe_local[mask]["配方編號"].astype(str).tolist())
                    else:
                        candidate_ids = set()

                    start_dt = pd.to_datetime(start_date)
                    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
                    orders_in_range = df_order_local[
                        df_order_local["生產日期"].notna() &
                        (df_order_local["生產日期"] >= start_dt) &
                        (df_order_local["生產日期"] < end_dt)
                    ]

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

                        packs_total = calc_packs_total_kg(order)

                        if packs_total <= 0:
                            continue

                        order_total = 0.0
                        sources_main, sources_add = set(), set()

                        for rec in recipe_rows:
                            rec_id = str(rec.get("配方編號", "")).strip()

                            # ── 合計類別命中 ──
                            rec_total_type = str(rec.get("合計類別", "")).strip()
                            if rec_total_type.upper() == powder_kw.upper():
                                try:
                                    net_weight = float(rec.get("淨重", 0) or 0)
                                except Exception:
                                    net_weight = 0.0
                                powder_sum = sum(
                                    float(rec.get(f"色粉重量{i}", 0) or 0)
                                    for i in range(1, 9)
                                )
                                remainder = net_weight - powder_sum
                                if remainder > 0:
                                    contrib = remainder * packs_total
                                    order_total += contrib
                                    name = recipe_display_name(rec)
                                    sources_main.add(name)
                                continue

                            if rec_id not in candidate_ids:
                                continue
                                
                            pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                            match_indexes = [
                                i for i, pval in enumerate(pvals, start=1)
                                if powder_kw in pval.lower()
                            ]
                            if not match_indexes:
                                continue
                            contrib = 0.0
                            for idx_r in match_indexes:
                                try:
                                    pw = float(rec.get(f"色粉重量{idx_r}", 0) or 0)
                                except Exception:
                                    pw = 0.0
                                if pw > 0:
                                    contrib += pw * packs_total
                            if contrib <= 0:
                                continue
                            order_total += contrib
                            name = recipe_display_name(rec)
                            if str(rec.get("配方類別", "")).strip() == "附加配方":
                                sources_add.add(name)
                            else:
                                sources_main.add(name)

                        if order_total <= 0:
                            continue

                        od = order["生產日期"]
                        if pd.isna(od):
                            continue
                        month_key = od.strftime("%Y/%m")
                        if month_key not in monthly_usage:
                            monthly_usage[month_key] = {
                                "usage": 0.0, "main_recipes": set(), "additional_recipes": set()
                            }
                        monthly_usage[month_key]["usage"] += order_total
                        monthly_usage[month_key]["main_recipes"].update(sources_main)
                        monthly_usage[month_key]["additional_recipes"].update(sources_add)
                        total_usage_g += order_total

                    for month in sorted(monthly_usage.keys()):
                        data    = monthly_usage[month]
                        usage_g = data["usage"]
                        if usage_g <= 0:
                            continue
                        per        = pd.Period(month, freq="M")
                        disp_start = max(start_date, per.start_time.date())
                        disp_end   = min(end_date,   per.end_time.date())
                        date_disp  = (
                            month
                            if (disp_start == per.start_time.date() and disp_end == per.end_time.date())
                            else f"{disp_start.strftime('%Y/%m/%d')}~{disp_end.strftime('%m/%d')}"
                        )
                        results.append({
                            "色粉編號":      powder_id,
                            "來源區間":      date_disp,
                            "月用量":        format_usage(usage_g),
                            "主配方來源":    ", ".join(sorted(data["main_recipes"])),
                            "附加配方來源":  ", ".join(sorted(data["additional_recipes"])),
                        })

                    results.append({
                        "色粉編號": powder_id, "來源區間": "總用量",
                        "月用量": format_usage(total_usage_g),
                        "主配方來源": "", "附加配方來源": ""
                    })

                st.session_state["tab4_usage_result"] = results
                st.session_state["tab4_signature"]    = t4_signature

        # ── 顯示（快取結果）──
        cached_t4 = st.session_state.get("tab4_usage_result")
        if cached_t4 is not None:
            if not cached_t4:  # 空列表 / 無資料
                st.info("查無符合條件的用量資料。")
            else:
                df_usage = pd.DataFrame(cached_t4)

                def highlight_total_row(s):
                    return [
                        "font-weight:bold; background-color:#333333; color:white"
                        if (s.name in df_usage.index and
                            df_usage.loc[s.name, "來源區間"] == "總用量" and
                            col_n in ["色粉編號", "來源區間", "月用量"])
                        else ""
                        for col_n in s.index
                    ]

                styled = df_usage.style.apply(highlight_total_row, axis=1)
                st.dataframe(styled, use_container_width=True, hide_index=True)

# ======== 洗車廠庫存分頁 =========
elif menu == "洗車廠庫存":

    st.markdown("""
    <style>
    div.block-container { padding-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

    carwash_headers = [
        "類型", "初始庫存日期", "初始數量", "貨品編號", "入庫日期", "出庫日期",
        "數量", "單位", "登記人", "備註"
    ]

    try:
        ws_carwash = get_cached_worksheet("洗車廠庫存")
    except Exception:
        ws_carwash = spreadsheet.add_worksheet("洗車廠庫存", rows=1000, cols=16)
        ws_carwash.append_row(carwash_headers)
        invalidate_sheet_cache("洗車廠庫存")

    if "carwash_need_reload" not in st.session_state:
        st.session_state.carwash_need_reload = False

    reload_carwash = st.session_state.pop("carwash_need_reload", False)

    if st.session_state.get("carwash_toast"):
        st.toast(
            st.session_state["carwash_toast"].get("msg", ""),
            icon=st.session_state["carwash_toast"].get("icon", "ℹ️")
        )
        st.session_state.pop("carwash_toast", None)

    try:
        df_carwash = get_cached_sheet_df("洗車廠庫存", force_reload=reload_carwash)
    except Exception:
        df_carwash = pd.DataFrame(columns=carwash_headers)

    for col in carwash_headers:
        if col not in df_carwash.columns:
            df_carwash[col] = ""

    df_carwash = df_carwash[carwash_headers].fillna("")

    def _to_date(s):
        return pd.to_datetime(s, errors="coerce").date() if str(s).strip() else None

    def _to_float(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    def _normalize_product_name(value):
        return re.sub(r"[^A-Z0-9]", "", str(value).upper().strip())

    def _is_similar_product_name(current_name, existing_name):
        cur_norm = _normalize_product_name(current_name)
        ex_norm = _normalize_product_name(existing_name)
        if not cur_norm or not ex_norm or cur_norm == ex_norm:
            return False
        return (cur_norm in ex_norm) or (ex_norm in cur_norm)

    def _save_carwash_df(df_to_save):
        upload_df = df_to_save.copy().fillna("")
        ws_carwash.clear()
        ws_carwash.update([carwash_headers] + upload_df[carwash_headers].astype(str).values.tolist())
        invalidate_sheet_cache("洗車廠庫存")
        st.session_state.carwash_need_reload = True

    tab_c1, tab_c2, tab_c3, tab_c4 = st.tabs([
        "洗車廠初始庫存",
        "入/出庫登錄",
        "洗車廠庫存查詢",
        "資料修改"
    ])

    # ── Tab C1：初始庫存 ──
    with tab_c1:
        with st.form("carwash_initial_form"):
            c1, c2 = st.columns(2)
            product_id = c1.text_input("貨品編號", key="cw_init_product_id").strip()
            init_date  = c2.date_input("初始庫存日期", key="cw_init_date")

            c3, c4 = st.columns(2)
            init_qty  = c3.number_input("數量", min_value=0.0, step=1.0, key="cw_init_qty")
            init_unit = c4.selectbox("單位", ["KG", "包"], key="cw_init_unit")

            c5, c6 = st.columns(2)
            registrar = c5.selectbox("登記人", ["德", "Q"], key="cw_init_registrar")
            note      = c6.text_input("備註", key="cw_init_note")

            submit_init = st.form_submit_button("💾 儲存初始庫存")

        if submit_init:
            if not product_id:
                st.warning("⚠️ 請輸入貨品編號")
            elif init_qty < 0:
                st.warning("⚠️ 數量不可小於 0")
            elif init_qty == 0:
                zero_confirm_key = "cw_init_zero_confirm"
                expected_signature = (
                    f"{product_id}|{init_date.strftime('%Y-%m-%d')}|"
                    f"{init_unit}|{registrar}|{note.strip()}"
                )
                if st.session_state.get(zero_confirm_key) == expected_signature:
                    st.session_state.pop(zero_confirm_key, None)
                    safe_append_row(ws_carwash, [
                        "初始庫存", init_date.strftime("%Y-%m-%d"), init_qty, product_id,
                        "", "", "", init_unit, registrar, note
                    ])
                    invalidate_sheet_cache("洗車廠庫存")
                    st.session_state.carwash_need_reload = True
                    st.session_state["carwash_toast"] = {
                        "msg": f"✅ 已儲存 {product_id} 初始庫存：{init_qty} {init_unit}",
                        "icon": "📦"
                    }
                    st.rerun()
                else:
                    st.session_state[zero_confirm_key] = expected_signature
                    st.warning("⚠️ 數量為 0，請再次按下「💾 儲存初始庫存」確認資料無誤。")
                    st.stop()
            else:
                safe_append_row(ws_carwash, [
                    "初始庫存", init_date.strftime("%Y-%m-%d"), init_qty, product_id,
                    "", "", "", init_unit, registrar, note
                ])
                invalidate_sheet_cache("洗車廠庫存")
                st.session_state.carwash_need_reload = True
                st.session_state["carwash_toast"] = {
                    "msg": f"✅ 已儲存 {product_id} 初始庫存：{init_qty} {init_unit}",
                    "icon": "📦"
                }
                st.rerun()

    # ── Tab C2：入/出庫登錄 ──
    with tab_c2:
        with st.form("carwash_inout_form"):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            io_type = r1c1.selectbox("出/入庫", ["入庫", "出庫"], key="cw_io_type")
            io_registrar = r1c2.selectbox("登記人", ["德", "Q"], key="cw_io_registrar")
            in_date  = r1c3.date_input("入庫日期",  key="cw_in_date",  disabled=(io_type == "出庫"))
            out_date = r1c4.date_input("出庫日期", key="cw_out_date", disabled=(io_type == "入庫"))

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            io_product_id = r2c1.text_input("貨品編號", key="cw_io_product_id")
            io_qty        = r2c2.number_input("數量", min_value=0.0, step=1.0, key="cw_io_qty")
            io_unit       = r2c3.selectbox("單位", ["KG", "包"], key="cw_io_unit")
            io_note       = r2c4.text_input("備註", key="cw_io_note")
            submit_io    = st.form_submit_button("💾 儲存入/出庫")

        if submit_io:
            io_product_id = io_product_id.strip()
            if not io_product_id:
                st.warning("⚠️ 請輸入貨品編號")
            elif io_qty <= 0:
                st.warning("⚠️ 數量需大於 0")
            else:
                existing_product_ids = sorted({
                    str(v).strip() for v in df_carwash["貨品編號"].tolist()
                    if str(v).strip()
                })
                similar_ids = [
                    pid for pid in existing_product_ids
                    if _is_similar_product_name(io_product_id, pid)
                ]
                confirm_key = "cw_io_similar_confirm"
                if similar_ids:
                    confirm_signature = (
                        f"{io_type}|{io_product_id}|{io_qty}|{io_unit}|"
                        f"{io_registrar}|{io_note.strip()}|{'|'.join(similar_ids)}"
                    )
                    if st.session_state.get(confirm_key) != confirm_signature:
                        st.session_state[confirm_key] = confirm_signature
                        st.warning(
                            "⚠️ 偵測到相似貨品編號，請再次按下「💾 儲存入/出庫」確認："
                            + "、".join(similar_ids)
                        )
                        st.stop()
                st.session_state.pop(confirm_key, None)
                safe_append_row(ws_carwash, [
                    io_type, "", "", io_product_id,
                    in_date.strftime("%Y-%m-%d")  if io_type == "入庫" else "",
                    out_date.strftime("%Y-%m-%d") if io_type == "出庫" else "",
                    io_qty, io_unit, io_registrar, io_note
                ])
                invalidate_sheet_cache("洗車廠庫存")
                st.session_state.carwash_need_reload = True
                st.session_state["carwash_toast"] = {
                    "msg": f"✅ 已登錄 {io_type}：{io_product_id} {io_qty} {io_unit}",
                    "icon": "🧾"
                }
                st.rerun()

    # ── Tab C3：庫存查詢 ──
    with tab_c3:
        with st.form("cw_query_form"):
            c1, c2 = st.columns([5, 1])
            q_pid     = c1.text_input("產品編號（留空顯示全部）", key="cw_query_pid")
            show_zero_inventory = st.checkbox(
                "顯示數量為 0 之庫存",
                value=False,
                key="cw_query_show_zero_inventory"
            )
            do_query  = c2.form_submit_button("搜尋")

        if do_query:
            q_pid = q_pid.strip()

            # 取得要查詢的 ID 清單
            if q_pid:
                pid_series = df_carwash["貨品編號"].astype(str).str.strip()
                query_ids = sorted({
                    pid for pid in pid_series.tolist()
                    if pid and q_pid.lower() in pid.lower()
                })
            else:
                query_ids = sorted({
                    str(v).strip() for v in df_carwash["貨品編號"].tolist()
                    if str(v).strip()
                })

            if not query_ids:
                st.info("目前沒有可查詢的洗車廠庫存資料。")
            else:
                result_rows = []
                today = datetime.now().date()

                for pid in query_ids:
                    pid_df = df_carwash[
                        df_carwash["貨品編號"].astype(str).str.strip() == pid
                    ].copy()

                    pid_df["初始庫存日期_dt"] = pid_df["初始庫存日期"].map(_to_date)
                    pid_df["入庫日期_dt"]     = pid_df["入庫日期"].map(_to_date)
                    pid_df["出庫日期_dt"]     = pid_df["出庫日期"].map(_to_date)
                    pid_df["初始數量_num"]    = pid_df["初始數量"].map(_to_float)
                    pid_df["數量_num"]        = pid_df["數量"].map(_to_float)

                    latest_init = pid_df[
                        pid_df["初始庫存日期_dt"].notna()
                    ].sort_values("初始庫存日期_dt", ascending=False)

                    if not latest_init.empty:
                        init_row  = latest_init.iloc[0]
                        init_date = init_row["初始庫存日期_dt"]
                        init_qty  = init_row["初始數量_num"]
                        unit      = str(init_row.get("單位", "")).strip() or "KG"
                    else:
                        init_date = None
                        init_qty  = 0.0
                        unit      = ""

                    if init_date is not None:
                        in_mask = (
                            (pid_df["類型"].astype(str).str.strip() == "入庫") &
                            (pid_df["入庫日期_dt"].notna()) &
                            (pid_df["入庫日期_dt"] >= init_date) &
                            (pid_df["入庫日期_dt"] <= today)
                        )
                        out_mask = (
                            (pid_df["類型"].astype(str).str.strip() == "出庫") &
                            (pid_df["出庫日期_dt"].notna()) &
                            (pid_df["出庫日期_dt"] >= init_date) &
                            (pid_df["出庫日期_dt"] <= today)
                        )
                    else:
                        in_mask = (
                            (pid_df["類型"].astype(str).str.strip() == "入庫") &
                            (pid_df["入庫日期_dt"].notna()) &
                            (pid_df["入庫日期_dt"] <= today)
                        )
                        out_mask = (
                            (pid_df["類型"].astype(str).str.strip() == "出庫") &
                            (pid_df["出庫日期_dt"].notna()) &
                            (pid_df["出庫日期_dt"] <= today)
                        )

                    in_qty      = pid_df.loc[in_mask,  "數量_num"].sum()
                    out_qty     = pid_df.loc[out_mask, "數量_num"].sum()
                    current_qty = init_qty + in_qty - out_qty

                    # 出入庫歷程（從「最新期初庫存」開始，依時間順序列出）
                    history = []
                    if init_date is not None:
                        init_registrar = str(init_row.get("登記人", "")).strip()
                        history.append((
                            init_date,
                            f"{init_date.strftime('%Y-%m-%d')}｜期初庫存 {init_qty:g}{unit}｜{init_registrar}"
                        ))
                        history_source = pid_df[
                            ((pid_df["類型"].astype(str).str.strip() == "入庫") &
                             (pid_df["入庫日期_dt"] >= init_date)) |
                            ((pid_df["類型"].astype(str).str.strip() == "出庫") &
                             (pid_df["出庫日期_dt"] >= init_date))
                        ].copy()
                    else:
                        history_source = pid_df[
                            pid_df["類型"].astype(str).str.strip().isin(["入庫", "出庫"])
                        ].copy()

                    for _, row in history_source.iterrows():
                        rec_type = str(row.get("類型", "")).strip()
                        rec_date = (row.get("入庫日期_dt") if rec_type == "入庫"
                                    else row.get("出庫日期_dt"))
                        if rec_date is None:
                            continue
                        rec_qty  = _to_float(row.get("數量_num", 0))
                        rec_unit = str(row.get("單位", "")).strip()
                        rec_name = str(row.get("登記人", "")).strip()
                        history.append((
                            rec_date,
                            f"{rec_date.strftime('%Y-%m-%d')}｜{rec_type} {rec_qty:g}{rec_unit}｜{rec_name}"
                        ))

                    history_text = "\n".join([
                        h[1] for h in sorted(history, key=lambda x: x[0], reverse=True)
                    ])
                    note_candidates = []
                    for _, row in pid_df.iterrows():
                        note_text = str(row.get("備註", "")).strip()
                        if note_text:
                            rec_type = str(row.get("類型", "")).strip()
                            candidate_dates = []
                            if rec_type == "初始庫存":
                                candidate_dates.append(row.get("初始庫存日期_dt"))
                            elif rec_type == "入庫":
                                candidate_dates.append(row.get("入庫日期_dt"))
                            elif rec_type == "出庫":
                                candidate_dates.append(row.get("出庫日期_dt"))
                            else:
                                candidate_dates.extend([
                                    row.get("初始庫存日期_dt"),
                                    row.get("入庫日期_dt"),
                                    row.get("出庫日期_dt"),
                                ])

                            note_date = next((d for d in candidate_dates if d is not None), None)
                            if note_date is not None:
                                note_candidates.append((note_date, note_text))
                            else:
                                # 沒日期也保留，避免「有備註卻顯示空白」
                                note_candidates.append((datetime.min.date(), note_text))

                    latest_note = "-"
                    if note_candidates:
                        latest_note = sorted(note_candidates, key=lambda x: x[0], reverse=True)[0][1]

                    result_rows.append({
                        "產品編號":     pid,
                        "期初庫存":     f"{init_qty:g} {unit}".strip(),
                        "區間入庫":     f"{in_qty:g} {unit}".strip(),
                        "區間出庫":     f"{out_qty:g} {unit}".strip(),
                        "目前庫存數量": f"{current_qty:g} {unit}".strip(),
                        "出入庫歷程":   history_text or "-",
                        "備註":         latest_note,
                        "_目前庫存數值": current_qty,
                    })

                result_df = pd.DataFrame(result_rows).sort_values("產品編號")
                if not show_zero_inventory:
                    result_df = result_df[result_df["_目前庫存數值"] != 0]

                result_df = result_df.drop(columns=["_目前庫存數值"], errors="ignore")

                if result_df.empty:
                    st.info("目前查無符合條件的資料（已隱藏庫存為 0 的產品）。")
                else:
                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "產品編號":     st.column_config.TextColumn("產品編號",     width="small"),
                            "期初庫存":     st.column_config.TextColumn("期初庫存",     width="small"),
                            "區間入庫":     st.column_config.TextColumn("區間入庫",     width="small"),
                            "區間出庫":     st.column_config.TextColumn("區間出庫",     width="small"),
                            "目前庫存數量": st.column_config.TextColumn("目前庫存數量", width="small"),
                            "出入庫歷程":   st.column_config.TextColumn("出入庫歷程",   width="large"),
                            "備註":         st.column_config.TextColumn("備註",         width="medium"),
                        },
                    )

    # ── Tab C4：資料修改 ──
    with tab_c4:
        edit_tab1, edit_tab2 = st.tabs(["初始庫存修改", "出/入庫記錄修改"])

        with edit_tab1:
            init_df = df_carwash[df_carwash["類型"].astype(str).str.strip() == "初始庫存"].copy()

            if init_df.empty:
                st.info("目前沒有可修改的初始庫存資料。")
            else:
                init_df["sheet_idx"] = init_df.index
                init_df = init_df.reset_index(drop=True)
                init_df["row_no"] = init_df["sheet_idx"] + 2
                init_df["選擇標籤"] = init_df.apply(
                    lambda r: f"列 {r['row_no']}｜{str(r.get('貨品編號', '')).strip()}｜{str(r.get('初始庫存日期', '')).strip()}｜{str(r.get('初始數量', '')).strip()} {str(r.get('單位', '')).strip()}",
                    axis=1
                )

                selected_init_label = st.selectbox(
                    "選擇要修改的初始庫存記錄",
                    options=init_df["選擇標籤"].tolist(),
                    key="cw_edit_init_select"
                )

                selected_init_row = init_df[init_df["選擇標籤"] == selected_init_label].iloc[0]
                selected_init_date = _to_date(selected_init_row.get("初始庫存日期", "")) or datetime.now().date()
                selected_init_qty = _to_float(selected_init_row.get("初始數量", 0))

                with st.form("cw_edit_initial_form"):
                    c1, c2 = st.columns(2)
                    edit_product_id = c1.text_input("貨品編號", value=str(selected_init_row.get("貨品編號", "")).strip())
                    edit_init_date = c2.date_input("初始庫存日期", value=selected_init_date)

                    c3, c4 = st.columns(2)
                    edit_init_qty = c3.number_input("數量", min_value=0.0, value=float(selected_init_qty), step=1.0)
                    edit_init_unit = c4.selectbox(
                        "單位",
                        ["KG", "包"],
                        index=0 if str(selected_init_row.get("單位", "KG")).strip() != "包" else 1
                    )

                    c5, c6 = st.columns(2)
                    edit_registrar = c5.selectbox(
                        "登記人",
                        ["德", "Q"],
                        index=0 if str(selected_init_row.get("登記人", "德")).strip() != "Q" else 1
                    )
                    edit_note = c6.text_input("備註", value=str(selected_init_row.get("備註", "")).strip())

                    submit_edit_init = st.form_submit_button("💾 儲存初始庫存修改")

                if submit_edit_init:
                    edit_product_id = edit_product_id.strip()
                    if not edit_product_id:
                        st.warning("⚠️ 貨品編號不可空白")
                    else:
                        sheet_idx = int(selected_init_row["sheet_idx"])
                        df_carwash.loc[sheet_idx, "類型"] = "初始庫存"
                        df_carwash.loc[sheet_idx, "初始庫存日期"] = edit_init_date.strftime("%Y-%m-%d")
                        df_carwash.loc[sheet_idx, "初始數量"] = edit_init_qty
                        df_carwash.loc[sheet_idx, "貨品編號"] = edit_product_id
                        df_carwash.loc[sheet_idx, "入庫日期"] = ""
                        df_carwash.loc[sheet_idx, "出庫日期"] = ""
                        df_carwash.loc[sheet_idx, "數量"] = ""
                        df_carwash.loc[sheet_idx, "單位"] = edit_init_unit
                        df_carwash.loc[sheet_idx, "登記人"] = edit_registrar
                        df_carwash.loc[sheet_idx, "備註"] = edit_note

                        _save_carwash_df(df_carwash)
                        st.session_state["carwash_toast"] = {
                            "msg": f"✅ 已更新初始庫存：{edit_product_id}",
                            "icon": "🛠️"
                        }
                        st.rerun()

        with edit_tab2:
            io_df = df_carwash[df_carwash["類型"].astype(str).str.strip().isin(["入庫", "出庫"])].copy()

            if io_df.empty:
                st.info("目前沒有可修改的出/入庫記錄。")
            else:
                io_df["sheet_idx"] = io_df.index
                io_df = io_df.reset_index(drop=True)
                io_df["row_no"] = io_df["sheet_idx"] + 2
                io_df["紀錄日期"] = io_df.apply(
                    lambda r: str(r.get("入庫日期", "")).strip() if str(r.get("類型", "")).strip() == "入庫"
                    else str(r.get("出庫日期", "")).strip(),
                    axis=1
                )
                io_df["選擇標籤"] = io_df.apply(
                    lambda r: f"列 {r['row_no']}｜{str(r.get('類型', '')).strip()}｜{str(r.get('貨品編號', '')).strip()}｜{str(r.get('紀錄日期', '')).strip()}｜{str(r.get('數量', '')).strip()} {str(r.get('單位', '')).strip()}",
                    axis=1
                )

                selected_io_label = st.selectbox(
                    "選擇要修改的出/入庫記錄",
                    options=io_df["選擇標籤"].tolist(),
                    key="cw_edit_io_select"
                )
                selected_io_row = io_df[io_df["選擇標籤"] == selected_io_label].iloc[0]
                selected_io_type = str(selected_io_row.get("類型", "入庫")).strip() or "入庫"
                selected_io_qty = _to_float(selected_io_row.get("數量", 0))
                selected_io_in_date = _to_date(selected_io_row.get("入庫日期", "")) or datetime.now().date()
                selected_io_out_date = _to_date(selected_io_row.get("出庫日期", "")) or datetime.now().date()

                with st.form("cw_edit_inout_form"):
                    c1, c2, c3, c4 = st.columns(4)
                    edit_io_type = c1.selectbox("出/入庫", ["入庫", "出庫"], index=0 if selected_io_type == "入庫" else 1)
                    edit_io_product_id = c2.text_input("貨品編號", value=str(selected_io_row.get("貨品編號", "")).strip())
                    edit_io_qty = c3.number_input("數量", min_value=0.0, value=float(selected_io_qty), step=1.0)
                    edit_io_unit = c4.selectbox(
                        "單位",
                        ["KG", "包"],
                        index=0 if str(selected_io_row.get("單位", "KG")).strip() != "包" else 1
                    )

                    c5, c6, c7, c8 = st.columns(4)
                    edit_io_in_date = c5.date_input("入庫日期", value=selected_io_in_date, disabled=(edit_io_type == "出庫"))
                    edit_io_out_date = c6.date_input("出庫日期", value=selected_io_out_date, disabled=(edit_io_type == "入庫"))
                    edit_io_registrar = c7.selectbox(
                        "登記人",
                        ["德", "Q"],
                        index=0 if str(selected_io_row.get("登記人", "德")).strip() != "Q" else 1
                    )
                    edit_io_note = c8.text_input("備註", value=str(selected_io_row.get("備註", "")).strip())
                    submit_edit_io = st.form_submit_button("💾 儲存出/入庫修改")

                if submit_edit_io:
                    edit_io_product_id = edit_io_product_id.strip()
                    if not edit_io_product_id:
                        st.warning("⚠️ 貨品編號不可空白")
                    elif edit_io_qty <= 0:
                        st.warning("⚠️ 數量需大於 0")
                    else:
                        sheet_idx = int(selected_io_row["sheet_idx"])
                        df_carwash.loc[sheet_idx, "類型"] = edit_io_type
                        df_carwash.loc[sheet_idx, "初始庫存日期"] = ""
                        df_carwash.loc[sheet_idx, "初始數量"] = ""
                        df_carwash.loc[sheet_idx, "貨品編號"] = edit_io_product_id
                        df_carwash.loc[sheet_idx, "入庫日期"] = edit_io_in_date.strftime("%Y-%m-%d") if edit_io_type == "入庫" else ""
                        df_carwash.loc[sheet_idx, "出庫日期"] = edit_io_out_date.strftime("%Y-%m-%d") if edit_io_type == "出庫" else ""
                        df_carwash.loc[sheet_idx, "數量"] = edit_io_qty
                        df_carwash.loc[sheet_idx, "單位"] = edit_io_unit
                        df_carwash.loc[sheet_idx, "登記人"] = edit_io_registrar
                        df_carwash.loc[sheet_idx, "備註"] = edit_io_note

                        _save_carwash_df(df_carwash)
                        st.session_state["carwash_toast"] = {
                            "msg": f"✅ 已更新{edit_io_type}記錄：{edit_io_product_id}",
                            "icon": "🛠️"
                        }
                        st.rerun()

# ===== 匯入配方備份檔案 =====
if st.session_state.menu == "匯入備份":

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
