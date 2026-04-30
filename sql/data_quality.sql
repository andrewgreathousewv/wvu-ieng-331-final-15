-- Data Quality Audit
-- Using the Olist dataset (9 tables)
-- This file runs four separate quality checks. Execute each block independently.

-- PART 1: Row counts per table
-- COUNT(*) counts every row including NULLs, we used to verify data was loaded correctly
-- UNION ALL stacks the results from all 9 tables into a single output

WITH row_counts AS (
    SELECT 'category_translation' AS table_name, COUNT(*) AS row_count FROM category_translation
    UNION ALL
    SELECT 'customers',    COUNT(*) FROM customers
    UNION ALL
    SELECT 'geolocation',  COUNT(*) FROM geolocation
    UNION ALL
    SELECT 'order_items',  COUNT(*) FROM order_items
    UNION ALL
    SELECT 'order_payments', COUNT(*) FROM order_payments
    UNION ALL
    SELECT 'order_reviews', COUNT(*) FROM order_reviews
    UNION ALL
    SELECT 'orders',       COUNT(*) FROM orders
    UNION ALL
    SELECT 'products',     COUNT(*) FROM products
    UNION ALL
    SELECT 'sellers',      COUNT(*) FROM sellers
)
SELECT * FROM row_counts;


-- PART 2: NULL rates for key columns
-- Key columns are the foreign/primary keys that link tables together
-- SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END) counts how many rows are missing a value
-- A NULL primary key is a serious data integrity problem

WITH null_checks AS (
    SELECT
        'orders'      AS table_name,
        COUNT(*)      AS total_rows,
        SUM(CASE WHEN order_id    IS NULL THEN 1 ELSE 0 END) AS null_order_id,
        SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS null_customer_id,
        0 AS null_product_id,
        0 AS null_seller_id
    FROM orders
    UNION ALL
    SELECT
        'customers',
        COUNT(*),
        0,
        SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END),
        0,
        0
    FROM customers
    UNION ALL
    SELECT
        'products',
        COUNT(*),
        0,
        0,
        SUM(CASE WHEN product_id IS NULL THEN 1 ELSE 0 END),
        0
    FROM products
    UNION ALL
    SELECT
        'sellers',
        COUNT(*),
        0,
        0,
        0,
        SUM(CASE WHEN seller_id IS NULL THEN 1 ELSE 0 END)
    FROM sellers
)
SELECT * FROM null_checks;


-- PART 3: Orphaned foreign keys
-- A LEFT JOIN keeps every row from the left table even without a match on the right
-- WHERE right.id IS NULL isolates rows where no match was found — these are "orphans"
-- Orphans mean a referenced entity (customer, product, etc.) is missing from its home table

WITH orphan_customer_id AS (
    SELECT o.customer_id
    FROM orders AS o
    LEFT JOIN customers AS c ON o.customer_id = c.customer_id
    WHERE c.customer_id IS NULL
),
orphan_order_id AS (
    SELECT oi.order_id
    FROM order_items AS oi
    LEFT JOIN orders AS o ON oi.order_id = o.order_id
    WHERE o.order_id IS NULL
),
orphan_product_id AS (
    SELECT oi.product_id
    FROM order_items AS oi
    LEFT JOIN products AS p ON oi.product_id = p.product_id
    WHERE p.product_id IS NULL
),
orphan_seller_id AS (
    SELECT oi.seller_id
    FROM order_items AS oi
    LEFT JOIN sellers AS s ON oi.seller_id = s.seller_id
    WHERE s.seller_id IS NULL
)
SELECT
    (SELECT COUNT(*) FROM orphan_customer_id) AS orphan_customer_id,
    (SELECT COUNT(*) FROM orphan_order_id)    AS orphan_order_id,
    (SELECT COUNT(*) FROM orphan_product_id)  AS orphan_product_id,
    (SELECT COUNT(*) FROM orphan_seller_id)   AS orphan_seller_id;


-- PART 4: Date range coverage and gaps
-- generate_series creates one row per calendar day between first and last order date
-- A LEFT JOIN to actual order dates exposes days where no orders were placed (gaps)
-- Gaps might indicate data loading errors or genuine business closures

WITH date_range AS (
    SELECT
        MIN(DATE(order_purchase_timestamp)) AS start_date,
        MAX(DATE(order_purchase_timestamp)) AS end_date
    FROM orders
),
all_dates AS (
    SELECT *
    FROM generate_series(
        (SELECT start_date FROM date_range),
        (SELECT end_date   FROM date_range),
        INTERVAL 1 DAY
    ) AS t(date)
),
order_dates AS (
    SELECT DISTINCT DATE(order_purchase_timestamp) AS date
    FROM orders
)
SELECT
    (SELECT start_date FROM date_range) AS start_date,
    (SELECT end_date   FROM date_range) AS end_date,
    COUNT(*) AS missing_days
FROM all_dates
LEFT JOIN order_dates ON all_dates.date = order_dates.date
WHERE order_dates.date IS NULL;

-- PART 5: Duplicate detection
-- GROUP BY + HAVING COUNT(*) > 1 finds any id that appears more than once
-- Duplicate primary keys break aggregations and joins, inflating counts and totals
-- order_reviews was added after initial run revealed duplicates there

WITH duplicate_orders AS (
    SELECT order_id,   COUNT(*) AS count FROM orders        GROUP BY order_id   HAVING COUNT(*) > 1
),
duplicate_customers AS (
    SELECT customer_id, COUNT(*) AS counnt FROM customers    GROUP BY customer_id HAVING COUNT(*) > 1
),
duplicate_products AS (
    SELECT product_id,  COUNT(*) AS count FROM products     GROUP BY product_id  HAVING COUNT(*) > 1
),
duplicate_sellers AS (
    SELECT seller_id,   COUNT(*) AS countnt FROM sellers      GROUP BY seller_id   HAVING COUNT(*) > 1
),
duplicate_reviews AS (
    SELECT review_id,   COUNT(*) AS count FROM order_reviews GROUP BY review_id  HAVING COUNT(*) > 1
)
SELECT
    (SELECT COUNT(*) FROM duplicate_orders)    AS duplicate_orders,
    (SELECT COUNT(*) FROM duplicate_customers) AS duplicate_customers,
    (SELECT COUNT(*) FROM duplicate_products)  AS duplicate_products,
    (SELECT COUNT(*) FROM duplicate_sellers)   AS duplicate_sellers,
    (SELECT COUNT(*) FROM duplicate_reviews)   AS duplicate_reviews;
-- End of data_quality refactored query
-- Edited commit comments
