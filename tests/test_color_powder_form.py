from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "app.py"


def test_color_powder_form_falls_back_for_unknown_package_values():
    source = APP_SOURCE.read_text(encoding="utf-8")
    form_section = source.split('with st.form("color_form_tab4"):', 1)[1]
    form_section = form_section.split("if submit_color:", 1)[0]

    assert 'current_package = st.session_state.form_color.get("包裝", "袋")' in form_section
    assert "if current_package in package_options" in form_section
    assert "else 0" in form_section
    assert "submit_color = st.form_submit_button" in form_section
