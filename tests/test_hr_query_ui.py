from utils.hr_card_ui import detail_card, safe_text, summary_card


def test_safe_text_escapes_database_content_for_html_cards():
    assert safe_text('<script>alert("x")</script>') == "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    assert safe_text("") == "—"


def test_summary_card_contains_formatted_content_and_selected_tone():
    card = summary_card("薪資總計", "NT$ 58,000", "green", "已結算")

    assert "薪資總計" in card
    assert "NT$ 58,000" in card
    assert "已結算" in card
    assert "#4fd17a" in card


def test_detail_card_renders_fields_and_escapes_notes():
    card = detail_card(
        "2026/08",
        "已納入薪資",
        [("使用額度", "1 日"), ("備註", "家庭 <重要>")],
        "gold",
    )

    assert "2026/08" in card
    assert "已納入薪資" in card
    assert "使用額度" in card
    assert "家庭 &lt;重要&gt;" in card
    assert "家庭 <重要>" not in card
