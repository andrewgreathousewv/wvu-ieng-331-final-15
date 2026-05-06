# Final Deliverable Grade

**Team 15 (Andrew Greathouse, Brady Stafford)**

| Criterion | Score | Max |
|-----------|------:|----:|
| Deliverable Quality | 4 | 6 |
| Visualizations | 6 | 6 |
| Pipeline Integration | 6 | 6 |
| Analytical Narrative | 6 | 6 |
| **Total (rubric portion)** | **22** | **24** |

Video walkthrough graded separately.

## Deliverable Quality (4/6)

`output/report.xlsx` is a five-sheet Excel workbook (Executive Summary, Seller Scorecard, Delivery Analysis, ABC Classification, Orders Over Time). The Executive Summary leads with Key Retention Metrics tiles, an Executive Summary paragraph, and a Key Findings at a Glance table. Each analysis sheet has its own title, sub-caption, data table, native Excel chart, and an Insight & Recommendation block. The polish issue: the Executive Summary prose says "fewer than 2% of customers return within 90 days", but the computed metric in the same sheet shows 10.71%. The hard-coded narrative does not match the dynamic data, which a manager would notice immediately.

## Visualizations (6/6)

Four native Excel charts covering all required types:

- **Monthly Order Volume Over Time** (line, temporal) - the team explicitly added a new SQL query (`orders_over_time.sql`) to satisfy the temporal requirement.
- **Top 20 Sellers by Total Revenue** (bar, categorical).
- **Average Delivery Delay by State** (bar, categorical).
- **Revenue Share by ABC Tier** (column, categorical).

All have chart titles, axis labels, and supporting data tables. Required types covered.

## Pipeline Integration (6/6)

`uv run wvu-ieng-331-final-15` after `uv sync` runs the full pipeline end-to-end with defaults: validation, queries, all M2 outputs (summary.csv, detail.parquet, chart.html), then the Excel report. Tested with the extended database; pipeline ran cleanly. Output filenames match the spec.

## Analytical Narrative (6/6)

Each per-sheet Insight & Recommendation section uses dynamically computed numbers and concrete recommendations: e.g. ABC sheet says "Class A products (8,130 items) generate 80.0% of all revenue ... Class C (13,893 items) contributes only 4.99%. Prioritize Class A product availability and seller reliability. Evaluate whether the long tail of Class C products justifies the catalog complexity." The Executive Summary frames three specific challenges (retention, delivery inequality, revenue concentration) and points the reader to per-sheet recommendations. Per-sheet narratives are well supported by data; recommendations are concrete and actionable.
