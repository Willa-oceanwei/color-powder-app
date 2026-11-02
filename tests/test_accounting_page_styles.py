from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from utils.database import DatabaseConfig, initialize_database


@pytest.mark.parametrize("module, page, marker", [
    ("receivable_ui", "render_customer_ranking", "ranking-page"),
    ("receivable_ui", "render_receivable_statement", "receivable-page"),
    ("product_transaction_ui", "render_product_transactions", "product-history-page"),
    ("product_ui", "render_product_management", "product-page"),
])
def test_shared_page_styles_use_html_without_visible_css(tmp_path, module, page, marker):
    root = str(Path(__file__).resolve().parents[1])
    config = DatabaseConfig(backend="sqlite", path=tmp_path / "styles.db")
    initialize_database(config.path)
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {root!r})
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from importlib import import_module
from utils.database import DatabaseConfig
ui = import_module("utils.{module}")
with ExitStack() as stack:
    # Exercise the real page entry point without unrelated report queries.
    if "{module}" == "receivable_ui":
        for name in ("render_receipt_entry", "render_report", "render_monthly_receipt_summary"):
            stack.enter_context(patch.object(ui, name))
    ui.{page}(DatabaseConfig(backend="sqlite", path=Path({str(config.path)!r})))
''').run(timeout=30)
    assert not app.exception
    assert any(f'id="{marker}"' in element.proto.body and "<style>" in element.proto.body
               for element in app.get("html"))
    assert not any("Keep item actions" in element.value or f"#{marker}" in element.value
                   for element in app.markdown)
