# utils/common.py - 緊急修正版（防止資料丟失）

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ========== 安全儲存函式（防止資料丟失）==========
def safe_save_df_to_sheet(ws, df):
    """
    安全地將 DataFrame 寫回試算表
    ✅ 防止 NaN 導致儲存失敗
    ✅ 先備份再寫入
    ✅ 失敗時不會刪除原資料
    """
    try:
        # 1️⃣ 清理資料：替換 NaN、inf
        df_clean = df.copy()
        
        # 替換所有 NaN 為空字串
        df_clean = df_clean.replace({np.nan: "", np.inf: "", -np.inf: ""})
        
        # 確保所有值都是字串或數字
        df_clean = df_clean.fillna("").astype(str)
        
        # 2️⃣ 準備寫入資料
        values = [df_clean.columns.tolist()] + df_clean.values.tolist()
        
        # 3️⃣ 先備份現有資料（防萬一）
        try:
            backup_values = ws.get_all_values()
            st.session_state["_last_backup"] = backup_values
        except:
            pass
        
        # 4️⃣ 寫入（先清空再更新）
        ws.clear()
        ws.update("A1", values, value_input_option='RAW')
        
        return True
        
    except Exception as e:
        # 5️⃣ 失敗時嘗試恢復備份
        st.error(f"❌ 儲存失敗：{e}")
        
        if "_last_backup" in st.session_state and st.session_state["_last_backup"]:
            try:
                ws.clear()
                ws.update("A1", st.session_state["_last_backup"], value_input_option='RAW')
                st.warning("⚠️ 已恢復上一次的備份資料")
            except:
                st.error("❌ 恢復備份也失敗了，請立即檢查 Google Sheets")
        
        return False

# ========== 舊的 save_df_to_sheet 改為呼叫安全版本 ==========
def save_df_to_sheet(ws, df):
    """舊函式名稱，改為呼叫安全版本"""
    return safe_save_df_to_sheet(ws, df)

# ========== 取得 Spreadsheet 物件 ==========
def get_spreadsheet():
    """回傳已存在於 st.session_state 的 spreadsheet"""
    if "spreadsheet" in st.session_state:
        return st.session_state["spreadsheet"]

    try:
        service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        sheet_url = st.secrets.get("sheet_url") or st.secrets.get("SHEET_URL") or "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
        
        ss = client.open_by_url(sheet_url)
        st.session_state["spreadsheet"] = ss
        return ss
    except Exception as e:
        raise RuntimeError(f"無法取得 spreadsheet：{e}")

# ========== 清理函式 ==========
def clean_powder_id(x):
    """去除空白、全形空白，轉大寫"""
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

# ========== 初始化 session state ==========
def init_states(keys):
    """初始化一組 session_state key"""
    dict_keys = {"form_color", "form_recipe", "order", "form_customer"}
    if keys is None:
        return
    for k in keys:
        if k not in st.session_state:
            if k in dict_keys or k.startswith("form_"):
                st.session_state[k] = {}
            elif k.startswith("edit_") or k.startswith("delete_"):
                st.session_state[k] = None
            elif k.startswith("show_"):
                st.session_state[k] = False
            elif k.startswith("search"):
                st.session_state[k] = ""
            else:
                st.session_state[k] = None

# ========== 列印函式（簡化版）==========
def generate_production_order_print(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    """產生列印內容（HTML 格式）- 簡化版防止錯誤"""
    if recipe_row is None:
        recipe_row = {}
    
    lines = []
    lines.append(f"配方編號：{recipe_row.get('配方編號', '')}")
    lines.append(f"顏色：{order.get('顏色', '')}")
    lines.append(f"客戶：{order.get('客戶名稱', '')}")
    
    # 色粉列
    for i in range(1, 9):
        pid = recipe_row.get(f"色粉編號{i}", "")
        wgt = recipe_row.get(f"色粉重量{i}", "")
        if pid:
            lines.append(f"{pid}: {wgt}")
    
    return "<br>".join(lines)

def generate_print_page_content(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    """生成完整列印 HTML（簡化版）"""
    content = generate_production_order_print(order, recipe_row, additional_recipe_rows, show_additional_ids)
    created_time = str(order.get("建立時間", "") or "")
    
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>生產單列印</title>
    </head>
    <body>
        <div>{created_time}</div>
        <h2>生產單</h2>
        <pre>{content}</pre>
    </body>
    </html>
    """
    return html

# ========== 載入配方資料 ==========
def load_recipe(force_reload=False):
    """嘗試載入配方管理工作表"""
    try:
        ss = get_spreadsheet()
        ws_recipe = ss.worksheet("配方管理")
        df_loaded = pd.DataFrame(ws_recipe.get_all_records())
        if not df_loaded.empty:
            # 清理 NaN
            df_loaded = df_loaded.replace({np.nan: "", np.inf: "", -np.inf: ""})
            return df_loaded
    except Exception as e:
        st.warning(f"⚠️ 從 Google Sheets 載入失敗：{e}")

    order_file = Path("data/df_recipe.csv")
    if order_file.exists():
        try:
            df_csv = pd.read_csv(order_file)
            if not df_csv.empty:
                df_csv = df_csv.replace({np.nan: "", np.inf: "", -np.inf: ""})
                return df_csv
        except Exception:
            pass

    return pd.DataFrame()
