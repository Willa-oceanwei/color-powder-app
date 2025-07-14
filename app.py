import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# ======== GCP SERVICE ACCOUNT =========
service_account_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# ======== INIT WORKSHEETS =========
ws_color = spreadsheet.worksheet("色粉管理")
try:
    ws_customer = spreadsheet.worksheet("客戶名單")
except gspread.WorksheetNotFound:
    ws_customer = spreadsheet.add_worksheet(title="客戶名單", rows=1000, cols=10)
    ws_customer.update("A1", [["客戶編號", "客戶簡稱", "備註"]])

# ======== STREAMLIT UI 選單 =========
module = st.sidebar.selectbox("請選擇模組", ["色粉管理", "客戶名單"])

# ======== 色粉管理模組 =========
if module == "色粉管理":
    from color_module import run_color_module
    run_color_module(ws_color)

# ======== 客戶名單模組 =========
elif module == "客戶名單":
    from customer_module import run_customer_module
    run_customer_module(ws_customer)
