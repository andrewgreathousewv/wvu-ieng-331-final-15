"""
Report generation module for the Olist analytics pipeline.

Builds a formatted Excel workbook with multiple sheets, charts, and
an analytical narrative for a non-technical business audience.
Running the pipeline produces report.xlsx in the output/ directory.
"""

from pathlib import Path

import polars as pl
import xlsxwriter
from loguru import logger


def _orders_time_chart(
    orders_time: pl.DataFrame,
    workbook,
    ws,
) -> None:
    """Write monthly order data and embed a line chart into the given worksheet.

    Args:
        orders_time: Polars DataFrame from get_orders_over_time().
        workbook: XlsxWriter workbook object.
        ws: XlsxWriter worksheet to write data and chart into.
    """
    if orders_time.is_empty():
        return

    records = orders_time.to_dicts()
    for row_i, row in enumerate(records):
        ws.write(4 + row_i, 0, str(row.get("order_month", ""))[:10])
        ws.write(4 + row_i, 1, row.get("total_orders", 0))
        ws.write(4 + row_i, 2, row.get("total_revenue", 0))

    n = len(records)
    chart = workbook.add_chart({"type": "line"})
    chart.add_series(
        {
            "name": "Total Orders",
            "categories": ["Orders Over Time", 4, 0, 4 + n - 1, 0],
            "values": ["Orders Over Time", 4, 1, 4 + n - 1, 1],
            "line": {"color": "#0f3460", "width": 2.5},
        }
    )
    chart.set_title({"name": "Monthly Order Volume Over Time"})
    chart.set_x_axis({"name": "Month", "num_font": {"rotation": -45}})
    chart.set_y_axis({"name": "Total Orders"})
    chart.set_size({"width": 550, "height": 350})
    ws.insert_chart("E4", chart)


def build_report(
    scorecard: pl.DataFrame,
    abc: pl.DataFrame,
    delivery: pl.DataFrame,
    retention: pl.DataFrame,
    orders_time: pl.DataFrame,
    output_dir: Path,
) -> None:
    """Build and save a formatted Excel report with charts and narrative.

    Creates a multi-sheet Excel workbook containing:
      - An executive summary sheet with key metrics and narrative
      - A seller scorecard sheet with top sellers and an embedded bar chart
      - A delivery analysis sheet with state delays and an embedded bar chart
      - An ABC classification sheet with tier summary and an embedded bar chart
      - An orders over time sheet with a line chart showing monthly trends

    Args:
        scorecard: Polars DataFrame from get_seller_scorecard().
        abc: Polars DataFrame from get_abc_classification().
        delivery: Polars DataFrame from get_delivery_analysis().
        retention: Polars DataFrame from get_cohort_retention().
        orders_time: Polars DataFrame from get_orders_over_time().
        output_dir: Directory to write report.xlsx into.

    Raises:
        OSError: If report.xlsx cannot be written to disk.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.xlsx"

    logger.info("Building Excel report...")

    try:
        workbook = xlsxwriter.Workbook(str(report_path))

        # ── Formats ──────────────────────────────────────────────────────
        title_fmt = workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": "#1a1a2e",
                "bottom": 2,
                "bottom_color": "#e94560",
            }
        )
        heading_fmt = workbook.add_format(
            {
                "bold": True,
                "font_size": 13,
                "font_color": "#16213e",
                "top": 1,
                "top_color": "#0f3460",
                "bg_color": "#eaf4fb",
            }
        )
        label_fmt = workbook.add_format(
            {
                "bold": True,
                "font_color": "#ffffff",
                "bg_color": "#1a1a2e",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
            }
        )
        metric_fmt = workbook.add_format(
            {
                "bold": True,
                "font_size": 14,
                "font_color": "#e94560",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
            }
        )
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1a1a2e",
                "font_color": "#ffffff",
                "border": 1,
                "align": "center",
            }
        )
        cell_fmt = workbook.add_format({"border": 1, "align": "center"})
        money_fmt = workbook.add_format(
            {
                "border": 1,
                "align": "center",
                "num_format": "#,##0.00",
            }
        )
        pct_fmt = workbook.add_format(
            {
                "border": 1,
                "align": "center",
                "num_format": "0.00%",
            }
        )
        wrap_fmt = workbook.add_format(
            {
                "text_wrap": True,
                "valign": "top",
                "border": 1,
                "font_color": "#333333",
            }
        )
        rec_fmt = workbook.add_format(
            {
                "text_wrap": True,
                "valign": "top",
                "bg_color": "#eaf4fb",
                "border": 1,
                "font_color": "#0f3460",
                "bold": False,
            }
        )

        # Pull retention numbers
        ret_30 = ret_60 = ret_90 = "N/A"
        if not retention.is_empty():
            row = retention.row(0, named=True)
            ret_30 = f"{row.get('retention_30_pct', 'N/A')}%"
            ret_60 = f"{row.get('retention_60_pct', 'N/A')}%"
            ret_90 = f"{row.get('retention_90_pct', 'N/A')}%"

        # Pull ABC numbers
        abc_a_pct = abc_b_pct = abc_c_pct = "N/A"
        abc_a_count = abc_b_count = abc_c_count = "N/A"
        if not abc.is_empty():
            for r in abc.to_dicts():
                if r["abc_class"] == "A":
                    abc_a_pct = f"{r['pct_of_total_revenue']}%"
                    abc_a_count = f"{r['product_count']:,}"
                elif r["abc_class"] == "B":
                    abc_b_pct = f"{r['pct_of_total_revenue']}%"
                    abc_b_count = f"{r['product_count']:,}"
                elif r["abc_class"] == "C":
                    abc_c_pct = f"{r['pct_of_total_revenue']}%"
                    abc_c_count = f"{r['product_count']:,}"

        # ── Sheet 1: Executive Summary ────────────────────────────────────
        ws = workbook.add_worksheet("Executive Summary")
        ws.set_column("A:A", 28)
        ws.set_column("B:D", 20)

        ws.merge_range(
            "A1:D1",
            "Olist E-Commerce Business Intelligence Report — Team 15",
            title_fmt,
        )
        ws.merge_range(
            "A2:D2", "WVU IENG 331  |  Andrew Greathouse, Brady Stafford", cell_fmt
        )

        ws.merge_range("A4:D4", "Key Retention Metrics", heading_fmt)
        ws.write("A5", "30-Day Retention", label_fmt)
        ws.write("B5", "60-Day Retention", label_fmt)
        ws.write("C5", "90-Day Retention", label_fmt)
        ws.write("A6", ret_30, metric_fmt)
        ws.write("B6", ret_60, metric_fmt)
        ws.write("C6", ret_90, metric_fmt)
        ws.set_row(5, 30)

        ws.merge_range("A8:D8", "Executive Summary", heading_fmt)
        summary_text = (
            "This report analyzes the Olist marketplace across four dimensions: "
            "seller performance, delivery reliability, inventory classification, "
            "and customer retention. The data reveals three critical challenges: "
            "(1) extremely low repeat purchase rates — fewer than 2% of customers "
            "return within 90 days; (2) significant delivery delays in northern "
            "Brazilian states compared to the southeast; and (3) heavy revenue "
            "concentration in a small subset of Class A products. Recommendations "
            "for each area are detailed in the following sheets."
        )
        ws.merge_range("A9:D12", summary_text, wrap_fmt)
        ws.set_row(8, 90)

        ws.merge_range("A14:D14", "Key Findings at a Glance", heading_fmt)
        findings = [
            (
                "Seller Scorecard",
                f"{len(scorecard):,} active sellers ranked by composite score",
            ),
            (
                "Delivery Analysis",
                "Northern states experience the most delays vs. estimates",
            ),
            (
                "ABC Classification",
                f"Class A ({abc_a_count} products) drives {abc_a_pct} of revenue",
            ),
            ("Customer Retention", f"Only {ret_90} of customers return within 90 days"),
        ]
        for i, (topic, finding) in enumerate(findings):
            ws.write(14 + i, 0, topic, label_fmt)
            ws.merge_range(14 + i, 1, 14 + i, 3, finding, wrap_fmt)

        # ── Sheet 2: Seller Scorecard ─────────────────────────────────────
        ws2 = workbook.add_worksheet("Seller Scorecard")
        ws2.set_column("A:A", 36)
        ws2.set_column("B:G", 18)

        ws2.merge_range(
            "A1:G1", "Seller Scorecard — Top 20 Sellers by Revenue", title_fmt
        )
        ws2.merge_range(
            "A2:G2",
            "Sellers ranked by composite score across revenue, delivery, reviews, and cancellations.",
            wrap_fmt,
        )

        headers = [
            "Seller ID",
            "Total Revenue (BRL)",
            "On-Time Rate",
            "Avg Review",
            "Cancel Rate",
            "Composite Score",
        ]
        for col, header in enumerate(headers):
            ws2.write(3, col, header, header_fmt)

        top_sellers = scorecard.sort("composite_score").head(20)
        for row_i, row in enumerate(top_sellers.to_dicts()):
            ws2.write(4 + row_i, 0, row.get("seller_id", ""), cell_fmt)
            ws2.write(4 + row_i, 1, row.get("total_revenue", 0), money_fmt)
            ws2.write(4 + row_i, 2, row.get("on_time_rate", 0), pct_fmt)
            ws2.write(4 + row_i, 3, row.get("avg_review", 0), cell_fmt)
            ws2.write(4 + row_i, 4, row.get("cancel_rate", 0), pct_fmt)
            ws2.write(4 + row_i, 5, row.get("composite_score", 0), cell_fmt)

        chart2 = workbook.add_chart({"type": "bar"})
        chart2.add_series(
            {
                "name": "Total Revenue (BRL)",
                "categories": ["Seller Scorecard", 4, 0, 23, 0],
                "values": ["Seller Scorecard", 4, 1, 23, 1],
                "fill": {"color": "#0f3460"},
            }
        )
        chart2.set_title({"name": "Top 20 Sellers by Total Revenue"})
        chart2.set_x_axis({"name": "Revenue (BRL)"})
        chart2.set_y_axis({"name": "Seller ID"})
        chart2.set_size({"width": 500, "height": 400})
        ws2.insert_chart("I4", chart2)

        ws2.merge_range("A26:G26", "Insight & Recommendation", heading_fmt)
        ws2.merge_range(
            "A27:G29",
            "High revenue does not always mean high quality. Some top-revenue sellers "
            "rank poorly on delivery and review scores. Focus seller development on "
            "composite score, not just sales volume. Consider flagging sellers with "
            "high revenue but composite scores above 500 for a performance review.",
            rec_fmt,
        )
        ws2.set_row(26, 70)

        # ── Sheet 3: Delivery Analysis ────────────────────────────────────
        ws3 = workbook.add_worksheet("Delivery Analysis")
        ws3.set_column("A:A", 20)
        ws3.set_column("B:F", 18)

        ws3.merge_range("A1:F1", "Delivery Performance by Customer State", title_fmt)
        ws3.merge_range(
            "A2:F2",
            "Average actual vs. estimated delivery days. Negative delay = arrived early.",
            wrap_fmt,
        )

        del_headers = [
            "State",
            "Total Orders",
            "Avg Actual Days",
            "Avg Estimated Days",
            "Avg Delay Days",
            "% Late",
        ]
        for col, header in enumerate(del_headers):
            ws3.write(3, col, header, header_fmt)

        for row_i, row in enumerate(delivery.to_dicts()):
            ws3.write(4 + row_i, 0, row.get("customer_state", ""), cell_fmt)
            ws3.write(4 + row_i, 1, row.get("total_orders", 0), cell_fmt)
            ws3.write(4 + row_i, 2, row.get("avg_actual_days", 0), cell_fmt)
            ws3.write(4 + row_i, 3, row.get("avg_estimated_days", 0), cell_fmt)
            ws3.write(4 + row_i, 4, row.get("avg_delay_days", 0), cell_fmt)
            ws3.write(4 + row_i, 5, row.get("pct_late", 0), cell_fmt)

        n_states = len(delivery)
        chart3 = workbook.add_chart({"type": "bar"})
        chart3.add_series(
            {
                "name": "Avg Delay Days",
                "categories": ["Delivery Analysis", 4, 0, 4 + n_states - 1, 0],
                "values": ["Delivery Analysis", 4, 4, 4 + n_states - 1, 4],
                "fill": {"color": "#e94560"},
            }
        )
        chart3.set_title({"name": "Average Delivery Delay by State"})
        chart3.set_x_axis({"name": "Avg Delay (days vs. estimate)"})
        chart3.set_y_axis({"name": "Customer State"})
        chart3.set_size({"width": 500, "height": 400})
        ws3.insert_chart("H4", chart3)

        ws3.merge_range("A33:F33", "Insight & Recommendation", heading_fmt)
        ws3.merge_range(
            "A34:F36",
            "Northern and northeastern states consistently experience the worst delivery "
            "performance relative to estimates. This likely reflects the geographic "
            "concentration of Olist sellers in the southeast. Recommend reviewing "
            "estimated delivery dates for high-delay states or improving logistics "
            "partnerships in those regions.",
            rec_fmt,
        )
        ws3.set_row(33, 70)

        # ── Sheet 4: ABC Classification ───────────────────────────────────
        ws4 = workbook.add_worksheet("ABC Classification")
        ws4.set_column("A:D", 22)

        ws4.merge_range(
            "A1:D1", "ABC Inventory Classification — Revenue by Tier", title_fmt
        )
        ws4.merge_range(
            "A2:D2",
            "Class A = top 80% of revenue. Class B = next 15%. Class C = remaining 5%.",
            wrap_fmt,
        )

        abc_headers = [
            "Class",
            "Product Count",
            "Total Revenue (BRL)",
            "% of Total Revenue",
        ]
        for col, header in enumerate(abc_headers):
            ws4.write(3, col, header, header_fmt)

        for row_i, row in enumerate(abc.to_dicts()):
            ws4.write(4 + row_i, 0, row.get("abc_class", ""), cell_fmt)
            ws4.write(4 + row_i, 1, row.get("product_count", 0), cell_fmt)
            ws4.write(4 + row_i, 2, row.get("total_revenue", 0), money_fmt)
            ws4.write(4 + row_i, 3, row.get("pct_of_total_revenue", 0), cell_fmt)

        chart4 = workbook.add_chart({"type": "column"})
        chart4.add_series(
            {
                "name": "% of Total Revenue",
                "categories": ["ABC Classification", 4, 0, 6, 0],
                "values": ["ABC Classification", 4, 3, 6, 3],
                "fill": {"color": "#2ecc71"},
            }
        )
        chart4.set_title({"name": "Revenue Share by ABC Tier"})
        chart4.set_x_axis({"name": "Inventory Class"})
        chart4.set_y_axis({"name": "% of Total Revenue"})
        chart4.set_size({"width": 400, "height": 300})
        ws4.insert_chart("F4", chart4)

        ws4.merge_range("A9:D9", "Insight & Recommendation", heading_fmt)
        ws4.merge_range(
            "A10:D12",
            f"Class A products ({abc_a_count} items) generate {abc_a_pct} of all revenue, "
            f"following a classic Pareto distribution. Class C ({abc_c_count} items) "
            f"contributes only {abc_c_pct}. Prioritize Class A product availability "
            "and seller reliability. Evaluate whether the long tail of Class C products "
            "justifies the catalog complexity.",
            rec_fmt,
        )
        ws4.set_row(9, 70)

        # ── Sheet 5: Orders Over Time ─────────────────────────────────────
        ws5 = workbook.add_worksheet("Orders Over Time")
        ws5.set_column("A:A", 18)
        ws5.set_column("B:C", 18)

        ws5.merge_range("A1:C1", "Monthly Order Volume Over Time", title_fmt)
        ws5.merge_range(
            "A2:C2",
            "Total orders placed each month. Shows business growth trends and seasonal patterns.",
            wrap_fmt,
        )

        ws5.write(3, 0, "Month", header_fmt)
        ws5.write(3, 1, "Total Orders", header_fmt)
        ws5.write(3, 2, "Total Revenue (BRL)", header_fmt)

        _orders_time_chart(orders_time, workbook, ws5)

        ws5.merge_range("A35:C35", "Insight & Recommendation", heading_fmt)
        ws5.merge_range(
            "A36:C38",
            "Monthly order volume reveals the overall growth trajectory of the Olist "
            "marketplace. Seasonal peaks can inform inventory and staffing decisions. "
            "Declining months should be investigated for external factors or data gaps.",
            rec_fmt,
        )
        ws5.set_row(35, 70)

        workbook.close()
        logger.info(f"Wrote report.xlsx -> {report_path}")

    except OSError as exc:
        logger.error(f"Failed to write report.xlsx: {exc}")
        raise
