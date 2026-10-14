import ast
from pathlib import Path

import pandas as pd
import pytest


@pytest.mark.parametrize('keyword', ['\\', '[', '(', '*', '.', 'A01'])
def test_recipe_search_treats_special_characters_as_literal_text(keyword):
    source = (Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    matches = [node for node in ast.walk(tree)
               if isinstance(node, ast.AugAssign)
               and 'search_df["_search_text"].str.contains(kw.lower()' in ast.get_source_segment(source, node)]
    assert len(matches) == 1
    expression = ast.Expression(matches[0].value)
    values = pd.Series([keyword.lower(), 'unrelated', None])
    actual = eval(compile(expression, '<recipe-search>', 'eval'),
                  {'search_df': pd.DataFrame({'_search_text': values}), 'kw': keyword})
    assert actual.tolist() == [True, False, False]

