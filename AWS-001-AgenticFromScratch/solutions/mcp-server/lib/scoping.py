"""Branch scoping: user identity decides which branch's data a tool may return.

hq      any branch
manager own branch only
staff   own branch only
"""
from lib.auth import current_caller
from lib.validation import ToolInputError, positive_int


def scoped_branch(requested_branch_id: int) -> tuple[int, str | None]:
    """Return (branch_id to query, note for the model or None)."""
    positive_int(requested_branch_id, "branch_id")
    caller = current_caller()
    if caller.role == "hq":
        return requested_branch_id, None
    if caller.branch_id is None:
        raise ToolInputError("Your account is not linked to a branch. Ask an administrator to set your branch.")
    if requested_branch_id != caller.branch_id:
        return caller.branch_id, (
            f"You can only view branch {caller.branch_id}. "
            f"Showing branch {caller.branch_id} instead of branch {requested_branch_id}."
        )
    return caller.branch_id, None


def require_hq(action: str) -> None:
    if current_caller().role != "hq":
        raise ToolInputError(f"Only HQ users can {action}.")
