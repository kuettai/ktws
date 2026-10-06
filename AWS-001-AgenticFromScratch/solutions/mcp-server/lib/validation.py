"""Input validation helpers (pre-built).

Validate every tool input before it reaches SQL or an API call. Errors raised here are
shown to the model, so messages tell it how to fix the call.
"""
from datetime import date

from mcp.server.mcpserver.exceptions import ToolError

MAX_RANGE_DAYS = 93


class ToolInputError(ToolError, ValueError):
    """Invalid tool input. The message is shown to the model so it can correct the call.

    Any other exception is treated as a crash: the model only sees "Error executing tool <name>".
    """


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolInputError(f"{field} must be a date in YYYY-MM-DD format, got {value!r}") from None


def date_range(start_date: str, end_date: str, max_days: int = MAX_RANGE_DAYS) -> tuple[str, str]:
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")
    if end < start:
        raise ToolInputError("end_date must be on or after start_date")
    if (end - start).days + 1 > max_days:
        raise ToolInputError(f"Date range is limited to {max_days} days. Split the request into smaller ranges.")
    return start.isoformat(), end.isoformat()


def bounded_int(value: int, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"{field} must be a whole number")
    if not low <= value <= high:
        raise ToolInputError(f"{field} must be between {low} and {high}")
    return value


def positive_int(value: int, field: str) -> int:
    return bounded_int(value, field, 1, 2**31 - 1)


def one_of(value: str, field: str, allowed: list[str]) -> str:
    if value not in allowed:
        raise ToolInputError(f"{field} must be one of {', '.join(allowed)}")
    return value
