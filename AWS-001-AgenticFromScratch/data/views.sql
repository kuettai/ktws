-- Curated views for MCP tools (schema mcp).
-- MCP server role may SELECT these views only. Standard (non late-binding) views run with the
-- view owner's privileges, but Redshift still requires USAGE on schema rst for the reader:
-- see grants.sql (USAGE only, no SELECT, so rst tables stay unreadable directly).
-- Changed a view? Update docs/data-dictionary.md too: mcp-server tests/test_data_dictionary.py checks it.

CREATE SCHEMA IF NOT EXISTS mcp;

CREATE OR REPLACE VIEW mcp.v_branch AS
SELECT branch_id, branch_name, region, branch_format, opened_date
FROM rst.dim_branch;

CREATE OR REPLACE VIEW mcp.v_menu_item AS
SELECT item_id, item_name, category, base_price
FROM rst.dim_menu_item;

CREATE OR REPLACE VIEW mcp.v_daily_branch_sales AS
SELECT d.cal_date,
       b.branch_id,
       b.branch_name,
       b.region,
       b.branch_format,
       d.is_weekend,
       d.is_public_holiday,
       COUNT(*)                                        AS order_count,
       SUM(o.total_amount)::DECIMAL(14,2)              AS revenue,
       (SUM(o.total_amount) / COUNT(*))::DECIMAL(10,2) AS avg_ticket
FROM rst.fact_orders o
JOIN rst.dim_branch b ON b.branch_id = o.branch_id
JOIN rst.dim_date   d ON d.date_key  = o.date_key
GROUP BY d.cal_date, b.branch_id, b.branch_name, b.region, b.branch_format,
         d.is_weekend, d.is_public_holiday;

CREATE OR REPLACE VIEW mcp.v_item_sales_daily AS
SELECT d.cal_date,
       o.branch_id,
       m.item_id,
       m.item_name,
       m.category,
       SUM(li.qty)                                          AS qty_sold,
       SUM(li.qty * li.unit_price - li.discount)::DECIMAL(14,2) AS revenue
FROM rst.fact_order_items li
JOIN rst.fact_orders   o ON o.order_id = li.order_id
JOIN rst.dim_menu_item m ON m.item_id  = li.item_id
JOIN rst.dim_date      d ON d.date_key = o.date_key
GROUP BY d.cal_date, o.branch_id, m.item_id, m.item_name, m.category;

CREATE OR REPLACE VIEW mcp.v_hourly_sales AS
SELECT d.cal_date,
       o.branch_id,
       EXTRACT(HOUR FROM o.order_ts)::INT  AS order_hour,
       COUNT(*)                            AS order_count,
       SUM(o.total_amount)::DECIMAL(14,2)  AS revenue
FROM rst.fact_orders o
JOIN rst.dim_date d ON d.date_key = o.date_key
GROUP BY d.cal_date, o.branch_id, EXTRACT(HOUR FROM o.order_ts);

CREATE OR REPLACE VIEW mcp.v_channel_mix_daily AS
SELECT d.cal_date,
       o.branch_id,
       o.channel,
       COUNT(*)                            AS order_count,
       SUM(o.total_amount)::DECIMAL(14,2)  AS revenue
FROM rst.fact_orders o
JOIN rst.dim_date d ON d.date_key = o.date_key
GROUP BY d.cal_date, o.branch_id, o.channel;

CREATE OR REPLACE VIEW mcp.v_inventory_daily AS
SELECT d.cal_date,
       i.branch_id,
       m.item_id,
       m.item_name,
       m.category,
       i.opening_qty,
       i.received_qty,
       i.sold_qty,
       i.wasted_qty,
       i.closing_qty,
       (i.wasted_qty * m.base_price)::DECIMAL(12,2) AS waste_value
FROM rst.fact_inventory_daily i
JOIN rst.dim_menu_item m ON m.item_id  = i.item_id
JOIN rst.dim_date      d ON d.date_key = i.date_key;

CREATE OR REPLACE VIEW mcp.v_loyalty_tier_sales_daily AS
SELECT d.cal_date,
       o.branch_id,
       COALESCE(c.loyalty_tier, 'none')    AS loyalty_tier,
       COUNT(*)                            AS order_count,
       SUM(o.total_amount)::DECIMAL(14,2)  AS revenue
FROM rst.fact_orders o
JOIN rst.dim_date          d ON d.date_key    = o.date_key
LEFT JOIN rst.dim_customer c ON c.customer_id = o.customer_id
GROUP BY d.cal_date, o.branch_id, COALESCE(c.loyalty_tier, 'none');

-- Optional for performance: convert the heavier views to materialized views
-- with AUTO REFRESH YES if Day 1 queries feel slow on Serverless base RPU.
