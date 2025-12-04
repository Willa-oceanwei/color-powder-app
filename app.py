elif menu == "配方管理":

    # ===== 縮小整個頁面最上方空白 =====
    st.markdown("""
    <style>
    div.block-container {
        padding-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    from pathlib import Path
    from datetime import datetime
    import pandas as pd
    import streamlit as st

    # ------------------- 配方資料初始化 -------------------
    # 初始化 session_state
    if "df_recipe" not in st.session_state:
        st.session_state.df_recipe = pd.DataFrame()
    if "trigger_load_recipe" not in st.session_state:
        st.session_state.trigger_load_recipe = False
    
    def load_recipe_data():
        """嘗試依序載入配方資料，來源：Google Sheet > CSV > 空 DataFrame"""
        try:
            ws_recipe = spreadsheet.worksheet("配方管理")
            df_loaded = pd.DataFrame(ws_recipe.get_all_records())
            if not df_loaded.empty:
                return df_loaded
        except Exception as e:
            st.warning(f"Google Sheet 載入失敗：{e}")
    
        # 回退 CSV
        order_file = Path("data/df_recipe.csv")
        if order_file.exists():
            try:
                df_csv = pd.read_csv(order_file)
                if not df_csv.empty:
                    return df_csv
            except Exception as e:
                st.error(f"CSV 載入失敗：{e}")
    
        # 都失敗時，回傳空 df
        return pd.DataFrame()
    
    # 統一使用 df_recipe
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

    # ✅ 如果還是空的，顯示提示
    if df_recipe.empty:
        st.error("⚠️ 配方資料尚未載入，請確認 Google Sheet 或 CSV 是否有資料")
    # 讀取表單
    try:
        df = pd.DataFrame(ws_recipe.get_all_records())
    except:
        df = pd.DataFrame(columns=columns)

    df = df.astype(str)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    import streamlit as st

    if "df" not in st.session_state:
        try:
            df = pd.DataFrame(ws_recipe.get_all_records())
        except:
            df = pd.DataFrame(columns=columns)

        df = df.astype(str)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        st.session_state.df = df# 儲存進 session_state
    
    # ✅ 後續操作都從 session_state 中抓資料

    #-------
    df = st.session_state.df
    # === 載入「色粉管理」的色粉清單，建立 existing_powders ===
    def clean_powder_id(x):
        s = str(x).replace('\u3000', '').replace(' ', '').strip().upper()
        return s
    
    # 讀取色粉管理清單
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
        
    st.markdown("""
    <style>
    .big-title {
        font-size: 24px;   /* 字體大小 */
        font-weight: bold;  /*加粗 */
        color: #F9DC5C; /* 字體顏色 */
        margin-bottom: 20px; /* 下方間距 */
    }
    </style>
    """, unsafe_allow_html=True)

    # 🎯 配方建立（加上 id 與跳轉按鈕）
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
  
    # === 欄位定義 ===
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態",
        "原始配方", "色粉類別", "計量單位", "Pantone色號",
        "比例1", "比例2", "比例3", "淨重", "淨重單位",
        *[f"色粉編號{i}" for i in range(1, 9)],
        *[f"色粉重量{i}" for i in range(1, 9)],
        "合計類別", "重要提醒", "備註", "建檔時間"
    ]

    order_file = Path("data/df_recipe.csv")

    # 載入 Google Sheets
    try:
        ws_customer = spreadsheet.worksheet("客戶名單")
        df_customers = pd.DataFrame(ws_customer.get_all_records())
        customer_options = ["{} - {}".format(row["客戶編號"], row["客戶簡稱"]) for _, row in df_customers.iterrows()]
    except:
        st.error("無法載入客戶名單")

    import gspread
    from gspread.exceptions import WorksheetNotFound, APIError
    
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
    except WorksheetNotFound:
        try:
            ws_recipe = spreadsheet.add_worksheet("配方管理", rows=500, cols=50)
        except APIError as e:
            st.error(f"❌ 無法建立工作表：{e}")
            st.stop()
            
    # 初始化 session_state
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
        "search_customer",
        "df"
    ])

    # 讀取原始資料(純字串)
    values = ws_recipe.get_all_values()
    if len(values) > 1:
        df_loaded = pd.DataFrame(values[1:], columns=values[0])
    else:
        df_loaded = pd.DataFrame(columns=columns)
    
    # 補齊缺少欄位
    for col in columns:
        if col not in df_loaded.columns:
            df_loaded[col] = ""
    
    # 清理配方編號（保持字串格式且不轉成數字）
    if "配方編號" in df_loaded.columns:
        df_loaded["配方編號"] = df_loaded["配方編號"].astype(str).map(clean_powder_id)
    
    st.session_state.df = df_loaded
    
    df = st.session_state.df
    
    # ===== 初始化欄位 =====
    import streamlit as st

    # 假設你已經有這個列表，是所有欄位名稱
    columns = [
        "配方編號", "顏色", "客戶編號", "客戶名稱", "配方類別", "狀態", "原始配方",
        "色粉類別", "計量單位", "Pantone色號", "重要提醒", "比例1", "比例2", "比例3",
        "備註", "淨重", "淨重單位", "合計類別"
    ] + [f"色粉編號{i}" for i in range(1, 9)] + [f"色粉重量{i}" for i in range(1, 9)]
    
    # 初始化 session_state
    if "form_recipe" not in st.session_state or not st.session_state.form_recipe:
        st.session_state.form_recipe = {col: "" for col in columns}
        st.session_state.form_recipe["配方類別"] = "原始配方"
        st.session_state.form_recipe["狀態"] = "啟用"
        st.session_state.form_recipe["色粉類別"] = "配方"
        st.session_state.form_recipe["計量單位"] = "包"
        st.session_state.form_recipe["淨重單位"] = "g"
        st.session_state.form_recipe["合計類別"] = "無"
    if "num_powder_rows" not in st.session_state:
        st.session_state.num_powder_rows = 5
    
    fr = st.session_state.form_recipe
        
    with st.form("recipe_form"):
        # 基本欄位
        col1, col2, col3 = st.columns(3)
        with col1:
            fr["配方編號"] = st.text_input("配方編號", value=fr.get("配方編號", ""), key="form_recipe_配方編號")
        with col2:
            fr["顏色"] = st.text_input("顏色", value=fr.get("顏色", ""), key="form_recipe_顏色")
        with col3:
            options = [""] + customer_options  # 例如 ["001 - 客戶A", "002 - 客戶B"]

            # 組合成目前的顯示值
            current = f"{fr.get('客戶編號','')} - {fr.get('客戶名稱','')}" if fr.get("客戶編號") else ""
            index = options.index(current) if current in options else 0

            selected = st.selectbox(
                "客戶編號",
                options,
                index=index,
                key="form_recipe_selected_customer"
            )

            # 只有在選了有效選項時才更新
            if selected and " - " in selected:
                c_no, c_name = selected.split(" - ", 1)
                fr["客戶編號"] = c_no.strip()
                fr["客戶名稱"] = c_name.strip()
   
        # 配方類別、狀態、原始配方
        col4, col5, col6 = st.columns(3)
        with col4:
            options = ["原始配方", "附加配方"]
            current = fr.get("配方類別", options[0])
            if current not in options:
                current = options[0]
            fr["配方類別"] = st.selectbox("配方類別", options, index=options.index(current), key="form_recipe_配方類別")
        with col5:
            options = ["啟用", "停用"]
            current = fr.get("狀態", options[0])
            if current not in options:
                current = options[0]
            fr["狀態"] = st.selectbox("狀態", options, index=options.index(current), key="form_recipe_狀態")
        with col6:
            fr["原始配方"] = st.text_input("原始配方", value=fr.get("原始配方", ""), key="form_recipe_原始配方")
    
        # 色粉類別、計量單位、Pantone 色號
        col7, col8, col9 = st.columns(3)
        with col7:
            options = ["配方", "色母", "色粉", "添加劑", "其他"]
            current = fr.get("色粉類別", options[0])
            if current not in options:
                current = options[0]
            fr["色粉類別"] = st.selectbox("色粉類別", options, index=options.index(current), key="form_recipe_色粉類別")
        with col8:
            options = ["包", "桶", "kg", "其他"]
            current = fr.get("計量單位", options[0])
            if current not in options:
                current = options[0]
            fr["計量單位"] = st.selectbox("計量單位", options, index=options.index(current), key="f
