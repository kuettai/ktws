# Approved Query Patterns

Every MCP tool built in the workshop should follow one of these patterns.

Conventions:

- Parameters use Redshift Data API named parameters: `:name`. Values are always passed separately, never formatted into the SQL string.
- Data API parameter values are strings, so cast explicitly: `CAST(:start_date AS DATE)`.
- Explicit column list. Always `LIMIT` with a literal integer (validate any user-controlled limit in Python first).
- Date ranges are inclusive and must be bounded (max 93 days unless stated).

---

## 1. Revenue for one branch over a date range

Business question: *"How much did branch 12 make last week?"*

```sql
SELECT cal_date, branch_name, order_count, revenue, avg_ticket
FROM mcp.v_daily_branch_sales
WHERE branch_id = CAST(:branch_id AS INT)
  AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
ORDER BY cal_date
LIMIT 100;
```

Parameters: `branch_id`, `start_date`, `end_date`

## 2. Top-N branches by revenue

Business question: *"Which 10 branches sold the most in August?"*

```sql
SELECT branch_id, branch_name, region,
       SUM(order_count) AS order_count,
       SUM(revenue)     AS revenue
FROM mcp.v_daily_branch_sales
WHERE cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
GROUP BY branch_id, branch_name, region
ORDER BY revenue DESC
LIMIT {top_n};  -- top_n validated in Python as int 1-50, then inserted
```

Parameters: `start_date`, `end_date`. `top_n` (1-50) is validated in Python and inlined: `LIMIT` does not accept bind parameters.

## 3. Best-selling items at a branch

Business question: *"What are the top 5 items at branch 12 this month?"*

```sql
SELECT item_id, item_name, category,
       SUM(qty_sold) AS qty_sold,
       SUM(revenue)  AS revenue
FROM mcp.v_item_sales_daily
WHERE branch_id = CAST(:branch_id AS INT)
  AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
GROUP BY item_id, item_name, category
ORDER BY qty_sold DESC
LIMIT {top_n};  -- top_n validated in Python as int 1-50, then inserted
```

## 4. Peak hours

Business question: *"When is branch 12 busiest on weekends?"* `day_type` is `all`, `weekday` or `weekend`.

```sql
SELECT h.order_hour,
       AVG(h.order_count) AS avg_orders,
       AVG(h.revenue)     AS avg_revenue
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
LIMIT 24;
```

## 5. Channel mix

Business question: *"What share of branch 12 sales is delivery?"*

```sql
SELECT channel,
       SUM(order_count) AS order_count,
       SUM(revenue)     AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_pct
FROM mcp.v_channel_mix_daily
WHERE branch_id = CAST(:branch_id AS INT)
  AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
GROUP BY channel
ORDER BY revenue DESC
LIMIT 10;
```

## 6. Waste by item

Business question: *"How much chicken did branch 12 waste last month?"*

```sql
SELECT item_id, item_name, category,
       SUM(wasted_qty)  AS wasted_qty,
       SUM(waste_value) AS waste_value
FROM mcp.v_inventory_daily
WHERE branch_id = CAST(:branch_id AS INT)
  AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
  AND (:category = 'all' OR category = :category)
GROUP BY item_id, item_name, category
ORDER BY waste_value DESC
LIMIT 50;
```

Parameters: `branch_id`, `start_date`, `end_date`, `category` (`all` or a category)

## 7. Weekend vs weekday comparison

```sql
SELECT is_weekend,
       AVG(order_count) AS avg_daily_orders,
       AVG(revenue)     AS avg_daily_revenue
FROM mcp.v_daily_branch_sales
WHERE branch_id = CAST(:branch_id AS INT)
  AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
GROUP BY is_weekend
LIMIT 2;
```

## 8. Resolve branch name to ID

Business question: *"Find the branch called 'Riverside'."* Used by the model before calling other tools.

```sql
SELECT branch_id, branch_name, region, branch_format
FROM mcp.v_branch
WHERE LOWER(branch_name) LIKE '%' || LOWER(:name_fragment) || '%'
ORDER BY branch_name
LIMIT 10;
```

---

## Anti-patterns (use in review exercises)

```python
# BAD: string formatting = SQL injection
sql = f"SELECT ... WHERE branch_id = {branch} AND cal_date = '{date}'"

# BAD: base table, SELECT *, no LIMIT
sql = "SELECT * FROM rst.fact_orders WHERE branch_id = :branch_id"

# BAD: unbounded date range scans 180 days x 30 branches every call
sql = "SELECT ... FROM mcp.v_item_sales_daily WHERE branch_id = :branch_id"

# BAD: aggregate without GROUP BY (the original whiteboard example)
sql = "SELECT SUM(o.amount), b.name FROM orders o JOIN branch b ... WHERE ..."
```
