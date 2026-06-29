import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/processed/bank_churn.db")
REPORT_PATH = Path("reports/05_demographic_analysis.txt")
OUT_CSV_PATH = Path("data/processed/05_geography_age_interaction.csv")

SMALL_SEGMENT_THRESHOLD = 100  # smaller threshold here since geography x age cells are finer-grained


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run scripts/03_load_to_sqlite.py first.")
    return sqlite3.connect(DB_PATH)


def gender_churn_breakdown(conn: sqlite3.Connection) -> pd.DataFrame:
    """Gender-based churn differences: rate and contribution, same logic
    as the segment breakdowns in 04_churn_distribution.py."""
    query = """
        WITH gender_stats AS (
            SELECT Gender, COUNT(*) AS segment_size, SUM(Exited) AS churned_count
            FROM customers
            GROUP BY Gender
        ),
        total_churned AS (SELECT SUM(Exited) AS total_churned FROM customers)
        SELECT
            gender_stats.Gender,
            gender_stats.segment_size,
            gender_stats.churned_count,
            ROUND(100.0 * gender_stats.churned_count / gender_stats.segment_size, 2) AS churn_rate_pct,
            ROUND(100.0 * gender_stats.churned_count / total_churned.total_churned, 2) AS contribution_pct
        FROM gender_stats, total_churned
        ORDER BY churn_rate_pct DESC
    """
    return pd.read_sql_query(query, conn)


def geography_age_interaction(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Geography x AgeGroup interaction. The key question: is the 46-60 age
    group's high churn risk (seen in 04_churn_distribution.py) consistent
    across all three countries, or is it concentrated/amplified in one
    geography? This cross-tab answers that directly.
    """
    query = """
        WITH cell_stats AS (
            SELECT
                Geography,
                AgeGroup,
                COUNT(*) AS segment_size,
                SUM(Exited) AS churned_count
            FROM customers
            GROUP BY Geography, AgeGroup
        )
        SELECT
            Geography,
            AgeGroup,
            segment_size,
            churned_count,
            ROUND(100.0 * churned_count / segment_size, 2) AS churn_rate_pct
        FROM cell_stats
        ORDER BY Geography, churn_rate_pct DESC
    """
    df = pd.read_sql_query(query, conn)
    df["small_sample_flag"] = df["segment_size"] < SMALL_SEGMENT_THRESHOLD
    return df


def financial_stability_vs_churn(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Financial stability vs churn: cross CreditScoreBand x BalanceSegment
    against churn rate. Tests the hypothesis that "financially stable"
    customers (high credit score AND high balance) churn less.
    """
    query = """
        WITH cell_stats AS (
            SELECT
                CreditScoreBand,
                BalanceSegment,
                COUNT(*) AS segment_size,
                SUM(Exited) AS churned_count
            FROM customers
            GROUP BY CreditScoreBand, BalanceSegment
        )
        SELECT
            CreditScoreBand,
            BalanceSegment,
            segment_size,
            churned_count,
            ROUND(100.0 * churned_count / segment_size, 2) AS churn_rate_pct
        FROM cell_stats
        ORDER BY CreditScoreBand, BalanceSegment
    """
    df = pd.read_sql_query(query, conn)
    df["small_sample_flag"] = df["segment_size"] < SMALL_SEGMENT_THRESHOLD
    return df


def build_report(gender_df, geo_age_df, fin_df) -> str:
    lines = []

    lines.append("=" * 70)
    lines.append("GENDER-BASED CHURN DIFFERENCES")
    lines.append("=" * 70)
    lines.append(f"{'Gender':<10} {'Size':>7} {'Churned':>8} {'Rate %':>8} {'Contrib %':>10}")
    for _, r in gender_df.iterrows():
        lines.append(
            f"{r['Gender']:<10} {int(r['segment_size']):>7} {int(r['churned_count']):>8} "
            f"{r['churn_rate_pct']:>8} {r['contribution_pct']:>10}"
        )
    lines.append("")

    lines.append("=" * 70)
    lines.append("GEOGRAPHY x AGE GROUP INTERACTION")
    lines.append("=" * 70)
    lines.append(f"{'Geography':<10} {'AgeGroup':<10} {'Size':>7} {'Churned':>8} {'Rate %':>8}  Note")
    for _, r in geo_age_df.iterrows():
        note = "SMALL SAMPLE" if r["small_sample_flag"] else ""
        lines.append(
            f"{r['Geography']:<10} {r['AgeGroup']:<10} {int(r['segment_size']):>7} "
            f"{int(r['churned_count']):>8} {r['churn_rate_pct']:>8}  {note}"
        )
    lines.append("")
    lines.append("Interpretation note: compare the 46-60 row across all three countries")
    lines.append("to see whether age-driven churn risk is uniform or geography-amplified.")
    lines.append("")

    lines.append("=" * 70)
    lines.append("FINANCIAL STABILITY (CreditScoreBand x BalanceSegment) vs CHURN")
    lines.append("=" * 70)
    lines.append(f"{'CreditBand':<12} {'BalanceSeg':<14} {'Size':>7} {'Churned':>8} {'Rate %':>8}  Note")
    for _, r in fin_df.iterrows():
        note = "SMALL SAMPLE" if r["small_sample_flag"] else ""
        lines.append(
            f"{r['CreditScoreBand']:<12} {r['BalanceSegment']:<14} {int(r['segment_size']):>7} "
            f"{int(r['churned_count']):>8} {r['churn_rate_pct']:>8}  {note}"
        )
    lines.append("")
    lines.append("Interpretation note: if 'financial stability' protected against churn, we'd")
    lines.append("expect High credit + High/Zero balance cells to show the LOWEST churn rates.")

    return "\n".join(lines)


def main():
    conn = get_connection()

    gender_df = gender_churn_breakdown(conn)
    geo_age_df = geography_age_interaction(conn)
    fin_df = financial_stability_vs_churn(conn)

    report = build_report(gender_df, geo_age_df, fin_df)
    print(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    OUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    geo_age_df.to_csv(OUT_CSV_PATH, index=False)

    print(f"\nReport written to: {REPORT_PATH}")
    print(f"Geography x AgeGroup CSV written to: {OUT_CSV_PATH}")

    conn.close()


if __name__ == "__main__":
    main()