-- 1 Join orders with customers
-- Filtering to only delivered orders
WITH delivery_times AS (
    SELECT
        o.order_id,
        c.customer_state,
        DATE_DIFF('day', o.order_purchase_timestamp::DATE, o.order_delivered_customer_date::DATE) AS actual_days,
        DATE_DIFF('day', o.order_purchase_timestamp::DATE, o.order_estimated_delivery_date::DATE)  AS estimated_days
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_delivered_customer_date IS NOT NULL
      AND o.order_status = 'delivered'
),

-- 2 Compute actual delivery
-- Find the actual vs. estimated delivery days using DATE_DIFF from purchase timestamp to each respective date
-- And 3 Aggregate by state
-- Calculate actual vs estimated days, avg delays, and % orders that come late
comparison AS (
    SELECT
        customer_state,
        COUNT(*)                            AS total_orders,
        ROUND(AVG(actual_days), 1)          AS avg_actual_days,
        ROUND(AVG(estimated_days), 1)       AS avg_estimated_days,
        ROUND(AVG(actual_days - estimated_days), 1) AS avg_delay_days,
        ROUND(SUM(CASE WHEN actual_days > estimated_days THEN 1 ELSE 0 END)
              * 100.0 / COUNT(*), 1)        AS pct_late
    FROM delivery_times
    GROUP BY customer_state
)

SELECT *
FROM comparison
ORDER BY avg_delay_days DESC;
