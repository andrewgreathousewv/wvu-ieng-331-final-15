# Design Rationale

## Parameter Flow

The command-line argument `--seller-state SP` is parsed in the `parse_args()` function in `pipeline.py`. In this function, `argparse` defines the argument as `seller_state`, so after parsing it is accessed as `args.seller_state`.

Inside the `main()` function, this value is assigned to a variable:
state = args.seller_state

This `state` variable is then passed into the queries module through the function call:
queries.get_seller_scorecard(db_path, start, end, state)

In `queries.py`, the function `get_seller_scorecard()` receives this parameter as `seller_state`. It loads the SQL using `_load_sql("seller_scorecard.sql")` and executes it with:
_execute(db_path, sql, [start_date, start_date, end_date, end_date, seller_state, seller_state])

The SQL file uses placeholders like `$5` and `$6` in conditions such as:
WHERE ($5 IS NULL OR s.seller_state = $5)

This means if `seller_state` is provided (like "SP"), the query filters results to that state. If it is `None`, the condition allows all rows. So the argument flows from `parse_args()` → `main()` → `get_seller_scorecard()` → `_execute()` → SQL placeholders, which directly control the filtering in the query.

## SQL Parameterization

In `seller_scorecard.sql`, the raw SQL uses placeholders such as `$1`, `$2`, etc. For example:
WHERE ($5 IS NULL OR s.seller_state = $5)

In `queries.py`, the SQL file is read using:
sql = _load_sql("seller_scorecard.sql")

Then it is executed with:
con.execute(sql, params)

The `params` list contains Python values like:
[start_date, start_date, end_date, end_date, seller_state, seller_state]

These values are safely inserted into the query by DuckDB.

Parameterized queries are used instead of f-strings because they prevent SQL injection, ensure proper handling of data types like dates and NULL values, and make the code more reliable.

SQL is stored in `.sql` files instead of inline Python to separate concerns. This makes the queries easier to read, maintain, and debug without modifying the Python logic.

## Validation Logic

The `check_tables_exist()` function checks whether all required tables are present in the database. This matters because missing tables would cause queries to fail. If a table is missing, a warning is logged but the pipeline continues.

The `check_key_columns_not_null()` function verifies that key columns such as IDs are not entirely NULL. This is important because joins and aggregations depend on these fields. If the check fails, a warning is logged.

The `check_date_range()` function checks the minimum and maximum order dates. This ensures the dataset is not empty and that dates are within a reasonable range (not too old or in the future). If invalid, warnings are issued depending on the issue.

The `check_row_counts()` function ensures each table has at least a minimum number of rows (e.g., 1,000). This prevents running analysis on incomplete data. If the count is below the threshold, a warning is logged.

The threshold of 1,000 rows was chosen because it is large enough to indicate meaningful data but not so large that slightly smaller datasets would fail validation. All validation checks produce warnings instead of stopping the pipeline so results can still be generated.

## Error Handling

One `try/except` block is in `queries.py`:
except duckdb.Error as exc:

This catches database-related errors such as invalid SQL or connection issues. When this exception is raised, the error is logged and re-raised, which allows the pipeline to handle it appropriately.

Another `try/except` block is in `pipeline.py`:
except OSError as exc:

This catches file system errors when writing output files, such as permission issues or missing directories. If triggered, the error is logged and the program exits.

If a bare `except:` was used instead, it would catch all exceptions, including unrelated bugs. This would make debugging much harder and could hide important errors from the user.

## Scaling & Adaptation

1. If the dataset grew to 10 million orders, the SQL queries would slow down first, especially those involving joins and aggregations like the seller scorecard and cohort retention queries. To fix this, I would add indexing or clustering, pre-aggregate data into summary tables, and possibly break large queries into smaller steps. Memory usage from loading large DataFrames would also become an issue.

2. To add a JSON output format, I would modify the `write_outputs()` function in `pipeline.py`. I would add logic to export results using a method like `write_json()`. This keeps changes isolated to the output stage, so no modifications are needed in `queries.py` or `validation.py`.

## Final Deliverable — Report Module

### Report Generation

The `report.py` module is called at the end of `pipeline.py` after all queries have run. The `build_report()` function accepts five Polars DataFrames (scorecard, abc, delivery, retention, orders_time) and the output directory path, then builds a formatted Excel workbook using XlsxWriter.

The function creates five worksheets in order: Executive Summary, Seller Scorecard, Delivery Analysis, ABC Classification, and Orders Over Time. Each sheet writes data row by row using `ws.write()` and `ws.merge_range()`, then embeds a chart using `workbook.add_chart()` and `ws.insert_chart()`.

The `_orders_time_chart()` helper function is called inside `build_report()` to write the monthly order data and embed the line chart into the Orders Over Time sheet. Separating it into its own function keeps `build_report()` readable and makes the chart logic easier to test independently.

### Why XlsxWriter

XlsxWriter was chosen over openpyxl because it produces cleaner formatted output and has better support for embedded charts. It is write-only, meaning it cannot read existing files, but since we generate the report fresh every run that is not a limitation.

### Scaling & Adaptation (Updated)

If a sixth output format were needed (for example a PDF summary), we would add a new helper function in `report.py` (e.g., `build_pdf_report()`) and call it from `pipeline.py` after `build_report()`. No changes to `queries.py` or `validation.py` would be needed since the data is already in Polars DataFrames by that point.
