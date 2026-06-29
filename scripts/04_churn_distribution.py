import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/processed/bank_churn.db")
REPORT_PATH = Path("reports/04_churn_distribution.txt")
OUT_CSV_PATH = Path("data/processed/04_churn_distribution_summary.csv")

# Segments we break churn down by, per the brief's segmentation design.
SEGMENT_COLUMNS = ["Geography", "AgeGroup", "CreditScoreBand", "TenureGroup", "BalanceSegment"]

# Below this size, we flag a segment's rate as based on a small sample.
SMALL_SEGMENT_THRESHOLD = 500


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run scripts/03_load_to_sqlite.py first.")
    return sqlite3.connect(DB_PATH)


def overall_churn_rate(conn: sqlite3.Connection) -> pd.DataFrame:
    """Overall churn rate across the whole customer base."""
    query = """
        SELECT
            COUNT(*) AS total_customers,
            SUM(Exited) AS total_churned,
            ROUND(100.0 * SUM(Exited) / COUNT(*), 2) AS churn_rate_pct
        FROM customers
    """
    return pd.read_sql_query(query, conn)


def segment_churn_breakdown(conn: sqlite3.Connection, segment_col: str) -> pd.DataFrame:
    """
    For a given segment column, compute per-segment:
      - segment_size: how many customers are in this segment
      - churned_count: how many of them churned
      - churn_rate_pct: % of THIS segment that churned (segment-wise rate)
      - contribution_pct: % of ALL churners that come from this segment
                           (churn contribution by segment size)
    """
    query = f"""
        WITH segment_stats AS (
            SELECT
                {segment_col} AS segment,
                COUNT(*) AS segment_size,
                SUM(Exited) AS churned_count
            FROM customers
            GROUP BY {segment_col}
        ),
        total_churned AS (
            SELECT SUM(Exited) AS total_churned FROM customers
        )
        SELECT
            segment_stats.segment,
            segment_stats.segment_size,
            segment_stats.churned_count,
            ROUND(100.0 * segment_stats.churned_count / segment_stats.segment_size, 2) AS churn_rate_pct,
            ROUND(100.0 * segment_stats.churned_count / total_churned.total_churned, 2) AS contribution_pct
        FROM segment_stats, total_churned
        ORDER BY churn_rate_pct DESC
    """
    df = pd.read_sql_query(query, conn)
    df["segment_column"] = segment_col
    df["small_sample_flag"] = df["segment_size"] < SMALL_SEGMENT_THRESHOLD
    return df


def churned_vs_retained_profile(conn: sqlite3.Connection) -> pd.DataFrame:
    """Compare mean values of key numeric fields between churned and
    retained customers -- the brief's 'comparison of churned vs retained
    profiles' requirement."""
    query = """
        SELECT
            CASE WHEN Exited = 1 THEN 'Churned' ELSE 'Retained' END AS customer_status,
            COUNT(*) AS customer_count,
            ROUND(AVG(Age), 1) AS avg_age,
            ROUND(AVG(CreditScore), 1) AS avg_credit_score,
            ROUND(AVG(Tenure), 1) AS avg_tenure,
            ROUND(AVG(Balance), 2) AS avg_balance,
            ROUND(AVG(NumOfProducts), 2) AS avg_num_products,
            ROUND(100.0 * AVG(IsActiveMember), 1) AS pct_active_member,
            ROUND(100.0 * AVG(HasCrCard), 1) AS pct_has_cr_card,
            ROUND(AVG(EstimatedSalary), 2) AS avg_estimated_salary
        FROM customers
        GROUP BY customer_status
    """
    return pd.read_sql_query(query, conn)


def build_report(overall: pd.DataFrame, segment_dfs: dict, profile: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("OVERALL CHURN RATE")
    lines.append("=" * 70)
    row = overall.iloc[0]
    lines.append(f"Total customers: {int(row['total_customers'])}")
    lines.append(f"Total churned:   {int(row['total_churned'])}")
    lines.append(f"Churn rate:      {row['churn_rate_pct']}%")
    lines.append("")

    for segment_col, df in segment_dfs.items():
        lines.append("=" * 70)
        lines.append(f"SEGMENT-WISE CHURN: {segment_col}")
        lines.append("=" * 70)
        lines.append(f"{'Segment':<15} {'Size':>7} {'Churned':>8} {'Rate %':>8} {'Contrib %':>10}  Note")
        for _, r in df.iterrows():
            note = "SMALL SAMPLE" if r["small_sample_flag"] else ""
            lines.append(
                f"{str(r['segment']):<15} {int(r['segment_size']):>7} {int(r['churned_count']):>8} "
                f"{r['churn_rate_pct']:>8} {r['contribution_pct']:>10}  {note}"
            )
        lines.append("")

    lines.append("=" * 70)
    lines.append("CHURNED VS RETAINED PROFILE COMPARISON")
    lines.append("=" * 70)
    lines.append(profile.to_string(index=False))
    lines.append("")

    lines.append("=" * 70)
    lines.append("READING NOTES")
    lines.append("=" * 70)
    lines.append(
        f"- 'Rate %' = % of customers WITHIN that segment who churned (segment risk).\n"
        f"- 'Contrib %' = % of ALL churners that come FROM that segment (business impact).\n"
        f"  A segment can have a high rate but low contribution if it's small, or vice versa.\n"
        f"- 'SMALL SAMPLE' flags segments under {SMALL_SEGMENT_THRESHOLD} customers -- "
        f"treat their churn rate with caution."
    )

    return "\n".join(lines)


def main():
    conn = get_connection()

    overall = overall_churn_rate(conn)
    segment_dfs = {col: segment_churn_breakdown(conn, col) for col in SEGMENT_COLUMNS}
    profile = churned_vs_retained_profile(conn)

    report = build_report(overall, segment_dfs, profile)
    print(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


    # Also save a single combined CSV of all segment breakdowns for the
    # dashboard / research paper to consume directly, without re-parsing text.
    combined = pd.concat(segment_dfs.values(), ignore_index=True)
    OUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_CSV_PATH, index=False)

    print(f"\nReport written to: {REPORT_PATH}")
    print(f"Combined segment CSV written to: {OUT_CSV_PATH}")

    conn.close()


if __name__ == "__main__":
    main()