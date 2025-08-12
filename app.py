elif menu == "生產單管理":
    st.markdown("""
    <style>
    .big-title {
        font-size: 35px;
        font-weight: bold;
        color: #ff3366;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="big-title">🚀生產單建立</div>', unsafe_allow_html=True)

    from pathlib import Path
    from datetime import datetime
    import pandas as pd

    # 建立資料夾（若尚未存在）
    Path("data").mkdir(parents=True, exist_ok=True)

    order_file = Path("data/df_order.csv")

    # 清理函式：去除空白、全形空白，並保持原輸入，不補零
    def clean_powder_id(x):
        if pd.isna(x):
            return ""
        return str(x).strip().replace('\u3000', '').replace(' ', '').upper()

    # 先嘗試取得 Google Sheet 兩個工作表 ws_recipe、ws_order
    try:
        ws_recipe = spreadsheet.worksheet("配方管理")
        ws_order = spreadsheet.worksheet("生產單")
    except Exception as e:
        st.error(f"❌ 無法載入工作表：{e}")
        st.stop()

    # 載入配方管理表
    try:
        records = ws_recipe.get_all_records()
        df_recipe = pd.DataFrame(records)
        df_recipe.columns = df_recipe.columns.str.strip()
        df_recipe.fillna("", inplace=True)
        if "配方編號" in df_recipe.columns:
            df_recipe["配方編號"] = df_recipe["配方編號"].astype(str).map(clean_powder_id)
        if "原始配方" in df_recipe.columns:
            df_recipe["原始配方"] = df_recipe["原始配方"].astype(str).map(clean_powder_id)
        st.session_state.df_recipe = df_recipe
    except Exception as e:
        st.error(f"❌ 讀取『配方管理』工作表失敗：{e}")
        st.stop()

    # 載入生產單表
    try:
        existing_values = ws_order.get_all_values()
        if existing_values:
            df_order = pd.DataFrame(existing_values[1:], columns=existing_values[0]).astype(str)
        else:
            # 空資料，先寫入標題列
            header = [
                "生產單號", "生產日期", "配方編號", "顏色", "客戶名稱", "建立時間",
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
        # 無法連線時讀本地 CSV
        if order_file.exists():
            st.warning("⚠️ 無法連線 Google Sheets，改用本地 CSV")
            df_order = pd.read_csv(order_file, dtype=str).fillna("")
            st.session_state.df_order = df_order
        else:
            st.error(f"❌ 無法讀取生產單資料：{e}")
            st.stop()

    df_recipe = st.session_state.df_recipe
    df_order = st.session_state.df_order.copy()

    # 轉換時間欄位與配方編號欄清理
    if "建立時間" in df_order.columns:
        df_order["建立時間"] = pd.to_datetime(df_order["建立時間"], errors="coerce")
    if "配方編號" in df_order.columns:
        df_order["配方編號"] = df_order["配方編號"].map(clean_powder_id)

    # 初始化 session_state 用的 key
    for key in ["order_page", "editing_order", "show_edit_panel", "new_order", "show_confirm_panel"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "order_page" else 1

    def format_option(r):
        label = f"{r['配方編號']} | {r['顏色']} | {r['客戶名稱']}"
        if r.get("配方類別", "") == "附加配方":
            label += "（附加配方）"
        return label

    st.subheader("🔎 配方搜尋與新增生產單")

    with st.form("search_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            search_text = st.text_input("配方編號或客戶名稱", value="", key="search_text")
        with col2:
            exact = st.checkbox("精確搜尋", key="exact_search")
        with col3:
            add_btn = st.form_submit_button("➕ 新增")

        if search_text:
            search_text = clean_powder_id(search_text)
            df_recipe["配方編號"] = df_recipe["配方編號"].astype(str)
            df_recipe["客戶名稱"] = df_recipe["客戶名稱"].astype(str)

            if exact:
                filtered = df_recipe[
                    (df_recipe["配方編號"] == search_text) |
                    (df_recipe["客戶名稱"] == search_text)
                ]
            else:
                filtered = df_recipe[
                    df_recipe["配方編號"].str.contains(search_text, case=False, na=False) |
                    df_recipe["客戶名稱"].str.contains(search_text, case=False, na=False)
                ]
        else:
            filtered = df_recipe.copy()

        filtered = filtered.copy()

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
            selected_row = option_map[selected_label]
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
