"""Module 02 tools: historical analytics from Redshift `mcp` views.

Each tool follows a pattern in docs/sample-queries.md.
"""
from app import mcp
from lib.redshift import run_query
from lib.scoping import require_hq, scoped_branch
from lib.validation import ToolInputError, bounded_int, date_range, one_of

CATEGORIES = ["all", "chicken", "burger", "sides", "drinks", "dessert"]
DAY_TYPES = ["all", "weekday", "weekend"]


def _result(rows: list[dict], limit: int, note: str | None = None) -> dict:
    result = {"rows": rows, "row_count": len(rows), "truncated": len(rows) >= limit}
    if note:
        result["note"] = note
    return result


@mcp.tool()
def get_daily_branch_sales(branch_id: int, start_date: str, end_date: str) -> dict:
    """Daily order count, revenue (USD) and average ticket for one branch.

    Use for historical sales up to yesterday. For today's live sales use get_today_sales.
    If you only know the branch name, call find_branch first.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD, e.g. 2026-09-01.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    rows = run_query(
        """
        SELECT cal_date, branch_name, order_count, revenue, avg_ticket
        FROM mcp.v_daily_branch_sales
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY cal_date
        LIMIT 100
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end},
    )
    return _result(rows, 100, note)


@mcp.tool()
def get_top_branches(start_date: str, end_date: str, top_n: int = 10) -> dict:
    """Rank branches by total revenue (USD) over a date range. HQ users only.

    Use to compare branches, e.g. "which 10 branches sold the most in August".

    Args:
        start_date: First day, YYYY-MM-DD, e.g. 2026-08-01.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
        top_n: Number of branches to return, 1-50. Default 10.
    """
    require_hq("compare branches")
    start, end = date_range(start_date, end_date)
    top_n = bounded_int(top_n, "top_n", 1, 50)
    rows = run_query(
        f"""
        SELECT branch_id, branch_name, region,
               SUM(order_count) AS order_count,
               SUM(revenue)     AS revenue
        FROM mcp.v_daily_branch_sales
        WHERE cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        GROUP BY branch_id, branch_name, region
        ORDER BY revenue DESC
        LIMIT {top_n}
        """,  # top_n is a validated int; LIMIT does not accept bind parameters
        {"start_date": start, "end_date": end},
    )
    return _result(rows, top_n)


@mcp.tool()
def get_top_items(branch_id: int, start_date: str, end_date: str, top_n: int = 5) -> dict:
    """Best-selling menu items at one branch by units sold, with revenue (USD).

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
        top_n: Number of items to return, 1-20. Default 5.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    top_n = bounded_int(top_n, "top_n", 1, 20)
    rows = run_query(
        f"""
        SELECT item_id, item_name, category,
               SUM(qty_sold) AS qty_sold,
               SUM(revenue)  AS revenue
        FROM mcp.v_item_sales_daily
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        GROUP BY item_id, item_name, category
        ORDER BY qty_sold DESC
        LIMIT {top_n}
        """,  # top_n is a validated int; LIMIT does not accept bind parameters
        {"branch_id": branch_id, "start_date": start, "end_date": end},
    )
    return _result(rows, top_n, note)


@mcp.tool()
def get_peak_hours(branch_id: int, start_date: str, end_date: str, day_type: str = "all") -> dict:
    """Average orders and revenue (USD) per hour of day at one branch. Use for staffing questions.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
        day_type: "weekend", "weekday", or "all". Default "all".
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    day_type = one_of(day_type, "day_type", DAY_TYPES)
    rows = run_query(
        """
        SELECT h.order_hour,
               AVG(h.order_count::FLOAT)::DECIMAL(10,1) AS avg_orders,
               AVG(h.revenue)::DECIMAL(12,2)            AS avg_revenue
        FROM mcp.v_hourly_sales h
        JOIN mcp.v_daily_branch_sales d
          ON d.branch_id = h.branch_id AND d.cal_date = h.cal_date
        WHERE h.branch_id = CAST(:branch_id AS INT)
          AND h.cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
          AND (:day_type = 'all'
               OR (:day_type = 'weekend' AND d.is_weekend)
               OR (:day_type = 'weekday' AND NOT d.is_weekend))
        GROUP BY h.order_hour
        ORDER BY h.order_hour
        LIMIT 24
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end, "day_type": day_type},
    )
    return _result(rows, 24, note)


@mcp.tool()
def get_channel_mix(branch_id: int, start_date: str, end_date: str) -> dict:
    """Orders, revenue (USD) and revenue share by channel (dine_in, takeaway, drive_thru, delivery).

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    rows = run_query(
        """
        SELECT channel,
               SUM(order_count) AS order_count,
               SUM(revenue)     AS revenue,
               ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_pct
        FROM mcp.v_channel_mix_daily
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        GROUP BY channel
        ORDER BY revenue DESC
        LIMIT 10
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end},
    )
    return _result(rows, 10, note)


@mcp.tool()
def get_waste_by_item(branch_id: int, start_date: str, end_date: str, category: str = "all") -> dict:
    """Units wasted and waste value (USD) per menu item at one branch, highest value first.

    Historical only. For current stock on hand use get_current_stock.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
        category: "all" or one of chicken, burger, sides, drinks, dessert. Default "all".
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    category = one_of(category, "category", CATEGORIES)
    rows = run_query(
        """
        SELECT item_id, item_name, category,
               SUM(wasted_qty)  AS wasted_qty,
               SUM(waste_value) AS waste_value
        FROM mcp.v_inventory_daily
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
          AND (:category = 'all' OR category = :category)
        GROUP BY item_id, item_name, category
        ORDER BY waste_value DESC
        LIMIT 50
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end, "category": category},
    )
    return _result(rows, 50, note)


@mcp.tool()
def compare_weekend_weekday(branch_id: int, start_date: str, end_date: str) -> dict:
    """Average daily orders and revenue (USD) on weekends vs weekdays at one branch.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    rows = run_query(
        """
        SELECT CASE WHEN is_weekend THEN 'weekend' ELSE 'weekday' END AS day_type,
               AVG(order_count::FLOAT)::DECIMAL(10,1) AS avg_daily_orders,
               AVG(revenue)::DECIMAL(12,2)            AS avg_daily_revenue
        FROM mcp.v_daily_branch_sales
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        GROUP BY is_weekend
        LIMIT 2
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end},
    )
    return _result(rows, 2, note)


@mcp.tool()
def find_branch(name_fragment: str) -> dict:
    """Find branches whose name contains the given text. Use to turn a branch name into a branch_id.

    Args:
        name_fragment: Part of the branch name, e.g. "Riverside" or "old town". 2-50 characters.
    """
    name_fragment = name_fragment.strip()
    if not 2 <= len(name_fragment) <= 50:
        raise ToolInputError("name_fragment must be 2-50 characters")
    rows = run_query(
        """
        SELECT branch_id, branch_name, region, branch_format
        FROM mcp.v_branch
        WHERE LOWER(branch_name) LIKE '%' || LOWER(:name_fragment) || '%'
        ORDER BY branch_name
        LIMIT 10
        """,
        {"name_fragment": name_fragment},
    )
    return _result(rows, 10)
