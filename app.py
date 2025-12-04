import streamlit as st
import gspread
import json
import pandas as pd
from google.oauth2.service_account import Credentials
from pathlib import Path



# ======================================================
# 🔥 1. Google Sheet Client（全域共用）
# ======================================================

def get_gspread_client():
    """建立 gspread client"""
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
        return client
    except Exception as e:
        st.error(f"❌ 無法建立 Google Sheet 連線：{e}")
        return None


def get_spreadsheet(name_or_url):
    """回傳 Spreadsheet 物件"""
    client = get_gspread_client()
    if not client:
        return None
    try:
        if str(name_or_url).startswith("http"):
            return client.open_by_url(name_or_url)
        else:
            return client.open(name_or_url)
    except Exception as e:
        st.error(f"❌ 無法開啟 Spreadsheet：{e}")
        return None



# ======================================================
# 🔥 2. DataFrame ↔ Google Sheet
# ======================================================

def sheet_to_df(ws):
    """worksheet → dataframe"""
    try:
        rows = ws.get_all_records()
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"❌ 載入 Google Sheet 錯誤：{e}")
        return pd.DataFrame()


def save_df_to_sheet(ws, df):
    """dataframe → worksheet"""
    try:
        values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        ws.clear()
        ws.update("A1", values)
    except Exception as e:
        st.error(f"❌ 無法寫入 Google Sheet：{e}")


# ======================================================
# 🔥 3. Session State 初始化
# ======================================================

def init_states(keys):
    """初始化 session_state"""
    dict_keys = {"form_color", "form_recipe", "order"}

    for k in keys:
        if k not in st.session_state:
            if k in dict_keys:
                st.session_state[k] = {}
            else:
                st.session_state[k] = ""


# ======================================================
# 🔥 4. CSV 備份
# ======================================================

def save_csv(df, filename):
    Path("data").mkdir(exist_ok=True)
    df.to_csv(Path("data") / filename, index=False, encoding="utf-8-sig")


def load_csv(filename):
    path = Path("data") / filename
    if path.exists():
        try:
            return pd.read_csv(path)
        except:
            return pd.DataFrame()
    return pd.DataFrame()


# ======================================================
# 🔥 5. 配方資料載入（Google Sheet → CSV → 空DF）
# ======================================================

def load_recipe(spreadsheet):
    try:
        ws = spreadsheet.worksheet("配方管理")
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty:
            return df
    except Exception as e:
        st.warning(f"Google Sheet 載入失敗：{e}")

    # fallback CSV
    try:
        df_csv = load_csv("df_recipe.csv")
        if not df_csv.empty:
            return df_csv
    except:
        pass

    return pd.DataFrame()



# ======================================================
# 🔥 6. 生產單列印：主函式
# ======================================================

def generate_production_order_print(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    """
    生產單列印格式（完整版本，不刪減）
    """
    if recipe_row is None:
        recipe_row = {}

    category = order.get("色粉類別", "").strip()

    unit = recipe_row.get("計量單位", "kg")
    ratio = recipe_row.get("比例3", "")
    total_type = recipe_row.get("合計類別", "").strip()

    if total_type == "原料":  # 舊資料相容
        total_type = "料"

    powder_label_width = 12
    pack_col_width = 11
    number_col_width = 6
    column_offsets = [1, 5, 5, 5]

    packing_weights = [
        float(order.get(f"包裝重量{i}", 0)) if str(order.get(f"包裝重量{i}", "")).replace(".", "", 1).isdigit() else 0
        for i in range(1, 5)
    ]
    packing_counts = [
        float(order.get(f"包裝份數{i}", 0)) if str(order.get(f"包裝份數{i}", "")).replace(".", "", 1).isdigit() else 0
        for i in range(1, 5)
    ]

    colorant_ids = [recipe_row.get(f"色粉編號{i+1}", "") for i in range(8)]
    colorant_weights = []
    for i in range(8):
        try:
            val = float(recipe_row.get(f"色粉重量{i+1}", 0) or 0)
        except:
            val = 0.0
        colorant_weights.append(val)

    multipliers = packing_weights

    try:
        net_weight = float(recipe_row.get("淨重", 0))
    except:
        net_weight = 0.0

    lines = []
    lines.append("")

    # ========= 第一行：配方資訊行 =========
    recipe_id = recipe_row.get('配方編號', '')
    color = order.get('顏色', '')
    pantone = order.get('Pantone 色號', '').strip()

    pantone_part = (
        f"<div style='flex:1; min-width:80px;'>Pantone：{pantone}</div>"
        if pantone else ""
    )

    info_line = (
        f"<div style='display:flex; font-size:20px; font-family:Arial;'>"
        f"<div style='flex:1;'>編號：<b>{recipe_id}</b></div>"
        f"<div style='flex:1;'>顏色：{color}</div>"
        f"<div style='flex:1;'>比例：{ratio} g/kg</div>"
        f"{pantone_part}</div>"
    )
    lines.append(info_line)
    lines.append("")

    # ========= 包裝列 =========
    pack_line = []
    for i in range(4):
        w = packing_weights[i]
        c = packing_counts[i]
        if w > 0 or c > 0:
            unit_str = f"{w:.2f}".rstrip("0").rstrip(".") + "kg"
            count_str = str(int(c)) if c == int(c) else str(c)
            pack_line.append(f"{unit_str} × {count_str:<{pack_col_width}}")

    lines.append("<b>" + " " * 14 + "".join(pack_line) + "</b>")

    # ========= 主配方色粉列 =========
    for idx in range(8):
        c_id = colorant_ids[idx]
        c_w = colorant_weights[idx]
        if not c_id:
            continue

        row = f"<b>{c_id.ljust(powder_label_width)}</b>"
        for i in range(4):
            val = c_w * multipliers[i] if multipliers[i] else 0
            val_str = (str(int(val)) if val.is_integer() else f"{val:.3f}".rstrip("0").rstrip(".")) if val else ""
            padding = " " * column_offsets[i]
            row += padding + f"<b>{val_str:>{number_col_width}}</b>"

        lines.append(row)

    # ========= 橫線 =========
    if category != "色母":
        lines.append("＿" * 28)

    # ========= 主配方合計 =========
    total_line = f"<b>{total_type.ljust(powder_label_width)}</b>"
    for i in range(4):
        result = net_weight * multipliers[i] if multipliers[i] else 0
        val_str = f"{result:.3f}".rstrip("0").rstrip(".") if result else ""
        padding = " " * column_offsets[i]
        total_line += padding + f"<b>{val_str:>{number_col_width}}</b>"
    lines.append(total_line)

    # ========= 備註 =========
    remark = order.get("備註", "").strip()
    if remark:
        lines.append("")
        lines.append(f"備註：{remark}")

    return "<br>".join(lines)



# ======================================================
# 🔥 7. 生產單列印 HTML Wrapper
# ======================================================

def generate_print_page_content(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):

    content = generate_production_order_print(
        order, recipe_row,
        additional_recipe_rows=additional_recipe_rows,
        show_additional_ids=show_additional_ids
    )

    created_time = str(order.get("建立時間", "") or "")

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>生產單列印</title>
        <style>
            @page {{ size: A5 landscape; margin: 10mm; }}
            body {{
                font-family: 'Courier New';
                font-size: 22px;
                line-height: 1.3;
            }}
            .title {{
                text-align: center;
                font-size: 26px;
                font-family: Arial;
            }}
            .timestamp {{
                text-align: center;
                font-size: 20px;
                margin-bottom: 8px;
            }}
            pre {{
                white-space: pre-wrap;
                margin-left: 20px;
            }}
        </style>
        <script> window.onload = () => window.print(); </script>
    </head>
    <body>
        <div class="timestamp">{created_time}</div>
        <div class="title">生產單</div>
        <pre>{content}</pre>
    </body>
    </html>
    """
    return html
