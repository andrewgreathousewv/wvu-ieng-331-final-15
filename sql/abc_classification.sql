-- Which products fall into A, B, and C categories based on revenue contribution?
-- Parameters: ? = start_date, ? = end_date (pass NULL to skip filtering)

-- 1. Compute Revenue per product
-- Sums all order_items prices grouped by product, joins to grab category name
-- Date filters are applied here so ABC tiers reflect the chosen time window
WITH product_revenue AS (
    SELECT
        oi.product_id,
        p.product_category_name,
        SUM(oi.price) AS revenue,
        COUNT(*)      AS units_sold
    FROM order_items oi
    LEFT JOIN products p ON oi.product_id = p.product_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE (?::DATE IS NULL OR o.order_purchase_timestamp::DATE >= ?::DATE)
      AND (?::DATE IS NULL OR o.order_purchase_timestamp::DATE <= ?::DATE)
    GROUP BY oi.product_id, p.product_category_name
),

-- 2. Calculate cumulative revenue using window functions
-- SUM() OVER () with no partition gives the grand total across all products
-- SUM() OVER (ORDER BY revenue DESC ...) accumulates revenue from highest to lowest
ranked_products AS (
    SELECT *,
        SUM(revenue) OVER ()                                                       AS total_revenue,
        SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING
                                                         AND CURRENT ROW)          AS cumulative_revenue
    FROM product_revenue
),

-- 3. Assign A, B, and C tiers based on cumulative % contribution
-- A = top 80% of revenue, B = next 15% (up to 95%), C = remaining 5%
-- This follows Pareto/ABC analysis logic used in inventory management
classified AS (
    SELECT
        product_id,
        product_category_name,
        revenue,
        units_sold,
        ROUND(revenue / total_revenue * 100, 4)            AS pct_of_revenue,
        ROUND(cumulative_revenue / total_revenue * 100, 4) AS cumulative_pct,
        CASE
            WHEN cumulative_revenue / total_revenue <= 0.80 THEN 'A'
            WHEN cumulative_revenue / total_revenue <= 0.95 THEN 'B'
            ELSE 'C'
        END AS abc_class
    FROM ranked_products
)

-- 4. Tier Summary
-- Aggregate results by class to show how many products and how much revenue fall in each tier
SELECT
    abc_class,
    COUNT(*)                      AS product_count,
    ROUND(SUM(revenue), 2)        AS total_revenue,
    ROUND(SUM(pct_of_revenue), 2) AS pct_of_total_revenue
FROM classified
GROUP BY abc_class
ORDER BY abc_class;
