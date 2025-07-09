import streamlit as st
import pandas as pd

# 預設初始資料 (demo)
dummy_data = [
    {
        "色粉編號": "C001",
        "國際色號": "INT001",
        "名稱": "紅色粉",
        "色粉類別": "色粉",
        "包裝": "袋",
        "備註": "暫無",
    },
    {
        "色粉編號": "C002",
        "國際色號": "INT002",
        "名稱": "藍色粉",
        "色粉類別": "色母",
        "包裝": "箱",
        "備註": "特殊用途",
    },
]

# Streamlit 預設頁面設定
st.set_page_config(
    page_title="色粉管理系統",
    layout="wide",
)

# Title
st.markdown("🎨 **色粉管理系統**")

# 功能模組選單
module = st.radio(
    "請選擇功能模組",
    ["色粉管理", "配方管理"],
    horizontal=True,
)

# === 色粉管理功能 ===
if module == "色粉管理":

    st.subheader("➕ 新增 / 修改 色粉")

    # 建立表單
    with st.form("form_color_powder"):
        col1, col2 = st.columns(2)

        with col1:
            color_id = st.text_input("色粉編號")
            intl_color = st.text_input("國際色號")
            name = st.text_input("名稱")

        with col2:
            powder_type = st.selectbox(
                "色粉類別",
                ["色粉", "色母", "添加劑"],
            )
            package = st.selectbox(
                "包裝",
                ["袋", "箱", "kg"],
            )
            note = st.text_input("備註")

        # 表單按鈕
        submitted = st.form_submit_button("✅ 儲存")
        clear_btn = st.form_submit_button("🧹 清空畫面")

        if submitted:
            st.success("✅ 已暫存，不會實際儲存到資料庫 (範例版)")
        elif clear_btn:
            st.experimental_rerun()

    st.divider()

    st.subheader("📋 色粉清單")

    # 模擬 DataFrame
    df = pd.DataFrame(dummy_data)

    for i, row in df.iterrows():
        # 單行顯示
        st.markdown(
            f"""
            **色粉編號**：{row["色粉編號"]}  
            **國際色號**：{row["國際色號"]}  
            **名稱**：{row["名稱"]}  
            **色粉類別**：{row["色粉類別"]}  
            **包裝**：{row["包裝"]}  
            **備註**：{row["備註"]}
            """,
            unsafe_allow_html=True,
        )

        # 修改、刪除按鈕同一行
        col_edit, col_delete = st.columns([1, 1])
        with col_edit:
            if st.button(f"✏️ 修改 {i}"):
                st.info(f"點選修改：{row['色粉編號']}（此版僅顯示訊息）")
        with col_delete:
            if st.button(f"🗑️ 刪除 {i}"):
                st.warning(f"點選刪除：{row['色粉編號']}（此版僅顯示訊息）")

        st.divider()

# === 配方管理功能 ===
elif module == "配方管理":
    st.subheader("⚙️ 配方管理模組")
    st.info("此範例尚未實作配方管理功能。")
