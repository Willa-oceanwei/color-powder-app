import ast
from pathlib import Path
from textwrap import dedent

from streamlit.testing.v1 import AppTest

from utils.database import DatabaseConfig, initialize_database
from utils.recipe_repository import create_recipe, list_recipes


def recipe_creation_app(config):
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    branch = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.If)
                  and ast.unparse(n.test) == "menu == '配方管理'")
    columns = next(n for n in branch.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "columns" for t in n.targets))
    section = dedent(source.split("# Tab 1：配方建立", 1)[1].split("# Tab 2：配方記錄表", 1)[0])
    script = f'''import sys
sys.path.insert(0, {str(root)!r})
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
from utils.database import DatabaseConfig
from utils.recipe_repository import create_recipe, list_recipes
DATABASE_CONFIG = DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r}))
{ast.unparse(columns)}
df = pd.DataFrame(list_recipes(DATABASE_CONFIG), columns=columns)
customer_options = ["C01 - Customer"]
existing_powders_str = set()
clean_powder_id = lambda value: str(value).strip().upper()
class Display:
    def selectbox(self, target, label, options, **kwargs):
        return target.selectbox(label, options, **kwargs)
customer_display = Display()
def save_recipe_row(frame, **kwargs):
    create_recipe(DATABASE_CONFIG, frame.iloc[-1].to_dict())
tab1 = st.container()
{section}
'''
    return AppTest.from_string(script).run(timeout=30)


def test_clear_recipe_form_discards_pending_values_and_keeps_saved_recipes(tmp_path):
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "recipes.db")
    initialize_database(config.path)
    create_recipe(config, {"配方編號": "EXISTING", "顏色": "Blue"})
    app = recipe_creation_app(config)
    next(b for b in app.button if b.label == "➕ 新增色粉列").click().run()
    assert not app.exception and app.session_state["num_powder_rows"] == 6
    for key, value in (("form_recipe_配方編號", "DRAFT"), ("ratio1", "12"),
                       ("form_recipe_色粉編號6", "P006"), ("form_recipe_色粉重量6", "50")):
        app.text_input(key=key).set_value(value)
    app.selectbox(key="form_recipe_selected_customer").set_value("C01 - Customer")
    app.selectbox(key="form_recipe_色粉類別").set_value("色母")
    app.number_input(key="form_recipe_oem_multiplier").set_value(2.0)
    app.text_area(key="form_recipe_備註").set_value("Discard this draft")
    next(b for b in app.button if b.label == "↺").click().run()
    assert not app.exception
    assert app.session_state["num_powder_rows"] == 5
    assert app.text_input(key="form_recipe_配方編號").value == ""
    assert app.text_input(key="ratio1").value == ""
    assert app.text_area(key="form_recipe_備註").value == ""
    assert app.selectbox(key="form_recipe_selected_customer").value == ""
    assert app.selectbox(key="form_recipe_色粉類別").value == "配方"
    assert app.number_input(key="form_recipe_oem_multiplier").value == 1
    assert [r["配方編號"] for r in list_recipes(config)] == ["EXISTING"]
    app.text_input(key="form_recipe_配方編號").set_value("NEXT")
    next(b for b in app.button if b.label == "💾 儲存配方").click().run()
    assert not app.exception
    assert {r["配方編號"] for r in list_recipes(config)} == {"EXISTING", "NEXT"}
