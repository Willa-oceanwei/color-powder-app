import json
import streamlit as st
import gspread
from google.oauth2 import service_account

# 讀 secrets
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])
sheet_url = st.secrets["gcp"]["sheet_url"]

# 建立 GSpread Client
creds = service_account.Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
)
client = gspread.authorize(creds)

# 開啟試算表
spreadsheet = client.open_by_url(sheet_url)

# ====== 共用工具 ======
def load_sheet(worksheet_name, columns):
    try:
        ws = spreadsheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=columns)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(worksheet_name, rows=1000, cols=len(columns))
        ws.append_row(columns)
        df = pd.DataFrame(columns=columns)
    return ws, df

def save_sheet(ws, df):
    ws.clear()
    ws.append_row(df.columns.tolist())
    if not df.empty:
        ws.append_rows(df.values.tolist())

# ====== 色粉管理模組 ======
def color_module():
    ws_color, df_color = load_sheet("色粉管理", ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"])

    st.header("🎨 色粉管理")

    # 搜尋
    search_input = st.text_input("🔍 搜尋色粉（編號/名稱）").strip()
    if search_input:
        filtered_df = df_color[df_color.apply(lambda r: search_input in str(r.values), axis=1)]
    else:
        filtered_df = df_color

    st.divider()

    # 新增/修改
    if "edit_color_index" not in st.session_state:
        st.session_state.edit_color_index = None

    with st.form(key="color_form", clear_on_submit=True):
        cols = st.columns(3)
        code = cols[0].text_input("色粉編號", key="form_color_色粉編號")
        intl = cols[1].text_input("國際色號", key="form_color_國際色號")
        name = cols[2].text_input("名稱", key="form_color_名稱")
        cols2 = st.columns(3)
        category = cols2[0].selectbox("色粉類別", ["色粉", "色母", "添加劑"], key="form_color_色粉類別")
        packaging = cols2[1].selectbox("包裝", ["袋裝", "桶裝", "箱裝"], key="form_color_包裝")
        note = cols2[2].text_input("備註", key="form_color_備註")
        submit = st.form_submit_button("💾 儲存")

    if submit:
        if not code:
            st.warning("請輸入色粉編號")
        else:
            if st.session_state.edit_color_index is None:
                if code in df_color["色粉編號"].values:
                    st.warning("色粉編號已存在！")
                else:
                    new_row = {"色粉編號": code, "國際色號": intl, "名稱": name, "色粉類別": category, "包裝": packaging, "備註": note}
                    df_color = pd.concat([df_color, pd.DataFrame([new_row])], ignore_index=True)
                    save_sheet(ws_color, df_color)
                    st.success("新增完成")
            else:
                df_color.iloc[st.session_state.edit_color_index] = [code, intl, name, category, packaging, note]
                save_sheet(ws_color, df_color)
                st.success("修改完成")
                st.session_state.edit_color_index = None
            st.experimental_rerun()

    st.divider()

    # 序列
    st.subheader("📋 色粉列表")
    for idx, row in filtered_df.iterrows():
        c = st.container()
        cols = c.columns([2, 2, 2, 1])
        cols[0].markdown(f"**{row['色粉編號']} - {row['名稱']}**")
        cols[1].markdown(f"{row['國際色號']} | {row['色粉類別']}")
        cols[2].markdown(f"{row['包裝']} - {row['備註']}")
        if cols[3].button("✏️ 修改", key=f"edit_color_{idx}"):
            st.session_state.edit_color_index = idx
            for col in ["色粉編號", "國際色號", "名稱", "色粉類別", "包裝", "備註"]:
                st.session_state[f"form_color_{col}"] = row[col]
            st.experimental_rerun()
        if cols[3].button("🗑️ 刪除", key=f"del_color_{idx}"):
            if st.confirm(f"確定要刪除色粉編號【{row['色粉編號']}】嗎？"):
                df_color = df_color.drop(idx).reset_index(drop=True)
                save_sheet(ws_color, df_color)
                st.success("已刪除")
                st.experimental_rerun()

# ====== 客戶名單模組 ======
def customer_module():
    ws_customer, df_customer = load_sheet("客戶名單", ["客戶編號", "客戶簡稱", "備註"])

    st.header("👥 客戶名單管理")

    # 搜尋
    search_input = st.text_input("🔍 搜尋客戶（編號/名稱）").strip()
    if search_input:
        filtered_df = df_customer[df_customer.apply(lambda r: search_input in str(r.values), axis=1)]
    else:
        filtered_df = df_customer

    st.divider()

    # 新增/修改
    if "edit_customer_index" not in st.session_state:
        st.session_state.edit_customer_index = None

    with st.form(key="customer_form", clear_on_submit=True):
        cols = st.columns(2)
        code = cols[0].text_input("客戶編號", key="form_customer_客戶編號")
        name = cols[1].text_input("客戶名稱", key="form_customer_客戶名稱")
        note = st.text_input("備註", key="form_customer_備註")
        submit = st.form_submit_button("💾 儲存")

    if submit:
        if not code:
            st.warning("請輸入客戶編號")
        else:
            if st.session_state.edit_customer_index is None:
                if code in df_customer["客戶編號"].values:
                    st.warning("客戶編號已存在！")
                else:
                    new_row = {"客戶編號": code, "客戶名稱": name, "備註": note}
                    df_customer = pd.concat([df_customer, pd.DataFrame([new_row])], ignore_index=True)
                    save_sheet(ws_customer, df_customer)
                    st.success("新增完成")
            else:
                df_customer.iloc[st.session_state.edit_customer_index] = [code, name, note]
                save_sheet(ws_customer, df_customer)
                st.success("修改完成")
                st.session_state.edit_customer_index = None
            st.experimental_rerun()

    st.divider()

    # 序列
    st.subheader("📋 客戶列表")
    for idx, row in filtered_df.iterrows():
        c = st.container()
        cols = c.columns([3, 3, 2, 1])
        cols[0].markdown(f"**{row['客戶編號']} - {row['客戶名稱']}**")
        cols[1].markdown(row["備註"])
        if cols[2].button("✏️ 修改", key=f"edit_customer_{idx}"):
            st.session_state.edit_customer_index = idx
            for col in ["客戶編號", "客戶名稱", "備註"]:
                st.session_state[f"form_customer_{col}"] = row[col]
            st.experimental_rerun()
        if cols[3].button("🗑️ 刪除", key=f"del_customer_{idx}"):
            if st.confirm(f"確定要刪除客戶編號【{row['客戶編號']}】嗎？"):
                df_customer = df_customer.drop(idx).reset_index(drop=True)
                save_sheet(ws_customer, df_customer)
                st.success("已刪除")
                st.experimental_rerun()

# ====== 主選單 ======
st.sidebar.title("系統選單")
module = st.sidebar.radio("請選擇功能模組", ["色粉管理", "客戶名單"])

if module == "色粉管理":
    color_module()
else:
    customer_module()
