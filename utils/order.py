# utils/order.py - 完整版（單一檔案）
import streamlit as st
import pandas as pd
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from .common import (
    get_spreadsheet,
    save_df_to_sheet,
    generate_production_order_print,
    generate_print_page_content,
    clean_powder_id,
    fix_leading_zero,
    normalize_search_text,
    load_recipe
)

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
    
    # ================= 初始化 =================
    Path("data").mkdir(parents=True, exist_ok=True)
    order_file = Path("data/df_order.csv")
    
    # 載入配方資料
    df_recipe = st.session_state.get("df_recipe", pd.DataFrame())
    if df_recipe.empty:
        df_recipe = load_recipe(force_reload=True)
        st.session_state.df_recipe = df_recipe
    
    # 取得 Google Sheets
    try:
        spreadsheet = get_spreadsheet()
        ws_recipe = spreadsheet.worksheet("配方管理")
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法連線 Google Sheet：{e}")
        return
    
    # 載入生產單資料
    try:
        existing_values = ws_order.get_all_values()
        if existing_values:
            df_order = pd.DataFrame(existing_values[1:], columns=existing_values[0]).astype(str)
            if "客戶編號" not in df_order.columns:
                df_order["客戶編號"] = ""
        else:
            header = [
                "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "客戶編號", 
                "建立時間", "Pantone 色號", "計量單位", "原料",
                "包裝重量1", "包裝重量2", "包裝重量3", "包裝重量4",
                "包裝份數1", "包裝份數2", "包裝份數3", "包裝份數4",
                "重要提醒", "備註",
                "色粉編號1", "色粉編號2", "色粉編號3", "色粉編號4",
                "色粉編號5", "色粉編號6", "色粉編號7", "色粉編號8", 
                "色粉合計", "合計類別", "色粉類別"
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
            return
    
    df_order = st.session_state.df_order.copy()
    
    # 初始化 session_state
    for key in ["new_order", "show_confirm_panel", "show_edit_panel", "editing_order", "show_delete_confirm"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "show_confirm_panel" else False
    
    # ================= 搜尋與新增表單 =================
    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")
        
        search_text_normalized = fix_leading_zero(search_text.strip())
        
        if search_text_normalized:
            df_recipe["_配方編號標準"] = df_recipe["配方編號"].map(
                lambda x: fix_leading_zero(clean_powder_id(x))
            )
            
            if exact:
                filtered = df_recipe[
                    (df_recipe["_配方編號標準"] == search_text_normalized) |
                    (df_recipe["客戶名稱"].str.upper() == search_text.strip().upper())
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
    
    # 建立選項
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
    
    # 顯示搜尋結果
    if not option_map:
        st.warning("查無符合的配方")
        selected_row = None
    elif len(option_map) == 1:
        selected_label = list(option_map.keys())[0]
        selected_row = option_map[selected_label].copy()
        st.success(f"已自動選取：{selected_label}")
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
    
    # 新增按鈕處理
    if add_btn and selected_row is not None:
        if selected_row.get("狀態") == "停用":
            st.warning("⚠️ 此配方已停用，請勿使用")
        else:
            # 產生新生產單號
            today_str = datetime.now().strftime("%Y%m%d")
            count_today = df_order[df_order["生產單號"].str.startswith(today_str)].shape[0]
            new_id = f"{today_str}-{count_today + 1:03}"
            
            # 查找附加配方
            main_recipe_code = selected_row.get("配方編號", "").strip()
            附加配方 = df_recipe[
                (df_recipe["配方類別"].astype(str).str.strip() == "附加配方") &
                (df_recipe["原始配方"].astype(str).str.strip() == main_recipe_code)
            ]
            
            # 整合色粉
            all_colorants = []
            for i in range(1, 9):
                id_val = selected_row.get(f"色粉編號{i}", "")
                wt_val = selected_row.get(f"色粉重量{i}", "")
                if id_val or wt_val:
                    all_colorants.append((id_val, wt_val))
            
            for _, sub in 附加配方.iterrows():
                for i in range(1, 9):
                    id_val = sub.get(f"色粉編號{i}", "")
                    wt_val = sub.get(f"色粉重量{i}", "")
                    if id_val or wt_val:
                        all_colorants.append((id_val, wt_val))
            
            # 建立訂單
            order = {
                "生產單號": new_id,
                "生產日期": datetime.now().strftime("%Y-%m-%d"),
                "建立時間": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                "配方編號": selected_row.get("配方編號", ""),
                "顏色": selected_row.get("顏色", ""),
                "客戶名稱": selected_row.get("客戶名稱", ""),
                "客戶編號": selected_row.get("客戶編號", ""),
                "Pantone 色號": selected_row.get("Pantone色號", ""),
                "計量單位": selected_row.get("計量單位", ""),
                "備註": str(selected_row.get("備註", "")).strip(),
                "重要提醒": str(selected_row.get("重要提醒", "")).strip(),
                "合計類別": str(selected_row.get("合計類別", "")).strip(),
                "色粉類別": selected_row.get("色粉類別", "").strip(),
            }
            
            # 用 all_colorants 填入色粉編號與重量欄位
            for i in range(1, 9):
                if i <= len(all_colorants):
                    id_val, wt_val = all_colorants[i-1]
                    order[f"色粉編號{i}"] = id_val
                    order[f"色粉重量{i}"] = wt_val
                else:
                    order[f"色粉編號{i}"] = ""
                    order[f"色粉重量{i}"] = ""
            
            st.session_state["new_order"] = order
            st.session_state["show_confirm_panel"] = True
            st.rerun()
    
    # ================= 詳情填寫面板 =================
    if st.session_state.get("show_confirm_panel"):
        order = st.session_state.get("new_order", {})
        recipe_id = order.get("配方編號", "")
        
        recipe_rows = df_recipe[df_recipe["配方編號"] == recipe_id]
        recipe_row = recipe_rows.iloc[0].to_dict() if not recipe_rows.empty else {}
        
        st.markdown("---")
        st.markdown("<span style='font-size:20px; font-weight:bold;'>新增生產單詳情填寫</span>", unsafe_allow_html=True)
        
        with st.form("order_detail_form"):
            # 不可編輯欄位
            c1, c2, c3, c4 = st.columns(4)
            c1.text_input("生產單號", value=order.get("生產單號", ""), disabled=True)
            c2.text_input("配方編號", value=order.get("配方編號", ""), disabled=True)
            c3.text_input("客戶編號", value=recipe_row.get("客戶編號", ""), disabled=True)
            c4.text_input("客戶名稱", value=order.get("客戶名稱", ""), disabled=True)
            
            # 可編輯欄位
            c5, c6, c7, c8 = st.columns(4)
            c5.text_input("計量單位", value=recipe_row.get("計量單位", "kg"), disabled=True)
            color = c6.text_input("顏色", value=order.get("顏色", ""), key="form_color")
            pantone = c7.text_input("Pantone 色號", value=order.get("Pantone 色號", ""), key="form_pantone")
            raw_material = c8.text_input("原料", value=order.get("原料", ""), key="form_raw_material")
            
            c9, c10 = st.columns(2)
            important_note = c9.text_input("重要提醒", value=order.get("重要提醒", ""), key="form_important_note")
            total_category = c10.text_input("合計類別", value=order.get("合計類別", ""), key="form_total_category")
            remark = st.text_area("備註", value=order.get("備註", ""), key="form_remark")
            
            # 包裝重量與份數
            st.markdown("**包裝重量與份數**")
            w_cols = st.columns(4)
            c_cols = st.columns(4)
            for i in range(1, 5):
                w_cols[i - 1].text_input(f"包裝重量{i}", value="", key=f"form_weight{i}")
                c_cols[i - 1].text_input(f"包裝份數{i}", value="", key=f"form_count{i}")
            
            # 提交按鈕
            submitted = st.form_submit_button("💾 儲存生產單")
            
            if submitted:
                # 檢查是否有包裝資料
                all_empty = True
                for i in range(1, 5):
                    if st.session_state.get(f"form_weight{i}", "").strip() or st.session_state.get(f"form_count{i}", "").strip():
                        all_empty = False
                        break
                
                if all_empty:
                    st.warning("⚠️ 請至少填寫一個包裝重量或包裝份數！")
                else:
                    # 更新訂單資料
                    order["顏色"] = st.session_state.form_color
                    order["Pantone 色號"] = st.session_state.form_pantone
                    order["備註"] = st.session_state.form_remark
                    order["重要提醒"] = st.session_state.form_important_note
                    order["合計類別"] = st.session_state.form_total_category
                    
                    for i in range(1, 5):
                        order[f"包裝重量{i}"] = st.session_state.get(f"form_weight{i}", "").strip()
                        order[f"包裝份數{i}"] = st.session_state.get(f"form_count{i}", "").strip()
                    
                    # 寫入
                    try:
                        header = [col for col in df_order.columns if col and str(col).strip() != ""]
                        row_data = [str(order.get(col, "")).strip() if order.get(col) is not None else "" for col in header]
                        ws_order.append_row(row_data)
                        
                        df_new = pd.DataFrame([order], columns=df_order.columns)
                        df_order = pd.concat([df_order, df_new], ignore_index=True)
                        df_order.to_csv(order_file, index=False, encoding="utf-8-sig")
                        st.session_state.df_order = df_order
                        st.success(f"✅ 生產單 {order['生產單號']} 已儲存！")
                    except Exception as e:
                        st.error(f"❌ 寫入失敗：{e}")
        
        # 下載列印 HTML
        show_ids = st.checkbox("列印時顯示附加配方編號", value=False)
        additional_recipe_rows = df_recipe[
            (df_recipe["配方類別"] == "附加配方") &
            (df_recipe["原始配方"].astype(str).str.strip() == recipe_id)
        ].to_dict("records") if recipe_id else []
        
        print_html = generate_print_page_content(
            order=order,
            recipe_row=recipe_row,
            additional_recipe_rows=additional_recipe_rows,
            show_additional_ids=show_ids
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 下載 A5 HTML",
                data=print_html.encode("utf-8"),
                file_name=f"{order['生產單號']}_列印.html",
                mime="text/html"
            )
        with col2:
            if st.button("🔙 返回", key="back_button"):
                st.session_state.new_order = None
                st.session_state.show_confirm_panel = False
                st.rerun()
    
    # ================= 生產單記錄表 =================
    st.markdown("---")
    st.markdown(
        '<h2 style="font-size:22px; font-family:Arial; color:#F9DC5C;">📑 生產單記錄表</h2>',
        unsafe_allow_html=True
    )
    
    search_order = st.text_input(
        "搜尋生產單 (生產單號、配方編號、客戶名稱、顏色)",
        key="search_order_input",
        value=""
    )
    
    # 篩選
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
    
    # 轉換時間並排序
    df_filtered["建立時間"] = pd.to_datetime(df_filtered["建立時間"], errors="coerce")
    df_filtered = df_filtered.sort_values(by="建立時間", ascending=False)
    
    # 分頁
    if "order_page" not in st.session_state:
        st.session_state.order_page = 1
    if "selectbox_order_limit" not in st.session_state:
        st.session_state.selectbox_order_limit = 5
    
    total_rows = len(df_filtered)
    limit = st.session_state.selectbox_order_limit
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    if st.session_state.order_page > total_pages:
        st.session_state.order_page = total_pages
    
    start_idx = (st.session_state.order_page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx].copy()
    
    # 計算出貨數量
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
            except:
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
                except:
                    continue
            
            return " + ".join(results) if results else ""
        except:
            return ""
    
    if not page_data.empty:
        page_data["出貨數量"] = page_data.apply(calculate_shipment, axis=1)
    
    # 顯示表格
    display_cols = ["生產單號", "配方編號", "顏色", "客戶名稱", "出貨數量", "建立時間"]
    existing_cols = [c for c in display_cols if c in page_data.columns]
    
    if not page_data.empty and existing_cols:
        st.dataframe(
            page_data[existing_cols].reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("查無符合的資料")
    
    # 分頁控制
    cols_page = st.columns([2, 2, 2, 2, 2])
    
    with cols_page[0]:
        if st.button("🏠首頁", key="first_page"):
            st.session_state.order_page = 1
            st.rerun()
    
    with cols_page[1]:
        if st.button("🔼上一頁", key="prev_page") and st.session_state.order_page > 1:
            st.session_state.order_page -= 1
            st.rerun()
    
    with cols_page[2]:
        if st.button("🔽下一頁", key="next_page") and st.session_state.order_page < total_pages:
            st.session_state.order_page += 1
            st.rerun()
    
    with cols_page[3]:
        jump_page = st.number_input(
            "",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.order_page,
            key="jump_page",
            label_visibility="collapsed"
        )
        if jump_page != st.session_state.order_page:
            st.session_state.order_page = jump_page
            st.rerun()
    
    with cols_page[4]:
        options_list = [5, 10, 20, 50, 75, 100]
        current_limit = st.session_state.selectbox_order_limit
        if current_limit not in options_list:
            current_limit = 5
        
        new_limit = st.selectbox(
            label=" ",
            options=options_list,
            index=options_list.index(current_limit),
            key="selectbox_order_limit_select",
            label_visibility="collapsed"
        )
        
        if new_limit != st.session_state.selectbox_order_limit:
            st.session_state.selectbox_order_limit = new_limit
            st.session_state.order_page = 1
            st.rerun()
    
    st.caption(f"頁碼 {st.session_state.order_page} / {total_pages}，總筆數 {total_rows}")
    
    st.markdown("---")
    st.markdown(
        '<h2 style="font-size:20px; font-family:Arial; color:#F9DC5C;">🛠️ 生產單修改/刪除</h2>',
        unsafe_allow_html=True
    )
    
    # 預覽與操作（簡化版）
    if not page_data.empty:
        st.info("選擇生產單後可進行預覽、修改或刪除操作")
