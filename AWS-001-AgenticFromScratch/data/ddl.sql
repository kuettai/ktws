-- Restaurant mock data: base tables (schema rst)
-- Redshift Serverless. Run as admin.

CREATE SCHEMA IF NOT EXISTS rst;

CREATE TABLE IF NOT EXISTS rst.dim_branch (
    branch_id      INT          NOT NULL PRIMARY KEY,
    branch_name    VARCHAR(100) NOT NULL,
    region         VARCHAR(50)  NOT NULL,
    branch_format  VARCHAR(20)  NOT NULL,
    opened_date    DATE         NOT NULL
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS rst.dim_menu_item (
    item_id     INT           NOT NULL PRIMARY KEY,
    item_name   VARCHAR(100)  NOT NULL,
    category    VARCHAR(20)   NOT NULL,
    base_price  DECIMAL(8,2)  NOT NULL
) DISTSTYLE ALL;

CREATE TABLE IF NOT EXISTS rst.dim_date (
    date_key           INT         NOT NULL PRIMARY KEY,  -- YYYYMMDD
    cal_date           DATE        NOT NULL,
    day_of_week        SMALLINT    NOT NULL,              -- 1 = Monday
    day_name           VARCHAR(10) NOT NULL,
    week_of_year       SMALLINT    NOT NULL,
    month_num          SMALLINT    NOT NULL,
    month_name         VARCHAR(10) NOT NULL,
    quarter            SMALLINT    NOT NULL,
    year_num           SMALLINT    NOT NULL,
    is_weekend         BOOLEAN     NOT NULL,
    is_public_holiday  BOOLEAN     NOT NULL
) DISTSTYLE ALL SORTKEY (date_key);

CREATE TABLE IF NOT EXISTS rst.dim_customer (
    customer_id   INT          NOT NULL PRIMARY KEY,
    loyalty_tier  VARCHAR(10)  NOT NULL,  -- silver, gold, platinum
    joined_date   DATE         NOT NULL
);

CREATE TABLE IF NOT EXISTS rst.fact_orders (
    order_id      BIGINT         NOT NULL PRIMARY KEY,
    branch_id     INT            NOT NULL REFERENCES rst.dim_branch (branch_id),
    customer_id   INT                     REFERENCES rst.dim_customer (customer_id),
    date_key      INT            NOT NULL REFERENCES rst.dim_date (date_key),
    order_ts      TIMESTAMP      NOT NULL,
    channel       VARCHAR(20)    NOT NULL,  -- dine_in, takeaway, drive_thru, delivery
    total_amount  DECIMAL(12,2)  NOT NULL
) DISTKEY (order_id) SORTKEY (date_key, branch_id);

CREATE TABLE IF NOT EXISTS rst.fact_order_items (
    order_id    BIGINT         NOT NULL REFERENCES rst.fact_orders (order_id),
    line_no     SMALLINT       NOT NULL,
    item_id     INT            NOT NULL REFERENCES rst.dim_menu_item (item_id),
    qty         SMALLINT       NOT NULL,
    unit_price  DECIMAL(8,2)   NOT NULL,
    discount    DECIMAL(8,2)   NOT NULL,  -- absolute amount off the line
    PRIMARY KEY (order_id, line_no)
) DISTKEY (order_id) SORTKEY (order_id);

CREATE TABLE IF NOT EXISTS rst.fact_inventory_daily (
    branch_id     INT  NOT NULL REFERENCES rst.dim_branch (branch_id),
    item_id       INT  NOT NULL REFERENCES rst.dim_menu_item (item_id),
    date_key      INT  NOT NULL REFERENCES rst.dim_date (date_key),
    opening_qty   INT  NOT NULL,
    received_qty  INT  NOT NULL,
    sold_qty      INT  NOT NULL,
    wasted_qty    INT  NOT NULL,
    closing_qty   INT  NOT NULL,
    PRIMARY KEY (branch_id, item_id, date_key)
) SORTKEY (date_key, branch_id);
