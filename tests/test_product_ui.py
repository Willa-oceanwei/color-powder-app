from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, initialize_database
from utils.product_repository import list_products, save_product
from utils.recipe_repository import create_recipe
from tests.test_product_repository import product


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
