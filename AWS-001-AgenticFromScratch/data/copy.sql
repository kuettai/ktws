-- Load seed files produced by generate_seed.py.
-- Replace <SEED_BUCKET>. Requires a default IAM role on the namespace with S3 read.

COPY rst.dim_branch           FROM 's3://<SEED_BUCKET>/seed/dim_branch.csv.gz'           IAM_ROLE default CSV GZIP IGNOREHEADER 1 DATEFORMAT 'auto';
COPY rst.dim_menu_item        FROM 's3://<SEED_BUCKET>/seed/dim_menu_item.csv.gz'        IAM_ROLE default CSV GZIP IGNOREHEADER 1;
COPY rst.dim_date             FROM 's3://<SEED_BUCKET>/seed/dim_date.csv.gz'             IAM_ROLE default CSV GZIP IGNOREHEADER 1 DATEFORMAT 'auto';
COPY rst.dim_customer         FROM 's3://<SEED_BUCKET>/seed/dim_customer.csv.gz'         IAM_ROLE default CSV GZIP IGNOREHEADER 1 DATEFORMAT 'auto';
COPY rst.fact_orders          FROM 's3://<SEED_BUCKET>/seed/fact_orders.csv.gz'          IAM_ROLE default CSV GZIP IGNOREHEADER 1 TIMEFORMAT 'auto' EMPTYASNULL;
COPY rst.fact_order_items     FROM 's3://<SEED_BUCKET>/seed/fact_order_items.csv.gz'     IAM_ROLE default CSV GZIP IGNOREHEADER 1;
COPY rst.fact_inventory_daily FROM 's3://<SEED_BUCKET>/seed/fact_inventory_daily.csv.gz' IAM_ROLE default CSV GZIP IGNOREHEADER 1;

-- Sanity checks
SELECT 'branches' AS t, COUNT(*) FROM rst.dim_branch
UNION ALL SELECT 'items',       COUNT(*) FROM rst.dim_menu_item
UNION ALL SELECT 'dates',       COUNT(*) FROM rst.dim_date
UNION ALL SELECT 'customers',   COUNT(*) FROM rst.dim_customer
UNION ALL SELECT 'orders',      COUNT(*) FROM rst.fact_orders
UNION ALL SELECT 'order_items', COUNT(*) FROM rst.fact_order_items
UNION ALL SELECT 'inventory',   COUNT(*) FROM rst.fact_inventory_daily;
