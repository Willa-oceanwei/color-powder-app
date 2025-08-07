# ===== 按鈕區 =====
col1, col2 = st.columns([1, 1])
with col1:
    clear_fields = st.button("🔄 清空欄位", key="btn_clear_recipe")
with col2:
    submit_recipe = st.button("✅ 儲存配方", key="btn_submit_recipe")

# ===== 按鈕事件處理 =====
if clear_fields:
    # 清空 fr 內所有欄位值
    for key in list(fr.keys()):
        fr[key] = ""

    # 清空 session_state 中對應的 key
    for key in list(st.session_state.keys()):
        if key.startswith("form_recipe_") or key.startswith("ratio") or key.startswith("色粉重量") or key.startswith("色粉編號"):
            try:
                st.session_state[key] = ""
            except Exception as e:
                print(f"⚠️ 無法清空 {key}: {e}")

    # 清空客戶選單 key（若存在）
    st.session_state.pop("form_recipe_selected_customer", None)

    # 色粉列數重設
    st.session_state["num_powder_rows"] = 1

    # 重新整理頁面（避免殘留畫面）
    st.rerun()
