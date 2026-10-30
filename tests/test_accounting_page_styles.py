from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("page, marker", [
    ("render_customer_ranking", "ranking-page"),
    ("render_receivable_statement", "receivable-page"),
])
def test_shared_page_styles_use_html_without_visible_css(page, marker):
    root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
import utils.receivable_ui as ui
# Exercise the page's real style entry point without querying report data.
ui.render_receipt_entry = lambda config: None
ui.render_report = lambda config, **kwargs: None
ui.render_monthly_receipt_summary = lambda config: None
ui.{page}(None)
''').run(timeout=30)
    assert not app.exception
    assert any(f'id="{marker}"' in element.proto.body and "<style>" in element.proto.body
               for element in app.get("html"))
    assert not any("Keep item actions" in element.value or f"#{marker}" in element.value
                   for element in app.markdown)
