# utils/order.py - 第1部分
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import base64
import re
from .common import get_spreadsheet, save_df_to_sheet, clean_powder_id, fix_leading_zero, normalize_search_text

def show_order_page():
    """生產單管理主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#F9DC5C;">🛸 生產單建立</h2>',
        unsafe_allow_html=True
    )
    
    # ------------------- 配方資料初始化 -------------------
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = pd.DataFrame()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    def load_recipe(force_reload=False):
        """嘗試依序載入配方資料，來源：Google Sheet > CSV > 空 DataFrame"""
        try:
            spreadsheet = get_spreadsheet()
            ws_recipe = spreadsheet.worksheet("配方管理")
            df_loaded = pd.DataFrame(ws_recipe.get_all_records())
            if not df_loaded.empty:
                return df_loaded
        except Exception as e:
            st.warning(f"Google Sheet 載入失敗：{e}")
        
        order_file = Path("data/df_recipe.csv")
        if order_file.exists():
            try:
                df_csv = pd.read_csv(order_file)
                if not df_csv.empty:
                    return df_csv
            except Exception as e:
                st.error(f"CSV 載入失敗：{e}")
        
        return pd.DataFrame()
    
    df_recipe = st.session_state.df_recipe
    
    # ------------------- 生產單資料初始化 -------------------
    order_file = Path("data/df_order.csv")
    
    try:
        spreadsheet = get_spreadsheet()
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法連線 Google Sheet：{e}")
        return
    
    # 載入配方管理表
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
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
            
            # 補齊缺少欄位（新增客戶編號）
            if "客戶編號" not in df_order.columns:
                df_order["客戶編號"] = ""
        else:
            header = [
                "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "客戶編號", "建立時間",
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
            
            if "客戶編號" not in df_order.columns:
                df_order["客戶編號"] = ""
            
            st.session_state.df_order = df_order
        else:
            st.error(f"❌ 無法讀取生產單資料：{e}")
            st.stop()
    
    df_recipe = st.session_state.df_recipe
    df_order = st.session_state.df_order.copy()
    
    # ===== 初始化庫存 =====
    st.session_state["last_final_stock"] = {}
    
    try:
        ws_stock = spreadsheet.worksheet("庫存記錄")
        records = ws_stock.get_all_records()
        df_stock = pd.DataFrame(records)
    except Exception as e:
        st.warning(f"⚠️ 無法讀取 Google Sheet 庫存資料：{e}")
        df_stock = pd.DataFrame(columns=["類型","色粉編號","數量","單位","備註"])
    
    # 標準化類型欄
    df_stock["類型"] = df_stock["類型"].astype(str).str.strip().replace('\u3000','')
    
    # 載入初始庫存
    for idx, row in df_stock.iterrows():
        if row["類型"] == "初始":
            pid = str(row.get("色粉編號","")).strip()
            qty = float(row.get("數量",0))
            if str(row.get("單位","g")).lower() == "kg":
                qty *= 1000
            st.session_state["last_final_stock"][pid] = qty
    
    # 轉換時間欄位與配方編號欄清理
    if "建立時間" in df_order.columns:
        df_order["建立時間"] = pd.to_datetime(df_order["建立時間"], errors="coerce")
    if "配方編號" in df_order.columns:
        df_order["配方編號"] = df_order["配方編號"].map(clean_powder_id)
    
    # 初始化 session_state
    for key in ["selected_order_code_edit", "editing_order", "show_edit_panel", "search_order_input", "order_page"]:
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
    
    # 繼續到第2部分...
# utils/order.py - 第2部分（接續第1部分）
# 這段要加在第1部分的 show_order_page() 函式內

# ===== 自訂函式：產生生產單列印格式 =====      
def generate_production_order_print(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}

    category = order.get("色粉類別", "").strip()
    
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
    
    # 配方資訊列（flex 平均分配 + 長文字自動摺開）
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
    lines.append("")
    
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
    total_offsets = [1, 5, 5, 5]
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
    if remark_text:
        lines.append("")
        lines.append("")
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
        show_additional_ids=show_additional_ids
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

# 繼續到第3部分...
# utils/order.py - 第3部分（接續第2部分）
# 這段要加在第2部分之後，仍在 show_order_page() 函式內

    # ------------------- 配方搜尋與新增生產單 -------------------
    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")
        
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
    def format_option(r):
        label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
        if r.get("配方類別", "") == "附加配方":
            label += "（附加配方）"
        return label
    
    if not filtered.empty:
        filtered["label"] = filtered.apply(format_option, axis=1)
        option_map = dict(zip(filtered["label"], filtered.to_dict(orient="records")))
    else:
        option_map = {}
    
    if not option_map:
        st.warning("查無符合的配方")
        selected_row = None
        selected_label = None
    elif len(option_map) == 1:
        selected_label = list(option_map.keys())[0]
        selected_row = option_map[selected_label].copy()
        
        true_formula_id = selected_row["配方編號"]
        selected_row["配方編號_原始"] = true_formula_id
        
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
            key="search_add_form_selected_recipe"
        )
        if selected_label == "請選擇":
            selected_row = None
        else:
            selected_row = option_map.get(selected_label)
    
    if add_btn:
        if selected_label is None or selected_label == "請選擇" or selected_label == "（無符合配方）":
            st.warning("請先選擇有效配方")
        else:
            if selected_row.get("狀態") == "停用":
                st.warning("⚠️ 此配方已停用，請勿使用")
                st.stop()
            else:
                order = st.session_state.get("new_order")
                if order is None or not isinstance(order, dict):
                    order = {}
                
                # 產生新的生產單號
                df_all_orders = st.session_state.df_order.copy()
                today_str = datetime.now().strftime("%Y%m%d")
                count_today = df_all_orders[df_all_orders["生產單號"].str.startswith(today_str)].shape[0]
                new_id = f"{today_str}-{count_today + 1:03}"
                
                # 查找附加配方
                main_recipe_code = selected_row.get("配方編號", "").strip()
                df_recipe["配方類別"] = df_recipe["配方類別"].astype(str).str.strip()
                df_recipe["原始配方"] = df_recipe["原始配方"].astype(str).str.strip()
                附加配方 = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"] == main_recipe_code)
                ]
                
                # 整合色粉：先加入主配方色粉
                all_colorants = []
                for i in range(1, 9):
                    id_key = f"色粉編號{i}"
                    wt_key = f"色粉重量{i}"
                    id_val = selected_row.get(id_key, "")
                    wt_val = selected_row.get(wt_key, "")
                    if id_val or wt_val:
                        all_colorants.append((id_val, wt_val))
                
                # 加入附加配方色粉
                for _, sub in 附加配方.iterrows():
                    for i in range(1, 9):
                        id_key = f"色粉編號{i}"
                        wt_key = f"色粉重量{i}"
                        id_val = sub.get(id_key, "")
                        wt_val = sub.get(wt_key, "")
                        if id_val or wt_val:
                            all_colorants.append((id_val, wt_val))
                
                # 設定訂單詳細資料
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
                
                # 用 all_colorants 填入色粉編號與重量欄位
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

# 繼續到第4部分...
# utils/order.py - 第四段（接續第三段）

            # ================= 確認刪除 =================
            if st.session_state.get("show_delete_confirm", False):
                order_id = st.session_state.get("delete_target_id")
                order_label = st.session_state.get("delete_target_label") or order_id or "未指定生產單"

                st.warning(f"⚠️ 確定要刪除生產單？\n\n👉 {order_label}")

                c1, c2 = st.columns(2)
    
                if c1.button("✅ 是，刪除", key="confirm_delete_yes"):
                    if order_id is None or order_id == "":
                        st.error("❌ 未指定要刪除的生產單 ID")
                    else:
                        order_id_str = str(order_id)
                        try:
                            deleted = delete_order_by_id(ws_order, order_id_str)
                            if deleted:
                                st.success(f"✅ 已刪除 {order_label}")
                            else:
                                st.error("❌ 找不到該生產單，刪除失敗")
                        except Exception as e:
                            st.error(f"❌ 刪除時發生錯誤：{e}")

                    st.session_state["show_delete_confirm"] = False
                    st.rerun()
        
                if c2.button("取消", key="confirm_delete_no"):
                    st.session_state["show_delete_confirm"] = False
                    st.rerun()
                    
    # ================= 修改面板 =================
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
        
        # 表單編輯欄位
        col_cust_no, col_cust_name, col_color = st.columns(3)

        with col_cust_no:
            new_customer_no = st.text_input(
                "客戶編號",
                value=order_dict.get("客戶編號", "") or recipe_row.get("客戶編號", ""),
                key="edit_customer_no"
            )

        with col_cust_name:
            new_customer = st.text_input(
                "客戶名稱",
                value=order_dict.get("客戶名稱", ""),
                key="edit_customer_name"
            )

        with col_color:
            new_color = st.text_input(
                "顏色",
                value=order_dict.get("顏色", ""),
                key="edit_color"
            )
  
        # 包裝重量 1~4
        pack_weights_cols = st.columns(4)
        new_packing_weights = []
        for i in range(1, 5):
            weight = pack_weights_cols[i - 1].text_input(
                f"包裝重量{i}", value=order_dict.get(f"包裝重量{i}", ""), key=f"edit_packing_weight_{i}"
            )
            new_packing_weights.append(weight)
    
        # 包裝份數 1~4
        pack_counts_cols = st.columns(4)
        new_packing_counts = []
        for i in range(1, 5):
            count = pack_counts_cols[i - 1].text_input(
                f"包裝份數{i}", value=order_dict.get(f"包裝份數{i}", ""), key=f"edit_packing_count_{i}"
            )
            new_packing_counts.append(count)
    
        new_remark = st.text_area("備註", value=order_dict.get("備註", ""), key="edit_remark")
    
        cols_edit = st.columns([1, 1, 1])
    
        with cols_edit[0]:
            if st.button("💾 儲存修改", key="save_edit_button"):
                idx_list = df_order.index[df_order["生產單號"] == order_no].tolist()

                if idx_list:
                    idx = idx_list[0]

                    df_order.at[idx, "客戶編號"] = new_customer_no
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
                            ws_order.update(f"A{row_idx}:{last_col_letter}{row_idx}", [row_data])
                            st.success(f"✅ 生產單 {order_no} 已更新並同步！")
                        else:
                            st.warning("⚠️ Google Sheets 找不到該筆生產單，未更新")
                    except Exception as e:
                        st.error(f"Google Sheets 更新錯誤：{e}")

                    import os
                    os.makedirs(os.path.dirname(order_file), exist_ok=True)
                    df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
                    st.session_state.df_order = df_order
                    st.success("✅ 本地資料更新成功，修改已儲存")
    
                    st.rerun()
                else:
                    st.error("⚠️ 找不到該筆生產單資料")
    
        with cols_edit[1]:
            if st.button("返回", key="return_button"):
                st.session_state.show_edit_panel = False
                st.session_state.editing_order = None
                st.rerun()


# ================= 輔助函式：刪除生產單 =================
def delete_order_by_id(ws, order_id):
    """直接刪除 Google Sheet 中的某一筆生產單"""
    try:
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
    except Exception:
        return False

