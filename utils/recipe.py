
# utils/recipe.py
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import traceback
from .common import get_spreadsheet, save_df_to_sheet, clean_powder_id, fix_leading_zero

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
    
    # 初始化 session_state
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = pd.DataFrame()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    def load_recipe_data():
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
    
    # 預期欄位
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "建檔時間"
    ]
    
    # 初始化 session_state 需要的變數
    def init_states(keys):
        for k in keys:
            if k not in st.session_state:
                st.session_state[k] = None
    
    init_states([
        "form_recipe",
        "edit_recipe_index",
        "delete_recipe_index",
        "show_delete_recipe_confirm",
        "search_recipe_code",
        "search_pantone",
        "search_customer"
    ])
    
    # 初始 form_recipe
    if st.session_state.form_recipe is None:
        st.session_state.form_recipe = {col: "" for col in columns}
        st.session_state.form_recipe["配方類別"] = "原始配方"
        st.session_state.form_recipe["狀態"] = "啟用"
        st.session_state.form_recipe["色粉類別"] = "配方"
        st.session_state.form_recipe["計量單位"] = "包"
        st.session_state.form_recipe["淨重單位"] = "g"
        st.session_state.form_recipe["合計類別"] = "無"
    if "num_powder_rows" not in st.session_state:
        st.session_state.num_powder_rows = 5
    
    # 如果還是空的，顯示提示
    if df_recipe.empty:
        st.error("⚠️ 配方資料尚未載入，請確認 Google Sheet 或 CSV 是否有資料")
    
    # 讀取表單
    try:
        spreadsheet = get_spreadsheet()
        ws_recipe = spreadsheet.worksheet("配方管理")
    except:
        st.error("❌ 無法連線 Google Sheet")
        return
    
    try:
        df = pd.DataFrame(ws_recipe.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)
    
    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    
    if "df" not in st.session_state:
        st.session_state.df = df
    
    df = st.session_state.df
    
    # 載入「色粉管理」的色粉清單，建立 existing_powders
    try:
        ws_powder = spreadsheet.worksheet("色粉管理")
        df_powders = pd.DataFrame(ws_powder.get_all_records())
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
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customers = pd.DataFrame(ws_customer.get_all_records())
        customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]
    except:
        st.error("無法載入客戶名單")
        customer_options = []
    
    # 🎯 配方建立
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
        col7, col8, col9, col10, col11 = st.columns(5)
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
        with col10:
            fr["淨重"] = st.text_input("淨重", value=fr.get("淨重", ""), key="form_recipe_淨重")
        with col11:
            options = ["g", "kg"]
            current = fr.get("淨重單位", options[0])
            fr["淨重單位"] = st.selectbox("單位", options, index=options.index(current), key="form_recipe_淨重單位")
        
        # 重要提醒、比例1-3、備註
        fr["重要提醒"] = st.text_input("重要提醒", value=fr.get("重要提醒", ""), key="form_recipe_重要提醒")
        colr1, col_colon, colr2, colr3, col_unit = st.columns([2, 0.5, 2, 2, 1])
        
        with colr1:
            fr["比例1"] = st.text_input(
                "", value=fr.get("比例1", ""), key="ratio1", label_visibility="collapsed"
            )
        
        with col_colon:
            st.markdown(
                """
                <div style="display:flex; justify-content:center; align-items:center;
                            font-size:18px; font-weight:bold; height:36px;">
                    :
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with colr2:
            fr["比例2"] = st.text_input(
                "", value=fr.get("比例2", ""), key="ratio2", label_visibility="collapsed"
            )
        
        with colr3:
            fr["比例3"] = st.text_input(
                "", value=fr.get("比例3", ""), key="ratio3", label_visibility="collapsed"
            )
        
        with col_unit:
            st.markdown(
                """
                <div style="display:flex; justify-content:flex-start; align-items:center;
                            font-size:16px; height:36px;">
                    g/kg
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # 備註
        fr["備註"] = st.text_area("備註", value=fr.get("備註", ""), key="form_recipe_備註")
        
        # CSS：縮小輸入框高度及上下間距
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
        
        # 控制避免重複 rerun 的 flag
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
    
    # === 表單提交後的處理邏輯（要在 form 區塊外） ===    
    existing_powders_str = {str(x).strip().upper() for x in existing_powders if str(x).strip() != ""}
    
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
            if st.session_state.edit_recipe_index is not None:
                df.iloc[st.session_state.edit_recipe_index] = pd.Series(fr, index=df.columns)
                st.success(f"✅ 配方 {fr['配方編號']} 已更新！")
            else:
                if fr["配方編號"] in df["配方編號"].values:
                    st.warning("⚠️ 此配方編號已存在！")
                else:
                    fr["建檔時間"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df = pd.concat([df, pd.DataFrame([fr])], ignore_index=True)
                    st.success(f"✅ 新增配方 {fr['配方編號']} 成功！")
            
            try:
                ws_recipe.clear()
                ws_recipe.update([df.columns.tolist()] + df.values.tolist())
                order_file = Path("data/df_recipe.csv")
                order_file.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(order_file, index=False, encoding="utf-8-sig")
            except Exception as e:
                st.error(f"❌ 儲存失敗：{e}")
                st.stop()
            
            st.session_state.df = df
            st.session_state.form_recipe = {col: "" for col in columns}
            st.session_state.edit_recipe_index = None
            st.rerun()
    
    # 刪除確認
    if st.session_state.show_delete_recipe_confirm:
        target_row = df.iloc[st.session_state.delete_recipe_index]
        target_text = f'{target_row["配方編號"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        
        c1, c2 = st.columns(2)
        if c1.button("是", key="confirm_delete_recipe_yes"):
            df.drop(index=st.session_state.delete_recipe_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(ws_recipe, df)
            st.success("✅ 刪除成功！")
            st.session_state.show_delete_recipe_confirm = False
            st.rerun()
        
        if c2.button("否", key="confirm_delete_recipe_no"):
            st.session_state.show_delete_recipe_confirm = False
            st.rerun()
    
    # --------- 客戶選單 ---------
    # 初始化布林遮罩（全部為 True）
    mask = pd.Series(True, index=df.index)
    
    # 初始化搜尋關鍵字，避免KeyError或型態錯誤
    for key in ["recipe_kw", "customer_kw", "pantone_kw"]:
        if key not in st.session_state:
            st.session_state[key] = ""
    
    recipe_kw = st.session_state.get("recipe_kw", "")
    if not isinstance(recipe_kw, str):
        recipe_kw = ""
    recipe_kw = recipe_kw.strip()
    
    customer_kw = st.session_state.get("customer_kw", "")
    if not isinstance(customer_kw, str):
        customer_kw = ""
    customer_kw = customer_kw.strip()
    
    pantone_kw = st.session_state.get("pantone_kw", "")
    if not isinstance(pantone_kw, str):
        pantone_kw = ""
    pantone_kw = pantone_kw.strip()
    
    # 依條件逐項過濾（多條件 AND）
    if recipe_kw:
        mask &= df["配方編號"].astype(str).str.contains(recipe_kw, case=False, na=False)
    
    if customer_kw:
        mask &= (
            df["客戶名稱"].astype(str).str.contains(customer_kw, case=False, na=False) |
            df["客戶編號"].astype(str).str.contains(customer_kw, case=False, na=False)
        )
    
    if pantone_kw:
        mask &= df["Pantone色號"].astype(str).str.contains(pantone_kw, case=False, na=False)
    
    # 套用遮罩，完成篩選
    df_filtered = df[mask]
    
    # 若有輸入上方欄位且搜尋結果為空，顯示提示
    top_has_input = any([
        st.session_state.get("search_recipe_code_top"),
        st.session_state.get("search_customer_top"),
        st.session_state.get("search_pantone_top")
    ])
    if top_has_input and df_filtered.empty:
        st.info("● 查無符合條件的配方。")
    
    # 🔒 配方記錄表（加上跳轉回去的按鈕）
    st.markdown("---")
    
    st.markdown("""
    <div id="recipe-table" style="display: flex; align-items: center; gap: 10px;">
        <h2 style="font-size:22px; font-family:Arial; color:#F9DC5C;">🔒配方記錄表</h2>
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
        search_recipe_bottom = st.text_input("配方編號", key="search_recipe_code_bottom")
    with col2:
        search_customer_bottom = st.text_input("客戶名稱或編號", key="search_customer_bottom")
    with col3:
        search_pantone_bottom = st.text_input("Pantone色號", key="search_pantone_bottom")
    
    # 先初始化 top 欄位變數
    recipe_kw = st.session_state.get("search_recipe_code_bottom", "").strip()
    customer_kw = st.session_state.get("search_customer_bottom", "").strip()
    pantone_kw = st.session_state.get("search_pantone_bottom", "").strip()
    
    # 篩選
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
    
    # ===== 分頁控制列（按鈕 + 輸入跳頁 + 每頁筆數） =====
    cols_page = st.columns([1, 1, 1, 2, 1])
    
    with cols_page[0]:
        if st.button("🏠 首頁", key="first_page"):
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
    
    # 配方預覽/修改/刪除（略，太長，可參考原本程式碼）
    # 這裡僅示範框架，完整版需要包含配方選擇、預覽、編輯等功能
    
    st.markdown(
        '<h2 style="font-size:20px; font-family:Arial; color:#F9DC5C;">🛠️ 配方預覽/修改/刪除</h2>',
        unsafe_allow_html=True
    )
    
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
            
            # 配方預覽 + 修改 / 刪除
            cols_preview_recipe = st.columns([6, 1.2])
            with cols_preview_recipe[0]:
                with st.expander("👀 配方預覽", expanded=False):
                    st.write("**基本資訊**")
                    st.write(f"配方編號：{recipe_row_preview.get('配方編號', '')}")
                    st.write(f"顏色：{recipe_row_preview.get('顏色', '')}")
                    st.write(f"客戶：{recipe_row_preview.get('客戶名稱', '')}")
                    st.write(f"Pantone：{recipe_row_preview.get('Pantone色號', '')}")
                    st.write(f"狀態：{recipe_row_preview.get('狀態', '')}")
                    
                    st.write("**色粉組成**")
                    for i in range(1, 9):
                        pid = recipe_row_preview.get(f"色粉編號{i}", "")
                        wgt = recipe_row_preview.get(f"色粉重量{i}", "")
                        if pid:
                            st.write(f"{pid}: {wgt}")
            
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
    
    # 頁面最下方手動載入按鈕
    st.markdown("---")
    if st.button("🔥 重新載入配方資料"):
        st.session_state.df_recipe = load_recipe_data()
        st.success("配方資料已重新載入！")
        st.rerun()
