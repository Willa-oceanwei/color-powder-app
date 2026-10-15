"""Shared list selection and compact pagination without changing source records."""

from hashlib import sha256
import json

import streamlit as st


def selection_key(key, row_ids):
    fingerprint = sha256(json.dumps([str(value) for value in row_ids], ensure_ascii=False).encode()).hexdigest()[:16]
    return f"{key}_{fingerprint}"


def render_selection_table(frame, records, *, key, id_field, height=None, disabled=False, auto_single=True):
    """Return the original selected record; never infer identity from a display index."""
    if len(frame) != len(records):
        raise ValueError("Display rows and source records must have matching order and length")
    options = dict(hide_index=True, use_container_width=True)
    if height is not None:
        options['height'] = height
    if disabled:
        st.dataframe(frame, **options)
        return None
    result = st.dataframe(frame, on_select='rerun', selection_mode='single-row',
                          key=selection_key(key, [row[id_field] for row in records]), **options)
    selected = result.selection.rows
    if selected and 0 <= selected[0] < len(records):
        return records[selected[0]]
    if auto_single and len(records) == 1:
        return records[0]
    return None


def _set_page(page_key, page, total_pages):
    st.session_state[page_key] = max(1, min(int(page), total_pages))


def _jump_page(page_key, widget_key, total_pages):
    _set_page(page_key, st.session_state[widget_key], total_pages)


def _change_limit(page_key):
    st.session_state[page_key] = 1


def render_compact_pagination(page_key, total_pages, total_rows, limit_key=None,
                              limit_options=None, key_prefix='', page_size=None):
    total_pages = max(1, int(total_pages))
    page = max(1, min(int(st.session_state.get(page_key, 1)), total_pages))
    st.session_state[page_key] = page
    prefix = key_prefix or page_key
    size = st.session_state.get(limit_key, page_size) if limit_key else page_size
    summary, prev, position, following, settings = st.columns([4, .65, 1.3, .65, 1.2], vertical_alignment='center')
    summary.markdown('''<span class="list-pager-marker"></span><style>
    [data-testid="stHorizontalBlock"]:has(.list-pager-marker) {flex-wrap:nowrap!important;gap:8px!important;}
    [data-testid="stHorizontalBlock"]:has(.list-pager-marker)>[data-testid="column"] {min-width:0!important;}
    @media(max-width:640px){
      [data-testid="stHorizontalBlock"]:has(.list-pager-marker)>[data-testid="column"]:has(.list-pager-marker){display:none!important;}
      [data-testid="stHorizontalBlock"]:has(.list-pager-marker)>[data-testid="column"]{width:auto!important;flex:1 1 0!important;}
    }
    </style>''', unsafe_allow_html=True)
    if size and total_rows:
        start = (page - 1) * int(size) + 1
        summary.caption(f"第 {start:,}–{min(page * int(size), total_rows):,} 筆 · 共 {total_rows:,} 筆")
    else:
        summary.caption(f"共 {total_rows:,} 筆")
    prev.button('‹', key=prefix + '_prev_page', help='上一頁', disabled=page == 1,
                on_click=_set_page, args=(page_key, page - 1, total_pages))
    position.caption(f'{page} / {total_pages:,} 頁')
    following.button('›', key=prefix + '_next_page', help='下一頁', disabled=page == total_pages,
                     on_click=_set_page, args=(page_key, page + 1, total_pages))
    with settings.popover('⋯', help='分頁設定：每頁筆數與跳頁'):
        st.caption(f'共 {total_rows:,} 筆 · 分頁設定')
        if limit_key and limit_options:
            current = st.session_state.get(limit_key, limit_options[0])
            if current not in limit_options:
                current = limit_options[0]
                st.session_state[limit_key] = current
            st.selectbox('每頁筆數', limit_options, index=limit_options.index(current), key=limit_key,
                          on_change=_change_limit, args=(page_key,))
        jump_key = prefix + '_jump_page'
        st.session_state[jump_key] = page
        st.number_input('跳至頁碼', min_value=1, max_value=total_pages, step=1, key=jump_key,
                        on_change=_jump_page, args=(page_key, jump_key, total_pages))
