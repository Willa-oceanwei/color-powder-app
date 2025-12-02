# pages/color_powder.py
import streamlit as st
import pandas as pd
from utils import save_df_to_sheet

def render(spreadsheet):
    menu = "色粉管理"
    st.markdown("""<style>div.block-container { padding-top: 5px; }</style>""", unsafe_allow_html=True)
    try:
        worksheet = spreadsheet.worksheet("色粉管理")
    except Exception:
        worksheet = spreadsheet.add_worksheet("色粉管理", rows=200, cols=10)
    required_columns = ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]
    # init session keys
    if "form_color" not in st.session_state or not isinstance(st.session_state.form_color, dict):
        st.session_state.form_color = {c:"" for c in required_columns}
    st.session_state.setdefault("edit_color_index", None)
    st.session_state.setdefault("delete_color_index", None)
    st.session_state.setdefault("show_delete_color_confirm", False)
    st.session_state.setdefault("search_keyword", "")

    try:
        df = pd.DataFrame(worksheet.get_all_records()).astype(str)
    except Exception:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🪅新增色粉</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_color["色粉編號"] = st.text_input("色粉編號", st.session_state.form_color["色粉編號"])
        st.session_state.form_color["國際色號"] = st.text_input("國際色號", st.session_state.form_color["國際色號"])
        st.session_state.form_color["名稱"] = st.text_input("名稱", st.session_state.form_color["名稱"])
    with col2:
        st.session_state.form_color["色粉類別"] = st.selectbox("色粉類別", ["色粉","色母","添加劑"], index=0, key="cp_type")
        st.session_state.form_color["包裝"] = st.selectbox("包裝", ["袋","箱","kg"], index=0, key="cp_pack")
        st.session_state.form_color["備註"] = st.text_input("備註", st.session_state.form_color["備註"])

    if st.button("💾 儲存"):
        new_data = st.session_state.form_color.copy()
        if new_data["色粉編號"].strip() == "":
            st.warning("請輸入色粉編號")
        else:
            if st.session_state.edit_color_index is not None:
                idx = st.session_state.edit_color_index
                for col in df.columns:
                    df.at[idx, col] = new_data.get(col, "")
                st.success("色粉已更新")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("此色粉編號已存在")
                else:
                    df = pd.concat([df, pd.DataFrame([new_data], columns=df.columns)], ignore_index=True)
                    st.success("新增成功")
            save_df_to_sheet(worksheet, df)
            st.session_state.form_color = {c:"" for c in required_columns}
            st.session_state.edit_color_index = None
            st.experimental_rerun()

    st.markdown("---")
    st.markdown('<h2 style="font-size:22px; font-family:Arial; color:#dbd818;">🛠️ 色粉修改 / 刪除</h2>', unsafe_allow_html=True)
    keyword = st.text_input("輸入色粉編號或名稱搜尋", value=st.session_state.get("search_keyword",""))
    st.session_state.search_keyword = keyword.strip()
    df_filtered = pd.DataFrame()
    if keyword:
        df_filtered = df[
            df["色粉編號"].str.contains(keyword, case=False, na=False) |
            df["名稱"].str.contains(keyword, case=False, na=False) |
            df["國際色號"].str.contains(keyword, case=False, na=False)
        ]
    if df_filtered.empty and keyword:
        st.warning("查無符合的資料")
    else:
        if not df_filtered.empty:
            st.dataframe(df_filtered[["色粉編號","國際色號","名稱","色粉類別","包裝"]], use_container_width=True, hide_index=True)
            for i, row in df_filtered.iterrows():
                c1, c2, c3 = st.columns([3,1,1])
                with c1:
                    st.markdown(f"🔸 {row['色粉編號']}　{row['名稱']}")
                with c2:
                    if st.button("✏️ 改", key=f"edit_color_{i}"):
                        st.session_state.edit_color_index = i
                        st.session_state.form_color = row.to_dict()
                        st.experimental_rerun()
                with c3:
                    if st.button("🗑️ 刪", key=f"delete_color_{i}"):
                        st.session_state.delete_color_index = i
                        st.session_state.show_delete_color_confirm = True
                        st.experimental_rerun()
    if st.session_state.get("show_delete_color_confirm", False):
        target_row = df.iloc[st.session_state.delete_color_index]
        target_text = f'{target_row["色粉編號"]} {target_row["名稱"]}'
        st.warning(f"⚠️ 確定要刪除 {target_text}？")
        c1, c2 = st.columns(2)
        if c1.button("刪除"):
            df.drop(index=st.session_state.delete_color_index, inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_df_to_sheet(worksheet, df)
            st.success("刪除成功")
            st.session_state.show_delete_color_confirm = False
            st.experimental_rerun()
        if c2.button("取消"):
            st.session_state.show_delete_color_confirm = False
            st.experimental_rerun()

