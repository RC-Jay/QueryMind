from services.kpi_service import _format_value


def test_currency():
    assert _format_value(124200, "currency") == "₹124,200"


def test_currency_zero_shows_paise_precision():
    # Amounts under ₹1 render with 2 decimals (e.g. ₹0.50); zero → ₹0.00
    assert _format_value(0, "currency") == "₹0.00"


def test_number():
    assert _format_value(1243, "number") == "1,243"


def test_percent():
    assert _format_value(87.3, "percent") == "87.3%"


def test_none_is_na():
    assert _format_value(None, "number") == "N/A"


def test_non_numeric_passthrough():
    assert _format_value("abc", "number") == "abc"
