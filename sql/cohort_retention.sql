-- What percentage of customers return within 30, 60, and 90 days of their first purchase?
-- Parameters: ? = start_date, ? = end_date (pass NULL to skip filtering)
-- The date filter applies to the FIRST purchase, so we analyze cohorts who started in the window

-- 1. Identify each customer's first purchase date
-- customer_unique_id tracks the same person across multiple customer_ids (Olist quirk)
WITH first_order AS (
    SELECT
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp) AS first_purchase
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE (?::DATE IS NULL OR o.order_purchase_timestamp::DATE >= ?::DATE)
      AND (?::DATE IS NULL OR o.order_purchase_timestamp::DATE <= ?::DATE)
    GROUP BY c.customer_unique_id
),

-- 2. Combine all future orders with each customer's known first purchase date
-- This produces one row per order, so we can measure how long after first purchase each one occurred
all_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_purchase_timestamp,
        f.first_purchase
    FROM orders o
    JOIN customers c  ON o.customer_id = c.customer_id
    JOIN first_order f ON c.customer_unique_id = f.customer_unique_id
),

-- 3. Calculate days elapsed since first purchase for every order
-- days_since_first = 0 means it IS the first purchase; > 0 means a return visit
time_diffs AS (
    SELECT
        customer_unique_id,
        DATE_DIFF(
            'day',
            CAST(first_purchase AS DATE),
            CAST(order_purchase_timestamp AS DATE)
        ) AS days_since_first
    FROM all_orders
),

-- 4. Flag whether each customer returned within each retention window
-- MAX() collapses multiple orders per customer into a single 0/1 flag per window
retention_flags AS (
    SELECT
        customer_unique_id,
        MAX(CASE WHEN days_since_first > 0 AND days_since_first <= 30 THEN 1 ELSE 0 END) AS retained_30,
        MAX(CASE WHEN days_since_first > 0 AND days_since_first <= 60 THEN 1 ELSE 0 END) AS retained_60,
        MAX(CASE WHEN days_since_first > 0 AND days_since_first <= 90 THEN 1 ELSE 0 END) AS retained_90
    FROM time_diffs
    GROUP BY customer_unique_id
)

-- Final: average the flags to get retention rates (AVG of 0/1 = proportion)
SELECT
    COUNT(*)                              AS total_customers,
    ROUND(AVG(retained_30) * 100, 2)     AS retention_30_pct,
    ROUND(AVG(retained_60) * 100, 2)     AS retention_60_pct,
    ROUND(AVG(retained_90) * 100, 2)     AS retention_90_pct
FROM retention_flags;
