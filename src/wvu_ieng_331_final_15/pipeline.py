"""
Pipeline entry point for the Olist analytics pipeline.

Orchestrates the full workflow:
  1. Parse CLI arguments
  2. Run validation
  3. Execute analysis queries
  4. Write summary.csv, detail.parquet, and chart.html to output/

Run with:
    uv run wvu-ieng-331-final-15
    uv run wvu-ieng-331-final-15 --start-date 2017-01-01 --end-date 2018-12-31
    uv run wvu-ieng-331-final-15 --seller-state SP
"""

import argparse
import datetime
import sys
from pathlib import Path

import altair as alt
import duckdb
import polars as pl
from loguru import logger

from wvu_ieng_331_final_15 import queries, validation

# Default database location: repo_root/data/olist.duckdb
# __file__ = src/wvu_ieng_331_m2_3/pipeline.py  → go up 4 levels to repo root
DEFAULT_DB: Path = Path(__file__).parent.parent.parent / "data" / "olist.duckdb"
OUTPUT_DIR: Path = Path(__file__).parent.parent.parent / "output"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the pipeline.

    Accepts optional date range filters and a seller state filter.
    All parameters default to None, which means no filtering is applied
    and the full dataset is analyzed.

    Args:
        argv: Argument list (defaults to sys.argv if None). Useful for testing.

    Returns:
        An argparse.Namespace with attributes: start_date, end_date,
        seller_state, and db.

    Raises:
        SystemExit: If invalid arguments are supplied (argparse default behavior).
    """
    parser = argparse.ArgumentParser(
        prog="wvu-ieng-331-m2-15",
        description="Olist e-commerce analytics pipeline -- Team 3",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Filter orders on or after this date (ISO format). Default: no filter.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Filter orders on or before this date (ISO format). Default: no filter.",
    )
    parser.add_argument(
        "--seller-state",
        default=None,
        metavar="STATE",
        help=(
            "Two-letter Brazilian state code to filter sellers (e.g., SP). "
            "Default: all states."
        ),
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        metavar="PATH",
        help=f"Path to the DuckDB database file. Default: {DEFAULT_DB}",
    )
    return parser.parse_args(argv)


def validate_date_param(value: str | None, name: str) -> None:
    """Validate that a date string is in YYYY-MM-DD format.

    Args:
        value: The date string to validate, or None to skip validation.
        name: Parameter name used in the error message (e.g., 'start-date').

    Raises:
        ValueError: If value is not None and not a valid YYYY-MM-DD date string.
    """
    if value is None:
        return
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"--{name} must be in YYYY-MM-DD format, got: '{value}'"
        ) from exc


def _write_chart(delivery: pl.DataFrame, output_dir: Path) -> None:
    """Build and save an Altair bar chart of average delivery delay by state.

    Shows the top 15 states ranked by average delay (actual days minus estimated
    days). Positive avg_delay_days means late on average; negative means early.
    Saved as a self-contained HTML file using Vega-Embed from a CDN.

    Uses Polars .to_dicts() instead of .to_pandas() so pandas is not required
    as a dependency -- Altair accepts a list of dicts natively via alt.Data.

    Args:
        delivery: Polars DataFrame from get_delivery_analysis(), must have columns
            customer_state (str), avg_delay_days (float), total_orders (int).
        output_dir: Directory to write chart.html into.

    Raises:
        OSError: If chart.html cannot be written to disk.
        Exception: If Altair fails to render or serialize the chart.
    """
    if delivery.is_empty():
        logger.warning("Delivery data is empty -- skipping chart generation.")
        return

    # Convert top 15 rows to list-of-dicts; Altair accepts this via alt.Data
    # This avoids adding pandas as a dependency just for chart creation
    records: list[dict] = (
        delivery.sort("avg_delay_days", descending=True)
        .head(15)
        .select(["customer_state", "avg_delay_days", "total_orders"])
        .to_dicts()
    )

    chart = (
        alt.Chart(alt.Data(values=records))
        .mark_bar()
        .encode(
            x=alt.X(
                "avg_delay_days:Q",
                title="Avg Delay (days vs. estimate)",
                axis=alt.Axis(grid=True),
            ),
            y=alt.Y(
                "customer_state:N",
                sort="-x",
                title="Customer State",
            ),
            color=alt.Color(
                "avg_delay_days:Q",
                scale=alt.Scale(scheme="redyellowgreen", reverse=True),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("customer_state:N", title="State"),
                alt.Tooltip("avg_delay_days:Q", title="Avg Delay (days)", format=".1f"),
                alt.Tooltip("total_orders:Q", title="Total Orders", format=","),
            ],
        )
        .properties(
            title="Top 15 States by Average Delivery Delay vs. Estimated Date",
            width=500,
            height=350,
        )
    )

    chart_path = output_dir / "chart.html"
    try:
        chart.save(str(chart_path))
        logger.info(f"Wrote chart.html -> {chart_path}")
    except OSError as exc:
        logger.error(f"Failed to write chart.html to disk: {exc}")
        raise
    except Exception as exc:
        logger.error(f"Altair failed to render chart: {exc}")
        raise


def write_outputs(
    scorecard: pl.DataFrame,
    abc: pl.DataFrame,
    delivery: pl.DataFrame,
    retention: pl.DataFrame,
    output_dir: Path,
) -> None:
    """Write the three required output files to the output/ directory.

    Creates output/ if it does not exist. Writes:
      - summary.csv: ABC classification tier summary (3 rows, one per tier).
      - detail.parquet: Full seller scorecard with all metrics and ranks.
      - chart.html: Altair bar chart of delivery delay by state (top 15).

    Args:
        scorecard: Polars DataFrame from get_seller_scorecard().
        abc: Polars DataFrame from get_abc_classification().
        delivery: Polars DataFrame from get_delivery_analysis().
        retention: Polars DataFrame from get_cohort_retention().
        output_dir: Path to the output directory (created automatically if missing).

    Raises:
        OSError: If a file cannot be written (e.g., disk full, permissions error).
    """
    # Create the output directory if it does not already exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- summary.csv ---
    # ABC tier summary: 3 rows (A, B, C) with product count and revenue share.
    # CSV format is readable by Excel, Google Sheets, and any data tool.
    summary_path = output_dir / "summary.csv"
    try:
        abc.write_csv(str(summary_path))
        logger.info(f"Wrote summary.csv -> {summary_path}")
    except OSError as exc:
        logger.error(f"Failed to write summary.csv: {exc}")
        raise

    # --- detail.parquet ---
    # Full seller scorecard with revenue, delivery, review, cancellation metrics
    # and composite rank. Parquet is compact and preserves data types better than CSV.
    detail_path = output_dir / "detail.parquet"
    try:
        scorecard.write_parquet(str(detail_path))
        logger.info(f"Wrote detail.parquet -> {detail_path}")
    except OSError as exc:
        logger.error(f"Failed to write detail.parquet: {exc}")
        raise

    # --- chart.html ---
    # Altair visualization; written by helper so chart logic stays separate
    _write_chart(delivery, output_dir)


def main() -> None:
    """Pipeline entry point -- parse args, validate, query, and write outputs.

    Called by the 'wvu-ieng-331-m2-15' script defined in pyproject.toml.
    Exits with code 1 if the database is not found or an argument is invalid.
    Individual query failures are logged as errors but the pipeline continues
    so that other outputs are still produced.

    Returns:
        None
    """
    args = parse_args()

    # Validate date format before touching the database
    try:
        validate_date_param(args.start_date, "start-date")
        validate_date_param(args.end_date, "end-date")
    except ValueError as exc:
        logger.error(f"Invalid parameter: {exc}")
        sys.exit(1)

    db_path: str = args.db
    start: str | None = args.start_date
    end: str | None = args.end_date
    state: str | None = args.seller_state

    logger.info("=" * 50)
    logger.info("Olist Analytics Pipeline -- Team 15")
    logger.info(f"  Database    : {db_path}")
    logger.info(f"  Date range  : {start or 'all'} -> {end or 'all'}")
    logger.info(f"  Seller state: {state or 'all'}")
    logger.info("=" * 50)

    # ------------------------------------------------------------------ #
    # Step 1: Validation                                                   #
    # ------------------------------------------------------------------ #
    try:
        passed = validation.run_validation(db_path)
    except FileNotFoundError as exc:
        # FileNotFoundError is raised by validation._connect() when the file
        # is missing. This is a fatal error -- no point continuing.
        logger.error(
            f"Database not found: {exc}\n"
            "Place olist.duckdb in the data/ directory and try again."
        )
        sys.exit(1)

    if not passed:
        logger.warning(
            "One or more validation checks failed. "
            "Pipeline will continue -- treat outputs with caution."
        )

    # Step 2: Run analysis queries                                         #
    # Each query is wrapped independently so one failure does not block   #
    # the others. Empty DataFrames are used as fallbacks.                 #

    logger.info("Running analysis queries...")

    try:
        scorecard = queries.get_seller_scorecard(db_path, start, end, state)
        logger.info(f"  Seller scorecard: {len(scorecard):,} sellers")
    except (FileNotFoundError, duckdb.Error) as exc:
        logger.error(f"Seller scorecard query failed: {exc}")
        scorecard = pl.DataFrame()

    try:
        abc = queries.get_abc_classification(db_path, start, end)
        logger.info(f"  ABC classification: {len(abc)} tiers")
    except (FileNotFoundError, duckdb.Error) as exc:
        logger.error(f"ABC classification query failed: {exc}")
        abc = pl.DataFrame()

    try:
        delivery = queries.get_delivery_analysis(db_path, start, end)
        logger.info(f"  Delivery analysis: {len(delivery):,} states")
    except (FileNotFoundError, duckdb.Error) as exc:
        logger.error(f"Delivery analysis query failed: {exc}")
        delivery = pl.DataFrame()

    try:
        retention = queries.get_cohort_retention(db_path, start, end)
        logger.info(f"  Cohort retention: {len(retention)} row(s)")
        if len(retention) > 0:
            row = retention.row(0, named=True)
            logger.info(
                f"  Retention -- 30d: {row.get('retention_30_pct', 'N/A')}%  "
                f"60d: {row.get('retention_60_pct', 'N/A')}%  "
                f"90d: {row.get('retention_90_pct', 'N/A')}%"
            )
    except (FileNotFoundError, duckdb.Error) as exc:
        logger.error(f"Cohort retention query failed: {exc}")
        retention = pl.DataFrame()

    # Step 3: Write outputs                                                #

    logger.info("Writing output files...")
    try:
        write_outputs(scorecard, abc, delivery, retention, OUTPUT_DIR)
    except OSError as exc:
        logger.error(f"Output write failed: {exc}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("Pipeline complete. Outputs written to: output/")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
# The pipeline is the main script in this project and is used for being the main entry point.
# Accepts command line arguments such as --seller-state and --start-date.
# The pipeline orchestrates the full workflow: from validate to query to process to output.
# The pipeline produces there 3 output files.
