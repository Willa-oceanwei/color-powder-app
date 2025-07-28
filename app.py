# ---------- 新增後欄位填寫區塊 ----------
# ===== 主流程頁面切換 =====
page = st.session_state.get("page", "新增生產單")
if page == "新增生產單":
    order = st.session_state.get("new_order", {})
    if st.session_state.get("show_confirm_panel") and order:
        st.markdown("---")
        st.subheader("新增生產單詳情填寫")

        recipe_id = order.get("配方編號", "")
        recipe_row = st.session_state.get("recipe_row_cache")
        if recipe_row is None or recipe_row.get("配方編號", None) != recipe_id:
            matched = df_recipe[df_recipe["配方編號"] == recipe_id]
            if matched.empty:
                st.error(f"找不到配方編號：{recipe_id}")
                st.stop()
            recipe_row = matched.iloc[0]
            # ✅ 清除 recipe_row 的欄位名稱空白
            recipe_row.index = recipe_row.index.str.strip()

            st.write("recipe_row 欄位列表：", list(recipe_row.index))
            st.write("✅ recipe_row keys:", recipe_row.index.tolist())
            
            st.session_state["recipe_row_cache"] = recipe_row

        unit = recipe_row.get("計量單位", "kg")
        print_html = generate_print_page_content(order, recipe_row)

        # 不可編輯欄位
        c1, c2, c3, c4 = st.columns(4)
        c1.text_input("生產單號", value=order.get("生產單號", ""), disabled=True)
        c2.text_input("配方編號", value=order.get("配方編號", ""), disabled=True)
        c3.text_input("客戶編號", value=recipe_row.get("客戶編號", ""), disabled=True)
        c4.text_input("客戶名稱", value=order.get("客戶名稱", ""), disabled=True)

        with st.form("order_detail_form"):
            c5, c6, c7, c8 = st.columns(4)
            c5.text_input("計量單位", value=unit, disabled=True)
            color = c6.text_input("顏色", value=order.get("顏色", ""), key="color")
            pantone = c7.text_input("Pantone 色號", value=order.get("Pantone 色號", recipe_row.get("Pantone色號", "")), key="pantone")
            raw_material = c8.text_input("原料", value=order.get("原料", ""), key="raw_material")

            st.markdown("**包裝重量與份數**")
            w_cols = st.columns(4)
            c_cols = st.columns(4)

            weights = []
            counts = []
            for i in range(1, 5):
                w = w_cols[i - 1].text_input(f"包裝重量{i}", value=order.get(f"包裝重量{i}", ""), key=f"weight{i}")
                c = c_cols[i - 1].text_input(f"包裝份數{i}", value=order.get(f"包裝份數{i}", ""), key=f"count{i}")
                weights.append(w)
                counts.append(c)

            remark_default = order.get("備註", "")  # ✅ 直接從 order 拿
            remark = st.text_area("備註", value=remark_default, key="remark")
            
            # 🎨 色粉配方顯示 (鎖定)
            st.markdown("### 🎨 色粉配方")
            colorant_ids = [recipe_row.get(f"色粉編號{i+1}", "") for i in range(8)]
            colorant_weights = []
            for i in range(8):
                val = recipe_row.get(f"色粉重量{i+1}", "0")
                try:
                    val_float = float(val)
                except:
                    val_float = 0.0
                colorant_weights.append(val_float)

            df_colorants = pd.DataFrame({
                "色粉編號": colorant_ids,
                "用量 (g)": colorant_weights
            })
            
            try:
                total_category = order.get("色粉合計類別", "") or recipe_row.get("合計類別", "")
                st.markdown(f"**合計類別：{total_category}**")
            except:
                total_quantity = 0.0

            try:
                net_weight = float(recipe_row.get("淨重", 0))
            except:
                net_weight = 0.0

            st.dataframe(df_colorants, use_container_width=True)
            
            col1, col2 = st.columns(2)
            # 🔄 顯示合計類別與淨重（合併版）
            col1, col2 = st.columns(2)
            
            with col1:
                # ✅ 顯示合計類別（優先取 order，其次 recipe_row）
                total_category = order.get("色粉合計類別") or recipe_row.get("合計類別", "")
                total_category = str(total_category).strip()
                st.markdown(f"**合計類別：{total_category}**")
            
            with col2:
                st.markdown(f"**淨重：** {net_weight} g")

            # ✅ 加入表單送出按鈕
            submitted = st.form_submit_button("💾 儲存生產單")

        # ✅ 表單送出後處理邏輯（寫入資料）
        if submitted:
            # 更新基本欄位
            order["顏色"] = st.session_state.color
            order["Pantone 色號"] = st.session_state.pantone
            order["計量單位"] = unit
            order["建立時間"] = "'" + (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
            order["原料"] = st.session_state.raw_material
            order["備註"] = st.session_state.remark
        
            for i in range(1, 5):
                order[f"包裝重量{i}"] = st.session_state.get(f"weight{i}", "").strip()
                order[f"包裝份數{i}"] = st.session_state.get(f"count{i}", "").strip()
        
            # ✅ 取得色粉編號（這段你可能也有）
            for i in range(1, 9):
                key = f"色粉編號{i}"
                val = recipe_row.get(key, "0")
                try:
                    val_float = float(val)
                except:
                    val_float = 0.0
                order[key] = f"{val_float:.2f}"
        
            # ✅ 新的色粉合計邏輯
            try:
                net_weight = float(recipe_row.get("淨重", 0))
            except:
                net_weight = 0.0
        
            color_weight_list = []
            total_category = str(recipe_row.get("合計類別", "")).strip()
        
            for i in range(1, 5):
                try:
                    w_str = st.session_state.get(f"weight{i}", "").strip()
                    weight = float(w_str) if w_str else 0.0
                    result = net_weight * weight
                    if weight > 0:
                        color_weight_list.append({
                            "項次": i,
                            "重量": weight,
                            "結果": result
                        })
                except:
                    continue
        
            order["色粉合計清單"] = color_weight_list
            order["色粉合計類別"] = total_category
        
            # ➕ 寫入 Google Sheets、CSV 等流程
            header = [col for col in df_order.columns if col and str(col).strip() != ""]
            row_data = [str(order.get(col, "")).strip() if order.get(col) is not None else "" for col in header]
        
            try:
                ws_order.append_row(row_data)
        
                import os
                os.makedirs(os.path.dirname("data/order.csv"), exist_ok=True)
                df_new = pd.DataFrame([order], columns=df_order.columns)
                df_order = pd.concat([df_order, df_new], ignore_index=True)
                df_order.to_csv("data/order.csv", index=False, encoding="utf-8-sig")
                st.session_state.df_order = df_order
                st.session_state.new_order_saved = True
                st.success(f"✅ 生產單 {order['生產單號']} 已存！")
            except Exception as e:
                st.error(f"❌ 寫入失敗：{e}")

        # 📥 下載列印 HTML
        st.download_button(
            label="📥 下載 A5 HTML",
            data=print_html.encode("utf-8"),
            file_name=f"{order['生產單號']}_列印.html",
            mime="text/html"
        )

        # 🔘 其他控制按鈕（除了 btn1 儲存按鈕，其他保留）
        btn1, btn2, = st.columns(2)
        with btn1:
            if st.session_state.get("new_order_saved"):
                st.warning("⚠️ 生產單已存")

        with btn2:
            if st.button("🔙 返回", key="back_button"):
                st.session_state.new_order = None
                st.session_state.show_confirm_panel = False
                st.session_state.new_order_saved = False
                st.rerun()

