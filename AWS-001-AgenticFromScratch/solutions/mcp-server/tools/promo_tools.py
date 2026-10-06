"""Module 03 Exercise B tools: Promotions service (legacy-app/), built by reading its code.

Things the legacy code does that the tools hide from the model:
    - money in integer cents      -> USD
    - dates as yyyymmdd integers         -> YYYY-MM-DD
    - channels as a bitmask (1/2/4/8)    -> list of channel names
    - reason codes BR/DT/CH/MN/BQ        -> plain-language reasons
    - auth header x-svc-tkn

Environment:
    PROMO_API_BASE_URL  e.g. http://localhost:8081
    PROMO_API_TOKEN     sent as x-svc-tkn
"""
import logging
import os

import httpx
from pydantic import BaseModel, Field

from app import mcp
from lib.scoping import scoped_branch
from lib.validation import ToolInputError, date_range, one_of

log = logging.getLogger(__name__)

CHANNEL_BITS = {"dine_in": 1, "takeaway": 2, "drive_thru": 4, "delivery": 8}
TYPES = {"P": "percent", "F": "fixed_amount", "B": "bundle"}
DAYS = {0: "any", 1: "weekend_only", 2: "weekday_only"}
REASONS = {
    "BR": "Promotion is not valid at this branch.",
    "DT": "Promotion is not active right now (date, day of week or hour restriction).",
    "CH": "Promotion is not valid for this order channel.",
    "MN": "Basket is below the minimum spend.",
    "BQ": "Basket does not contain the required bundle items.",
}


def _call(method: str, path: str, **kwargs):
    try:
        response = httpx.request(
            method,
            os.environ["PROMO_API_BASE_URL"].rstrip("/") + path,
            headers={"x-svc-tkn": os.environ["PROMO_API_TOKEN"]},
            timeout=10,
            **kwargs,
        )
    except httpx.HTTPError as e:
        log.error("Promotions service unreachable: %s", e)
        raise ToolInputError("The promotions system is unavailable. Try again shortly.") from None
    body = response.json()
    if body.get("rc") == "E02":
        raise ToolInputError("Promotion not found.")
    if response.status_code >= 400:
        log.error("Promotions service %s %s: %s", path, response.status_code, body)
        raise ToolInputError("The promotions system rejected the request. Check the inputs.")
    return body


def _usd(cents: int | None) -> float | None:
    return round(cents / 100, 2) if cents else None


def _iso(yyyymmdd: int) -> str:
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _promo(p: dict) -> dict:
    promo = {
        "code": p["pcd"],
        "description": p["ds"],
        "type": TYPES[p["typ"]],
        "min_spend_usd": _usd(p.get("mn")),
        "days": DAYS[p["wk"]],
        "hours": p.get("hr"),
        "channels": [name for name, bit in CHANNEL_BITS.items() if p["chn"] & bit],
        "branches": "all" if p["brs"] == "*" else [int(b) for b in p["brs"].split(",")],
        "start_date": _iso(p["sd"]),
        "end_date": _iso(p["ed"]),
    }
    if p["typ"] == "P":
        promo |= {"percent_off": p["val"], "max_discount_usd": _usd(p.get("mx"))}
    elif p["typ"] == "F":
        promo["amount_off_usd"] = _usd(p["val"])
    else:
        promo["bundle"] = {"buy_item_id": p["bi"], "buy_qty": p["bq"], "free_item_id": p["gi"], "free_qty": p["gq"]}
    if "live" in p:
        promo["active_now"] = p["live"]
    return promo


class BasketItem(BaseModel):
    item_id: int = Field(ge=1, le=20, description="Menu item ID, e.g. 19 for Egg Tart")
    qty: int = Field(ge=1, le=50, description="Quantity, e.g. 2")


@mcp.tool()
def list_active_promotions(branch_id: int) -> dict:
    """Promotions a customer can use at one branch right now (respects day-of-week and hour rules).

    Args:
        branch_id: Branch ID, e.g. 12.
    """
    branch_id, note = scoped_branch(branch_id)
    promos = [_promo(p) for p in _call("GET", "/api/v1/promo/lst", params={"br": branch_id, "act": "1"})["dt"]]
    result = {"promotions": promos, "count": len(promos)}
    return {**result, "note": note} if note else result


@mcp.tool()
def get_promotion(code: str) -> dict:
    """Full rules for one promotion code, and whether it is active right now.

    Args:
        code: Promotion code, case-insensitive, e.g. "WKND20".
    """
    if not code.strip().isalnum() or len(code) > 20:
        raise ToolInputError("code must be letters and digits only, e.g. WKND20")
    return _promo(_call("GET", f"/api/v1/promo/dtl/{code.strip().upper()}")["dt"])


@mcp.tool()
def check_promotion(code: str, branch_id: int, items: list[BasketItem], channel: str = "dine_in") -> dict:
    """Check whether a promotion code applies to a basket and calculate the discount (USD).

    Uses menu list prices. Does not place an order.

    Args:
        code: Promotion code, e.g. "WKND20".
        branch_id: Branch ID, e.g. 12.
        items: Basket, e.g. [{"item_id": 3, "qty": 2}, {"item_id": 9, "qty": 1}].
        channel: dine_in, takeaway, drive_thru or delivery. Default dine_in.
    """
    branch_id, note = scoped_branch(branch_id)
    channel = one_of(channel, "channel", list(CHANNEL_BITS))
    body = _call("POST", "/api/v1/promo/chk", json={
        "pcd": code.strip().upper(),
        "br": branch_id,
        "chn": CHANNEL_BITS[channel],
        "itms": [{"id": i.item_id, "q": i.qty} for i in items],
    })["dt"]
    if not body["ok"]:
        result = {"applies": False, "reason": REASONS.get(body.get("rsn"), "Promotion does not apply.")}
    else:
        result = {
            "applies": True,
            "basket_total_usd": _usd(body["tot"]),
            "discount_usd": _usd(body["dsc"]),
            "net_total_usd": _usd(body["net"]),
        }
    return {**result, "note": note} if note else result


@mcp.tool()
def get_promotion_redemptions(branch_id: int, start_date: str, end_date: str) -> dict:
    """Number of redemptions per promotion code at one branch over a date range.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    rows = _call("GET", "/api/v1/promo/rpt", params={
        "br": branch_id, "dt1": start.replace("-", ""), "dt2": end.replace("-", ""),
    })["dt"]
    result = {"rows": [{"code": r["pcd"], "redemptions": r["rdm"]} for r in rows]}
    return {**result, "note": note} if note else result
