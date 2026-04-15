# utils/recipe.py - 完整版（第一部分）
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import traceback
from .common import (
    get_sheet_df,
    get_sheet_values,
    get_worksheet,
    save_df_to_sheet, 
    init_states,
    clean_powder_id,
)

def show_recipe_page():
    """配方管理主頁面"""
    
    # 縮小整個頁面最上方空白
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ================= 初始化與載入資料 =================
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = pd.DataFrame()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    def load_recipe_data():
        """嘗試依序載入配方資料"""
        try:
            df_loaded = get_sheet_df("配方管理")
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
    
    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "重要提醒", "備註", "建檔時間"
    ]
    
    # 初始化 session_state
    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe_code",
        "search_pantone",
        "search_customer",
        "show_edit_recipe_panel",
        "editing_recipe_index"
    ])
    
    # 初始 form_recipe
    if st.session_state.form_recipe is None or not isinstance(st.session_state.form_recipe, dict):
        st.session_state.form_recipe = {col: "" for col in columns}
        st.session_state.form_recipe["配方類別"] = "原始配方"
        st.session_state.form_recipe["狀態"] = "啟用"
        st.session_state.form_recipe["色粉類別"] = "配方"
        st.session_state.form_recipe["計量單位"] = "包"
        st.session_state.form_recipe["淨重單位"] = "g"
        st.session_state.form_recipe["合計類別"] = "無"
    
    if "num_powder_rows" not in st.session_state:
        st.session_state.num_powder_rows = 5
    
    # 載入資料
    try:
        ws_recipe = get_worksheet("配方管理")
    except Exception as e:
        st.error(f"❌ 無法連線 Google Sheet：{e}")
        return
    
    # 讀取原始資料(純字串)
    try:
        values = get_sheet_values("配方管理")
        if len(values) > 1:
            df_loaded = pd.DataFrame(values[1:], columns=values[0])
        else:
            df_loaded = pd.DataFrame(columns=columns)
    except:
        df_loaded = pd.DataFrame(columns=columns)
    
    # 補齊缺少欄位
    for col in columns:
        if col not in df_loaded.columns:
            df_loaded[col] = ""
    
    # 清理配方編號
    if "配方編號" in df_loaded.columns:
        df_loaded["配方編號"] = df_loaded["配方編號"].astype(str).map(clean_powder_id)
    
    st.session_state.df = df_loaded
    st.session_state.df_recipe = df_loaded
    df = st.session_state.df
    
    # 如果還是空的，顯示提示
    if df.empty:
        st.error("⚠️ 配方資料尚未載入，請確認 Google Sheet 或 CSV 是否有資料")
    
    # 載入「色粉管理」的色粉清單
    try:
        df_powders = get_sheet_df("色粉管理")
        if "色粉編號" not in df_powders.columns:
            st.error("❌ 色粉管理表缺少『色粉編號』欄位")
            existing_powders = set()
        else:
            existing_powders = set(df_powders["色粉編號"].map(clean_powder_id).unique())
    except Exception as e:
        st.warning(f"⚠️ 無法載入色粉管理：{e}")
        existing_powders = set()
    
    # 載入客戶清單
    try:
        df_customers = get_sheet_df("客戶名單")
        customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]
    except:
        st.error("無法載入客戶名單")
        customer_options = []
    
    # ================= 配方建立表單 =================
    st.markdown("""
        <div id="recipe-create" style="display: flex; align-items: center; gap: 10px;">
            <h2 style="font-size:22px; font-family:Arial; color:#F9DC5C; margin:0;">🎯 配方建立</h2>
            <a href="#recipe-table" style="
                background-color: var(--background-color);
                color: var(--text-color);
                padding:4px 10px;
                border-radius:6px;
                text-decoration:none;
                font-size:14px;
                font-family:Arial;
            ">⬇ 跳到記錄表</a>
        </div>
        """, unsafe_allow_html=True)
    
    fr = st.session_state.form_recipe
    
    with st.form("recipe_form"):
        # 基本欄位
        col1, col2, col3 = st.columns(3)
        with col1:
            fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="form_recipe_配方編號")
        with col2:
            fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="form_recipe_顏色")
        with col3:
            options = [""] + customer_options
            current = f"{fr.get('客戶編號','')} - {fr.get('客戶名稱','')}" if fr.get("客戶編號") else ""
            index = options.index(current) if current in options else 0
            
            selected = st.selectbox(
                "客戶編號",
                options,
                index=index,
                key="form_recipe_selected_customer"
            )
            
            if selected and " - " in selected:
                c_no, c_name = selected.split(" - ", 1)
                fr["客戶編號"] = c_no.strip()
                fr["客戶名稱"] = c_name.strip()
        
        # 配方類別、狀態、原始配方
        col4, col5, col6 = st.columns(3)
        with col4:
            options_cat = ["原始配方", "附加配方"]
            current = fr.get("配方類別", options_cat[0])
            if current not in options_cat:
                current = options_cat[0]
            fr["配方類別"] = st.selectbox("配方類別", options_cat, index=options_cat.index(current), key="form_recipe_配方類別")
        with col5:
            options_status = ["啟用", "停用"]
            current = fr.get("狀態", options_status[0])
            if current not in options_status:
                current = options_status[0]
            fr["狀態"] = st.selectbox("狀態", options_status, index=options_status.index(current), key="form_recipe_狀態")
        with col6:
            fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方", ""), key="form_recipe_原始配方")
        
        # 色粉類別、計量單位、Pantone
        col7, col8, col9 = st.columns(3)
        with col7:
            options_type = ["配方", "色母", "色粉", "添加劑", "其他"]
            current = fr.get("色粉類別", options_type[0])
            if current not in options_type:
                current = options_type[0]
            fr["色粉類別"] = st.selectbox("色粉類別", options_type, index=options_type.index(current), key="form_recipe_色粉類別")
        with col8:
            options_unit = ["包", "桶", "kg", "其他"]
            current = fr.get("計量單位", options_unit[0])
            if current not in options_unit:
                current = options_unit[0]
            fr["計量單位"] = st.selectbox("計量單位", options_unit, index=options_unit.index(current), key="form_recipe_計量單位")
        with col9:
            fr["Pantone色號"] = st.text_input("Pantone色號", value=fr.get("Pantone色號", ""), key="form_recipe_Pantone色號")
        
        # 重要提醒 + 比例1-3
        fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒", ""), key="form_recipe_重要提醒")
        
        colr1, col_colon, colr2, colr3, col_unit = st.columns([2, 0.5, 2, 2, 1])
        with colr1:
            fr["比例1"] = st.text_input("", value=fr.get("比例1", ""), key="ratio1", label_visibility="collapsed")
        with col_colon:
            st.markdown("<div style='display:flex; justify-content:center; align-items:center; font-size:18px; font-weight:bold; height:36px;'>:</div>", unsafe_allow_html=True)
        with colr2:
            fr["比例2"] = st.text_input("", value=fr.get("比例2", ""), key="ratio2", label_visibility="collapsed")
        with colr3:
            fr["比例3"] = st.text_input("", value=fr.get("比例3", ""), key="ratio3", label_visibility="collapsed")
        with col_unit:
            st.markdown("<div style='display:flex; justify-content:flex-start; align-items:center; font-size:16px; height:36px;'>g/kg</div>", unsafe_allow_html=True)
        
        # 備註
        fr["備註"] = st.text_area("備註", value=fr.get("備註", ""), key="form_recipe_備註")
        
        # 色粉淨重與單位
        col1, col2 = st.columns(2)
        with col1:
            fr["淨重"] = st.text_input("色粉淨重", value=fr.get("淨重", ""), key="form_recipe_淨重")
        with col2:
            options = ["g", "kg"]
            current = fr.get("淨重單位", options[0])
            if current not in options:
                current = options[0]
            fr["淨重單位"] = st.selectbox("單位", options, index=options.index(current), key="form_recipe_淨重單位")
        
        # CSS：縮小輸入框高度
        st.markdown("""
        <style>
        div.stTextInput > div > div > input {
            padding: 2px 6px !important;
            height: 36px !important;
            font-size: 16px;
        }
        div.stTextInput {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }
        [data-testid="stVerticalBlock"] > div[style*="gap"] {
            gap: 0px !important;
            margin-bottom: 0px !important;
        }
        section[data-testid="stHorizontalBlock"] {
            padding-top: -2px !important;
            padding-bottom: -2px !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 色粉設定多列
        st.markdown("##### 色粉設定")
        for i in range(1, st.session_state.get("num_powder_rows", 5) + 1):
            c1, c2 = st.columns([2.5, 2.5])
            
            fr[f"色粉編號{i}"] = c1.text_input(
                "",  
                value=fr.get(f"色粉編號{i}", ""), 
                placeholder=f"色粉{i}編號",
                key=f"form_recipe_色粉編號{i}"
            )
            
            fr[f"色粉重量{i}"] = c2.text_input(
                "",  
                value=fr.get(f"色粉重量{i}", ""), 
                placeholder="重量",
                key=f"form_recipe_色粉重量{i}"
            )
        
        # 合計類別與合計差額
        col1, col2 = st.columns(2)
        with col1:
            category_options = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
            default_raw = fr.get("合計類別", "無")
            default = "\u2002" if default_raw == "無" else default_raw
            if default not in category_options:
                default = category_options[0]
            fr["合計類別"] = st.selectbox("合計類別", category_options, index=category_options.index(default), key="form_recipe_合計類別")
        with col2:
            try:
                net = float(fr.get("淨重") or 0)
                total = sum(float(fr.get(f"色粉重量{i}") or 0) for i in range(1, 9))
                st.write(f"合計差額: {net - total:.2f} g/kg")
            except Exception:
                st.write("合計差額: 計算錯誤")
        
        # 按鈕區
        col1, col2 = st.columns([3, 2])
        with col1:
            submitted = st.form_submit_button("💾 儲存配方")
        with col2:
            add_powder = st.form_submit_button("➕ 新增色粉列")
        
        # 控制避免重複 rerun
        if "add_powder_clicked" not in st.session_state:
            st.session_state.add_powder_clicked = False
        
        if add_powder and not st.session_state.add_powder_clicked:
            st.session_state.num_powder_rows = st.session_state.get("num_powder_rows", 5) + 1
            st.session_state.add_powder_clicked = True
            st.rerun()
        elif submitted:
            pass  # 儲存邏輯在 form 外處理
        else:
            st.session_state.add_powder_clicked = False
    
    # ================= 表單提交處理（接續在第二部分）=================
    # ================= 在表單提交處理中，找到這段並替換 =================
    if submitted:
        missing_powders = []
        for i in range(1, st.session_state.num_powder_rows + 1):
            pid_raw = fr.get(f"色粉編號{i}", "")
            pid = clean_powder_id(pid_raw)
            if pid and pid not in existing_powders:
                missing_powders.append(pid_raw)
    
        if missing_powders:
            st.warning(f"⚠️ 以下色粉尚未建檔：{', '.join(missing_powders)}")
            st.stop()
    
        # 儲存配方邏輯
        if fr["配方編號"].strip() == "":
            st.warning("⚠️ 請輸入配方編號！")
        elif fr["配方類別"] == "附加配方" and fr["原始配方"].strip() == "":
            st.warning("⚠️ 附加配方必須填寫原始配方！")
        else:
            # ✅ 修正：先備份，再更新
            try:
                # 1️⃣ 建立本地備份
                backup_dir = Path("data/backups")
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_file = backup_dir / f"recipe_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(backup_file, index=False, encoding="utf-8-sig")
            
                # 2️⃣ 更新 DataFrame
                if st.session_state.edit_recipe_index is not None:
                    idx = st.session_state.edit_recipe_index
                    for col in df.columns:
                        df.at[idx, col] = fr.get(col, "")
                    st.success(f"✅ 配方 {fr['配方編號']} 已更新！")
                else:
                    if fr["配方編號"] in df["配方編號"].values:
                        st.warning("⚠️ 此配方編號已存在！")
                        st.stop()
                    else:
                        fr["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 清理 NaN
                        fr_clean = {k: (v if pd.notna(v) else "") for k, v in fr.items()}
                        df = pd.concat([df, pd.DataFrame([fr_clean])], ignore_index=True)
                        st.success(f"✅ 新增配方 {fr['配方編號']} 成功！")
            
                # 3️⃣ 清理 DataFrame 中的 NaN
                import numpy as np
                df = df.replace({np.nan: "", np.inf: "", -np.inf: ""})
            
                # 4️⃣ 儲存到 Google Sheets（使用安全函式）
                save_success = save_df_to_sheet(ws_recipe, df)
            
                if not save_success:
                    st.error("❌ Google Sheets 儲存失敗，但本地備份已建立")
                    st.info(f"📁 備份位置：{backup_file}")
                    st.stop()
            
                # 5️⃣ 儲存本地 CSV
                order_file = Path("data/df_recipe.csv")
                order_file.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(order_file, index=False, encoding="utf-8-sig")
            
                # 6️⃣ 更新 session_state
                st.session_state.df = df
                st.session_state.df_recipe = df
                st.session_state.form_recipe = {col: "" for col in columns}
                st.session_state.edit_recipe_index = None
            
                st.success("💾 資料已安全儲存！")
            
                # 7️⃣ 防止無限迴圈：使用 flag
                if "save_completed" not in st.session_state:
                    st.session_state.save_completed = True
                    st.rerun()
            
            except Exception as e:
                st.error(f"❌ 儲存過程發生錯誤：{e}")
                st.error("⚠️ 請檢查本地備份檔案")
                st.stop()
        
    # ================= 配方記錄表 =================
    st.markdown("---")
    
    st.markdown("""
    <div id="recipe-table" style="display: flex; align-items: center; gap: 10px;">
        <h2 style="font-size:22px; font-family:Arial; color:#F9DC5C;">📑配方記錄表</h2>
        <a href="#recipe-create" style="
            background-color: var(--background-color);
            color: var(--text-color);
            padding:4px 10px;
            border-radius:6px;
            text-decoration:none;
            font-size:14px;
            font-family:Arial;
        ">⬆ 回頁首</a>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("配方編號", key="search_recipe_code_bottom")
    with col2:
        st.text_input("客戶名稱或編號", key="search_customer_bottom")
    with col3:
        st.text_input("Pantone色號", key="search_pantone_bottom")
    
    # 篩選
    recipe_kw = st.session_state.get("search_recipe_code_bottom", "").strip()
    customer_kw = st.session_state.get("search_customer_bottom", "").strip()
    pantone_kw = st.session_state.get("search_pantone_bottom", "").strip()
    
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
    
    df_filtered = df[mask]    
    
    # ===== 計算分頁 =====
    total_rows = df_filtered.shape[0]
    limit = st.session_state.get("limit_per_page", 5)
    total_pages = max((total_rows - 1) // limit + 1, 1)
    
    if "page" not in st.session_state:
        st.session_state.page = 1
    if st.session_state.page > total_pages:
        st.session_state.page = total_pages
    
    # ===== 分頁索引 =====
    start_idx = (st.session_state.page - 1) * limit
    end_idx = start_idx + limit
    page_data = df_filtered.iloc[start_idx:end_idx]
    
    # ===== 顯示表格 =====
    show_cols = ["配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方", "Pantone色號"]
    existing_cols = [c for c in show_cols if c in page_data.columns]
    
    if not page_data.empty:
        st.dataframe(page_data[existing_cols].reset_index(drop=True),
                     use_container_width=True,
                     hide_index=True)
    else:
        st.info("查無符合的配方（分頁結果）")
    
    # ===== 分頁控制列 =====
    cols_page = st.columns([1, 1, 1, 2, 1])
    
    with cols_page[0]:
        if st.button("🏠首頁", key="first_page"):
            st.session_state.page = 1
            st.rerun()
    
    with cols_page[1]:
        if st.button("🔼上一頁", key="prev_page") and st.session_state.page > 1:
            st.session_state.page -= 1
            st.rerun()
    
    with cols_page[2]:
        if st.button("🔽下一頁", key="next_page") and st.session_state.page < total_pages:
            st.session_state.page += 1
            st.rerun()
    
    with cols_page[3]:
        jump_page = st.number_input(
            "",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.page,
            key="jump_page",
            label_visibility="collapsed"
        )
        if jump_page != st.session_state.page:
            st.session_state.page = jump_page
            st.rerun()
    
    with cols_page[4]:
        limit = st.selectbox(
            "",
            options=[5, 10, 20, 50, 100],
            index=[5, 10, 20, 50, 100].index(st.session_state.get("limit_per_page", 5)),
            key="limit_per_page",
            label_visibility="collapsed"
        )
    
    st.caption(f"頁碼 {st.session_state.page} / {total_pages}，總筆數 {total_rows}")
    
    st.markdown("---")
    
    # ================= 配方預覽/修改/刪除 =================
    st.markdown(
        '<h2 style="font-size:20px; font-family:Arial; color:#F9DC5C;">🛠️ 配方預覽/修改/刪除</h2>',
        unsafe_allow_html=True
    )
    
    # 配方預覽函式
    def generate_recipe_preview_text(recipe_row):
        """生成配方預覽文字"""
        html_text = ""
        html_text += f"編號：{recipe_row.get('配方編號', '')}  "
        html_text += f"顏色：{recipe_row.get('顏色', '')}  "
        html_text += f"客戶：{recipe_row.get('客戶名稱', '')}  "
        html_text += f"Pantone：{recipe_row.get('Pantone色號', '')}\n\n"
        
        # 色粉列
        for i in range(1, 9):
            pid = recipe_row.get(f"色粉編號{i}", "").strip()
            wgt = recipe_row.get(f"色粉重量{i}", "").strip()
            if pid:
                html_text += f"{pid.ljust(12)}{wgt}\n"
        
        # 合計列
        total_label = recipe_row.get("合計類別", "=")
        net_weight = recipe_row.get("淨重", "")
        if net_weight:
            html_text += "_" * 40 + "\n"
            html_text += f"{total_label.ljust(12)}{net_weight}\n"
        
        # 備註
        note = recipe_row.get("備註", "").strip()
        if note:
            html_text += f"\n備註：{note}\n"
        
        return "```\n" + html_text.strip() + "\n```"
    
    if not page_data.empty:
        default_index = page_data.index[0]
        
        selected_index = st.selectbox(
            "輸入配方",
            options=page_data.index,
            format_func=lambda i: f"{page_data.at[i, '配方編號']} | {page_data.at[i, '顏色']} | {page_data.at[i, '客戶名稱']}",
            key="select_recipe_code_page",
            index=page_data.index.get_loc(default_index) if default_index in page_data.index else 0
        )
        
        selected_code = page_data.at[selected_index, "配方編號"] if selected_index is not None else None
        
        if selected_code:
            recipe_row_preview = page_data.loc[selected_index].to_dict()
            preview_text = generate_recipe_preview_text(recipe_row_preview)
            
            # 配方預覽 + 修改 / 刪除
            cols_preview_recipe = st.columns([6, 1.2])
            with cols_preview_recipe[0]:
                with st.expander("👀 配方預覽", expanded=False):
                    st.markdown(preview_text, unsafe_allow_html=True)
            
            with cols_preview_recipe[1]:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ ", key=f"edit_recipe_btn_{selected_index}"):
                        st.session_state.show_edit_recipe_panel = True
                        st.session_state.editing_recipe_index = selected_index
                        st.rerun()
                with col_btn2:
                    if st.button("🗑️ ", key=f"delete_recipe_btn_{selected_index}"):
                        st.session_state.show_delete_recipe_confirm = True
                        st.session_state.delete_recipe_index = selected_index
                        st.rerun()
            
            # ================= 確認刪除 =================
            if st.session_state.get("show_delete_recipe_confirm", False):
                idx = st.session_state["delete_recipe_index"]
                recipe_label = df.at[idx, "配方編號"]
                st.warning(f"⚠️ 確定要刪除配方？\n\n👉 {recipe_label}")

                c1, c2 = st.columns(2)
                if c1.button("✅ 是，刪除", key="confirm_delete_recipe_yes_2"):
                    df.drop(idx, inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    ws_recipe.clear()
                    ws_recipe.update([df.columns.tolist()] + df.values.tolist())
                    st.success(f"✅ 已刪除 {recipe_label}")
                    st.session_state.show_delete_recipe_confirm = False
                    st.session_state.df = df
                    st.session_state.df_recipe = df
                    st.rerun()

                if c2.button("取消", key="confirm_delete_recipe_no_2"):
                    st.session_state.show_delete_recipe_confirm = False
                    st.rerun()
            
            # ================= 修改配方面板 =================
            if st.session_state.get("show_edit_recipe_panel") and st.session_state.get("editing_recipe_index") is not None:
                st.markdown("---")
                idx = st.session_state.editing_recipe_index
                st.markdown(
                    f"<p style='font-size:18px; font-weight:bold; color:#fceca6;'>✏️ 修改配方 {df.at[idx, '配方編號']}</p>",
                    unsafe_allow_html=True
                )

                fr_edit = df.loc[idx].to_dict()

                # 基本欄位
                col1, col2, col3 = st.columns(3)
                with col1:
                    fr_edit["配方編號"] = st.text_input("配方編號", value=fr_edit.get("配方編號", ""), key="edit_recipe_code")
                with col2:
                    fr_edit["顏色"] = st.text_input("顏色", value=fr_edit.get("顏色", ""), key="edit_recipe_color")
                with col3:
                    options = [""] + customer_options
                    cust_id = fr_edit.get("客戶編號", "").strip()
                    cust_name = fr_edit.get("客戶名稱", "").strip()
                    current = f"{cust_id} - {cust_name}" if cust_id else ""
                    index = options.index(current) if current in options else 0
                    selected = st.selectbox("客戶編號", options, index=index, key="edit_recipe_selected_customer")
                    
                    if " - " in selected:
                        c_no, c_name = selected.split(" - ", 1)
                        fr_edit["客戶編號"] = c_no
                        fr_edit["客戶名稱"] = c_name

                # 配方類別、狀態、原始配方、Pantone、淨重
                col4, col5, col6 = st.columns(3)
                with col4:
                    options_cat = ["原始配方", "附加配方"]
                    current = fr_edit.get("配方類別", options_cat[0])
                    fr_edit["配方類別"] = st.selectbox("配方類別", options_cat, index=options_cat.index(current), key="edit_recipe_category")
                with col5:
                    options_status = ["啟用", "停用"]
                    current = fr_edit.get("狀態", options_status[0])
                    fr_edit["狀態"] = st.selectbox("狀態", options_status, index=options_status.index(current), key="edit_recipe_status")
                with col6:
                    fr_edit["原始配方"] = st.text_input("原始配方", value=fr_edit.get("原始配方", ""), key="edit_recipe_origin")

                col7, col8, col9 = st.columns(3)
                with col7:
                    fr_edit["Pantone色號"] = st.text_input("Pantone色號", value=fr_edit.get("Pantone色號", ""), key="edit_recipe_pantone")
                with col8:
                    fr_edit["淨重"] = st.text_input("淨重", value=fr_edit.get("淨重", ""), key="edit_recipe_net_weight")
                with col9:
                    options = ["g", "kg"]
                    current = fr_edit.get("淨重單位", options[0])
                    fr_edit["淨重單位"] = st.selectbox("單位", options, index=options.index(current), key="edit_recipe_net_unit")

                # 色粉設定
                st.markdown("##### 色粉設定")
                num_rows = max(5, sum(1 for i in range(1, 9) if fr_edit.get(f"色粉編號{i}")))
                for i in range(1, num_rows + 1):
                    c1, c2 = st.columns([2.5, 2.5])
                    fr_edit[f"色粉編號{i}"] = c1.text_input("", value=fr_edit.get(f"色粉編號{i}", ""), placeholder=f"色粉{i}編號", key=f"edit_recipe_powder_code{i}")
                    fr_edit[f"色粉重量{i}"] = c2.text_input("", value=fr_edit.get(f"色粉重量{i}", ""), placeholder="重量", key=f"edit_recipe_powder_weight{i}")
                
                # 合計類別
                col1, col2 = st.columns(2)
                category_options = ["LA", "MA", "S", "CA", "T9", "料", "\u2002", "其他"]
                default = str(fr_edit.get("合計類別", "\u2002")).strip()
                if default not in category_options:
                    default = "\u2002"
                fr_edit["合計類別"] = col1.selectbox("合計類別", category_options, index=category_options.index(default), key="edit_recipe_total_category")

                # 儲存 / 返回
                cols_edit = st.columns([1, 1])
                
                with cols_edit[0]:
                    if st.button("💾 儲存修改", key="save_edit_recipe_btn"):
                        for k, v in fr_edit.items():
                            df.at[idx, k] = v

                        try:
                            ws_recipe.clear()
                            ws_recipe.update([df.columns.tolist()] + df.values.tolist())
                            st.success("✅ 配方已更新並寫入 Google Sheet")
                        except Exception as e:
                            st.error(f"❌ 儲存到 Google Sheet 失敗：{e}")
                            st.text(traceback.format_exc())

                        st.session_state.show_edit_recipe_panel = False
                        st.session_state.df = df
                        st.session_state.df_recipe = df
                        st.rerun()

                with cols_edit[1]:
                    if st.button("返回", key="return_edit_recipe_btn"):
                        st.session_state.show_edit_recipe_panel = False
                        st.rerun()
    
    # 頁面最下方手動載入按鈕
    st.markdown("---")
    if st.button("📥 重新載入配方資料"):
        st.session_state.df_recipe = load_recipe_data()
        st.success("配方資料已重新載入！")
        st.rerun()
