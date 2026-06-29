import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/processed/bank_churn.db")
REPORT_PATH = Path("reports/06_high_value_churn.txt")
OUT_CSV_PATH = Path("data/processed/06_high_value_churn_summary.csv")


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run scripts/03_load_to_sqlite.py first.")
    return sqlite3.connect(DB_PATH)


def high_balance_churn_profile(conn: sqlite3.Connection) -> pd.DataFrame:
    """High-value churn ratio: churn rate specifically within the
    High-balance segment, compared against the other two balance segments
    as a baseline (already computed in 04, repeated here for self-containment)."""
    query = """
        SELECT
            BalanceSegment,
            COUNT(*) AS segment_size,
            SUM(Exited) AS churned_count,
            ROUND(100.0 * SUM(Exited) / COUNT(*), 2) AS churn_rate_pct,
            ROUND(SUM(CASE WHEN Exited = 1 THEN Balance ELSE 0 END), 2) AS balance_lost_to_churn,
            ROUND(SUM(Balance), 2) AS total_segment_balance
        FROM customers
        GROUP BY BalanceSegment
        ORDER BY churn_rate_pct DESC
    """
    return pd.read_sql_query(query, conn)


def salary_vs_balance_churn_pattern(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Salary vs balance are NOT the same dimension of "value" -- a customer
    can have a high salary but keep most of their money elsewhere (low
    balance with this bank), or vice versa. This cross-tab tests whether
    churn risk tracks balance, salary, both, or neither.
    """
    query = """
        SELECT
            BalanceSegment,
            CASE
                WHEN EstimatedSalary >= (SELECT AVG(EstimatedSalary) FROM customers) THEN 'Above-avg salary'
                ELSE 'Below-avg salary'
            END AS SalaryBand,
            COUNT(*) AS segment_size,
            SUM(Exited) AS churned_count,
            ROUND(100.0 * SUM(Exited) / COUNT(*), 2) AS churn_rate_pct
        FROM customers
        GROUP BY BalanceSegment, SalaryBand
        ORDER BY BalanceSegment, SalaryBand
    """
    return pd.read_sql_query(query, conn)


def revenue_risk_summary(conn: sqlite3.Connection) -> dict:
    """Quantify total revenue risk: balance held by churned customers as
    a share of total balance across the entire bank."""
    query = """
        SELECT
            COUNT(*) AS total_customers,
            SUM(Exited) AS total_churned,
            ROUND(SUM(Balance), 2) AS total_balance,
            ROUND(SUM(CASE WHEN Exited = 1 THEN Balance ELSE 0 END), 2) AS balance_at_risk,
            ROUND(SUM(CASE WHEN Exited = 1 THEN EstimatedSalary ELSE 0 END), 2) AS salary_base_of_churners
        FROM customers
    """
    row = pd.read_sql_query(query, conn).iloc[0]
    balance_share_pct = round(100.0 * row["balance_at_risk"] / row["total_balance"], 2)
    customer_share_pct = round(100.0 * row["total_churned"] / row["total_customers"], 2)
    return {
        "total_customers": int(row["total_customers"]),
        "total_churned": int(row["total_churned"]),
        "total_balance": row["total_balance"],
        "balance_at_risk": row["balance_at_risk"],
        "balance_share_pct": balance_share_pct,
        "customer_share_pct": customer_share_pct,
        "disproportion_ratio": round(balance_share_pct / customer_share_pct, 2),
    }


def germany_high_value_check(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Follow-up to 05_demographic_analysis.py: is Germany's churn problem
    (especially in the 46-60 group) concentrated among High-balance
    customers specifically, making it more costly than the raw rate implies?
    """
    query = """
        SELECT
            Geography,
            BalanceSegment,
            COUNT(*) AS segment_size,
            SUM(Exited) AS churned_count,
            ROUND(100.0 * SUM(Exited) / COUNT(*), 2) AS churn_rate_pct,
            ROUND(SUM(CASE WHEN Exited = 1 THEN Balance ELSE 0 END), 2) AS balance_lost_to_churn
        FROM customers
        WHERE Geography = 'Germany'
        GROUP BY Geography, BalanceSegment
        ORDER BY churn_rate_pct DESC
    """
    return pd.read_sql_query(query, conn)


def build_report(hb_df, sv_df, risk: dict, germany_df) -> str:
    lines = []

    lines.append("=" * 70)
    lines.append("HIGH-VALUE CUSTOMER CHURN RATIO (by BalanceSegment)")
    lines.append("=" * 70)
    lines.append(f"{'Segment':<14} {'Size':>7} {'Churned':>8} {'Rate %':>8} {'Balance Lost':>16}")
    for _, r in hb_df.iterrows():
        lines.append(
            f"{r['BalanceSegment']:<14} {int(r['segment_size']):>7} {int(r['churned_count']):>8} "
            f"{r['churn_rate_pct']:>8} {r['balance_lost_to_churn']:>16,.2f}"
        )
    lines.append("")

    lines.append("=" * 70)
    lines.append("SALARY vs BALANCE CHURN PATTERN")
    lines.append("=" * 70)
    lines.append(f"{'BalanceSeg':<14} {'SalaryBand':<18} {'Size':>7} {'Churned':>8} {'Rate %':>8}")
    for _, r in sv_df.iterrows():
        lines.append(
            f"{r['BalanceSegment']:<14} {r['SalaryBand']:<18} {int(r['segment_size']):>7} "
            f"{int(r['churned_count']):>8} {r['churn_rate_pct']:>8}"
        )
    lines.append("")
    lines.append("Interpretation note: if salary band barely changes churn rate within a")
    lines.append("given balance segment, that confirms BALANCE (not income) drives churn risk.")
    lines.append("")

    lines.append("=" * 70)
    lines.append("REVENUE RISK QUANTIFICATION")
    lines.append("=" * 70)
    lines.append(f"Total customers:              {risk['total_customers']:,}")
    lines.append(f"Total churned customers:      {risk['total_churned']:,} ({risk['customer_share_pct']}% of base)")
    lines.append(f"Total balance (whole bank):   {risk['total_balance']:,.2f}")
    lines.append(f"Balance held by churners:     {risk['balance_at_risk']:,.2f} ({risk['balance_share_pct']}% of total balance)")
    lines.append(
        f"Disproportion ratio:          {risk['disproportion_ratio']}x "
        f"(churners hold {risk['disproportion_ratio']}x the balance share their headcount share would predict)"
    )
    lines.append("")

    lines.append("=" * 70)
    lines.append("GERMANY: CHURN BY BALANCE SEGMENT (follow-up to geography-age finding)")
    lines.append("=" * 70)
    lines.append(f"{'BalanceSeg':<14} {'Size':>7} {'Churned':>8} {'Rate %':>8} {'Balance Lost':>16}")
    for _, r in germany_df.iterrows():
        lines.append(
            f"{r['BalanceSegment']:<14} {int(r['segment_size']):>7} {int(r['churned_count']):>8} "
            f"{r['churn_rate_pct']:>8} {r['balance_lost_to_churn']:>16,.2f}"
        )
    lines.append("")
    lines.append("Interpretation note: compare these rates to the bank-wide BalanceSegment")
    lines.append("rates above -- if Germany's rate is elevated across ALL balance segments,")
    lines.append("the country-level effect is broad, not concentrated in one value tier.")
    lines.append("")
    lines.append("IMPORTANT: Germany has ZERO customers in the 'Zero-balance' segment -- every")
    lines.append("German customer in this dataset carries an account balance. Since Zero-balance")
    lines.append("customers churn least bank-wide (13.82%), Germany's customer base is structurally")
    lines.append("weighted toward the higher-churn balance tiers. This explains PART of Germany's")
    lines.append("elevated overall churn rate, but Germany's Low/High-balance rates (33.3% / 31.6%)")
    lines.append("are still well above the bank-wide Low/High-balance rates (24.0% / 24.2%), so a")
    lines.append("genuine country-level effect remains on top of this structural difference.")

    return "\n".join(lines)


def main():
    conn = get_connection()

    hb_df = high_balance_churn_profile(conn)
    sv_df = salary_vs_balance_churn_pattern(conn)
    risk = revenue_risk_summary(conn)
    germany_df = germany_high_value_check(conn)

    report = build_report(hb_df, sv_df, risk, germany_df)
    print(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    OUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    hb_df.to_csv(OUT_CSV_PATH, index=False)

    print(f"\nReport written to: {REPORT_PATH}")
    print(f"High-value summary CSV written to: {OUT_CSV_PATH}")

    conn.close()


if __name__ == "__main__":
    main()