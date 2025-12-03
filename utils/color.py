import streamlit as st
import pandas as pd
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

from utils.common import (
    load_csv, save_csv, SHEET_COLOR_NAME, get_gsheet,
    show_success, show_error
)

# ========== 主功能：色粉管理 ==========
def render_color_page():
    st.title("🎨 色粉管理")

    # ---------- 讀取資料 ----------
    df = load_color_data()

    # 若資料不存在，顯示提示
    if df is None or df.empty:
        st.warning("目前尚無任何色粉資料。")
        if st.button("➕ 新增第一筆色粉資料"):
            st.session_state["color_edit_mode"] = "new"
        return

    # ---------- 搜尋 & 篩選 ----------
    search_keyword = st.text_input("🔍 搜尋色粉名稱 / 國際色號 / 類別", "")
    if search_keyword:
        df = df[df.apply(lambda row: row.astype(str).str.contains(search_keyword, case=False).any(), axis=1)]

    # ---------- 顯示色粉資料表 ----------
    st.dataframe(df, use_container_width=True)

    # ---------- 新增 / 編輯 / 刪除 ----------
    col1, col2, col3 = st.columns(3)
    if col1.button("➕ 新增色粉資料"):
        st.session_state["color_edit_mode"] = "new"
        st.session_state["color_edit_row"] = None

    if col2.button("✏️ 編輯選取資料"):
        select_color_for_edit(df)

    if col3.button("🗑️ 刪除選取資料"):
        delete_color(df)

    # ---------- 編輯表單 ----------
    if st.session_state.get("color_edit_mode"):
        render_color_editor(df)


# ========== 讀取色粉 CSV / Google Sheet ==========
def load_color_data():
    try:
        df = load_csv("color.csv")
        return df
    except Exception as e:
        show_error(f"讀取色粉資料時發生錯誤：{e}")
        return None


# ========== 儲存色粉 ==========
def save_color_data(df):
    save_csv("color.csv", df)
    show_success("色粉資料已成功儲存！")


# ========== 選取一筆進入編輯 ==========
def select_color_for_edit(df):
    st.info("請在下方輸入想編輯的色粉名稱：")
    name = st.text_input("輸入色粉名稱")

    if st.button("開始編輯"):
        row = df[df["色粉名稱"] == name]

        if row.empty:
            show_error("找不到此色粉資料")
            return

        st.session_state["color_edit_mode"] = "edit"
        st.session_state["color_edit_row"] = row.iloc[0]


# ========== 刪除色粉 ==========
def delete_color(df):
    st.info("請輸入要刪除的色粉名稱：")
    name = st.text_input("欲刪除色粉名稱")

    if st.button("確認刪除"):
        if name not in df["色粉名稱"].values:
            show_error("查無此色粉")
            return

        df = df[df["色粉名稱"] != name]
        save_color_data(df)
        st.experimental_rerun()


# ========== 新增 / 編輯畫面 ==========
def render_color_editor(df):
    mode = st.session_state["color_edit_mode"]
    row = st.session_state.get("color_edit_row")

    st.subheader("✏️ 編輯色粉資料" if mode == "edit" else "➕ 新增色粉資料")

    # 預設值
    default = {
        "色粉名稱": "" if row is None else row["色粉名稱"],
        "國際色號": "" if row is None else row.get("國際色號", ""),
        "色粉類別": "" if row is None else row.get("色粉類別", ""),
        "使用建議": "" if row is None else row.get("使用建議", ""),
    }

    v_name = st.text_input("色粉名稱", default["色粉名稱"])
    v_code = st.text_input("國際色號", default["國際色號"])
    v_type = st.selectbox("色粉類別", ["色粉", "色母", "配方", "添加劑"], 
                          index=["色粉","色母","配方","添加劑"].index(default["色粉類別"]) if default["色粉類別"] else 0)
    v_note = st.text_area("使用建議", default["使用建議"])

    colA, colB = st.columns(2)
    if colA.button("💾 儲存"):
        if v_name == "":
            show_error("色粉名稱不可空白")
            return
        
        save_one_color(df, mode, row, v_name, v_code, v_type, v_note)

    if colB.button("❌ 取消"):
        st.session_state["color_edit_mode"] = None
        st.session_state["color_edit_row"] = None
        st.experimental_rerun()


# ========== 儲存單筆色粉 ==========
def save_one_color(df, mode, old_row, name, code, type, note):
    if mode == "new":
        new_row = pd.DataFrame([{
            "色粉名稱": name,
            "國際色號": code,
            "色粉類別": type,
            "使用建議": note,
            "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    else:  # edit
        df.loc[df["色粉名稱"] == old_row["色粉名稱"], 
               ["色粉名稱", "國際色號", "色粉類別", "使用建議"]] = [
                   name, code, type, note
        ]

    save_color_data(df)
    st.session_state["color_edit_mode"] = None
    st.session_state["color_edit_row"] = None
    st.experimental_rerun()

