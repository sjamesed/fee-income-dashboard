"""Page 2: Analysis — free filtering and pivot table."""
import streamlit as st
import pandas as pd
import plotly.express as px
from src.db import FeeIncomeDB


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

@st.cache_data
def load_data(_db, snapshot):
    rows = _db.query("""
        SELECT platform, project_name, fee_type, period_type, period, amount_usd
        FROM fee_income WHERE snapshot = ? AND period LIKE '____-__'
    """, (snapshot,))
    return pd.DataFrame(rows)

def main():
    st.title("Analysis")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    df = load_data(db, selected)
    if df.empty:
        st.info("No monthly data found for this snapshot.")
        return

    with st.sidebar:
        st.header("Filters")
        platforms = st.multiselect("Platform", sorted(df["platform"].unique()))
        projects = st.multiselect("Project", sorted(df["project_name"].unique()))
        fee_types = st.multiselect("Fee Type", sorted(df["fee_type"].unique()))
        period_types = st.multiselect("Period Type", sorted(df["period_type"].unique()), default=["actual"])
        all_periods = sorted(df["period"].unique())
        if all_periods:
            col1, col2 = st.columns(2)
            period_start = col1.selectbox("From", all_periods, index=0)
            period_end = col2.selectbox("To", all_periods, index=len(all_periods) - 1)

    filtered = df.copy()
    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]
    if projects:
        filtered = filtered[filtered["project_name"].isin(projects)]
    if fee_types:
        filtered = filtered[filtered["fee_type"].isin(fee_types)]
    if period_types:
        filtered = filtered[filtered["period_type"].isin(period_types)]
    if all_periods:
        filtered = filtered[(filtered["period"] >= period_start) & (filtered["period"] <= period_end)]

    st.write(f"**{len(filtered):,}** data points")
    agg_mode = st.radio("View", ["By Project", "By Platform", "By Fee Type"], horizontal=True)

    group_col = {"By Project": "project_name", "By Platform": "platform", "By Fee Type": "fee_type"}[agg_mode]

    if not filtered.empty:
        pivot = filtered.pivot_table(values="amount_usd", index=group_col, columns="period", aggfunc="sum", fill_value=0)
        pivot_display = (pivot / 1e6).round(1)
        st.subheader("Pivot Table (USD millions)")
        st.dataframe(pivot_display, use_container_width=True)

        st.subheader("Trend Chart")
        chart_data = filtered.groupby([group_col, "period"])["amount_usd"].sum().reset_index()
        chart_data["amount_usd"] = chart_data["amount_usd"] / 1e6
        fig = px.line(chart_data, x="period", y="amount_usd", color=group_col,
                      labels={"amount_usd": "USD millions"}, height=400)
        st.plotly_chart(fig, use_container_width=True)

main()
