# utils/query.py
import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, date
from .common import get_spreadsheet, get_worksheet, get_sheet_df, save_df_to_sheet, init_states


def show_query_page(mode="pantone"):
    """查詢區主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())
    
    if mode == "pantone":
        show_pantone_page()
    elif mode == "cross":
        show_cross_query_page()

def show_pantone_page():
    """Pantone色號表頁面"""
    try:
        df_recipe = get_sheet_df("配方管理")
    except Exception as e:
        st.error(f"無法載入資料：{e}")
        return
    
    st.markdown(
        '<h1 style="font-size:22px; font-family:Arial; color:#dbd818;">🭭 Pantone色號表</h1>',
        unsafe_allow_html=True
    )
    
    # 嘗試讀取 Pantone色號表
    try:
        ws_pantone = get_worksheet("Pantone色號表")
    except:
        spreadsheet = get_spreadsheet()
        ws_pantone = spreadsheet.add_worksheet(title="Pantone色號表", rows=100, cols=4)
    
    df_pantone = get_sheet_df("Pantone色號表")
    
    # 如果表格是空的，補上欄位名稱
    if df_pantone.empty:
        ws_pantone.clear()
        ws_pantone.append_row(["Pantone色號", "配方編號", "客戶名稱", "料號"])
        df_pantone = pd.DataFrame(columns=["Pantone色號", "配方編號", "客戶名稱", "料號"])
    
    # === 新增區塊（2 欄一列） ===
    with st.form("add_pantone"):
        col1, col2 = st.columns(2)
        with col1:
            pantone_code = st.text_input("Pantone 色號")
        with col2:
            formula_id = st.text_input("配方編號")
        
        col3, col4 = st.columns(2)
        with col3:
            customer = st.text_input("客戶名稱")
        with col4:
            material_no = st.text_input("料號")
        
        submitted = st.form_submit_button("➕ 新增")
        
        if submitted:
            if not pantone_code or not formula_id:
                st.error("❌ Pantone 色號與配方編號必填")
            else:
                # 單向檢查配方管理
                if formula_id in df_recipe["配方編號"].astype(str).values:
                    st.warning(f"⚠️ 配方編號 {formula_id} 已存在於『配方管理』，不新增")
                # 檢查 Pantone 色號表內是否重複
                elif formula_id in df_pantone["配方編號"].astype(str).values:
                    st.error(f"❌ 配方編號 {formula_id} 已經在 Pantone 色號表裡")
                else:
                    ws_pantone.append_row([pantone_code, formula_id, customer, material_no])
                    st.success(f"✅ 已新增：Pantone {pantone_code}（配方編號 {formula_id}）")
    
    # 查詢區域樣式微調
    st.markdown("""
        <style>
        /* 查詢框下方距離縮小 */
        div.stTextInput {
            margin-bottom: 0.2rem !important;
        }
        /* 表格上方和下方距離縮小 */
        div[data-testid="stTable"] {
            margin-top: 0.2rem !important;
            margin-bottom: 0.2rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # ======== 🔍 查詢 Pantone 色號 ========
    st.markdown(
        '<h1 style="font-size:22px; font-family:Arial; color:#f0efa2;">🔍 查詢 Pantone 色號</h1>',
        unsafe_allow_html=True
    )
    
    search_code = st.text_input("輸入 Pantone 色號")
    
    if search_code:
        # Pantone 對照表
        df_result_pantone = df_pantone[df_pantone["Pantone色號"].str.contains(search_code, case=False, na=False)] if not df_pantone.empty else pd.DataFrame()
        
        # 配方管理
        if "df_recipe" in st.session_state and not st.session_state.df_recipe.empty:
            df_recipe = st.session_state.df_recipe
        else:
            df_recipe = pd.DataFrame()
        
        if not df_recipe.empty and "Pantone色號" in df_recipe.columns:
            df_result_recipe = df_recipe[df_recipe["Pantone色號"].str.contains(search_code, case=False, na=False)]
        else:
            df_result_recipe = pd.DataFrame()
        
        if df_result_pantone.empty and df_result_recipe.empty:
            st.warning("查無符合的 Pantone 色號資料。")
        else:
            if not df_result_pantone.empty:
                st.markdown(
                    '<div style="font-size:20px; font-family:Arial; color:#f0efa2; line-height:1.2; margin:2px 0;">🔍 Pantone 對照表</div>',
                    unsafe_allow_html=True
                )
                st.table(df_result_pantone.reset_index(drop=True))
            
            if not df_result_recipe.empty:
                st.markdown('<div style="margin-top:0px;"></div>', unsafe_allow_html=True)
                st.dataframe(
                    df_result_recipe[["配方編號", "顏色", "客戶名稱", "Pantone色號", "配方類別", "狀態"]].reset_index(drop=True)
                )

def show_cross_query_page():
    """交叉查詢頁面"""
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())
    
    # ---------------- 第一段：交叉查詢 ----------------
    st.markdown(
        '<h1 style="font-size:22px; font-family:Arial; color:#dbd818;">♻️ 依色粉編號查配方</h1>',
        unsafe_allow_html=True
    )
    
    cols = st.columns(5)
    inputs = []
    for i in range(5):
        val = cols[i].text_input(f"色粉編號{i+1}", key=f"cross_color_{i}")
        if val.strip():
            inputs.append(val.strip())
    
    if st.button("查詢配方", key="btn_cross_query") and inputs:
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
                orders = df_order[df_order["配方編號"].astype(str) == str(recipe["配方編號"])]
                last_date = pd.NaT
                if not orders.empty and "生產日期" in orders.columns:
                    orders["生產日期"] = pd.to_datetime(orders["生產日期"], errors="coerce")
                    last_date = orders["生產日期"].max()
                
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
                df_result = df_result.sort_values(by="最後生產時間", ascending=False)
                df_result["最後生產時間"] = df_result["最後生產時間"].apply(
                    lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else ""
                )
            
            st.dataframe(df_result, use_container_width=True)
    
    st.markdown("---")
    
    # ---------------- 第二段：色粉用量查詢 ----------------
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🧮 色粉用量查詢</h2>',
        unsafe_allow_html=True
    )
    
    cols = st.columns(4)
    powder_inputs = []
    for i in range(4):
        val = cols[i].text_input(f"色粉編號{i+1}", key=f"usage_color_{i}")
        if val.strip():
            powder_inputs.append(val.strip())
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("開始日期", key="usage_start_date")
    end_date = col2.date_input("結束日期", key="usage_end_date")
    
    def format_usage(val):
        if val >= 1000:
            kg = val / 1000
            if round(kg, 2) == int(kg):
                return f"{int(kg)} kg"
            else:
                return f"{kg:.2f} kg"
        else:
            if round(val, 2) == int(val):
                return f"{int(val)} g"
            else:
                return f"{val:.2f} g"

    def parse_pack_value(val):
        """將包裝重量/份數轉為數值，容忍包含單位或符號的輸入（例如 500K、25kg）。"""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)

        text = str(val).strip()
        if not text:
            return 0.0

        try:
            return float(text)
        except (TypeError, ValueError):
            pass

        normalized = text.replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return 0.0

    def get_effective_powder_weights(rec: dict) -> dict:
        """依配方列計算每個色粉的有效 g/kg，並補上合計類別差額。"""
        totals = {}
        for i in range(1, 9):
            pid = str(rec.get(f"色粉編號{i}", "")).strip()
            if not pid:
                continue
            try:
                weight = float(rec.get(f"色粉重量{i}", 0) or 0)
            except (TypeError, ValueError):
                weight = 0.0
            if weight <= 0:
                continue
            totals[pid] = totals.get(pid, 0.0) + weight

        total_category = str(rec.get("合計類別", "")).strip()
        if total_category:
            try:
                net_weight = float(rec.get("淨重", 0) or 0)
            except (TypeError, ValueError):
                net_weight = 0.0
            remainder = net_weight - sum(totals.values())
            if remainder > 0:
                totals[total_category] = totals.get(total_category, 0.0) + remainder
        return totals
    
    if st.button("查詢用量", key="btn_powder_usage") and powder_inputs:
        results = []
        df_order_local = df_order.copy()
        
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        for c in powder_cols + ["配方編號", "配方類別", "原始配方", "配方名稱", "顏色", "客戶名稱"]:
            if c not in df_recipe.columns:
                df_recipe[c] = ""
        
        if "生產日期" in df_order_local.columns:
            df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
        else:
            df_order_local["生產日期"] = pd.NaT
        
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
        
        for powder_id in powder_inputs:
            total_usage_g = 0.0
            monthly_usage = {}
            
            orders_in_range = df_order_local[
                (df_order_local["生產日期"].notna()) &
                (df_order_local["生產日期"] >= pd.to_datetime(start_date)) &
                (df_order_local["生產日期"] <= pd.to_datetime(end_date))
            ]
            
            for _, order in orders_in_range.iterrows():
                order_recipe_id = str(order.get("配方編號", "")).strip()
                if not order_recipe_id:
                    continue
                
                recipe_rows = []
                main_df = df_recipe[df_recipe["配方編號"].astype(str) == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
                add_df = df_recipe[
                    (df_recipe["配方類別"] == "附加配方") &
                    (df_recipe["原始配方"].astype(str) == order_recipe_id)
                ]
                if not add_df.empty:
                    recipe_rows.extend(add_df.to_dict("records"))
                
                packs_total = 0.0
                for j in range(1, 5):
                    w = parse_pack_value(order.get(f"包裝重量{j}", 0))
                    n = parse_pack_value(order.get(f"包裝份數{j}", 0))
                    packs_total += w * n
                
                if packs_total <= 0:
                    continue
                
                order_total_for_powder = 0.0
                sources_main = set()
                sources_add = set()
                
                for rec in recipe_rows:
                    powder_weight = get_effective_powder_weights(rec).get(powder_id, 0.0)
                    if powder_weight <= 0:
                        continue
                    
                    contrib = powder_weight * packs_total
                    order_total_for_powder += contrib
                    
                    disp_name = recipe_display_name(rec)
                    if str(rec.get("配方類別", "")).strip() == "附加配方":
                        sources_add.add(disp_name)
                    else:
                        sources_main.add(disp_name)
                
                if order_total_for_powder <= 0:
                    continue
                
                od = order["生產日期"]
                if pd.isna(od):
                    continue
                month_key = od.strftime("%Y/%m")
                if month_key not in monthly_usage:
                    monthly_usage[month_key] = {"usage": 0.0, "main_recipes": set(), "additional_recipes": set()}
                
                monthly_usage[month_key]["usage"] += order_total_for_powder
                monthly_usage[month_key]["main_recipes"].update(sources_main)
                monthly_usage[month_key]["additional_recipes"].update(sources_add)
                total_usage_g += order_total_for_powder
            
            months_sorted = sorted(monthly_usage.keys())
            for month in months_sorted:
                data = monthly_usage[month]
                usage_g = data["usage"]
                if usage_g <= 0:
                    continue
                
                per = pd.Period(month, freq="M")
                month_start = per.start_time.date()
                month_end = per.end_time.date()
                disp_start = max(start_date, month_start)
                disp_end = min(end_date, month_end)
                
                if (disp_start == month_start) and (disp_end == month_end):
                    date_disp = month
                else:
                    date_disp = f"{disp_start.strftime('%Y/%m/%d')}~{disp_end.strftime('%m/%d')}"
                
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
        st.dataframe(styled, use_container_width=True)
    
    st.markdown("---")
    
    # ---------------- 第三段：色粉用量排行榜 ----------------
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🏆 色粉用量排行榜</h2>',
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns(2)
    rank_start = col1.date_input("開始日期（排行榜）", key="rank_start_date")
    rank_end = col2.date_input("結束日期（排行榜）", key="rank_end_date")
    
    if st.button("生成排行榜", key="btn_powder_rank"):
        df_order_local = df_order.copy()
        
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        weight_cols = [f"色粉重量{i}" for i in range(1, 9)]
        for c in powder_cols + weight_cols + ["配方編號", "配方類別", "原始配方"]:
            if c not in df_recipe.columns:
                df_recipe[c] = ""
        
        if "生產日期" in df_order_local.columns:
            df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce")
        else:
            df_order_local["生產日期"] = pd.NaT
        
        orders_in_range = df_order_local[
            (df_order_local["生產日期"].notna()) &
            (df_order_local["生產日期"] >= pd.to_datetime(rank_start)) &
            (df_order_local["生產日期"] <= pd.to_datetime(rank_end))
        ]
        
        pigment_usage = {}
        
        for _, order in orders_in_range.iterrows():
            order_recipe_id = str(order.get("配方編號", "")).strip()
            if not order_recipe_id:
                continue
            
            recipe_rows = []
            main_df = df_recipe[df_recipe["配方編號"].astype(str) == order_recipe_id]
            if not main_df.empty:
                recipe_rows.append(main_df.iloc[0].to_dict())
            add_df = df_recipe[
                (df_recipe["配方類別"] == "附加配方") &
                (df_recipe["原始配方"].astype(str) == order_recipe_id)
            ]
            if not add_df.empty:
                recipe_rows.extend(add_df.to_dict("records"))
            
            packs_total = 0.0
            for j in range(1, 5):
                w = parse_pack_value(order.get(f"包裝重量{j}", 0))
                n = parse_pack_value(order.get(f"包裝份數{j}", 0))
                packs_total += w * n
            
            if packs_total <= 0:
                continue
            
            for rec in recipe_rows:
                for pid, pw in get_effective_powder_weights(rec).items():
                    if pid and pw > 0:
                        contrib = pw * packs_total
                        pigment_usage[pid] = pigment_usage.get(pid, 0.0) + contrib
        
        df_rank = pd.DataFrame([
            {"色粉編號": k, "總用量_g": v} for k, v in pigment_usage.items()
        ])
        
        df_rank = df_rank.sort_values("總用量_g", ascending=False).reset_index(drop=True)
        df_rank["總用量"] = df_rank["總用量_g"].map(format_usage)
        df_rank = df_rank[["色粉編號", "總用量"]]
        st.dataframe(df_rank, use_container_width=True)
        
        csv = pd.DataFrame(list(pigment_usage.items()), columns=["色粉編號", "總用量(g)"]).to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ 下載排行榜 CSV",
            data=csv,
            file_name=f"powder_rank_{rank_start}_{rank_end}.csv",
            mime="text/csv"
        )
