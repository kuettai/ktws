"""Module 01 tools."""
from app import mcp
from lib.auth import current_caller


@mcp.tool()
def ping(name: str) -> str:
    """Health check. Returns a greeting.

    Args:
        name: Who is saying hello, e.g. "Alex".
    """
    return f"Hello {name}, restaurant MCP is alive"


@mcp.tool()
def who_am_i() -> dict:
    """Who is signed in: their role (hq, manager or staff) and branch_id.

    Call this first when the user says "my branch", "my store" or "here", to get the branch_id
    for other tools. Also useful to debug access issues.
    """
    caller = current_caller()
    return {"role": caller.role, "branch_id": caller.branch_id, "is_service": caller.is_service}
