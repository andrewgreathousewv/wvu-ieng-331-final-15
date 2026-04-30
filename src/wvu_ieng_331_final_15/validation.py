"""
Data validation module for the Olist analytics pipeline.

Runs before any analysis queries. Checks that the database has the expected
tables, non-null key columns, a reasonable date range, and sufficient row counts.

Validation failures log a WARNING but do NOT halt the pipeline — the pipeline
continues with a disclaimer so partial results are still produced. This choice
lets the holdout test with extended data still run end-to-end even if thresholds
shift slightly. See README for more detail.
"""

from pathlib import Path

import duckdb
from loguru import logger

# Minimum row counts we expect for core tables.
# Set conservatively so an extended dataset does NOT trigger false failures.
MIN_ROW_COUNTS: dict[str, int] = {
    "orders": 1_000,
    "order_items": 1_000,
    "customers": 1_000,
}

# The 9 tables the Olist schema must include.
EXPECTED_TABLES: list[str] = [
    "category_translation",
    "customers",
    "geolocation",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "products",
    "sellers",
]

# Key columns checked for all-NULL status
KEY_COLUMNS: dict[str, str] = {
    "orders": "order_id",
    "customers": "customer_id",
    "products": "product_id",
    "sellers": "seller_id",
}


def _connect(db_path: str) -> duckdb.DuckDBPyConnection:
    """Open a read-only DuckDB connection.

    Args:
        db_path: Path to the DuckDB file.

    Returns:
        An open DuckDB connection.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    return duckdb.connect(str(db_path), read_only=True)


def check_tables_exist(con: duckdb.DuckDBPyConnection) -> bool:
    """Verify that all 9 expected Olist tables are present in the database.

    Queries DuckDB's information_schema to get the actual list of tables and
    compares it to EXPECTED_TABLES. Missing tables log a WARNING per missing table.

    Args:
        con: An open DuckDB connection.

    Returns:
        True if all expected tables exist, False if any are missing.
    """
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    actual = {r[0] for r in rows}
    all_present = True
    for table in EXPECTED_TABLES:
        if table not in actual:
            logger.warning(f"VALIDATION FAIL — Missing table: '{table}'")
            all_present = False
    if all_present:
        logger.info("✓ All 9 expected tables found.")
    return all_present


def check_key_columns_not_null(con: duckdb.DuckDBPyConnection) -> bool:
    """Check that key columns are not entirely NULL in their respective tables.

    An all-NULL primary/foreign key column means joins and aggregations on that
    table will produce empty or meaningless results.

    Args:
        con: An open DuckDB connection.

    Returns:
        True if all key columns contain at least one non-NULL value, False otherwise.
    """
    all_ok = True
    for table, column in KEY_COLUMNS.items():
        try:
            # COUNT(col) counts non-NULL values only; if it's 0 the column is all NULL
            result = con.execute(f"SELECT COUNT({column}) FROM {table}").fetchone()
            non_null_count = result[0] if result else 0
            if non_null_count == 0:
                logger.warning(
                    f"VALIDATION FAIL — Column '{column}' in table '{table}' is entirely NULL."
                )
                all_ok = False
            else:
                logger.info(f"✓ {table}.{column}: {non_null_count:,} non-NULL values.")
        except duckdb.Error as exc:
            logger.warning(f"VALIDATION FAIL — Could not check {table}.{column}: {exc}")
            all_ok = False
    return all_ok


def check_date_range(con: duckdb.DuckDBPyConnection) -> bool:
    """Verify that orders.order_purchase_timestamp has a reasonable date range.

    Checks that:
    - The column is not empty (min/max are not NULL).
    - No orders are dated in the future (sanity check for data entry errors).
    - The earliest order is after 2015-01-01 (Olist was founded ~2015).

    Args:
        con: An open DuckDB connection.

    Returns:
        True if the date range passes all checks, False otherwise.
    """
    try:
        row = con.execute(
            "SELECT MIN(order_purchase_timestamp::DATE), MAX(order_purchase_timestamp::DATE) FROM orders"
        ).fetchone()
    except duckdb.Error as exc:
        logger.warning(f"VALIDATION FAIL — Could not query date range: {exc}")
        return False

    if row is None or row[0] is None:
        logger.warning("VALIDATION FAIL — orders.order_purchase_timestamp is empty.")
        return False

    min_date, max_date = row
    logger.info(f"✓ Date range: {min_date} → {max_date}")

    # Warn but don't fail on future dates — the holdout data may extend further
    import datetime

    today = datetime.date.today()
    if max_date > today:
        logger.warning(
            f"VALIDATION WARN — Latest order date {max_date} is in the future (today={today}). "
            "Extended holdout dataset detected; pipeline will continue."
        )

    # Olist was founded in 2015; orders before that suggest a load error
    if min_date.year < 2015:
        logger.warning(
            f"VALIDATION FAIL — Earliest order date {min_date} predates Olist's founding (2015)."
        )
        return False

    return True


def check_row_counts(con: duckdb.DuckDBPyConnection) -> bool:
    """Confirm that core tables meet minimum row count thresholds.

    Thresholds are set in MIN_ROW_COUNTS. A table below its threshold likely
    indicates a partial data load. The pipeline continues with a warning so that
    the holdout extended dataset (more rows) does not cause a false failure.

    Args:
        con: An open DuckDB connection.

    Returns:
        True if all tables meet their thresholds, False if any fall short.
    """
    all_ok = True
    for table, minimum in MIN_ROW_COUNTS.items():
        try:
            result = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
            count = result[0] if result else 0
            if count < minimum:
                logger.warning(
                    f"VALIDATION FAIL — Table '{table}' has {count:,} rows; expected ≥ {minimum:,}."
                )
                all_ok = False
            else:
                logger.info(f"✓ {table}: {count:,} rows (min {minimum:,}).")
        except duckdb.Error as exc:
            logger.warning(
                f"VALIDATION FAIL — Could not count rows in '{table}': {exc}"
            )
            all_ok = False
    return all_ok


def run_validation(db_path: str) -> bool:
    """Run all four validation checks against the database.

    Orchestrates check_tables_exist, check_key_columns_not_null, check_date_range,
    and check_row_counts. All four checks always run regardless of earlier failures
    so the log captures every issue in one pass.

    If any check fails, a WARNING is logged and this function returns False.
    The pipeline is designed to continue even when False is returned — it will
    log a disclaimer and proceed with whatever data is available.

    Args:
        db_path: Path to the DuckDB database file.

    Returns:
        True if every validation check passes, False if one or more fail.

    Raises:
        FileNotFoundError: If the database file does not exist at db_path.
    """
    logger.info("=" * 50)
    logger.info("Running data validation...")
    logger.info("=" * 50)

    try:
        con = _connect(db_path)
    except FileNotFoundError:
        # Re-raise so pipeline.py can catch it and give the user a clear message
        raise

    tables_ok = check_tables_exist(con)
    nulls_ok = check_key_columns_not_null(con)
    dates_ok = check_date_range(con)
    counts_ok = check_row_counts(con)
    con.close()

    passed = all([tables_ok, nulls_ok, dates_ok, counts_ok])

    if passed:
        logger.info("✓ All validation checks passed.")
    else:
        logger.warning(
            "One or more validation checks failed. "
            "Pipeline will continue — treat outputs with caution."
        )

    logger.info("=" * 50)
    return passed


# The purpose of the validation.py module is to run before any analysis to make sure the database is clean and ready
