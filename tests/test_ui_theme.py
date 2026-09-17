from utils.ui_theme import (
    LEGACY_VISUAL_STYLE,
    REFINED_SHELL_CSS,
    REFINED_VISUAL_STYLE,
    selected_visual_style,
)


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
