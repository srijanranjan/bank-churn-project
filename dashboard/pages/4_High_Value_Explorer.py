import streamlit as st
import plotly.express as px
import pandas as pd

from data_loader import (
    load_customers, render_sidebar_filters,
    BALANCE_ORDER, COLOR_CHURNED, COLOR_RETAINED,
)

st.set_page_config(page_title="High-Value Explorer | Churn Analytics", page_icon="💰", layout="wide")
st.title("💰 High-Value Customer Churn Explorer")

df = load_customers()
filtered = render_sidebar_filters(df)

# ---- Revenue risk summary -----------------------------------------------
st.subheader("Revenue Risk Summary")

total_balance = filtered["Balance"].sum()
balance_at_risk = filtered.loc[filtered["Exited"] == 1, "Balance"].sum()
balance_share_pct = round(100 * balance_at_risk / total_balance, 2) if total_balance else 0
customer_share_pct = round(100 * filtered["Exited"].mean(), 2)
disproportion = round(balance_share_pct / customer_share_pct, 2) if customer_share_pct else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Balance", f"€{total_balance:,.0f}")
c2.metric("Balance at Risk (Churned)", f"€{balance_at_risk:,.0f}", f"{balance_share_pct}% of total")
c3.metric("Customer Share Churned", f"{customer_share_pct}%")
c4.metric("Disproportion Ratio", f"{disproportion}x", help="Churners' share of balance ÷ their share of customers. >1 means churners are disproportionately high-value.")

st.markdown("---")

# ---- Churn by balance segment -------------------------------------------
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Churn Rate by Balance Segment")
    bal_summary = (
        filtered.groupby("BalanceSegment", observed=True)
        .agg(Total=("CustomerId", "count"), Churned=("Exited", "sum"), Balance_Lost=("Balance", lambda s: s[filtered.loc[s.index, "Exited"] == 1].sum()))
        .reset_index()
    )
    bal_summary["Churn Rate %"] = (100 * bal_summary["Churned"] / bal_summary["Total"]).round(2)
    bal_summary["BalanceSegment"] = pd.Categorical(bal_summary["BalanceSegment"], categories=BALANCE_ORDER, ordered=True)
    bal_summary = bal_summary.sort_values("BalanceSegment")

    fig_bal = px.bar(
        bal_summary, x="BalanceSegment", y="Churn Rate %", text="Churn Rate %",
        color_discrete_sequence=[COLOR_CHURNED],
    )
    fig_bal.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_bal.update_layout(yaxis_title="Churn Rate (%)", xaxis_title=None, margin=dict(t=10))
    st.plotly_chart(fig_bal, use_container_width=True)

with col2:
    st.subheader("Balance Lost to Churn, by Segment")
    fig_lost = px.bar(
        bal_summary, x="BalanceSegment", y="Balance_Lost",
        color_discrete_sequence=[COLOR_CHURNED],
        labels={"Balance_Lost": "Balance Lost (€)"},
    )
    fig_lost.update_layout(yaxis_title="Balance Lost (€)", xaxis_title=None, margin=dict(t=10))
    st.plotly_chart(fig_lost, use_container_width=True)

st.markdown("---")

# ---- Salary vs Balance churn pattern -------------------------------------
st.subheader("Salary vs Balance Churn Pattern")
st.caption(
    "Tests whether income (salary) or wealth held at this bank (balance) better predicts "
    "churn. The research found balance segment matters far more than salary band."
)

avg_salary = filtered["EstimatedSalary"].mean()
sv = filtered.copy()
sv["SalaryBand"] = sv["EstimatedSalary"].apply(lambda x: "Above-avg salary" if x >= avg_salary else "Below-avg salary")

sv_summary = (
    sv.groupby(["BalanceSegment", "SalaryBand"], observed=True)["Exited"]
    .agg(["count", "sum"])
    .reset_index()
    .rename(columns={"count": "Total", "sum": "Churned"})
)
sv_summary["Churn Rate %"] = (100 * sv_summary["Churned"] / sv_summary["Total"]).round(2)
sv_summary["BalanceSegment"] = pd.Categorical(sv_summary["BalanceSegment"], categories=BALANCE_ORDER, ordered=True)
sv_summary = sv_summary.sort_values(["BalanceSegment", "SalaryBand"])

fig_sv = px.bar(
    sv_summary, x="BalanceSegment", y="Churn Rate %", color="SalaryBand",
    barmode="group", text="Churn Rate %",
)
fig_sv.update_traces(texttemplate="%{text}%", textposition="outside")
fig_sv.update_layout(yaxis_title="Churn Rate (%)", xaxis_title=None, margin=dict(t=10))
st.plotly_chart(fig_sv, use_container_width=True)

st.markdown("---")

# ---- Drill-down: searchable high-value churner table ---------------------
st.subheader("High-Value Churner Drill-Down")
st.caption("Customer-level view of High-balance customers who churned. Sortable by clicking column headers.")

high_value_churners = filtered[
    (filtered["BalanceSegment"] == "High-balance") & (filtered["Exited"] == 1)
].sort_values("Balance", ascending=False)

slider_min = int(filtered["Balance"].min())
slider_max = int(filtered["Balance"].max())
slider_default = int(high_value_churners["Balance"].min()) if len(high_value_churners) else slider_min

min_balance = st.slider(
    "Minimum balance filter (€)",
    min_value=slider_min,
    max_value=slider_max,
    value=slider_default,
)
drill = high_value_churners[high_value_churners["Balance"] >= min_balance]

st.dataframe(
    drill[[
        "CustomerId", "Geography", "Gender", "Age", "Tenure", "Balance",
        "NumOfProducts", "IsActiveMember", "CreditScore", "EstimatedSalary",
    ]].rename(columns={"IsActiveMember": "Active?"}),
    use_container_width=True, hide_index=True,
)
st.caption(f"Showing {len(drill):,} high-balance churned customers (≥ €{min_balance:,}).")