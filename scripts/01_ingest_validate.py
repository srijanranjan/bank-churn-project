import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ---- Paths -----------------------------------------------------------------
RAW_PATH = Path("data/raw/European_Bank.csv")
OUT_PATH = Path("data/processed/01_validated.csv")
REPORT_PATH = Path("reports/01_validation_report.txt")

# Expected schema per the project brief (Year is an extra column present in
# this export but not part of the brief — we keep it but flag it).
EXPECTED_COLUMNS = [
    "CustomerId", "Surname", "CreditScore", "Geography", "Gender", "Age",
    "Tenure", "Balance", "NumOfProducts", "HasCrCard", "IsActiveMember",
    "EstimatedSalary", "Exited",
]

# Expected pandas dtype "kind" per column. 'i' = integer, 'f' = float,
# 'O' = object/string. Used to catch silent coercion to 'object' (e.g. a
# stray non-numeric string landing in what should be a numeric column).
EXPECTED_DTYPE_KINDS = {
    "CustomerId": "i",
    "CreditScore": "i",
    "Geography": "O",
    "Gender": "O",
    "Age": "i",
    "Tenure": "i",
    "Balance": "f",
    "NumOfProducts": "i",
    "HasCrCard": "i",
    "IsActiveMember": "i",
    "EstimatedSalary": "f",
    "Exited": "i",
}

BINARY_COLS = ["HasCrCard", "IsActiveMember", "Exited"]
VALID_GEOGRAPHY = {"France", "Germany", "Spain"}
VALID_GENDER = {"Male", "Female"}

# Note on dedup scope: we check for exact full-row duplicates and duplicate
# CustomerId only. We deliberately do NOT attempt fuzzy/probabilistic dedup
# (e.g. same person under a slightly different Surname/Age) — that requires
# identity-resolution techniques outside this project's scope, and the brief
# does not call for it. This is a stated limitation, not an oversight.

def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"ERROR: raw data file not found at {path}")
    df = pd.read_csv(path)
    return df

def validate(df: pd.DataFrame) -> list[str]:
    """Run all validation checks and return a list of human-readable findings."""
    findings = []

    # 1. Schema check ---------------------------------------------------
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    extra_cols = [c for c in df.columns if c not in EXPECTED_COLUMNS]
    if missing_cols:
        findings.append(f"[FAIL] Missing expected columns: {missing_cols}")
    else:
        findings.append("[PASS] All expected columns present.")
    if extra_cols:
        findings.append(f"[INFO] Extra columns not in brief schema (kept as-is): {extra_cols}")

    # 1b. Dtype check ------------------------------------------------------
    # Catches the common silent-corruption case: a numeric column gets read
    # in as 'object' because one row somewhere contains a stray string
    # (e.g. "N/A", a stray comma, a typo). pandas won't error on this by
    # default — it'll just quietly give you a column of strings.
    dtype_issues = []
    for col, expected_kind in EXPECTED_DTYPE_KINDS.items():
        if col not in df.columns:
            continue
        actual_kind = df[col].dtype.kind
        if actual_kind != expected_kind:
            dtype_issues.append(f"{col} (expected {expected_kind}, got {actual_kind})")
    if dtype_issues:
        findings.append(f"[FAIL] Dtype mismatches: {dtype_issues}")
    else:
        findings.append("[PASS] All columns have the expected dtype (no silent string coercion).")

    # 2. Row count / shape -----------------------------------------------
    findings.append(f"[INFO] Shape: {df.shape[0]} rows x {df.shape[1]} columns")

    # 3. Nulls -------------------------------------------------------------
    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if len(cols_with_nulls) == 0:
        findings.append("[PASS] No null values in any column.")
    else:
        findings.append(f"[FAIL] Null values found:\n{cols_with_nulls.to_string()}")

    # 4. Duplicate rows / duplicate customer IDs --------------------------
    full_dupes = df.duplicated().sum()
    findings.append(
        f"[PASS] No duplicate rows." if full_dupes == 0
        else f"[FAIL] {full_dupes} fully duplicated rows found."
    )
    if "CustomerId" in df.columns:
        id_dupes = df["CustomerId"].duplicated().sum()
        findings.append(
            f"[PASS] CustomerId is unique (no duplicate IDs)." if id_dupes == 0
            else f"[FAIL] {id_dupes} duplicate CustomerId values found."
        )

# 5. Binary variable consistency (HasCrCard, IsActiveMember, Exited) --
    for col in BINARY_COLS:
        if col not in df.columns:
            continue
        bad_vals = set(df[col].unique()) - {0, 1}
        if bad_vals:
            findings.append(f"[FAIL] '{col}' has non-binary values: {bad_vals}")
        else:
            findings.append(f"[PASS] '{col}' is strictly binary (0/1).")

    # 6. Churn label accuracy (Exited specifically) ------------------------
    if "Exited" in df.columns:
        churn_rate = df["Exited"].mean() * 100
        findings.append(f"[INFO] Overall churn rate (Exited=1): {churn_rate:.2f}%")
        if df["Exited"].isnull().any():
            findings.append("[FAIL] Exited contains nulls — churn label incomplete.")
        else:
            findings.append("[PASS] Exited label is fully populated.")

# 7. Categorical validity (Geography, Gender) --------------------------
    if "Geography" in df.columns:
        bad_geo = set(df["Geography"].unique()) - VALID_GEOGRAPHY
        findings.append(
            f"[PASS] Geography values match expected set {VALID_GEOGRAPHY}." if not bad_geo
            else f"[FAIL] Unexpected Geography values: {bad_geo}"
        )
    if "Gender" in df.columns:
        bad_gender = set(df["Gender"].unique()) - VALID_GENDER
        findings.append(
            f"[PASS] Gender values match expected set {VALID_GENDER}." if not bad_gender
            else f"[FAIL] Unexpected Gender values: {bad_gender}"
        )

    # 8. Engagement / product field range checks ---------------------------
    if "NumOfProducts" in df.columns:
        bad_products = df[(df["NumOfProducts"] < 1) | (df["NumOfProducts"] > 4)]
        findings.append(
            "[PASS] NumOfProducts within expected range (1-4)." if bad_products.empty
            else f"[FAIL] {len(bad_products)} rows with NumOfProducts outside 1-4."
        )

# 9. Numeric sanity checks (Age, CreditScore, Balance, Tenure, Salary) --
    checks = {
        "Age": (18, 100),
        "CreditScore": (300, 850),
        "Tenure": (0, 15),
        "Balance": (0, None),
        "EstimatedSalary": (0, None),
    }
    for col, (lo, hi) in checks.items():
        if col not in df.columns:
            continue
        too_low = df[df[col] < lo] if lo is not None else pd.DataFrame()
        too_high = df[df[col] > hi] if hi is not None else pd.DataFrame()
        if too_low.empty and too_high.empty:
            findings.append(f"[PASS] '{col}' within plausible range ({lo}–{hi}).")
        else:
            findings.append(
                f"[WARN] '{col}' has {len(too_low)} rows below {lo} and "
                f"{len(too_high)} rows above {hi}."
            )
# 10. Engagement cross-field consistency --------------------------------
    # These are soft logical checks, not hard failures — a customer CAN
    # legitimately be inactive with a high balance (e.g. a dormant savings
    # account). We flag them as INFO so the patterns are visible going into
    # EDA, not because they indicate a data quality problem.
    if {"IsActiveMember", "Balance"}.issubset(df.columns):
        inactive_high_balance = df[(df["IsActiveMember"] == 0) & (df["Balance"] > df["Balance"].quantile(0.75))]
        findings.append(
            f"[INFO] {len(inactive_high_balance)} inactive members ({len(inactive_high_balance)/len(df)*100:.1f}%) "
            f"hold balances in the top quartile — worth investigating as a churn-risk segment."
        )
    if {"NumOfProducts", "IsActiveMember"}.issubset(df.columns):
        single_product_inactive = df[(df["NumOfProducts"] == 1) & (df["IsActiveMember"] == 0)]
        findings.append(
            f"[INFO] {len(single_product_inactive)} customers ({len(single_product_inactive)/len(df)*100:.1f}%) "
            f"hold only 1 product AND are inactive — classic disengagement profile."
        )

    # 11. Statistical outlier detection (IQR method) -------------------------
    # Range checks (section 9) catch impossible values. This catches
    # legitimate-but-extreme values worth knowing about before EDA, so
    # outliers don't show up as a "surprise" later in segment analysis.
    outlier_cols = ["CreditScore", "Age", "Balance", "EstimatedSalary"]
    for col in outlier_cols:
        if col not in df.columns:
            continue
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        lower_fence, upper_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = df[(df[col] < lower_fence) | (df[col] > upper_fence)]
        pct = len(outliers) / len(df) * 100
        findings.append(
            f"[INFO] '{col}': {len(outliers)} statistical outliers ({pct:.1f}%) "
            f"outside IQR fences [{lower_fence:.1f}, {upper_fence:.1f}]."
        )

    return findings

def main():
    df = load_data(RAW_PATH)
    findings = validate(df)

    report_text = "\n".join(findings)
    print(report_text)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"\nValidation report written to: {REPORT_PATH}")
    print(f"Validated dataset written to: {OUT_PATH}")

    failures = [f for f in findings if f.startswith("[FAIL]")]
    if failures:
        print(f"\n{len(failures)} validation check(s) FAILED. See report for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()