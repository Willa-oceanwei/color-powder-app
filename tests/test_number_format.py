from utils.number_format import format_optional_decimals


def test_format_optional_decimals_hides_zero_fraction():
    assert format_optional_decimals(100.0) == "100"
    assert format_optional_decimals("42.00") == "42"


def test_format_optional_decimals_keeps_nonzero_fraction():
    assert format_optional_decimals(12.5) == "12.5"
    assert format_optional_decimals("3.25") == "3.25"
