import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials

# 正確讀取 secrets
gcp_info = json.loads(st.secrets["gcp"]["gcp_service_account"])

creds = Credentials.from_service_account_info(
    gcp_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)

client = gspread.authorize(creds)


# 工作表 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NVI1HHSd87BhFT66ycZKsXNsfsOzk6cXzTSc_XXp_bk/edit#gid=0"
spreadsheet = client.open_by_url(SHEET_URL)

# =========== SIDEBAR 選單 ===========

module = st.sidebar.radio(
    "請選擇功能模組",
    ["色粉管理", "客戶名單"],
)

# ======================================
# ========== 色粉管理模組 ==============
# ======================================

if module == "色粉管理":

    worksheet = spreadsheet.get_worksheet(0)

    required_columns = [
        "色粉編號",
        "國際色號",
        "名稱",
        "色粉類別",
        "包裝",
        "備註",
    ]

    # 載入資料
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame(columns=required_columns)

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df.columns = df.columns.str.strip()

    for col in required_columns:
        st.session_state.setdefault(f"form_powder_{col}", "")

    st.session_state.setdefault("powder_edit_mode", False)
    st.session_state.setdefault("powder_edit_index", None)
    st.session_state.setdefault("powder_delete_index", None)
    st.session_state.setdefault("powder_show_delete_confirm", False)
    st.session_state.setdefault("powder_search_input", "")

    st.title("🎨 色粉管理系統")

    st.subheader("🔎 搜尋色粉")
    search_input = st.text_input(
        "請輸入色粉編號或國際色號",
        st.session_state.powder_search_input,
        key="powder_search_input_input"
    )
    st.session_state.powder_search_input = search_input

    # ======== 新增 / 修改表單 ========
    st.subheader("➕ 新增 / 修改 色粉")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_powder_色粉編號"] = st.text_input(
            "色粉編號",
            st.session_state["form_powder_色粉編號"],
            key="powder_色粉編號"
        )

        st.session_state["form_powder_國際色號"] = st.text_input(
            "國際色號",
            st.session_state["form_powder_國際色號"],
            key="powder_國際色號"
        )

        st.session_state["form_powder_名稱"] = st.text_input(
            "名稱",
            st.session_state["form_powder_名稱"],
            key="powder_名稱"
        )

    with col2:
        st.session_state["form_powder_色粉類別"] = st.selectbox(
            "色粉類別",
            ["色粉", "色母", "添加劑"],
            index=["色粉", "色母", "添加劑"].index(
                st.session_state["form_powder_色粉類別"]
            ) if st.session_state["form_powder_色粉類別"] in ["色粉", "色母", "添加劑"] else 0,
            key="powder_色粉類別"
        )

        st.session_state["form_powder_包裝"] = st.selectbox(
            "包裝",
            ["袋", "箱", "kg"],
            index=["袋", "箱", "kg"].index(
                st.session_state["form_powder_包裝"]
            ) if st.session_state["form_powder_包裝"] in ["袋", "箱", "kg"] else 0,
            key="powder_包裝"
        )

        st.session_state["form_powder_備註"] = st.text_input(
            "備註",
            st.session_state["form_powder_備註"],
            key="powder_備註"
        )

    save_btn = st.button("💾 儲存", key="powder_save_btn")

    if save_btn:
        new_data = {
            col: st.session_state[f"form_powder_{col}"] for col in required_columns
        }
        new_df_row = pd.DataFrame([new_data])

        if not new_data["色粉編號"]:
            st.warning("⚠️ 色粉編號為必填！")
        else:
            if st.session_state.powder_edit_mode:
                df.iloc[st.session_state.powder_edit_index] = new_data
                st.success("✅ 色粉已更新！")
            else:
                if new_data["色粉編號"] in df["色粉編號"].values:
                    st.warning("⚠️ 此色粉編號已存在，請勿重複新增！")
                else:
                    df = pd.concat([df, new_df_row], ignore_index=True)
                    st.success("✅ 新增色粉成功！")

            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.powder_edit_mode = False
            st.session_state.powder_edit_index = None
            for col in required_columns:
                st.session_state[f"form_powder_{col}"] = ""
            st.experimental_rerun()

    # ====== 刪除確認 ======
    if st.session_state.powder_show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆色粉嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="powder_delete_yes"):
            idx = st.session_state.powder_delete_index
            df.drop(index=idx, inplace=True)
            df.reset_index(drop=True, inplace=True)
            try:
                values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
                worksheet.update(values)
                st.success("✅ 色粉已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.powder_show_delete_confirm = False
            st.experimental_rerun()
        if col_no.button("否，取消", key="powder_delete_no"):
            st.session_state.powder_show_delete_confirm = False
            st.experimental_rerun()

    # ====== 資料過濾 ======
    if st.session_state.powder_search_input:
        df_filtered = df[
            df["色粉編號"].astype(str).str.contains(st.session_state.powder_search_input, case=False, na=False)
            | df["國際色號"].astype(str).str.contains(st.session_state.powder_search_input, case=False, na=False)
        ]
    else:
        df_filtered = df

    st.subheader("📋 色粉清單")

    for i, row in df_filtered.iterrows():
        cols = st.columns([2, 2, 2, 2, 2, 1, 1])
        cols[0].write(row["色粉編號"])
        cols[1].write(row["國際色號"])
        cols[2].write(row["名稱"])
        cols[3].write(row["色粉類別"])
        cols[4].write(row["包裝"])
        if cols[5].button("✏️ 修改", key=f"powder_edit_{i}"):
            st.session_state.powder_edit_mode = True
            st.session_state.powder_edit_index = i
            for col in required_columns:
                st.session_state[f"form_powder_{col}"] = row[col]
            st.experimental_rerun()
        if cols[6].button("🗑️ 刪除", key=f"powder_delete_{i}"):
            st.session_state.powder_delete_index = i
            st.session_state.powder_show_delete_confirm = True
            st.experimental_rerun()

# ======================================
# ========== 客戶名單模組 ==============
# ======================================

elif module == "客戶名單":

    worksheet_cust = spreadsheet.get_worksheet(1)
    required_columns = [
    "客戶編號",
    "客戶簡稱",
    "備註",
]
    cust_columns = ["客戶編號", "客戶簡稱", "備註"]

    try:
        cust_data = worksheet_cust.get_all_records()
        df_cust = pd.DataFrame(cust_data)
    except:
        df_cust = pd.DataFrame(columns=cust_columns)

    for col in cust_columns:
        if col not in df_cust.columns:
            df_cust[col] = ""

    for col in cust_columns:
        st.session_state.setdefault(f"form_cust_{col}", "")

    st.session_state.setdefault("cust_edit_mode", False)
    st.session_state.setdefault("cust_edit_index", None)
    st.session_state.setdefault("cust_delete_index", None)
    st.session_state.setdefault("cust_show_delete_confirm", False)
    st.session_state.setdefault("cust_search_input", "")

    st.title("👥 客戶名單管理")

    st.subheader("🔎 搜尋客戶")
    search_input = st.text_input(
        "請輸入客戶編號或名稱",
        st.session_state.cust_search_input,
        key="cust_search_input_input"
    )
    st.session_state.cust_search_input = search_input

    st.subheader("➕ 新增 / 修改 客戶名單")

    col1, col2 = st.columns(2)

    with col1:
        st.session_state["form_cust_客戶編號"] = st.text_input(
            "客戶編號",
            st.session_state["form_cust_客戶編號"],
            key="cust_客戶編號"
        )

        st.session_state["form_cust_客戶簡稱"] = st.text_input(
            "客戶簡稱",
            st.session_state["form_cust_客戶簡稱"],
            key="cust_客戶簡稱"
        )

    with col2:
        st.session_state["form_cust_備註"] = st.text_area(
            "備註",
            st.session_state["form_cust_備註"],
            key="cust_備註"
        )

    save_btn_cust = st.button("💾 儲存", key="cust_save_btn")

    if save_btn_cust:
        new_data = {
            col: st.session_state[f"form_cust_{col}"] for col in cust_columns
        }
        new_df_row = pd.DataFrame([new_data])

        if not new_data["客戶編號"]:
            st.warning("⚠️ 客戶編號為必填！")
        else:
            if st.session_state.cust_edit_mode:
                df_cust.iloc[st.session_state.cust_edit_index] = new_data
                st.success("✅ 客戶資料已更新！")
            else:
                if new_data["客戶編號"] in df_cust["客戶編號"].values:
                    st.warning("⚠️ 此客戶編號已存在，請勿重複新增！")
                else:
                    df_cust = pd.concat([df_cust, new_df_row], ignore_index=True)
                    st.success("✅ 新增客戶成功！")

            try:
                values = [df_cust.columns.tolist()] + df_cust.fillna("").astype(str).values.tolist()
                worksheet_cust.update(values)
            except Exception as e:
                st.error(f"❌ 寫入 Google Sheet 失敗: {e}")

            st.session_state.cust_edit_mode = False
            st.session_state.cust_edit_index = None
            for col in cust_columns:
                st.session_state[f"form_cust_{col}"] = ""
            st.experimental_rerun()

    if st.session_state.cust_show_delete_confirm:
        st.warning("⚠️ 確定要刪除此筆客戶資料嗎？")
        col_yes, col_no = st.columns(2)
        if col_yes.button("是，刪除", key="cust_delete_yes"):
            idx = st.session_state.cust_delete_index
            df_cust.drop(index=idx, inplace=True)
            df_cust.reset_index(drop=True, inplace=True)
            try:
                values = [df_cust.columns.tolist()] + df_cust.fillna("").astype(str).values.tolist()
                worksheet_cust.update(values)
                st.success("✅ 客戶已刪除！")
            except Exception as e:
                st.error(f"❌ 刪除失敗: {e}")
            st.session_state.cust_show_delete_confirm = False
            st.experimental_rerun()
        if col_no.button("否，取消", key="cust_delete_no"):
            st.session_state.cust_show_delete_confirm = False
            st.experimental_rerun()

    if st.session_state.cust_search_input:
        df_cust_filtered = df_cust[
            df_cust["客戶編號"].astype(str).str.contains(st.session_state.cust_search_input, case=False, na=False)
            | df_cust["客戶簡稱"].astype(str).str.contains(st.session_state.cust_search_input, case=False, na=False)
        ]
    else:
        df_cust_filtered = df_cust

    st.subheader("📋 客戶清單")

    for i, row in df_cust_filtered.iterrows():
        cols = st.columns([2, 3, 3, 1, 1])
        cols[0].write(row["客戶編號"])
        cols[1].write(row["客戶簡稱"])
        cols[2].write(row["備註"])
        if cols[3].button("✏️ 修改", key=f"cust_edit_{i}"):
            st.session_state.cust_edit_mode = True
            st.session_state.cust_edit_index = i
            for col in cust_columns:
                st.session_state[f"form_cust_{col}"] = row[col]
            st.experimental_rerun()
        if cols[4].button("🗑️ 刪除", key=f"cust_delete_{i}"):
            st.session_state.cust_delete_index = i
            st.session_state.cust_show_delete_confirm = True
            st.experimental_rerun()
