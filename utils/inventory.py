# utils/inventory.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from .common import get_spreadsheet, save_df_to_sheet, init_states

def show_inventory_page():
    """庫存管理主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 取得資料
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    df_order = st.session_state.get("df_order", pd.DataFrame())
    
    # 初始化庫存
    if "last_final_stock" not in st.session_state:
        st.session_state["last_final_stock"] = {}
    
    try:
        spreadsheet = get_spreadsheet()
        ws_stock = spreadsheet.worksheet("庫存記錄")
        records = ws_stock.get_all_records()
        df_stock = pd.DataFrame(records) if records else pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
    except Exception as e:
        st.warning(f"⚠️ 無法讀取 Google Sheet 庫存資料：{e}")
        df_stock = pd.DataFrame(columns=["類型","色粉編號","日期","數量","單位","備註"])
    
    st.session_state.df_stock = df_stock
    
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
    
    # 工具函式
    def to_grams(qty, unit):
        try:
            q = float(qty or 0)
        except:
            q = 0.0
        return q * 1000 if str(unit).lower() == "kg" else q
    
    def format_usage(val_g):
        try:
            val = float(val_g or 0)
        except:
            val = 0.0
        if abs(val) >= 1000:
            kg = val / 1000.0
            return f"{kg:.2f} kg" if not float(int(kg * 100)) == (kg * 100) else f"{int(kg)} kg"
        else:
            return f"{int(round(val))} g" if float(int(val)) == val else f"{val:.2f} g"
    
    def calc_usage_for_stock(powder_id, df_order, df_recipe, start_date, end_date):
        """計算色粉用量"""
        total_usage_g = 0.0 
        df_order_local = df_order.copy()
        
        if "生產日期" not in df_order_local.columns:
            return 0.0
        
        df_order_local["生產日期"] = pd.to_datetime(df_order_local["生產日期"], errors="coerce").dt.normalize()
        
        powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
        candidate_ids = set()
        
        if not df_recipe.empty:
            recipe_df_copy = df_recipe.copy()
            for c in powder_cols:
                if c not in recipe_df_copy.columns:
                    recipe_df_copy[c] = ""
            
            mask = recipe_df_copy[powder_cols].astype(str).apply(lambda row: powder_id in [s.strip() for s in row.values], axis=1)
            recipe_candidates = recipe_df_copy[mask].copy()
            candidate_ids = set(recipe_candidates["配方編號"].astype(str).str.strip().tolist())
        
        if not candidate_ids:
            return 0.0
        
        s_dt = pd.to_datetime(start_date).normalize()
        e_dt = pd.to_datetime(end_date).normalize()
        
        orders_in_range = df_order_local[
            (df_order_local["生產日期"].notna()) &
            (df_order_local["生產日期"] >= s_dt) &
            (df_order_local["生產日期"] <= e_dt)
        ].copy()
        
        if orders_in_range.empty:
            return 0.0
        
        for _, order in orders_in_range.iterrows():
            order_recipe_id = str(order.get("配方編號", "")).strip()
            if not order_recipe_id:
                continue
            
            recipe_rows = []
            if "配方編號" in df_recipe.columns:
                main_df = df_recipe[df_recipe["配方編號"].astype(str).str.strip() == order_recipe_id]
                if not main_df.empty:
                    recipe_rows.append(main_df.iloc[0].to_dict())
            
            if "配方類別" in df_recipe.columns and "原始配方" in df_recipe.columns:
                add_df = df_recipe[
                    (df_recipe["配方類別"].astype(str).str.strip() == "附加配方") &
                    (df_recipe["原始配方"].astype(str).str.strip() == order_recipe_id)
                ]
                if not add_df.empty:
                    recipe_rows.extend(add_df.to_dict("records"))
            
            packs_total_kg = 0.0
            for j in range(1, 5):
                w_key = f"包裝重量{j}"
                n_key = f"包裝份數{j}"
                w_val = order.get(w_key, 0)
                n_val = order.get(n_key, 0)
                try:
                    pack_w = float(w_val or 0)
                    pack_n = float(n_val or 0)
                except (ValueError, TypeError):
                    pack_w, pack_n = 0.0, 0.0
                packs_total_kg += pack_w * pack_n
            
            if packs_total_kg <= 0:
                continue
            
            order_total_for_powder = 0.0
            for rec in recipe_rows:
                rec_id = str(rec.get("配方編號", "")).strip()
                if rec_id not in candidate_ids:
                    continue
                
                pvals = [str(rec.get(f"色粉編號{i}", "")).strip() for i in range(1, 9)]
                if powder_id not in pvals:
                    continue
                
                idx = pvals.index(powder_id) + 1
                
                try:
                    powder_weight_per_kg_product = float(rec.get(f"色粉重量{idx}", 0) or 0)
                except (ValueError, TypeError):
                    powder_weight_per_kg_product = 0.0
                
                if powder_weight_per_kg_product <= 0:
                    continue
                
                contrib = powder_weight_per_kg_product * packs_total_kg
                order_total_for_powder += contrib
            
            total_usage_g += order_total_for_powder
        
        return total_usage_g
    
    def safe_calc_usage(pid, df_order, df_recipe, start_dt, end_dt):
        try:
            if pd.isna(start_dt) or pd.isna(end_dt) or start_dt > end_dt:
                return 0.0
            if df_order.empty or df_recipe.empty:
                return 0.0
            return calc_usage_for_stock(pid, df_order, df_recipe, start_dt, end_dt)
        except Exception as e:
            return 0.0
    
    # ================= 初始庫存設定 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📦 初始庫存設定</h2>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    ini_powder = col1.text_input("色粉編號", key="ini_color")
    ini_qty = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="ini_qty")
    ini_unit = col3.selectbox("單位", ["g", "kg"], key="ini_unit")
    ini_date = st.date_input("設定日期", value=datetime.today(), key="ini_date")
    ini_note = st.text_input("備註", key="ini_note")
    
    if st.button("儲存初始庫存", key="btn_save_ini"):
        if not ini_powder.strip():
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            df_stock = df_stock[~((df_stock["類型"]=="初始") & (df_stock["色粉編號"]==ini_powder.strip()))]
            
            new_row = {
                "類型": "初始",
                "色粉編號": ini_powder.strip(),
                "日期": ini_date,
                "數量": ini_qty,
                "單位": ini_unit,
                "備註": ini_note
            }
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
            
            df_to_upload = df_stock.copy()
            df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce").dt.strftime("%Y/%m/%d").fillna("")
            try:
                ws_stock.clear()
                ws_stock.update([df_to_upload.columns.values.tolist()] + df_to_upload.values.tolist())
            except:
                pass
            
            st.session_state.df_stock = df_stock
            st.success(f"✅ 初始庫存已儲存，色粉 {ini_powder.strip()} 將以最新設定為準")
    
    st.markdown("---")
    
    # ================= 進貨新增 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#18aadb;">📲 進貨新增</h2>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    in_powder = col1.text_input("色粉編號", key="in_color")
    in_qty = col2.number_input("數量", min_value=0.0, value=0.0, step=1.0, key="in_qty_add")
    in_unit = col3.selectbox("單位", ["g", "kg"], key="in_unit_add")
    in_date = col4.date_input("進貨日期", value=datetime.today(), key="in_date")
    in_note = st.text_input("備註", key="in_note")
    
    if st.button("新增進貨", key="btn_add_in"):
        if not in_powder.strip():
            st.warning("⚠️ 請輸入色粉編號！")
        else:
            new_row = {"類型":"進貨",
                        "色粉編號":in_powder.strip(),
                        "日期":in_date,
                        "數量":in_qty,
                        "單位":in_unit,
                        "備註":in_note}
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
            
            df_to_upload = df_stock.copy()
            if "日期" in df_to_upload.columns:
                df_to_upload["日期"] = pd.to_datetime(df_to_upload["日期"], errors="coerce").dt.strftime("%Y/%m/%d").fillna("")
            try:
                ws_stock.clear()
                ws_stock.update([df_to_upload.columns.values.tolist()] + df_to_upload.values.tolist())
            except:
                pass
            st.success("✅ 進貨記錄已新增")
    
    st.markdown("---")
    
    # ================= 進貨查詢 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🔍 進貨查詢</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    search_code = col1.text_input("色粉編號", key="in_search_code")
    search_start = col2.date_input("進貨日期(起)", key="in_search_start")
    search_end = col3.date_input("進貨日期(迄)", key="in_search_end")
    
    if st.button("查詢進貨", key="btn_search_in_v3"):
        df_result = df_stock[df_stock["類型"] == "進貨"].copy()
        
        if search_code.strip():
            df_result = df_result[df_result["色粉編號"].astype(str).str.contains(search_code.strip(), case=False)]
        
        df_result["日期_dt"] = pd.to_datetime(df_result["日期"], errors="coerce").dt.normalize()
        
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
        
        if not df_result.empty:
            show_cols = {
                "色粉編號": "色粉編號",
                "日期_dt": "日期",
                "數量": "數量",
                "單位": "單位",
                "備註": "備註"
            }
            df_display = df_result[list(show_cols.keys())].rename(columns=show_cols)
            
            def format_quantity_unit(row):
                qty = row["數量"]
                unit = row["單位"].strip().lower()
                if unit == "g" and qty >= 1000:
                    return pd.Series([qty/1000, "kg"])
                else:
                    return pd.Series([qty, row["單位"]])
            
            df_display[["數量", "單位"]] = df_display.apply(format_quantity_unit, axis=1)
            df_display["日期"] = df_display["日期"].dt.strftime("%Y/%m/%d")
            
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("ℹ️ 沒有符合條件的進貨資料")
    
    st.markdown("---")
    
    # ================= 庫存查詢 =================
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">📊 庫存查詢</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    query_start = col1.date_input("查詢起日", key="stock_start_query") 
    query_end = col2.date_input("查詢迄日", key="stock_end_query")
    
    input_key = "stock_powder"
    st.markdown(f"""
        <style>
        div[data-testid="stTextInput"][data-baseweb="input"] > div:has(input#st-{input_key}) {{
            margin-top: -32px !important;
        }}
        </style>
        <label style="font-size:16px; font-weight:500;">
            色粉編號
            <span style="color:gray; font-size:13px; font-weight:400;">
                （01 以下需選擇日期，或至「交叉查詢區」➜「色粉用量查詢」）
            </span>
        </label>
        """, unsafe_allow_html=True)
    
    stock_powder = st.text_input("", key=input_key)
    
    if "ini_dict" not in st.session_state:
        st.session_state["ini_dict"] = {}
    if "last_final_stock" not in st.session_state:
        st.session_state["last_final_stock"] = {}
    
    if not query_start and not query_end:
        st.info(f"ℹ️ 未選擇日期，系統將顯示截至 {date.today()} 的最新庫存數量")
    elif query_start and not query_end:
        st.info(f"ℹ️ 查詢 {query_start} ~ {date.today()} 的庫存數量")
    elif not query_start and query_end:
        st.info(f"ℹ️ 查詢最早 ~ {query_end} 的庫存數量")
    else:
        st.success(f"✅ 查詢 {query_start} ~ {query_end} 的庫存數量")
    
    run_query = st.button("計算庫存", key="btn_calc_stock_v2") or bool(stock_powder.strip())
    
    if run_query:
        df_stock_copy = df_stock.copy()
        df_stock_copy["日期"] = pd.to_datetime(df_stock_copy["日期"], errors="coerce").dt.normalize()
        df_stock_copy["數量_g"] = df_stock_copy.apply(lambda r: to_grams(r["數量"], r["單位"]), axis=1)
        df_stock_copy["色粉編號"] = df_stock_copy["色粉編號"].astype(str).str.strip()
        
        df_order_copy = df_order.copy()
        if "生產日期" in df_order_copy.columns:
            df_order_copy["生產日期"] = pd.to_datetime(df_order_copy["生產日期"], errors="coerce").dt.normalize()
        
        all_pids_stock = df_stock_copy["色粉編號"].unique() if not df_stock_copy.empty else []
        all_pids_recipe = []
        if not df_recipe.empty:
            powder_cols = [f"色粉編號{i}" for i in range(1, 9)]
            for c in powder_cols:
                if c in df_recipe.columns:
                    all_pids_recipe.extend(df_recipe[c].astype(str).str.strip().tolist())
        all_pids_all = sorted(list(set(all_pids_stock) | set([p for p in all_pids_recipe if p])))
        
        stock_powder_strip = stock_powder.strip()
        if stock_powder_strip:
            all_pids = [pid for pid in all_pids_all if stock_powder_strip.lower() in pid.lower()]
            if not all_pids:
                st.warning(f"⚠️ 查無與 '{stock_powder_strip}' 相關的色粉記錄。")
                st.stop()
        else:
            all_pids = all_pids_all
        
        if not all_pids:
            st.warning("⚠️ 查無任何色粉記錄。")
            st.stop()
        
        today = pd.Timestamp.today().normalize()
        min_date_stock = df_stock_copy["日期"].min() if not df_stock_copy.empty else today
        min_date_order = df_order_copy["生產日期"].min() if not df_order_copy.empty else today
        global_min_date = min(min_date_stock, min_date_order).normalize()
        
        s_dt_use = pd.to_datetime(query_start).normalize() if query_start else global_min_date
        e_dt_use = pd.to_datetime(query_end).normalize() if query_end else today
        
        if s_dt_use > e_dt_use:
            st.error("❌ 查詢起日不能晚於查詢迄日。")
            st.stop()
        
        no_date_selected = (query_start is None and query_end is None)
        
        def safe_format(x):
            try:
                return format_usage(x)
            except:
                return "0"
        
        stock_summary = []
        
        for pid in all_pids:
            df_pid = df_stock_copy[df_stock_copy["色粉編號"] == pid].copy()
            ini_total = 0.0
            ini_date = None
            ini_base_value = 0.0
            
            df_pid_stock = df_pid.dropna(subset=["日期"]).copy()
            df_ini = df_pid_stock[df_pid_stock["類型"].astype(str).str.strip() == "初始"]
            if not df_ini.empty:
                latest_ini_row = df_ini.sort_values("日期", ascending=False).iloc[0]
                ini_base_value = latest_ini_row["數量_g"]
                ini_date = pd.to_datetime(latest_ini_row["日期"], errors="coerce").normalize()
            else:
                df_in = df_pid_stock[df_pid_stock["類型"].astype(str).str.strip() == "進貨"]
                min_stock_date = df_in["日期"].min() if not df_in.empty else None
                
                if "配方編號" in df_order_copy.columns and "生產日期" in df_order_copy.columns:
                    df_order_pid = df_order_copy[df_order_copy["配方編號"].astype(str).str.strip() == pid]
                    min_order_date = df_order_pid["生產日期"].min() if not df_order_pid.empty else None
                else:
                    min_order_date = None
                
                candidate_dates = [d for d in [min_stock_date, min_order_date] if d is not None]
                ini_date = min(candidate_dates).normalize() if candidate_dates else pd.Timestamp.today().normalize()
                ini_base_value = 0.0
            
            if no_date_selected:
                s_dt_pid = ini_date if ini_date is not None else global_min_date
            else:
                s_dt_pid = s_dt_use
            
            if ini_date is not None and ini_date <= e_dt_use:
                s_dt_pid = ini_date
                ini_total = ini_base_value
                ini_date_note = f"期初來源：{ini_date.strftime('%Y/%m/%d')}"
            else:
                s_dt_pid = s_dt_use
                ini_total = 0.0
                ini_date_note = "—"
            
            in_qty_interval = df_pid[
                (df_pid["類型"].astype(str).str.strip() == "進貨") &
                (df_pid["日期"] >= s_dt_pid) & (df_pid["日期"] <= e_dt_use)
            ]["數量_g"].sum()
            
            usage_interval = safe_calc_usage(pid, df_order_copy, df_recipe, s_dt_pid, e_dt_use) \
                             if not df_order.empty and not df_recipe.empty else 0.0
            
            final_g = ini_total + in_qty_interval - usage_interval
            st.session_state["last_final_stock"][pid] = final_g
            
            if not str(pid).endswith(("01", "001", "0001")):
                stock_summary.append({
                    "色粉編號": str(pid),
                    "期初庫存": safe_format(ini_total),
                    "區間進貨": safe_format(in_qty_interval),
                    "區間用量": safe_format(usage_interval),
                    "期末庫存": safe_format(final_g),
                    "備註": ini_date_note,
                })
        
        df_result = pd.DataFrame(stock_summary)
        st.dataframe(df_result, use_container_width=True)
        st.caption("🌟期末庫存 = 期初庫存 + 區間進貨 − 區間用量（單位皆以 g 計算，顯示自動轉換）")
