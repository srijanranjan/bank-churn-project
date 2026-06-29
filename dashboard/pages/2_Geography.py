import streamlit as st
import plotly.express as px
import pandas as pd

from data_loader import (
    load_customers, render_sidebar_filters,
    AGE_ORDER, GEOGRAPHY_ORDER, GEOGRAPHY_COLORS, COLOR_CHURNED,
)

st.set_page_config(page_title="Geography | Churn Analytics", page_icon="🌍", layout="wide")
st.title("🌍 Geography-Wise Churn Analysis")

df = load_customers()
filtered = render_sidebar_filters(df)

# ---- Country-level summary table ---------------------------------------
st.subheader("Churn by Country")

geo_summary = (
    filtered.groupby("Geography", observed=True)
    .agg(
        Customers=("CustomerId", "count"),
        Churned=("Exited", "sum"),
        Avg_Balance=("Balance", "mean"),
        Pct_Active=("IsActiveMember", "mean"),
    )
    .reset_index()
)
geo_summary["Churn Rate %"] = (100 * geo_summary["Churned"] / geo_summary["Customers"]).round(2)
geo_summary["Pct_Active"] = (100 * geo_summary["Pct_Active"]).round(1)
geo_summary["Avg_Balance"] = geo_summary["Avg_Balance"].round(0)
geo_summary["Geography"] = pd.Categorical(geo_summary["Geography"], categories=GEOGRAPHY_ORDER, ordered=True)
geo_summary = geo_summary.sort_values("Geography")

col1, col2 = st.columns([1, 1])

with col1:
    fig = px.bar(
        geo_summary, x="Geography", y="Churn Rate %", text="Churn Rate %",
        color="Geography", color_discrete_map=GEOGRAPHY_COLORS,
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(showlegend=False, yaxis_title="Churn Rate (%)", margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.dataframe(
        geo_summary.rename(columns={
            "Customers": "Customers", "Churned": "Churned",
            "Avg_Balance": "Avg Balance (€)", "Pct_Active": "% Active Members",
        })[["Geography", "Customers", "Churned", "Churn Rate %", "Avg Balance (€)", "% Active Members"]],
        use_container_width=True, hide_index=True,
    )

st.markdown("---")

# ---- Geography x Age interaction ---------------------------------------
st.subheader("Geography × Age Group Interaction")
st.caption(
    "Tests whether age-driven churn risk is consistent across countries, or "
    "amplified in a specific geography. Germany shows the strongest interaction effect."
)

cross = (
    filtered.groupby(["Geography", "AgeGroup"], observed=True)["Exited"]
    .agg(["count", "sum"])
    .reset_index()
    .rename(columns={"count": "Total", "sum": "Churned"})
)
cross["Churn Rate %"] = (100 * cross["Churned"] / cross["Total"]).round(2)
cross["AgeGroup"] = pd.Categorical(cross["AgeGroup"], categories=AGE_ORDER, ordered=True)
cross["Geography"] = pd.Categorical(cross["Geography"], categories=GEOGRAPHY_ORDER, ordered=True)
cross = cross.sort_values(["AgeGroup", "Geography"])

fig_cross = px.bar(
    cross, x="AgeGroup", y="Churn Rate %", color="Geography",
    barmode="group", color_discrete_map=GEOGRAPHY_COLORS,
    text="Churn Rate %",
)
fig_cross.update_traces(texttemplate="%{text}%", textposition="outside")
fig_cross.update_layout(yaxis_title="Churn Rate (%)", xaxis_title="Age Group", margin=dict(t=10))
st.plotly_chart(fig_cross, use_container_width=True)

# Highlight callout for the 46-60 finding, only if that age group is in the filtered data
if "46-60" in cross["AgeGroup"].astype(str).values:
    pivot = cross[cross["AgeGroup"] == "46-60"].set_index("Geography")["Churn Rate %"]
    if len(pivot) > 0:
        max_geo = pivot.idxmax()
        st.info(
            f"In the current filter selection, **{max_geo}** shows the highest churn rate "
            f"in the 46-60 age group at **{pivot.max()}%** -- the segment most worth prioritizing "
            f"for retention efforts."
        )

st.markdown("---")

# ---- Balance segment breakdown within Germany context (drill-down) -----
st.subheader("Balance Segment Mix by Country")
st.caption(
    "Germany's customer base carries no Zero-balance customers (the lowest-churn segment "
    "bank-wide), which structurally contributes to its higher overall churn rate."
)

balance_mix = (
    filtered.groupby(["Geography", "BalanceSegment"], observed=True)
    .size()
    .reset_index(name="Customers")
)
fig_mix = px.bar(
    balance_mix, x="Geography", y="Customers", color="BalanceSegment",
    barmode="stack",
    category_orders={"Geography": GEOGRAPHY_ORDER},
)
fig_mix.update_layout(margin=dict(t=10))
st.plotly_chart(fig_mix, use_container_width=True)