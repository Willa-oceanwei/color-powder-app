"""Compact explicit confirmation before opening a new legacy-code draft."""
import hashlib
import streamlit as st
from .recipe_code_review import (
    suggested_recipe_code, reviewed_recipe_codes, recipe_code_preview, confirm_recipe_code,
)
from .recipe_repository import RecipeError


def _confirm(config, preview, rename, on_renamed):
    try:
        result = confirm_recipe_code(config, preview["source"], preview["token"], rename=rename)
    except RecipeError as error:
        st.session_state["recipe_code_review_error"] = str(error)
        st.session_state.pop("recipe_code_review_preview", None)
    except Exception:
        st.session_state["recipe_code_review_error"] = "確認未完成，資料未變更，請稍後重試。"
    else:
        st.session_state.pop("recipe_code_review_preview", None)
        if rename:
            on_renamed(result)
        st.session_state["recipe_code_review_notice"] = (
            f"已將配方編號 {preview['source']} 改為 {result}" if rename
            else f"已確認保留配方編號 {result}，下次不再詢問此編號"
        )


def render_recipe_code_review(config, code, *, on_renamed):
    if not suggested_recipe_code(code):
        return True
    if any(row["source_code"] == code for row in reviewed_recipe_codes(config)):
        return True
    identity = (hashlib.sha256(repr(config).encode()).hexdigest(), code)
    saved = st.session_state.get("recipe_code_review_preview")
    if not saved or saved[0] != identity:
        try:
            saved = (identity, recipe_code_preview(config, code))
        except RecipeError as error:
            st.warning(str(error))
            return False
        st.session_state["recipe_code_review_preview"] = saved
    preview = saved[1]
    st.warning(f"請確認舊編號：{code} 是否要正式改成 {preview['target']}？")
    st.caption("只修改編號與關聯，不變更色粉、重量、比例或包裝數量；每個編號分別確認。")
    if preview["target_exists"]:
        st.info(f"{preview['target']} 已存在，不能覆蓋；請保留原編號或先到配方管理查核。")
    left, right = st.columns(2)
    left.button(f"改成 {preview['target']}", key="recipe_code_review_rename",
                disabled=preview["target_exists"], on_click=_confirm,
                args=(config, preview, True, on_renamed))
    right.button(f"保留 {code}", key="recipe_code_review_keep", on_click=_confirm,
                 args=(config, preview, False, on_renamed))
    return False
