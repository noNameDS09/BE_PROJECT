import pytest

from loupe.tools.calc import CalcError, calculate


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("25785 - 22680", 3105),
        ("(7658 - 6168) / 6168 * 100", pytest.approx(24.157, abs=1e-3)),
        ("pct_change(22680, 25785)", pytest.approx(13.690, abs=1e-3)),
        ("cagr(100, 121, 2)", pytest.approx(10.0)),
        ("round(ratio(3, 4), 2)", 0.75),
        ("1,234,567 / 1000", 1234.567),
        ("-2 ** 2", -4),
    ],
)
def test_arithmetic_and_finance_helpers(expr, expected):
    assert calculate(expr) == expected


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('ls')",
        "open('x')",
        "x + 1",
        "2 ** 1000",
        "1 / 0",
        "(1).real",
        "True + 1",
    ],
)
def test_unsafe_or_invalid_expressions_are_rejected(expr):
    with pytest.raises(CalcError):
        calculate(expr)
