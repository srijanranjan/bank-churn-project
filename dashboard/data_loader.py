import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "processed" / "bank_churn.db"

# Consistent ordering for categorical segments so charts don't randomly
# reorder bars/axes between pages.
AGE_ORDER = ["<30", "30-45", "46-60", "60+"]
CREDIT_ORDER = ["Low", "Medium", "High"]
TENURE_ORDER = ["New", "Mid-term", "Long-term"]
BALANCE_ORDER = ["Zero-balance", "Low-balance", "High-balance"]
GEOGRAPHY_ORDER = ["France", "Germany", "Spain"]

# A small, deliberate banking-appropriate palette: deep navy as the base
# (trust, stability), a warm amber for "churned/at-risk" so it reads as a
# warning without being alarmist red, and a muted teal for "retained".
COLOR_CHURNED = "#C9722D"     # warm amber/rust -- "at risk"
COLOR_RETAINED = "#2A6F77"    # muted teal -- "stable"
COLOR_NEUTRAL = "#1F3A5F"     # deep navy -- neutral/base bars
COLOR_ACCENT = "#8A8D91"      # grey -- secondary/context bars

GEOGRAPHY_COLORS = {"France": "#1F3A5F", "Germany": "#C9722D", "Spain": "#5B8A72"}


@st.cache_data
def load_customers() -> pd.DataFrame:
    """Load the full customers table. Cached so every page doesn't re-hit
    the database on every interaction/filter change."""
    if not DB_PATH.exists():
        st.error(
            f"Database not found at {DB_PATH}. "
            f"Run `python scripts/run_pipeline.py` from the project root first."
        )
        st.stop()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()

    # Re-apply categorical ordering (SQLite doesn't preserve pandas Categorical order)
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
    """Renders a standard row of top-line KPIs. Used at the top of most
    pages so users always see the headline numbers before drilling down."""
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