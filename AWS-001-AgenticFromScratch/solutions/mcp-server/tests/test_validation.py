import pytest

from lib.validation import ToolInputError, bounded_int, date_range, one_of


def test_date_range_ok():
    assert date_range("2026-09-01", "2026-09-07") == ("2026-09-01", "2026-09-07")


@pytest.mark.parametrize("start,end", [
    ("2026-09-01'; DROP TABLE x;--", "2026-09-07"),
    ("01/09/2026", "2026-09-07"),
    ("2026-09-07", "2026-09-01"),
    ("2026-01-01", "2026-09-30"),
])
def test_date_range_rejects(start, end):
    with pytest.raises(ToolInputError):
        date_range(start, end)


def test_bounded_int():
    assert bounded_int(5, "top_n", 1, 50) == 5
    for bad in (0, 51, True, "5", 5.0):
        with pytest.raises(ToolInputError):
            bounded_int(bad, "top_n", 1, 50)


def test_one_of():
    with pytest.raises(ToolInputError):
        one_of("chicken' OR 1=1", "category", ["all", "chicken"])
