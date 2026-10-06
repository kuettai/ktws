#!/usr/bin/env python3
"""Generate mock restaurant seed data as gzipped CSV for Redshift COPY.

Pure standard library. Output files match data/ddl.sql column order.

Usage:
    python generate_seed.py --out ./seed
    python generate_seed.py --out ./seed --branches 30 --days 180 --end-date 2026-09-30 --seed 42
    python generate_seed.py --out ./seed --reference-json ../mock-api/app/reference.json
    aws s3 cp ./seed s3://<SEED_BUCKET>/seed/ --recursive
"""
import argparse
import csv
import gzip
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

# (area, region) - branch name is "Branch <area>"
AREAS = [
    ("Riverside", "Central"), ("Harbor Point", "Central"), ("Old Town", "Lakeshore"),
    ("Maple Grove", "Lakeshore"), ("Union Square", "Lakeshore"), ("Lakeview", "Capital"),
    ("Westgate", "Capital"), ("Northfield", "Metro"), ("Eastwood", "Valley"),
    ("Southbank", "East Isles"), ("Hillcrest", "West Isles"), ("Bayside", "North"),
    ("Cedar Park", "Heritage Coast"), ("Market Street", "East"), ("Station Road", "Lakeshore"),
    ("Pine Hollow", "Lakeshore"), ("Midtown", "Lakeshore"), ("Airport", "Lakeshore"),
    ("University", "Lakeshore"), ("Seaside", "Lakeshore"), ("Greenfield", "Highlands"),
    ("Brookside", "Lakeshore"), ("Oakridge", "Capital"), ("Elm Plaza", "Metro"),
    ("Kingsway", "Metro"), ("Sunset Mall", "Valley"), ("Millbrook", "West Isles"),
    ("Stonebridge", "East Isles"), ("Willow Creek", "Lakeshore"), ("Central Plaza", "Central"),
]
FORMATS = [("mall", 0.35), ("street", 0.30), ("drive_thru", 0.25), ("kiosk", 0.10)]
# Channel weights per branch format
CHANNELS = {
    "mall":       {"dine_in": 0.55, "takeaway": 0.30, "drive_thru": 0.00, "delivery": 0.15},
    "street":     {"dine_in": 0.40, "takeaway": 0.30, "drive_thru": 0.00, "delivery": 0.30},
    "drive_thru": {"dine_in": 0.20, "takeaway": 0.15, "drive_thru": 0.45, "delivery": 0.20},
    "kiosk":      {"dine_in": 0.00, "takeaway": 0.80, "drive_thru": 0.00, "delivery": 0.20},
}
# (item_id, name, category, base_price, popularity weight, perishable)
MENU = [
    (1,  "Original Chicken 2pc",   "chicken", 12.90, 10, True),
    (2,  "Spicy Chicken 2pc",      "chicken", 13.40, 9,  True),
    (3,  "Chicken Wings 6pc",      "chicken", 15.90, 6,  True),
    (4,  "Chicken Nuggets 9pc",    "chicken", 11.50, 7,  True),
    (5,  "Classic Burger",         "burger",  9.90,  8,  True),
    (6,  "Double Cheese Burger",   "burger",  13.90, 6,  True),
    (7,  "Spicy Chicken Burger",   "burger",  11.90, 7,  True),
    (8,  "Fish Burger",            "burger",  10.90, 3,  True),
    (9,  "Fries Regular",          "sides",   4.90,  9,  True),
    (10, "Fries Large",            "sides",   6.50,  6,  True),
    (11, "Coleslaw",               "sides",   3.90,  4,  True),
    (12, "Mashed Potato",          "sides",   3.90,  4,  True),
    (13, "Corn Cup",               "sides",   4.50,  3,  True),
    (14, "Cola Regular",           "drinks",  3.90,  9,  False),
    (15, "Cola Large",             "drinks",  4.90,  5,  False),
    (16, "Iced Lemon Tea",         "drinks",  4.50,  6,  False),
    (17, "Mineral Water",          "drinks",  2.50,  3,  False),
    (18, "Sundae Chocolate",       "dessert", 4.90,  4,  True),
    (19, "Egg Tart",               "dessert", 3.50,  4,  True),
    (20, "Apple Pie",              "dessert", 4.20,  3,  True),
]
# Fixed-date public holidays in range (fictional calendar). Extend as needed.
PUBLIC_HOLIDAYS = {date(2026, 5, 1), date(2026, 6, 15), date(2026, 9, 7)}
# Hour-of-day weights, opening 07:00 - 23:00
HOUR_WEIGHTS = {7: 2, 8: 3, 9: 3, 10: 3, 11: 6, 12: 10, 13: 9, 14: 5, 15: 4,
                16: 4, 17: 6, 18: 9, 19: 10, 20: 8, 21: 5, 22: 3}
LOYALTY_TIERS = [("silver", 0.65), ("gold", 0.28), ("platinum", 0.07)]
MEMBER_SHARE = 0.6
AVG_LINES = 2.4
UNITS_PER_ORDER = 4.0  # ~2.9 lines x ~1.4 qty, used for par levels


def weighted(rng, pairs):
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights, k=1)[0]


def writer(out_dir, name, header):
    f = gzip.open(out_dir / f"{name}.csv.gz", "wt", newline="")
    w = csv.writer(f)
    w.writerow(header)
    return f, w


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("seed"))
    p.add_argument("--branches", type=int, default=30)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 9, 30))
    p.add_argument("--avg-orders", type=int, default=120, help="Average orders per branch per day")
    p.add_argument("--customers", type=int, default=20000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--reference-json", type=Path,
                   help="Also write branch/menu reference data for the mock API, e.g. ../mock-api/app/reference.json")
    args = p.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    start = args.end_date - timedelta(days=args.days - 1)
    dates = [start + timedelta(days=i) for i in range(args.days)]

    # dim_menu_item
    f, w = writer(args.out, "dim_menu_item", ["item_id", "item_name", "category", "base_price"])
    for item_id, name, cat, price, _, _ in MENU:
        w.writerow([item_id, name, cat, f"{price:.2f}"])
    f.close()

    # dim_branch
    branches = []
    f, w = writer(args.out, "dim_branch", ["branch_id", "branch_name", "region", "branch_format", "opened_date"])
    for i in range(1, args.branches + 1):
        area, region = AREAS[(i - 1) % len(AREAS)]
        fmt = weighted(rng, FORMATS)
        opened = date(2015, 1, 1) + timedelta(days=rng.randint(0, 3000))
        traffic = rng.uniform(0.6, 1.5)
        branches.append({"id": i, "name": f"Branch {area}", "region": region, "format": fmt, "traffic": traffic})
        w.writerow([i, f"Branch {area}", region, fmt, opened.isoformat()])
    f.close()

    # dim_date
    f, w = writer(args.out, "dim_date", ["date_key", "cal_date", "day_of_week", "day_name", "week_of_year",
                                         "month_num", "month_name", "quarter", "year_num",
                                         "is_weekend", "is_public_holiday"])
    for d in dates:
        w.writerow([d.strftime("%Y%m%d"), d.isoformat(), d.isoweekday(), d.strftime("%A"),
                    d.isocalendar()[1], d.month, d.strftime("%B"), (d.month - 1) // 3 + 1, d.year,
                    str(d.isoweekday() >= 6).lower(), str(d in PUBLIC_HOLIDAYS).lower()])
    f.close()

    # dim_customer
    f, w = writer(args.out, "dim_customer", ["customer_id", "loyalty_tier", "joined_date"])
    for cid in range(1, args.customers + 1):
        joined = date(2019, 1, 1) + timedelta(days=rng.randint(0, (start - date(2019, 1, 1)).days))
        w.writerow([cid, weighted(rng, LOYALTY_TIERS), joined.isoformat()])
    f.close()

    # Facts
    item_pairs = [(m, m[4]) for m in MENU]
    total_weight = sum(m[4] for m in MENU)
    hour_pairs = list(HOUR_WEIGHTS.items())

    fo, wo = writer(args.out, "fact_orders", ["order_id", "branch_id", "customer_id", "date_key",
                                              "order_ts", "channel", "total_amount"])
    fl, wl = writer(args.out, "fact_order_items", ["order_id", "line_no", "item_id", "qty",
                                                   "unit_price", "discount"])
    fi, wi = writer(args.out, "fact_inventory_daily", ["branch_id", "item_id", "date_key", "opening_qty",
                                                       "received_qty", "sold_qty", "wasted_qty", "closing_qty"])

    # Par level per branch/item: expected daily units x 1.6 (covers weekend uplift + buffer)
    par = {}
    closing = {}
    for b in branches:
        for m in MENU:
            expected = args.avg_orders * b["traffic"] * UNITS_PER_ORDER * m[4] / total_weight
            par[(b["id"], m[0])] = math.ceil(expected * 1.6)
            closing[(b["id"], m[0])] = par[(b["id"], m[0])] // 2

    order_id = 0
    for d in dates:
        date_key = d.strftime("%Y%m%d")
        day_factor = 1.3 if d.isoweekday() >= 6 else 1.0
        if d in PUBLIC_HOLIDAYS:
            day_factor *= 1.5
        for b in branches:
            sold = {m[0]: 0 for m in MENU}
            channels = [(c, wt) for c, wt in CHANNELS[b["format"]].items() if wt > 0]
            n_orders = max(10, int(rng.gauss(args.avg_orders * b["traffic"] * day_factor, 15)))
            for _ in range(n_orders):
                order_id += 1
                hour = weighted(rng, hour_pairs)
                ts = datetime(d.year, d.month, d.day, hour, rng.randint(0, 59), rng.randint(0, 59))
                customer_id = rng.randint(1, args.customers) if rng.random() < MEMBER_SHARE else ""
                n_lines = max(1, min(6, int(rng.expovariate(1 / AVG_LINES)) + 1))
                total = 0.0
                for line_no in range(1, n_lines + 1):
                    m = weighted(rng, item_pairs)
                    qty = 1 if rng.random() < 0.8 else rng.randint(2, 4)
                    discount = round(qty * m[3] * 0.10, 2) if rng.random() < 0.10 else 0.0
                    total += qty * m[3] - discount
                    sold[m[0]] += qty
                    wl.writerow([order_id, line_no, m[0], qty, f"{m[3]:.2f}", f"{discount:.2f}"])
                wo.writerow([order_id, b["id"], customer_id, date_key,
                             ts.strftime("%Y-%m-%d %H:%M:%S"), weighted(rng, channels), f"{total:.2f}"])

            for m in MENU:
                key = (b["id"], m[0])
                opening = closing[key]
                received = max(0, par[key] - opening)
                shortfall = sold[m[0]] - (opening + received)
                if shortfall > 0:  # emergency top-up, keeps closing >= 0
                    received += shortfall
                remaining = opening + received - sold[m[0]]
                wasted = int(remaining * rng.uniform(0.10, 0.30)) if m[5] else 0
                closing[key] = remaining - wasted
                wi.writerow([b["id"], m[0], date_key, opening, received, sold[m[0]], wasted, closing[key]])

    for f in (fo, fl, fi):
        f.close()
    if args.reference_json:
        reference = {
            "branches": [{"branchId": b["id"], "name": b["name"], "region": b["region"], "format": b["format"],
                          "traffic": round(b["traffic"], 3)} for b in branches],
            "menu": [{"itemId": m[0], "name": m[1], "category": m[2], "price": m[3], "popularity": m[4],
                      "perishable": m[5]} for m in MENU],
            "parLevels": {f"{b}:{i}": v for (b, i), v in par.items()},
            "hourWeights": HOUR_WEIGHTS,
            "channels": CHANNELS,
            "avgOrders": args.avg_orders,
        }
        args.reference_json.parent.mkdir(parents=True, exist_ok=True)
        args.reference_json.write_text(json.dumps(reference, indent=2))
        print(f"Wrote reference data to {args.reference_json}")
    print(f"Wrote seed files to {args.out}/ ({order_id} orders, {len(dates)} days, {len(branches)} branches)")


if __name__ == "__main__":
    main()
