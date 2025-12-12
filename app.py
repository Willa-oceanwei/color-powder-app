with tab2:
    if df.empty:
        st.info("目前無資料")
        df_filtered = pd.DataFrame()  # 空 DataFrame
    else:
        # ===== 搜尋欄位 =====
        col1, col2, col3 = st.columns(3)
        with col1:
            search_recipe = st.text_input("配方編號", key="search_recipe_tab2")
        with col2:
            search_customer = st.text_input("客戶名稱或編號", key="search_customer_tab2")
        with col3:
            search_pantone = st.text_input("Pantone色號", key="search_pantone_tab2")

        recipe_kw = search_recipe.strip()
        customer_kw = search_customer.strip()
        pantone_kw = search_pantone.strip()

        # ===== 判斷是否有輸入搜尋條件 =====
        if not (recipe_kw or customer_kw or pantone_kw):
            st.info("請輸入搜尋條件開始查詢。")
            df_filtered = pd.DataFrame()  # 空 DataFrame，不顯示表格
        else:
            # ===== 篩選資料 =====
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

            if not df_filtered.empty:
                # 顯示表格、詳細資訊、分頁
                st.dataframe(df_filtered)  # 範例
            else:
                # 只有有條件但結果為空才顯示
                st.info("查無符合的配方（分頁結果）")
