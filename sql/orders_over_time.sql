-- How has order volume and revenue changed over time?
-- Parameters: ? = start_date, ? = end_date (pass NULL to skip filtering)

-- Aggregate orders by month to show business growth trends
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', order_purchase_timestamp::DATE) AS order_month,
        COUNT(*) AS total_orders,
        ROUND(SUM(oi.price), 2) AS total_revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status != 'canceled'
      AND (?::DATE IS NULL OR o.order_purchase_timestamp::DATE >= ?::DATE)
      AND (?::DATE IS NULL OR o.order_purchase_timestamp::DATE <= ?::DATE)
    GROUP BY DATE_TRUNC('month', order_purchase_timestamp::DATE)
)

SELECT *
FROM monthly
ORDER BY order_month ASC;
