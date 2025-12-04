import streamlit as st
import pandas as pd
from pathlib import Path

# ===== 自訂函式：產生生產單列印格式 =====      
def generate_production_order_print(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}

    category = order.get("色粉類別", "").strip()
    
    unit = recipe_row.get("計量單位", "kg")
    ratio = recipe_row.get("比例3", "")
    total_type = recipe_row.get("合計類別", "").strip()

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
    
    try:
        net_weight = float(recipe_row.get("淨重", 0))
    except:
        net_weight = 0.0
    
    lines = []
    lines.append("")
    
    recipe_id = recipe_row.get('配方編號', '')
    color = order.get('顏色', '')
    pantone = order.get('Pantone 色號', '').strip()

    pantone_part = (
        f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>Pantone：{pantone}</div>"
        if pantone else ""
    )

    recipe_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>編號：<b>{recipe_id}</b></div>"
    color_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>顏色：{color}</div>"
    ratio_part = f"<div style='flex:1; min-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>比例：{ratio} g/kg</div>"

    info_line = (
        f"<div style='display:flex; font-size:20px; font-family:Arial; align-items:center; gap:12px;'>"
        f"{recipe_part}{color_part}{ratio_part}{pantone_part}"
        f"</div>"
    )
    lines.append(info_line)
    lines.append("")
    
    pack_line = []
    for i in range(4):
        w = packing_weights[i]
        c = packing_counts[i]
        if w > 0 or c > 0:
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
                unit_str = f"{real_w:.2f}".rstrip("0").rstrip(".") + "kg"
        
            count_str = str(int(c)) if c == int(c) else str(c)
            text = f"{unit_str} × {count_str}"
            pack_line.append(f"{text:<{pack_col_width}}")
        
    packing_indent = " " * 14
    lines.append(f"<b>{packing_indent + ''.join(pack_line)}</b>")
                                    
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
            row += padding + f"<b class='num'>{val_str:>{number_col_width}}</b>"
        lines.append(row)
        
    category = (order.get("色粉類別") or "").strip()
    if category != "色母":
        lines.append("＿" * 28)
                    
    total_offsets = [1, 5, 5, 5]
    if total_type == "" or total_type == "無":
        total_type_display = f"<b>{'='.ljust(powder_label_width)}</b>"
    elif category == "色母":
        total_type_display = f"<b><span style='font-size:22px; display:inline-block; width:{powder_label_width}ch'>料</span></b>"
    else:
        total_type_display = f"<b>{total_type.ljust(powder_label_width)}</b>"
        
    total_line = total_type_display
        
    for i in range(4):
        if category == "色母":
            pigment_total = sum(colorant_weights)
            result = (net_weight - pigment_total) * multipliers[i] if multipliers[i] > 0 else 0
        else:
            result = net_weight * multipliers[i] if multipliers[i] > 0 else 0
        
        val_str = f"{result:.3f}".rstrip('0').rstrip('.') if result else ""
        padding = " " * max(0, int(round(total_offsets[i])))
        total_line += padding + f"<b class='num'>{val_str:>{number_col_width}}</b>"
        
    lines.append(total_line)
           
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

            line_length = powder_label_width + sum([number_col_width + int(round(column_offsets[j])) for j in range(4)])
            lines.append("―" * line_length)
   
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

        
    remark_text = order.get("備註", "").strip()
    if remark_text:
        lines.append("")
        lines.append("")
        lines.append(f"備註 : {remark_text}")

    return "<br>".join(lines)

# --------------- 列印 HTML 生成函式 ---------------
def generate_print_page_content(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}

    if additional_recipe_rows is not None and not isinstance(additional_recipe_rows, list):
        additional_recipe_rows = [additional_recipe_rows]

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
    dict_keys = {"form_color", "form_recipe", "order"}
    
    for k in keys:
        if k not in st.session_state:
            if k in dict_keys:
                st.session_state[k] = {}
            else:
                st.session_state[k] = ""


#===「載入配方資料」的核心函式====
def load_recipe(force_reload=False):
    try:
        ws_recipe = st.session_state.spreadsheet.worksheet("配方管理")
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
