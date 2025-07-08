if st.button("💾 新增 / 修改色粉", key="save"):
    code = st.session_state["code_input"].strip()

    if code == "":
        st.warning("請輸入色粉編號。")
    else:
        exists = code in df["色粉編號"].astype(str).values
        if exists:
            # 進行修改
            df.loc[
                df["色粉編號"].astype(str) == code,
                ["名稱", "國際色號", "色粉類別", "規格", "產地", "備註"]
            ] = [
                st.session_state["name_input"],
                st.session_state["pantone_input"],
                st.session_state["color_type_select"],
                st.session_state["spec_select"],
                st.session_state["origin_input"],
                st.session_state["remark_input"]
            ]
            st.success(f"✅ 已更新色粉【{code}】！")
        else:
            # 檢查是否重複
            if code in df["色粉編號"].astype(str).values:
                st.warning(f"⚠️ 色粉編號【{code}】已存在，請勿重複新增。")
            else:
                new_row = {
                    "色粉編號": code,
                    "名稱": st.session_state["name_input"],
                    "國際色號": st.session_state["pantone_input"],
                    "色粉類別": st.session_state["color_type_select"],
                    "規格": st.session_state["spec_select"],
                    "產地": st.session_state["origin_input"],
                    "備註": st.session_state["remark_input"]
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                st.success(f"✅ 已新增色粉【{code}】！")

        worksheet.clear()
        worksheet.update(
            [df.columns.tolist()] +
            df.fillna("").astype(str).values.tolist()
        )

        # 清空表單
        for f in fields:
            st.session_state[f] = ""
