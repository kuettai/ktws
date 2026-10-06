"""Deterministic simulation of today's operations at each branch.

Branches, menu and par levels come from reference.json, written by data/generate_seed.py,
so IDs match the Redshift mock data. Redshift holds history up to yesterday; this API
simulates today, up to the current time.

Environment:
    MOCK_TZ   time zone for the business day, default UTC
    MOCK_NOW  fixed "current time" for tests/demos, e.g. 2026-10-01T14:30:00
"""
import json
import os
import random
import threading
import uuid
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

REF = json.loads((Path(__file__).parent / "reference.json").read_text())
BRANCHES = {b["branchId"]: b for b in REF["branches"]}
MENU = {m["itemId"]: m for m in REF["menu"]}
PAR = {tuple(int(x) for x in k.split(":")): v for k, v in REF["parLevels"].items()}
HOUR_WEIGHTS = {int(h): w for h, w in REF["hourWeights"].items()}
CHANNELS = REF["channels"]

OPEN_HOUR, CLOSE_HOUR = 7, 23
LOW_STOCK_RATIO = 0.25
# Demo script: "Branch 12 is low on chicken right now"
FORCED_LOW_STOCK = {(12, 1), (12, 2)}
MANAGERS = ["Alex Morgan", "Sam Rivera", "Jordan Lee", "Taylor Brooks", "Casey Kim", "Riley Patel"]

_lock = threading.Lock()
REFUNDS: dict[int, dict] = {}       # order_id -> refund
TRANSFERS: list[dict] = []


def now() -> datetime:
    tz = ZoneInfo(os.environ.get("MOCK_TZ", "UTC"))
    if fixed := os.environ.get("MOCK_NOW"):
        return datetime.fromisoformat(fixed).replace(tzinfo=tz)
    return datetime.now(tz)


def branch_detail(branch_id: int) -> dict:
    b = BRANCHES[branch_id]
    current = now()
    return {
        "branchId": branch_id,
        "name": b["name"],
        "region": b["region"],
        "format": b["format"],
        "isOpen": OPEN_HOUR <= current.hour < CLOSE_HOUR,
        "openTime": f"{OPEN_HOUR:02d}:00",
        "closeTime": f"{CLOSE_HOUR:02d}:00",
        "managerName": MANAGERS[branch_id % len(MANAGERS)],
        "phone": f"+1 555-{100 + branch_id:03d}-{1000 + branch_id * 7:04d}",  # 555: fictional numbers
    }


@lru_cache(maxsize=512)
def _full_day_orders(branch_id: int, business_date: date) -> tuple[dict, ...]:
    """Every order the branch will take on business_date, deterministic per branch and day."""
    b = BRANCHES[branch_id]
    rng = random.Random(f"{branch_id}:{business_date.isoformat()}")
    day_factor = 1.3 if business_date.isoweekday() >= 6 else 1.0
    total_orders = int(REF["avgOrders"] * b["traffic"] * day_factor)
    weight_sum = sum(HOUR_WEIGHTS.values())
    items = list(MENU.values())
    channels = [(c, w) for c, w in CHANNELS[b["format"]].items() if w > 0]
    tz = ZoneInfo(os.environ.get("MOCK_TZ", "UTC"))

    orders = []
    for hour, weight in sorted(HOUR_WEIGHTS.items()):
        for _ in range(round(total_orders * weight / weight_sum)):
            created = datetime.combine(business_date, time(hour, rng.randint(0, 59), rng.randint(0, 59)), tz)
            lines = []
            for _ in range(max(1, min(6, int(rng.expovariate(1 / 2.4)) + 1))):
                m = rng.choices(items, weights=[i["popularity"] for i in items])[0]
                qty = 1 if rng.random() < 0.8 else rng.randint(2, 4)
                discount = round(qty * m["price"] * 0.10, 2) if rng.random() < 0.10 else 0.0
                lines.append({"itemId": m["itemId"], "name": m["name"], "qty": qty,
                              "unitPrice": m["price"], "discount": discount})
            orders.append({
                "createdAt": created,
                "channel": rng.choices([c for c, _ in channels], weights=[w for _, w in channels])[0],
                "cancelled": rng.random() < 0.02,
                "lines": lines,
                "totalAmount": round(sum(l["qty"] * l["unitPrice"] - l["discount"] for l in lines), 2),
            })
    orders.sort(key=lambda o: o["createdAt"])
    prefix = int(business_date.strftime("%Y%m%d")) * 10_000_000 + branch_id * 10_000
    for seq, o in enumerate(orders, start=1):
        o["orderId"] = prefix + seq
    return tuple(orders)


def _status(order: dict, current: datetime) -> str:
    if order["orderId"] in REFUNDS:
        return "refunded"
    if order["cancelled"]:
        return "cancelled"
    age = (current - order["createdAt"]).total_seconds() / 60
    if age < 5:
        return "open"
    if age < 10:
        return "preparing"
    if age < 15:
        return "ready"
    return "completed"


def orders_today(branch_id: int) -> list[dict]:
    current = now()
    result = []
    for o in _full_day_orders(branch_id, current.date()):
        if o["createdAt"] > current:
            break
        result.append({
            "orderId": o["orderId"],
            "branchId": branch_id,
            "createdAt": o["createdAt"].isoformat(),
            "channel": o["channel"],
            "status": _status(o, current),
            "totalAmount": o["totalAmount"],
            "lines": o["lines"],
        })
    return result


def find_order(branch_id: int, order_id: int) -> dict | None:
    return next((o for o in orders_today(branch_id) if o["orderId"] == order_id), None)


def stock_levels(branch_id: int) -> list[dict]:
    sold: dict[int, int] = {}
    for o in orders_today(branch_id):
        if o["status"] != "cancelled":
            for line in o["lines"]:
                sold[line["itemId"]] = sold.get(line["itemId"], 0) + line["qty"]
    moved: dict[int, int] = {}
    for t in TRANSFERS:
        if t["toBranchId"] == branch_id:
            moved[t["itemId"]] = moved.get(t["itemId"], 0) + t["qty"]
        if t["fromBranchId"] == branch_id:
            moved[t["itemId"]] = moved.get(t["itemId"], 0) - t["qty"]

    updated = now().isoformat()
    levels = []
    for item_id, m in MENU.items():
        par = PAR[(branch_id, item_id)]
        on_hand = max(0, par - sold.get(item_id, 0))
        if (branch_id, item_id) in FORCED_LOW_STOCK:
            on_hand = min(on_hand, int(par * 0.1))
        on_hand = max(0, on_hand + moved.get(item_id, 0))
        levels.append({
            "branchId": branch_id,
            "itemId": item_id,
            "itemName": m["name"],
            "onHand": on_hand,
            "parLevel": par,
            "isLowStock": on_hand < par * LOW_STOCK_RATIO,
            "lastUpdated": updated,
        })
    return levels


def sales_today(branch_id: int) -> dict:
    by_channel: dict[str, float] = {}
    count, revenue = 0, 0.0
    for o in orders_today(branch_id):
        if o["status"] == "cancelled":
            continue
        amount = o["totalAmount"] - REFUNDS.get(o["orderId"], {}).get("amount", 0.0)
        count += 1
        revenue += amount
        by_channel[o["channel"]] = round(by_channel.get(o["channel"], 0.0) + amount, 2)
    current = now()
    return {
        "branchId": branch_id,
        "businessDate": current.date().isoformat(),
        "orderCount": count,
        "revenue": round(revenue, 2),
        "avgTicket": round(revenue / count, 2) if count else 0.0,
        "byChannel": by_channel,
        "asOf": current.isoformat(),
    }


class Conflict(Exception):
    pass


def issue_refund(branch_id: int, order_id: int, reason: str, amount: float | None) -> dict:
    with _lock:
        order = find_order(branch_id, order_id)
        if order is None:
            raise KeyError(order_id)
        if order["status"] in ("refunded", "cancelled"):
            raise Conflict(f"Order {order_id} is {order['status']} and cannot be refunded")
        refund_amount = order["totalAmount"] if amount is None else round(amount, 2)
        if not 0 < refund_amount <= order["totalAmount"]:
            raise Conflict(f"Refund amount must be between 0.01 and {order['totalAmount']}")
        refund = {
            "refundId": f"RF-{uuid.uuid4().hex[:10].upper()}",
            "orderId": order_id,
            "amount": refund_amount,
            "reason": reason,
            "issuedAt": now().isoformat(),
        }
        REFUNDS[order_id] = refund
        return refund


def request_transfer(from_branch: int, to_branch: int, item_id: int, qty: int) -> dict:
    with _lock:
        if from_branch == to_branch:
            raise Conflict("fromBranchId and toBranchId must differ")
        available = next(s["onHand"] for s in stock_levels(from_branch) if s["itemId"] == item_id)
        if qty > available:
            raise Conflict(f"Branch {from_branch} only has {available} units of item {item_id}")
        transfer = {
            "transferId": f"TR-{uuid.uuid4().hex[:10].upper()}",
            "status": "requested",
            "fromBranchId": from_branch,
            "toBranchId": to_branch,
            "itemId": item_id,
            "qty": qty,
        }
        TRANSFERS.append(transfer)
        return transfer
