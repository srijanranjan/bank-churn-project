import streamlit as st
import plotly.express as px
import pandas as pd

from data_loader import (
    load_customers, render_sidebar_filters, kpi_row,
    AGE_ORDER, CREDIT_ORDER, TENURE_ORDER, BALANCE_ORDER, GEOGRAPHY_ORDER,
    COLOR_CHURNED, COLOR_RETAINED, GEOGRAPHY_COLORS,
)

st.set_page_config(
    page_title="European Bank Churn Analytics",
    page_icon="🏦",
    layout="wide",
)

st.title("European Bank Customer Churn Analytics")
st.caption("Segmentation-driven churn analysis across France, Germany, and Spain")

df = load_customers()
filtered = render_sidebar_filters(df)

# ---- KPI row ----------------------------------------------------------
kpi_row(filtered)
st.markdown("---")

# ---- Overall churn donut + segment overview row ------------------------
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Overall Churn Split")
    status_counts = filtered["Exited"].value_counts().rename({0: "Retained", 1: "Churned"})
    fig_donut = px.pie(
        names=status_counts.index,
        values=status_counts.values,
        hole=0.55,
        color=status_counts.index,
        color_discrete_map={"Retained": COLOR_RETAINED, "Churned": COLOR_CHURNED},
    )
    fig_donut.update_traces(textinfo="percent+label")
    fig_donut.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    st.subheader("Churn Rate by Geography")
    geo_summary = (
        filtered.groupby("Geography", observed=True)["Exited"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"count": "Total", "sum": "Churned"})
    )
    geo_summary["Churn Rate %"] = (100 * geo_summary["Churned"] / geo_summary["Total"]).round(2)
    geo_summary["Geography"] = pd.Categorical(geo_summary["Geography"], categories=GEOGRAPHY_ORDER, ordered=True)
    geo_summary = geo_summary.sort_values("Geography")

    fig_geo = px.bar(
        geo_summary, x="Geography", y="Churn Rate %", text="Churn Rate %",
        color="Geography", color_discrete_map=GEOGRAPHY_COLORS,
    )
    fig_geo.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_geo.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), yaxis_title="Churn Rate (%)")
    st.plotly_chart(fig_geo, use_container_width=True)

st.markdown("---")

# ---- Segment overview grid ---------------------------------------------
st.subheader("Churn Rate by Segment")
st.caption("Quick comparison across all segmentation dimensions. Use the sidebar pages for deeper drill-downs.")

segment_specs = [
    ("AgeGroup", AGE_ORDER),
    ("CreditScoreBand", CREDIT_ORDER),
    ("TenureGroup", TENURE_ORDER),
    ("BalanceSegment", BALANCE_ORDER),
]

grid_cols = st.columns(4)
for col, (seg_col, order) in zip(grid_cols, segment_specs):
    with col:
        seg_summary = (
            filtered.groupby(seg_col, observed=True)["Exited"]
            .agg(["count", "sum"])
            .reset_index()
            .rename(columns={"count": "Total", "sum": "Churned"})
        )
        seg_summary["Churn Rate %"] = (100 * seg_summary["Churned"] / seg_summary["Total"]).round(1)
        seg_summary[seg_col] = pd.Categorical(seg_summary[seg_col], categories=order, ordered=True)
        seg_summary = seg_summary.sort_values(seg_col)

        fig = px.bar(
            seg_summary, x=seg_col, y="Churn Rate %", text="Churn Rate %",
            color_discrete_sequence=[COLOR_CHURNED],
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(
            title=seg_col, margin=dict(t=30, b=10, l=10, r=10), height=300,
            yaxis_title=None, xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(
    "Use the pages in the sidebar to explore Geography, Age & Tenure, and "
    "High-Value Customer views in more depth."
)