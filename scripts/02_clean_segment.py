import pandas as pd
from pathlib import Path

IN_PATH = Path("data/processed/01_validated.csv")
OUT_PATH = Path("data/processed/02_segmented.csv")
REPORT_PATH = Path("reports/02_segmentation_summary.txt")

def drop_non_analytical_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Remove fields with no analytical value (per brief: Surname)."""
    return df.drop(columns=["Surname"])

def convert_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Convert grouping variables to pandas 'category' dtype for memory
    efficiency and to make groupby operations explicit about intent."""
    for col in ["Geography", "Gender"]:
        df[col] = df[col].astype("category")
    return df

def add_age_segment(df: pd.DataFrame) -> pd.DataFrame:
    """Age Segmentation: <30, 30-45, 46-60, 60+"""
    bins = [0, 29, 45, 60, 200]
    labels = ["<30", "30-45", "46-60", "60+"]
    df["AgeGroup"] = pd.cut(df["Age"], bins=bins, labels=labels)
    return df

def add_credit_score_band(df: pd.DataFrame) -> pd.DataFrame:
    """Credit Score Bands: Low (<580), Medium (580-700), High (>700).
    Cut points follow common credit-scoring convention (sub-580 = poor,
    580-700 = fair/good, 700+ = very good/excellent)."""
    bins = [0, 579, 700, 1000]
    labels = ["Low", "Medium", "High"]
    df["CreditScoreBand"] = pd.cut(df["CreditScore"], bins=bins, labels=labels)
    return df

def add_tenure_group(df: pd.DataFrame) -> pd.DataFrame:
    """Tenure Groups: New (0-2 yrs), Mid-term (3-6 yrs), Long-term (7+ yrs).
    Dataset's Tenure range is 0-10 years."""
    bins = [-1, 2, 6, 100]
    labels = ["New", "Mid-term", "Long-term"]
    df["TenureGroup"] = pd.cut(df["Tenure"], bins=bins, labels=labels)
    return df

def add_balance_segment(df: pd.DataFrame) -> pd.DataFrame:
    """Balance Segments: Zero-balance (=0), Low-balance (0 < x <= median of
    non-zero balances), High-balance (above that median).
    Zero is split out explicitly since ~36% of customers carry a zero
    balance - folding that into "low" would mask a structurally distinct
    group (likely customers using the bank for products other than savings)."""
    median_nonzero = df.loc[df["Balance"] > 0, "Balance"].median()

    def classify(bal):
        if bal == 0:
            return "Zero-balance"
        elif bal <= median_nonzero:
            return "Low-balance"
        else:
            return "High-balance"

    df["BalanceSegment"] = df["Balance"].apply(classify)
    df["BalanceSegment"] = pd.Categorical(
        df["BalanceSegment"],
        categories=["Zero-balance", "Low-balance", "High-balance"],
        ordered=True,
    )
    return df

def build_summary(df: pd.DataFrame) -> str:
    """Build a human-readable summary of segment sizes for the report."""
    lines = []
    lines.append(f"Rows after cleaning: {len(df)}")
    lines.append(f"Columns: {list(df.columns)}")
    lines.append("")
    for col in ["AgeGroup", "CreditScoreBand", "TenureGroup", "BalanceSegment", "Geography"]:
        lines.append(f"--- {col} distribution ---")
        counts = df[col].value_counts().sort_index()
        pct = (df[col].value_counts(normalize=True).sort_index() * 100).round(1)
        for idx in counts.index:
            lines.append(f"  {idx}: {counts[idx]} customers ({pct[idx]}%)")
        lines.append("")
    return "\n".join(lines)

def main():
    df = pd.read_csv(IN_PATH)

    df = drop_non_analytical_fields(df)
    df = convert_categoricals(df)
    df = add_age_segment(df)
    df = add_credit_score_band(df)
    df = add_tenure_group(df)
    df = add_balance_segment(df)

    summary = build_summary(df)
    print(summary)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(summary, encoding="utf-8")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"\nSegmentation summary written to: {REPORT_PATH}")
    print(f"Segmented dataset written to: {OUT_PATH}")


if __name__ == "__main__":
    main()