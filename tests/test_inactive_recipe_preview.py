import ast
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from utils.recipe_page_data import recipe_is_inactive, recipe_preview_labels
from utils.paper_preview import build_paper_preview


@pytest.mark.parametrize('row,disabled', [
    ({'生命週期': 'inactive', '狀態': '啟用'}, True),
    ({'生命週期': 'active', '狀態': '停用'}, True),
    ({'生命週期': 'active', '狀態': '啟用'}, False),
    ({}, False),
])
def test_disabled_status_recognizes_both_recipe_flags(row, disabled):
    assert recipe_is_inactive(row) is disabled


def test_preview_labels_keep_inactive_recipes_and_mark_them():
    frame = pd.DataFrame([
        {'配方編號': 'A1', '顏色': 'Blue', '客戶名稱': 'Customer', '生命週期': 'active', '狀態': '啟用'},
        {'配方編號': 'I1', '顏色': 'White', '客戶名稱': 'Customer', '生命週期': 'inactive', '狀態': '啟用'},
        {'配方編號': 'L1', '顏色': 'Red', '客戶名稱': 'Customer', '生命週期': 'active', '狀態': '停用'},
    ])
    before = frame.copy(deep=True)
    labels = recipe_preview_labels(frame)
    assert set(labels) == {'', 'A1', 'I1', 'L1'}
    assert '停用配方' not in labels['A1']
    assert '停用配方' in labels['I1'] and '停用配方' in labels['L1']
    pd.testing.assert_frame_equal(frame, before)


def test_recipe_management_uses_its_own_complete_snapshot_after_production_visit():
    tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
    branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and
                  ast.unparse(n.test) == "menu == '配方管理'")
    names = {'df', 'df_recipe'}
    assignments = [n for n in branch.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    complete = pd.DataFrame([{'配方編號': 'A1'}, {'配方編號': 'I1'}])
    state = SimpleNamespace(recipe_management_df=complete, df=complete.iloc[:1], df_recipe=complete.iloc[:1])
    ns = {'st': SimpleNamespace(session_state=state)}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), 'recipe-cache', 'exec'), ns)
    assert ns['df']['配方編號'].tolist() == ['A1', 'I1']
    assert ns['df_recipe']['配方編號'].tolist() == ['A1', 'I1']
    # An existing browser session without the new snapshot must reload all rows.
    guard = next(n for n in branch.body if isinstance(n, ast.If) and 'recipe_management_df' in ast.unparse(n.test))
    assert 'recipe_data_loaded' in ast.unparse(guard.test)


def test_disabled_marker_is_inside_paper_preview_and_additional_recipes():
    tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate_recipe_preview_text')
    ns = dict(st=SimpleNamespace(session_state={}), safe_str=lambda v: str(v or ''),
              safe_float=lambda v: float(v or 0), fmt_num=lambda v: f'{v:g}')
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'preview', 'exec'), ns)
    render = ns['generate_recipe_preview_text']
    main = {'配方編號': 'I1', '生命週期': 'inactive', '色粉編號1': '302', '色粉重量1': 25, '淨重': 25}
    text = render({'配方編號': 'I1'}, main, recipe_frame=pd.DataFrame())
    assert '停用配方' in text and '302' in text
    assert '停用配方' in build_paper_preview(text, title='配方')
    assert '停用配方' not in render({}, dict(main, 生命週期='active'), recipe_frame=pd.DataFrame())
    additional = pd.DataFrame([dict(main, 配方編號='SUB1', 配方類別='附加配方', 原始配方='BASE')])
    text = render({'配方編號': 'BASE'}, dict(main, 生命週期='active'), recipe_frame=additional)
    assert 'SUB1' in text and '停用配方' in text
