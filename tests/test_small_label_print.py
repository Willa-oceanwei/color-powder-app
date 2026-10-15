from utils.small_label_print import generate_small_label_html


def test_small_labels_paginate_in_two_columns_within_physical_sheet():
    rows = [{"編號": f"ID{i}", "名稱": "紅色", "日期": "115/10/14", "比例": "4g/kg", "數量": "25KG"} for i in range(11)]
    result = generate_small_label_html(rows, paper_stock="custom")
    assert "size: 14cm 23cm;" in result
    assert result.count('class="sheet"') == 2
    assert result.count('class="label-slot"') == 11
    for left in (0.6, 7.2):
        for top in (0.25, 4.75, 9.25, 13.75, 18.25):
            assert f'left:{left}cm;top:{top}cm;width:6.3cm' in result
    assert 'left:2.2cm;top:1.95cm;width:1.45cm">4</div>' in result
    assert "25KG" not in result and "4g/kg" not in result
    assert 7.2 + 6.3 == 14 - 0.5
    assert 18.25 + 4.5 < 23


def test_small_labels_escape_fields_and_support_a4():
    assert generate_small_label_html([]) == ""
    result = generate_small_label_html([{"名稱": "<script>bad</script>"}] * 2,
                                       paper_stock="a4_driver")
    assert "size: A4;" in result
    assert 'left:0.6cm;top:0.25cm;width:6.3cm' in result
    assert 'left:7.2cm;top:0.25cm;width:6.3cm' in result
    assert "&lt;script&gt;bad&lt;/script&gt;" in result
    assert "<script>bad</script>" not in result


def test_small_label_calibration_moves_fields_and_only_last_three_rows_down():
    from html.parser import HTMLParser

    class Slots(HTMLParser):
        def __init__(self):
            super().__init__()
            self.slots = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("class") == "label-slot":
                self.slots.append([])
            elif attrs.get("class") == "field":
                self.slots[-1].append((attrs["style"], attrs["data-size"]))

    for stock in ("custom", "a4_driver"):
        parser = Slots()
        parser.feed(generate_small_label_html([{"編號": "10032"}] * 20, paper_stock=stock))
        assert len(parser.slots) == 20
        for index, fields in enumerate(parser.slots):
            shift = (0, 0.1, 0.3, 0.5, 0.6)[index % 10 // 2]
            for (field, font_size), x, y, width, expected_size in zip(fields, (0.15, 3.15, 0.65, 2.2),
                                         (0.3, 0.3, 1.0, 1.95), (2.45, 1.35, 4.8, 1.45), ("12", "11", "12", "11")):
                if x == 3.15:
                    x = 2.85 if index % 2 == 1 else 2.95
                if x == 0.65 and index % 10 // 2 == 4:
                    y += 0.1
                assert field == f"left:{x}cm;top:{round(y + shift, 3)}cm;width:{width}cm"
                assert font_size == expected_size


def test_selected_positions_keep_blank_slots_and_repeat_selection_on_next_page():
    rows = [{"編號": f"ORDER{i}"} for i in range(4)]
    result = generate_small_label_html(rows, selected_positions=[8, 4, 6])
    assert result.count('class="sheet"') == 2
    assert result.count('class="label-slot"') == 4
    for top in (9.25, 13.75, 18.25):
        assert f'left:0.6cm;top:{top}cm;' in result
    assert 'left:7.2cm;top:' not in result
    assert result.count('left:0.6cm;top:9.25cm;') == 2
    assert result.index("ORDER0") < result.index("ORDER1") < result.index("ORDER2") < result.index("ORDER3")
    assert 'left:0.15cm;top:0.8cm;' in result
    assert 'left:0.15cm;top:0.9cm;' in result
    assert generate_small_label_html(rows, selected_positions=[]) == ""


def test_invalid_positions_are_rejected():
    import pytest

    for positions in ([-1], [10], [1.5], [True]):
        with pytest.raises(ValueError):
            generate_small_label_html([{"編號": "1"}], selected_positions=positions)


def test_default_a4_fourteen_labels_keep_same_origin_on_both_pages():
    rows = [{"編號": "51066", "名稱": "灰白", "日期": "115/10/15", "比例": "2g/kg"}] * 14
    result = generate_small_label_html(rows)
    assert "@page { size: A4; margin: 0; }" in result
    assert "width: 21cm; height: 29.7cm;" in result
    assert "body { margin: 0; padding: 0; }" in result
    assert "14cm 23cm" not in result
    pages = result.split('<div class="sheet">')[1:]
    assert len(pages) == 2
    assert [page.count('class="label-slot"') for page in pages] == [10, 4]
    for page in pages:
        assert page.startswith('<div class="label-slot" style="left:0.6cm;top:0.25cm;width:6.3cm">')
        assert 'left:0.15cm;top:0.3cm;width:2.45cm">51066' in page
    assert generate_small_label_html(rows, paper_stock="a4_driver") == result
