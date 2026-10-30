import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from streamlit.elements.widgets.data_editor import DataEditorSerde
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def include_data_editor_browser_state(monkeypatch):
    """AppTest has no editor widget; send its JSON state as a browser would."""
    original = AppTest._run

    def run(app, widget_state=None, *args, **kwargs):
        if widget_state is not None:
            state = app.session_state._state
            for table in app.dataframe:
                widget_id = table.proto.id
                metadata = state._new_widget_state.widget_metadata.get(widget_id)
                if metadata is None or not isinstance(getattr(metadata.deserializer, '__self__', None), DataEditorSerde):
                    continue
                widget = widget_state.widgets.add(id=widget_id)
                widget.string_value = metadata.serializer(app.session_state[widget_id])
        return original(app, widget_state, *args, **kwargs)

    monkeypatch.setattr(AppTest, '_run', run)
