"""
Data access module for the Olist analytics pipeline.

Each function reads a .sql file from the sql/ directory, executes it against
DuckDB with parameterized placeholders, and returns a Polars DataFrame.
No inline SQL strings are used anywhere in this module.
"""

from pathlib import Path

import duckdb
import polars as pl
from loguru import logger

# Path to the sql/ directory -- two levels up from this file (src/pkg/ -> repo root)
SQL_DIR: Path = Path(__file__).parent.parent.parent / "sql"


def _load_sql(filename: str) -> str:
    """Read a .sql file from the sql/ directory.

    Args:
        filename: Name of the .sql file (e.g., seller_scorecard.sql).

    Returns:
        The raw SQL string read from the file.

    Raises:
        FileNotFoundError: If the .sql file does not exist at the expected path.
    """
    path = SQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def _execute(
    db_path: str,
    sql: str,
    params: list,
) -> pl.DataFrame:
    """Open a DuckDB connection, execute a parameterized query, return a Polars DataFrame.

    Args:
        db_path: Path to the DuckDB database file.
        sql: Parameterized SQL string using $1, $2, ... placeholders.
        params: List of parameter values to bind in placeholder order.

    Returns:
        A Polars DataFrame with the query results.

    Raises:
        FileNotFoundError: If db_path does not exist.
        duckdb.Error: If the query fails at the DuckDB level.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    try:
        con = duckdb.connect(str(db_file), read_only=True)
        result = con.execute(sql, params).pl()
        con.close()
        return result
    except duckdb.Error as exc:
        logger.error(f"DuckDB query failed: {exc}")
        raise


def get_seller_scorecard(
    db_path: str,
    start_date: str | None = None,
    end_date: str | None = None,
    seller_state: str | None = None,
) -> pl.DataFrame:
    """Run the seller scorecard query and return ranked seller performance metrics.

    Combines revenue, on-time delivery rate, average review score, and cancellation
    rate into a single composite rank for every seller. All filters are optional.
    Passing no arguments returns results for all sellers across all time.

    Args:
        db_path: Path to the DuckDB database file.
        start_date: ISO date string (YYYY-MM-DD) for the earliest order purchase date.
            Pass None to include all historical dates.
        end_date: ISO date string (YYYY-MM-DD) for the latest order purchase date.
            Pass None to include all dates through present.
        seller_state: Two-letter Brazilian state code (e.g., SP) to restrict results
            to sellers registered in that state. Pass None for all states.

    Returns:
        A Polars DataFrame with one row per seller, including total_revenue,
        on_time_rate, avg_review, cancel_rate, individual ranks, and composite_score.
        Ordered by composite_score ascending (lower is better overall seller).

    Raises:
        FileNotFoundError: If the SQL file or database file is not found.
        duckdb.Error: If the query fails.
    """
    logger.info(
        f"Running seller scorecard | start={start_date} end={end_date} state={seller_state}"
    )
    sql = _load_sql("seller_scorecard.sql")
    return _execute(
        db_path,
        sql,
        [start_date, start_date, end_date, end_date, seller_state, seller_state],
    )


def get_abc_classification(
    db_path: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pl.DataFrame:
    """Run the ABC inventory classification query and return tier-level revenue summaries.

    Classifies products into A (top 80% of revenue), B (next 15%), and C (remaining 5%)
    using cumulative revenue window functions. The summary collapses individual products
    into three rows, one per tier.

    Args:
        db_path: Path to the DuckDB database file.
        start_date: ISO date string for the earliest order purchase date. None = no filter.
        end_date: ISO date string for the latest order purchase date. None = no filter.

    Returns:
        A Polars DataFrame with columns: abc_class, product_count, total_revenue,
        pct_of_total_revenue. Three rows (A, B, C) ordered alphabetically.

    Raises:
        FileNotFoundError: If the SQL file or database file is not found.
        duckdb.Error: If the query fails.
    """
    logger.info(f"Running ABC classification | start={start_date} end={end_date}")
    sql = _load_sql("abc_classification.sql")
    return _execute(db_path, sql, [start_date, start_date, end_date, end_date])


def get_delivery_analysis(
    db_path: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pl.DataFrame:
    """Run the geographic delivery analysis query and return delay metrics by state.

    Computes average actual vs. estimated delivery days and the percentage of late
    orders for each Brazilian customer state. Useful for identifying which regions
    experience the worst delivery performance.

    Args:
        db_path: Path to the DuckDB database file.
        start_date: ISO date string for the earliest order purchase date. None = no filter.
        end_date: ISO date string for the latest order purchase date. None = no filter.

    Returns:
        A Polars DataFrame with columns: customer_state, total_orders, avg_actual_days,
        avg_estimated_days, avg_delay_days, pct_late. Ordered by avg_delay_days descending
        so worst-performing states appear first.

    Raises:
        FileNotFoundError: If the SQL file or database file is not found.
        duckdb.Error: If the query fails.
    """
    logger.info(f"Running delivery analysis | start={start_date} end={end_date}")
    sql = _load_sql("delivery_analysis.sql")
    return _execute(db_path, sql, [start_date, start_date, end_date, end_date])


def get_cohort_retention(
    db_path: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pl.DataFrame:
    """Run the cohort retention query and return 30/60/90-day return rates.

    Identifies each customer first purchase, then checks whether they placed
    another order within 30, 60, or 90 days. The date filter scopes which
    first purchase cohort is analyzed.

    Args:
        db_path: Path to the DuckDB database file.
        start_date: ISO date string limiting the cohort first purchase date. None = all.
        end_date: ISO date string limiting the cohort first purchase date. None = all.

    Returns:
        A Polars DataFrame with one row and columns: total_customers, retention_30_pct,
        retention_60_pct, retention_90_pct.

    Raises:
        FileNotFoundError: If the SQL file or database file is not found.
        duckdb.Error: If the query fails.
    """
    logger.info(f"Running cohort retention | start={start_date} end={end_date}")
    sql = _load_sql("cohort_retention.sql")
    return _execute(db_path, sql, [start_date, start_date, end_date, end_date])


# The queries.py is the data access layer.
# Reads the SQL files from the sql/ folder and runs them against the DuckDB database.
# Returns the results as Polars DataFrames that the rest of the pipeline can use.
# Has one function per analysis query.
