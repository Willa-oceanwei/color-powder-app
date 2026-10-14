from utils.small_label_print import generate_small_label_html


def test_small_labels_paginate_in_two_columns_within_physical_sheet():
    rows = [{"編號": f"ID{i}", "名稱": "紅色", "日期": "115/10/14", "比例": "4g/kg", "數量": "25KG"} for i in range(11)]
    result = generate_small_label_html(rows)
    assert "size: 14cm 23cm;" in result
    assert result.count('class="sheet"') == 2
    assert result.count('class="label-slot"') == 11
    for left in (0.6, 7.2):
        for top in (0.25, 4.75, 9.25, 13.75, 18.25):
            assert f'left:{left}cm;top:{top}cm;width:6.3cm' in result
    assert 'width:1.45cm">4</div>' in result
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
