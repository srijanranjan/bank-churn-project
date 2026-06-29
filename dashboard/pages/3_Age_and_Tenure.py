import streamlit as st
import plotly.express as px
import pandas as pd

from data_loader import (
    load_customers, render_sidebar_filters,
    AGE_ORDER, TENURE_ORDER, COLOR_CHURNED, COLOR_RETAINED,
)

st.set_page_config(page_title="Age & Tenure | Churn Analytics", page_icon="📊", layout="wide")
st.title("📊 Age & Tenure Churn Comparison")

df = load_customers()
filtered = render_sidebar_filters(df)

col1, col2 = st.columns(2)

# ---- Age group churn ----------------------------------------------------
with col1:
    st.subheader("Churn Rate by Age Group")
    age_summary = (
        filtered.groupby("AgeGroup", observed=True)["Exited"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"count": "Total", "sum": "Churned"})
    )
    age_summary["Churn Rate %"] = (100 * age_summary["Churned"] / age_summary["Total"]).round(2)
    age_summary["AgeGroup"] = pd.Categorical(age_summary["AgeGroup"], categories=AGE_ORDER, ordered=True)
    age_summary = age_summary.sort_values("AgeGroup")

    fig_age = px.bar(
        age_summary, x="AgeGroup", y="Churn Rate %", text="Churn Rate %",
        color_discrete_sequence=[COLOR_CHURNED],
    )
    fig_age.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_age.update_layout(yaxis_title="Churn Rate (%)", xaxis_title="Age Group", margin=dict(t=10))
    st.plotly_chart(fig_age, use_container_width=True)

    if len(age_summary) > 0:
        riskiest = age_summary.loc[age_summary["Churn Rate %"].idxmax()]
        st.info(f"Highest risk: **{riskiest['AgeGroup']}** at **{riskiest['Churn Rate %']}%** churn rate.")

# ---- Tenure group churn -------------------------------------------------
with col2:
    st.subheader("Churn Rate by Tenure Group")
    tenure_summary = (
        filtered.groupby("TenureGroup", observed=True)["Exited"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"count": "Total", "sum": "Churned"})
    )
    tenure_summary["Churn Rate %"] = (100 * tenure_summary["Churned"] / tenure_summary["Total"]).round(2)
    tenure_summary["TenureGroup"] = pd.Categorical(tenure_summary["TenureGroup"], categories=TENURE_ORDER, ordered=True)
    tenure_summary = tenure_summary.sort_values("TenureGroup")

    fig_tenure = px.bar(
        tenure_summary, x="TenureGroup", y="Churn Rate %", text="Churn Rate %",
        color_discrete_sequence=[COLOR_CHURNED],
    )
    fig_tenure.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_tenure.update_layout(yaxis_title="Churn Rate (%)", xaxis_title="Tenure Group", margin=dict(t=10))
    st.plotly_chart(fig_tenure, use_container_width=True)

    st.caption(
        "Tenure shows a much flatter churn gradient than age -- how long someone has "
        "been a customer matters far less than how old they are or how engaged they are."
    )

st.markdown("---")

# ---- Engagement: Active vs Inactive (the sharpest behavioral signal) ----
st.subheader("Engagement: Active vs Inactive Members")
st.caption(
    "Of all behavioral signals in the dataset, membership activity shows the widest "
    "gap between churned and retained customers."
)

engagement = (
    filtered.groupby("IsActiveMember", observed=True)["Exited"]
    .agg(["count", "sum"])
    .reset_index()
    .rename(columns={"count": "Total", "sum": "Churned"})
)
engagement["Status"] = engagement["IsActiveMember"].map({0: "Inactive", 1: "Active"})
engagement["Churn Rate %"] = (100 * engagement["Churned"] / engagement["Total"]).round(2)

col3, col4 = st.columns([1, 1])
with col3:
    fig_eng = px.bar(
        engagement, x="Status", y="Churn Rate %", text="Churn Rate %",
        color="Status", color_discrete_map={"Active": COLOR_RETAINED, "Inactive": COLOR_CHURNED},
    )
    fig_eng.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_eng.update_layout(showlegend=False, yaxis_title="Churn Rate (%)", margin=dict(t=10))
    st.plotly_chart(fig_eng, use_container_width=True)

with col4:
    st.dataframe(
        engagement[["Status", "Total", "Churned", "Churn Rate %"]],
        use_container_width=True, hide_index=True,
    )

st.markdown("---")

# ---- Age x Tenure heatmap (drill-down) ----------------------------------
st.subheader("Age × Tenure Churn Heatmap")
st.caption("Drill-down view: churn rate for every combination of age group and tenure group.")

pivot = filtered.pivot_table(
    index="AgeGroup", columns="TenureGroup", values="Exited", aggfunc="mean", observed=True
) * 100
pivot = pivot.reindex(index=AGE_ORDER, columns=TENURE_ORDER)

fig_heat = px.imshow(
    pivot.round(1),
    text_auto=True,
    color_continuous_scale="Oranges",
    labels=dict(color="Churn Rate %"),
)
fig_heat.update_layout(margin=dict(t=10))
st.plotly_chart(fig_heat, use_container_width=True)