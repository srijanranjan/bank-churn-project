import sqlite3
import subprocess
import sys
import pandas as pd
import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "bank_churn.db"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

BUILD_STAGES = [
    "01_ingest_validate.py",
    "02_clean_segment.py",
    "03_load_to_sqlite.py",
]

AGE_ORDER = ["<30", "30-45", "46-60", "60+"]
CREDIT_ORDER = ["Low", "Medium", "High"]
TENURE_ORDER = ["New", "Mid-term", "Long-term"]
BALANCE_ORDER = ["Zero-balance", "Low-balance", "High-balance"]
GEOGRAPHY_ORDER = ["France", "Germany", "Spain"]

COLOR_CHURNED = "#C9722D"     # warm amber/rust -- "at risk"
COLOR_RETAINED = "#2A6F77"    # muted teal -- "stable"
COLOR_NEUTRAL = "#1F3A5F"     # deep navy -- neutral/base bars
COLOR_ACCENT = "#8A8D91"      # grey -- secondary/context bars

GEOGRAPHY_COLORS = {"France": "#1F3A5F", "Germany": "#C9722D", "Spain": "#5B8A72"}


def build_database_if_missing() -> None:

    if DB_PATH.exists():
        return

    raw_csv = PROJECT_ROOT / "data" / "raw" / "European_Bank.csv"
    if not raw_csv.exists():
        st.error(
            f"Raw data file not found at {raw_csv}. This file must be committed "
            f"to the repository for the app to build its database on first run."
        )
        st.stop()

    with st.spinner("First-time setup: building database from raw data..."):
        for stage in BUILD_STAGES:
            script_path = SCRIPTS_DIR / stage
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                st.error(f"Setup failed while running {stage}:\n\n{result.stderr}")
                st.stop()


@st.cache_data
def load_customers() -> pd.DataFrame:

    build_database_if_missing()

    if not DB_PATH.exists():
        st.error(
            f"Database not found at {DB_PATH}. "
            f"Run `python scripts/run_pipeline.py` from the project root first."
        )
        st.stop()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()

    
    df["AgeGroup"] = pd.Categorical(df["AgeGroup"], categories=AGE_ORDER, ordered=True)
    df["CreditScoreBand"] = pd.Categorical(df["CreditScoreBand"], categories=CREDIT_ORDER, ordered=True)
    df["TenureGroup"] = pd.Categorical(df["TenureGroup"], categories=TENURE_ORDER, ordered=True)
    df["BalanceSegment"] = pd.Categorical(df["BalanceSegment"], categories=BALANCE_ORDER, ordered=True)
    return df


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders the standard filter set in the sidebar and returns the
    filtered dataframe. Used by every page so filters behave identically
    everywhere (the brief's 'Segment filters' + 'Dynamic KPI updates'
    requirement).
    """
    st.sidebar.header("Filters")

    geo_filter = st.sidebar.multiselect(
        "Geography", options=GEOGRAPHY_ORDER, default=GEOGRAPHY_ORDER
    )
    age_filter = st.sidebar.multiselect(
        "Age Group", options=AGE_ORDER, default=AGE_ORDER
    )
    balance_filter = st.sidebar.multiselect(
        "Balance Segment", options=BALANCE_ORDER, default=BALANCE_ORDER
    )
    gender_filter = st.sidebar.multiselect(
        "Gender", options=["Male", "Female"], default=["Male", "Female"]
    )

    filtered = df[
        df["Geography"].isin(geo_filter)
        & df["AgeGroup"].isin(age_filter)
        & df["BalanceSegment"].isin(balance_filter)
        & df["Gender"].isin(gender_filter)
    ]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"{len(filtered):,} of {len(df):,} customers shown")

    if filtered.empty:
        st.warning("No customers match the current filters. Adjust the filters in the sidebar.")
        st.stop()

    return filtered


def kpi_row(df: pd.DataFrame) -> None:

    total = len(df)
    churned = int(df["Exited"].sum())
    churn_rate = round(100 * churned / total, 2) if total else 0
    avg_balance = df["Balance"].mean()
    balance_at_risk = df.loc[df["Exited"] == 1, "Balance"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Customers", f"{total:,}")
    c2.metric("Churned", f"{churned:,}", delta=f"{churn_rate}% churn rate", delta_color="inverse")
    c3.metric("Avg Balance", f"€{avg_balance:,.0f}")
    c4.metric("Balance at Risk", f"€{balance_at_risk:,.0f}")