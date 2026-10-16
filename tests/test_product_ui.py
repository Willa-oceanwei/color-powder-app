from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, initialize_database
from utils.product_repository import list_products, save_product
from utils.recipe_repository import create_recipe
from tests.test_product_repository import product


@pytest.mark.parametrize('state,prefix,recipes', [
    ({'product_epoch': 1, 'product_1_recipe_id': 'R1'}, 'product_1_', {'R1': {'recipe_id': 'R1', 'color': '白'}}),
    ({'product_epoch': 2, 'product_draft': {}, 'product_1_recipe_id': 'R1'}, 'product_1_', {'R1': {'recipe_id': 'R1', 'color': '白'}}),
    ({'product_epoch': 2, 'product_draft': {}, 'product_view_P1_1_recipe_id': 'R1'}, 'product_view_P1_1_', {'R1': {'recipe_id': 'R1', 'color': '白'}}),
    ({'product_epoch': 1, 'product_draft': {}, 'product_1_recipe_id': 'removed'}, 'product_1_', {}),
])
def test_recipe_callback_ignores_closed_or_stale_editors(monkeypatch, state, prefix, recipes):
    from copy import deepcopy
    import utils.product_ui as ui

    class SessionState(dict):
        def __getattr__(self, key):
            if key not in self:
                raise AttributeError(key)
            return self[key]

    state = SessionState(state)
    before = deepcopy(state)
    monkeypatch.setattr(ui.st, 'session_state', state)
    ui._fill_recipe(prefix, recipes)
    assert state == before


def test_read_only_recipe_update_does_not_require_an_editing_draft(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'read-only.db')
    initialize_database(config.path)
    create_recipe(config, {'配方編號': 'R1', '顏色': '白'})
    save_product(config, product(recipe_id='R1'))
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_ui import render_product_management
render_product_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    picker = next(w for w in app.selectbox if w.label == '關聯配方')
    assert picker.disabled and picker.value == 'R1'
    # A delayed client value must not run editing callbacks on a saved record.
    picker.set_value('').run()
    assert not app.exception
    assert 'product_draft' not in app.session_state
    assert list_products(config)[0]['recipe_id'] == 'R1'


def test_number_lookup_rechecks_before_filling_and_preserves_new_draft(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'number-lookup.db')
    initialize_database(config.path)
    save_product(config, product(product_id='A0008'))
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_ui import render_product_management
render_product_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    app.text_input(key='product_number_prefix').set_value('A')
    next(w for w in app.button if w.label == '查號').click().run()
    assert next(w for w in app.text_input if w.label == '下一個可用編號').value == 'A0009'
    # Another user may save a number after the lookup.
    save_product(config, product(product_id='A0009'))
    app.button(key='product_number_use').click().run()
    assert not app.exception
    assert app.session_state['product_draft']['product_id'] == 'A0010'
    assert len(list_products(config)) == 2
    next(w for w in app.text_input if w.label == '貨品名稱').set_value('保留名稱').run()
    next(w for w in app.number_input if w.label == '標準售價').set_value(125.0).run()
    app.button(key='product_number_use').click().run()
    assert not app.exception
    assert app.session_state['product_draft']['name'] == '保留名稱'
    assert float(app.session_state['product_draft']['standard_price']) == 125.0
    app.button(key='product_save').click().run()
    assert not app.exception
    assert len(list_products(config)) == 3
    app.button(key='product_edit').click().run()
    assert app.button(key='product_number_use').disabled


def test_combined_picker_opens_product_without_recipe_and_prefers_saved_prices(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'combined-picker.db')
    initialize_database(config.path)
    create_recipe(config, {'配方編號': 'R1', '顏色': '配方名稱'})
    save_product(config, product(product_id='R1', name='已定價名稱', recipe_id='R1', standard_price='375'))
    save_product(config, product(product_id='ONLY01', name='獨立貨品', standard_price='180'))
    retired = save_product(config, product(product_id='OLD01'))
    from utils.product_repository import set_product_active
    set_product_active(config, 'OLD01', retired['version'], active=False, reason='停用')
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_ui import render_product_management
render_product_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    picker = app.selectbox(key='product_recipe_search')
    assert sum('R1 ·' in label for label in picker.options) == 1
    assert any('ONLY01 · 獨立貨品' in label for label in picker.options)
    assert not any('OLD01 ·' in label for label in picker.options)
    picker.set_value('ONLY01').run()
    app.button(key='product_recipe_open').click().run()
    assert not app.exception
    assert app.session_state['product_draft']['product_id'] == 'ONLY01'
    assert float(app.session_state['product_draft']['standard_price']) == 180
    app.button(key='product_cancel').click().run()
    app.selectbox(key='product_recipe_search').set_value('R1').run()
    app.button(key='product_recipe_open').click().run()
    assert not app.exception
    assert app.session_state['product_draft']['name'] == '已定價名稱'
    assert float(app.session_state['product_draft']['standard_price']) == 375
    app.button(key='product_cancel').click().run()
    app.toggle(key='product_show_inactive').set_value(True).run()
    app.selectbox(key='product_recipe_search').set_value('OLD01').run()
    app.button(key='product_recipe_open').click().run()
    assert not app.exception and 'product_draft' not in app.session_state
    assert app.session_state['product_selected'] == 'OLD01'


def test_product_editor_create_modify_cancel_delete_restore(tmp_path):
    config = DatabaseConfig(backend='sqlite', path=tmp_path / 'ui.db')
    initialize_database(config.path)
    create_recipe(config, {'配方編號': 'R1', '顏色': '白'})
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from utils.database import DatabaseConfig
from utils.product_ui import render_product_management
render_product_management(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    app.button(key='product_new').click().run()
    next(w for w in app.selectbox if w.label == '關聯配方').set_value('R1').run()
    assert next(w for w in app.text_input if w.label == '貨品編號').value == 'R1'
    assert next(w for w in app.text_input if w.label == '貨品名稱').value == '白'
    next(w for w in app.number_input if w.label == '標準售價').set_value(260.0).run()
    app.button(key='product_save').click().run()
    assert not app.exception
    assert list_products(config)[0]['standard_price'] == '260.0'
    app.button(key='product_edit').click().run()
    next(w for w in app.text_input if w.label == '貨品名稱').set_value('不要儲存').run()
    app.button(key='product_cancel').click().run()
    assert list_products(config)[0]['name'] == '白'
    app.button(key='product_edit').click().run()
    next(w for w in app.text_input if w.label == '規格').set_value('25KG').run()
    assert app.session_state['product_draft']['specification'] == '25KG'
    app.button(key='product_save').click().run()
    assert not app.exception
    assert not app.error
    assert list_products(config)[0]['specification'] == '25KG'
    save_product(config, product())
    app.run()
    app.button(key='product_nav_首筆').click().run()
    assert app.session_state['product_selected'] == '68146AM'
    app.button(key='product_delete').click().run()
    next(w for w in app.text_input if w.label == '刪除原因').set_value('停止販售')
    next(w for w in app.toggle if w.label == '確認刪除此貨品，保留歷史單據').set_value(True)
    next(w for w in app.button if w.label == '確認刪除').click().run()
    assert not app.exception
    assert len(list_products(config)) == 1
    app.toggle(key='product_show_inactive').set_value(True).run()
    app.button(key='product_nav_首筆').click().run()
    app.button(key='product_restore').click().run()
    assert not app.exception
    assert len(list_products(config)) == 2
