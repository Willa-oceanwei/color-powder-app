# utils/schedule.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from .common import get_spreadsheet, save_df_to_sheet, init_states

def show_schedule_page():
    st.title("代工排程（開發中）")
    st.info("代工排程功能尚未開發完成，預計由生產單代入資料。")
    st.write("此頁目前為 placeholder（開發中）")

