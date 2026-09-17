from utils.ui_theme import (
    LEGACY_VISUAL_STYLE,
    REFINED_SHELL_CSS,
    REFINED_VISUAL_STYLE,
    selected_visual_style,
)


class MarkdownRecorder:
    def __init__(self):
        self.calls = []

    def markdown(self, body, **kwargs):
        self.calls.append((body, kwargs))


def test_refined_visual_style_is_default():
    assert selected_visual_style({}) == REFINED_VISUAL_STYLE


def test_legacy_visual_style_can_restore_previous_shell():
    assert selected_visual_style({"VISUAL_STYLE": " legacy "}) == LEGACY_VISUAL_STYLE


def test_unknown_visual_style_falls_back_to_refined():
    assert selected_visual_style({"VISUAL_STYLE": "unknown"}) == REFINED_VISUAL_STYLE


def test_refined_shell_reuses_existing_palette():
    expected_existing_colors = {"#0b2f4a", "#0a0a0a", "#c6582f", "#ffffff", "#9fb6cc", "#124466"}
    for color in expected_existing_colors:
        assert color in REFINED_SHELL_CSS


def test_refined_shell_follows_reference_dimensions_without_copying_its_colors():
    assert "height: 60px" in REFINED_SHELL_CSS
    assert "width: 250px !important" in REFINED_SHELL_CSS
    assert "left: 234px" in REFINED_SHELL_CSS
    assert "#2c3e50" not in REFINED_SHELL_CSS
    assert "#dbd818" not in REFINED_SHELL_CSS


def test_refined_shell_renders_css_and_header_in_separate_html_blocks(monkeypatch):
    from utils import ui_theme

    monkeypatch.setattr(ui_theme, "selected_visual_style", lambda: REFINED_VISUAL_STYLE)
    recorder = MarkdownRecorder()

    assert ui_theme.apply_refined_shell(recorder)
    assert len(recorder.calls) == 2
    assert recorder.calls[0] == (REFINED_SHELL_CSS, {"unsafe_allow_html": True})
    assert recorder.calls[1] == (
        '<div class="cp-app-header">配方管理系統</div>',
        {"unsafe_allow_html": True},
    )
