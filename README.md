# wvu-ieng331-m2-15
# Milestone 2: Python Pipeline

**Team 15**: Andrew Greathouse, Brady Stafford

## How to Run

Instructions to run the pipeline from a fresh clone:

```bash
git clone https://github.com/andrewgreathousewv/wvu-ieng-331-m2-15.git
cd wvu-ieng-331-m2-15
uv sync
# place olist.duckdb in the data/ directory
uv run wvu-ieng-331-m2-15
uv run wvu-ieng-331-m2-15 --start-date 2024-01-01 --end-date 2024-12-31
uv run wvu-ieng-331-m2-15 --seller-state SP
uv run wvu-ieng-331-m2-15 --start-date 2024-01-01 --seller-state SP
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start-date` | date | None (no filter) | Filter orders on or after this date in YYYY-MM-DD format |
| `--end-date` | date | None (no filter) | Filter orders on or before this date in YYYY-MM-DD format |
| `--seller-state` | string | None (all states) | Two letter Brazilian state code to filter sellers, for example SP or RJ |
| `--db` | path | data/olist.duckdb | Path to the DuckDB database file |

## Outputs

| File | Format | Description |
|------|--------|-------------|
| `summary.csv` | CSV | ABC inventory tier summary with 3 rows, one for each tier A, B, and C. Shows product count, total revenue, and percentage of total revenue per tier. Open in Excel or Google Sheets. |
| `detail.parquet` | Parquet | Full seller scorecard with one row per seller. Includes total revenue, on time delivery rate, average review score, cancellation rate, and a composite rank score. Lower composite score means better overall seller. |
| `chart.html` | HTML | Bar chart showing the top 15 customer states ranked by average delivery delay compared to the estimated date. Open in any browser. Red bars mean most delayed, green bars mean arrived early. |

## Validation Checks

The pipeline runs four checks before any analysis. If a check fails it logs a warning but keeps running so you still get output.

| Check | What it does | If it fails |
|-------|-------------|-------------|
| Tables exist | Confirms all 9 Olist tables are in the database | Logs a warning per missing table, pipeline continues |
| Key columns not null | Makes sure order_id, customer_id, product_id, and seller_id all have values | Logs a warning, pipeline continues |
| Date range | Checks that order dates are not empty and not before 2015 when Olist was founded | Future dates log a warning, pre-2015 dates log a failure |
| Row counts | Confirms orders, order_items, and customers each have at least 1000 rows | Logs a warning, pipeline continues |

## Analysis Summary

**Seller Scorecard**: Sellers are ranked across four dimensions which are revenue, on time delivery, average review score, and cancellation rate. These are combined into one composite rank. The top sellers tend to perform well across all four categories, not just revenue. Some high revenue sellers actually rank poorly on delivery and reviews which shows that raw sales volume alone does not mean a seller is doing a good job.

**ABC Inventory Classification**: A small number of products drive most of the revenue. Class A has 8,535 products and makes up 80% of all revenue. Class B has 11,301 products and covers 15%. Class C has 13,115 products but only contributes 5% of revenue. This is the classic Pareto pattern and means inventory focus should be on Class A products.

**Delivery Analysis**: States in the north and northeast of Brazil experience the biggest delays compared to their estimated delivery dates. States in the southeast like SP tend to arrive on time or early, likely because most sellers are located there. We cannot tell from this data alone whether delays are caused by the seller or the shipping carrier.

**Cohort Retention**: Most Olist customers only buy once. The 30 day return rate is 0.68%, 60 day is 1.03%, and 90 day is 1.24%. This is very low and suggests Olist works more like a product discovery platform where people find something once rather than a place people come back to regularly.

## Limitations & Caveats

- The delivery analysis cannot separate seller caused delays from carrier caused delays since we only have the final delivery date
- The seller state filter only applies to the seller scorecard query, not delivery analysis or cohort retention
- Retention rates might be slightly underestimated because Olist creates a new customer ID for the same person if they use a different email or device, we use customer_unique_id to fix this but it is not perfect
- The chart only shows the top 15 states by delay to keep it readable, all states are still included in the output files
- The pipeline does not halt if validation fails, it continues and logs a warning so outputs could be incomplete if the database has serious issues
