"""Day 2 / Day 3 write tools: actions that change data in the Restaurant Operations API.

Unlike the read tools, a write never silently switches branch: a manager asking to act on
another branch is refused. Staff and service-to-service callers (no human to confirm) cannot
use write tools at all.

Environment:
    OPS_API_BASE_URL  e.g. http://localhost:8080
    OPS_API_KEY       sent as X-API-Key
"""
import logging
import os

import httpx

from app import mcp
from lib.auth import current_caller
from lib.validation import ToolInputError, bounded_int, positive_int

log = logging.getLogger(__name__)


def _post(path: str, body: dict):
    try:
        response = httpx.post(
            os.environ["OPS_API_BASE_URL"].rstrip("/") + path,
            json=body,
            headers={"X-API-Key": os.environ["OPS_API_KEY"]},
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.error("Operations API unreachable: %s", e)
        raise ToolInputError("The operations system is unavailable. Nothing was changed. Try again shortly.") from None
    if response.status_code in (404, 409, 422):
        raise ToolInputError(response.json().get("message", "The request was rejected. Nothing was changed."))
    if response.status_code >= 400:
        log.error("Operations API %s %s: %s", path, response.status_code, response.text)
        raise ToolInputError("The operations system returned an error. Nothing was changed.")
    return response.json()


def _require_write_access(branch_id: int, action: str) -> None:
    """HQ may act on any branch; a manager only on their own; staff and services never."""
    caller = current_caller()
    if caller.is_service:
        raise ToolInputError(f"Service accounts cannot {action}. A signed-in user must do this.")
    if caller.role == "hq":
        return
    if caller.role != "manager":
        raise ToolInputError(f"Only managers and HQ users can {action}.")
    if caller.branch_id is None:
        raise ToolInputError("Your account is not linked to a branch. Ask an administrator to set your branch.")
    if branch_id != caller.branch_id:
        raise ToolInputError(f"You can only {action} for branch {caller.branch_id}, not branch {branch_id}.")


@mcp.tool()
def issue_refund(branch_id: int, order_id: int, reason: str, amount: float | None = None) -> dict:
    """CHANGES DATA: refund one of today's orders at one branch. Confirm the order, amount and
    reason with the user before calling. Cannot be undone.

    Look up the order with get_order first. Managers can refund only at their own branch.

    Args:
        branch_id: Branch ID, e.g. 12.
        order_id: Order ID from list_orders_today, e.g. 20261001000120045.
        reason: Why the order is refunded, shown on the receipt. Max 200 characters.
        amount: Partial refund in USD, e.g. 12.50. Omit for a full refund.
    """
    positive_int(branch_id, "branch_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        raise ToolInputError("order_id must be a positive whole number from list_orders_today")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ToolInputError("reason is required and must be at most 200 characters")
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0):
        raise ToolInputError("amount must be a positive number in USD, or omitted for a full refund")
    _require_write_access(branch_id, "issue refunds")
    body = {"reason": reason.strip()}
    if amount is not None:
        body["amount"] = round(float(amount), 2)
    log.info("issue_refund by %s: branch=%s order=%s amount=%s", current_caller().subject, branch_id, order_id, amount)
    return _post(f"/pos/{branch_id}/orders/{order_id}/refund", body)


@mcp.tool()
def request_stock_transfer(from_branch_id: int, to_branch_id: int, item_id: int, qty: int) -> dict:
    """CHANGES DATA: request a stock transfer of one menu item from one branch to another.
    Confirm the item, quantity and both branches with the user before calling.

    Check stock first with get_current_stock. Managers can only send stock from their own branch.
    Item IDs: 1-4 chicken, 5-8 burgers, 9-13 sides, 14-17 drinks, 18-20 desserts.

    Args:
        from_branch_id: Branch sending the stock, e.g. 12.
        to_branch_id: Branch receiving the stock, e.g. 5. Must differ from from_branch_id.
        item_id: Menu item ID, e.g. 1 for Original Chicken 2pc.
        qty: Portions to transfer, 1-500.
    """
    positive_int(from_branch_id, "from_branch_id")
    positive_int(to_branch_id, "to_branch_id")
    positive_int(item_id, "item_id")
    qty = bounded_int(qty, "qty", 1, 500)
    if from_branch_id == to_branch_id:
        raise ToolInputError("from_branch_id and to_branch_id must be different branches")
    _require_write_access(from_branch_id, "transfer stock")
    log.info("request_stock_transfer by %s: %s -> %s item=%s qty=%s",
             current_caller().subject, from_branch_id, to_branch_id, item_id, qty)
    return _post("/inventory/transfers",
                 {"fromBranchId": from_branch_id, "toBranchId": to_branch_id, "itemId": item_id, "qty": qty})
