-- Which seller performs best?
-- Parameters: ? = start_date, ? = end_date, ? = seller_state

-- 0. Pre-filter orders to the requested date range and seller state
WITH filtered AS (
    SELECT
        oi.seller_id,
        oi.price,
        o.order_status,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN sellers s ON oi.seller_id = s.seller_id
    WHERE (? IS NULL OR o.order_purchase_timestamp::DATE >= ?)
      AND (? IS NULL OR o.order_purchase_timestamp::DATE <= ?)
      AND (? IS NULL OR s.seller_state = ?)
),

-- 1. Compute Revenue
revenue AS (
    SELECT seller_id, SUM(price) AS total_revenue, COUNT(*) AS total_items_sold
    FROM filtered
    GROUP BY seller_id
),

-- 2. Measure Delivery
delivery AS (
    SELECT seller_id,
        AVG(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date THEN 1 ELSE 0 END) AS on_time_rate
    FROM filtered
    WHERE order_delivered_customer_date IS NOT NULL
      AND order_status = 'delivered'
    GROUP BY seller_id
),

-- 3. Review Scores
reviews AS (
    SELECT oi.seller_id, AVG(r.review_score) AS avg_review
    FROM order_reviews r
    JOIN order_items oi ON r.order_id = oi.order_id
    GROUP BY oi.seller_id
),

-- 4. Cancellation Rate
cancellations AS (
    SELECT seller_id,
        AVG(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) AS cancel_rate
    FROM filtered
    GROUP BY seller_id
),

-- 5. Combine
combined AS (
    SELECT r.seller_id, r.total_revenue, r.total_items_sold,
        d.on_time_rate, rv.avg_review, c.cancel_rate
    FROM revenue r
    LEFT JOIN delivery d      ON r.seller_id = d.seller_id
    LEFT JOIN reviews rv      ON r.seller_id = rv.seller_id
    LEFT JOIN cancellations c ON r.seller_id = c.seller_id
),

-- 6. Rank -- composite score: lower is better
ranked AS (
    SELECT *,
        RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank,
        RANK() OVER (ORDER BY on_time_rate DESC)  AS delivery_rank,
        RANK() OVER (ORDER BY avg_review DESC)    AS review_rank,
        RANK() OVER (ORDER BY cancel_rate ASC)    AS cancel_rank,
        ROUND((
            RANK() OVER (ORDER BY total_revenue DESC) +
            RANK() OVER (ORDER BY on_time_rate DESC)  +
            RANK() OVER (ORDER BY avg_review DESC)    +
            RANK() OVER (ORDER BY cancel_rate ASC)
        ) / 4.0, 1) AS composite_score
    FROM combined
)

SELECT *
FROM ranked
ORDER BY composite_score ASC;
