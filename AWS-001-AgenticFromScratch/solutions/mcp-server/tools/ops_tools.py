"""Module 03 Exercise A tools: live operations from the Restaurant Operations API (mock-api/openapi.yaml).

Environment:
    OPS_API_BASE_URL  e.g. http://localhost:8080
    OPS_API_KEY       sent as X-API-Key
"""
import logging
import os

import httpx

from app import mcp
from lib.scoping import scoped_branch
from lib.validation import ToolInputError, bounded_int, one_of, positive_int

log = logging.getLogger(__name__)

ORDER_STATUSES = ["open", "preparing", "ready", "completed", "cancelled", "refunded"]


def _get(path: str, params: dict | None = None):
    try:
        response = httpx.get(
            os.environ["OPS_API_BASE_URL"].rstrip("/") + path,
            params=params,
            headers={"X-API-Key": os.environ["OPS_API_KEY"]},
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.error("Operations API unreachable: %s", e)
        raise ToolInputError("The operations system is unavailable. Try again shortly.") from None
    if response.status_code == 404:
        raise ToolInputError(response.json().get("message", "Not found"))
    if response.status_code >= 400:
        log.error("Operations API %s %s: %s", path, response.status_code, response.text)
        raise ToolInputError("The operations system returned an error. Try again shortly.")
    return response.json()


def _with_note(result: dict, note: str | None) -> dict:
    return {**result, "note": note} if note else result


@mcp.tool()
def get_current_stock(branch_id: int, item_id: int | None = None) -> dict:
    """Live stock on hand vs par level at one branch, right now. Units are menu portions.

    For historical waste use get_waste_by_item. Item IDs: 1-4 chicken, 5-8 burgers,
    9-13 sides, 14-17 drinks, 18-20 desserts.

    Args:
        branch_id: Branch ID, e.g. 12.
        item_id: Optional menu item ID, e.g. 1 for Original Chicken 2pc. Omit for all items.
    """
    branch_id, note = scoped_branch(branch_id)
    if item_id is None:
        return _with_note({"items": _get(f"/inventory/{branch_id}/stock")}, note)
    positive_int(item_id, "item_id")
    return _with_note({"items": [_get(f"/inventory/{branch_id}/stock/{item_id}")]}, note)


@mcp.tool()
def list_low_stock_items(branch_id: int) -> dict:
    """Items at one branch whose stock on hand is below 25% of par level, right now.

    Args:
        branch_id: Branch ID, e.g. 12.
    """
    branch_id, note = scoped_branch(branch_id)
    items = _get(f"/inventory/{branch_id}/stock", {"lowStockOnly": "true"})
    return _with_note({"items": items, "count": len(items)}, note)


@mcp.tool()
def get_today_sales(branch_id: int) -> dict:
    """Live sales so far today at one branch: order count, revenue (USD), average ticket, revenue by channel.

    For previous days use get_daily_branch_sales.

    Args:
        branch_id: Branch ID, e.g. 12.
    """
    branch_id, note = scoped_branch(branch_id)
    return _with_note(_get(f"/sales/{branch_id}/today"), note)


@mcp.tool()
def list_orders_today(branch_id: int, status: str = "open", limit: int = 20) -> dict:
    """Today's orders at one branch, newest first, filtered by status.

    Args:
        branch_id: Branch ID, e.g. 12.
        status: open, preparing, ready, completed, cancelled or refunded. Default "open".
        limit: Max orders to return, 1-100. Default 20.
    """
    branch_id, note = scoped_branch(branch_id)
    status = one_of(status, "status", ORDER_STATUSES)
    limit = bounded_int(limit, "limit", 1, 100)
    orders = _get(f"/pos/{branch_id}/orders", {"status": status, "limit": limit})
    return _with_note({"orders": orders, "count": len(orders)}, note)


@mcp.tool()
def get_order(branch_id: int, order_id: int) -> dict:
    """One of today's orders with its line items, prices (USD) and discounts.

    Args:
        branch_id: Branch ID, e.g. 12.
        order_id: Order ID from list_orders_today, e.g. 20261001000120045.
    """
    branch_id, note = scoped_branch(branch_id)
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        raise ToolInputError("order_id must be a positive whole number from list_orders_today")
    return _with_note(_get(f"/pos/{branch_id}/orders/{order_id}"), note)
