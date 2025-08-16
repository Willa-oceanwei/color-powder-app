def generate_production_order_print_integrated(order, recipe_row, additional_recipe_rows=None, show_additional_ids=True):
    if recipe_row is None:
        recipe_row = {}
    if additional_recipe_rows is None:
        additional_recipe_rows = []

    lines = []
    powder_label_width = 12
    number_col_width = 8
    pack_col_width = 12
    column_offsets = [2, 2, 2, 2] 

    # ---------- 取得基本資訊 ----------
    recipe_id = recipe_row.get("配方編號", "")
    color = recipe_row.get("顏色", "")
    ratio = recipe_row.get("比例", "")
    pantone = order.get("Pantone 色號") or recipe_row.get("Pantone色號", "")
    created_time = str(order.get("建立時間", "") or "")

    lines.append(f"編號：{recipe_id}  顏色：{color}  比例：{ratio} g/kg  Pantone：{pantone}")

    # ---------- 包裝列 ----------
    pack_line = []
    unit = str(order.get("計量單位") or recipe_row.get("計量單位", "包"))
    for i in range(1, 5):
        w = float(order.get(f"包裝重量{i}", 0) or 0)
        c = float(order.get(f"包裝份數{i}", 0) or 0)
        if w > 0 or c > 0:
            if unit == "包":
                real_w_str = f"{w*25:.2f}".rstrip('0').rstrip('.') + "K"
            elif unit == "桶":
                real_w_str = f"{w*100:.2f}".rstrip('0').rstrip('.') + "K"
            else:
                real_w_str = f"{w:.2f}".rstrip('0').rstrip('.') + "kg"
            count_str = str(int(c)) if c == int(c) else str(c)
            pack_line.append(f"{real_w_str} × {count_str}".ljust(pack_col_width))
    if pack_line:
        lines.append(" " * 14 + "".join(pack_line))

    # ---------- multipliers ----------
    multipliers = [float(order.get(f"包裝重量{i}", 0) or 0) for i in range(1, 5)]

    # ---------- 主配方色粉列 ----------
    colorant_total = 0
    for idx in range(1, 9):
        c_id = recipe_row.get(f"色粉編號{idx}", "")
        c_wt = float(recipe_row.get(f"色粉重量{idx}", 0) or 0)
        if not c_id and c_wt == 0:
            continue
        if c_wt:
            colorant_total += c_wt
        row = str(c_id).ljust(powder_label_width)
        for i in range(4):
            val = c_wt * multipliers[i] if c_wt else 0
            val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
            row += f"{val_str:>{number_col_width}}"
        lines.append(row)

    # ---------- 合計列（抓合計類別） ----------
    total_type = recipe_row.get("合計類別", "").strip() or "合計"
    net_weight = float(recipe_row.get("淨重", 0) or 0)
    total_line = total_type.ljust(powder_label_width)
    for m in multipliers:
        val = net_weight * m if m > 0 else 0
        val_str = f"{val:.2f}".rstrip('0').rstrip('.') if val else ""
        total_line += f"{val_str:>{number_col_width}}"
    lines.append(total_line)

    # ---------- 附加配方列 ----------
    for idx, sub in enumerate(additional_recipe_rows, 1):
        lines.append("")
        if show_additional_ids:
            lines.append(f"附加配方 {idx}：{sub.get('配方編號','')}")
        else:
            lines.append(f"附加配方 {idx}")
        for i in range(1, 9):
            c_id = sub.get(f"色粉編號{i}", "")
            if not c_id:
                continue
            c_id_str = str(c_id).ljust(powder_label_width)
            val = float(sub.get(f"色粉重量{i}", 0) or 0)
            row = c_id_str
            for j in range(4):
                val_mult = val * multipliers[j] if val else 0
                val_str = str(int(val_mult)) if val_mult.is_integer() else f"{val_mult:.3f}".rstrip('0').rstrip('.') if val_mult else ""
                offset = " " * column_offsets[j]
                row += offset + f"{val_str:>{number_col_width}}"
            lines.append(row)

    return "\n".join(lines), created_time  # 確保 return 是文字
