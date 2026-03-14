"""Page 1: Overview — summary cards, charts, and FY tables."""
import streamlit as st
import pandas as pd
import plotly.express as px
from src.db import FeeIncomeDB
from src.queries import get_fee_by_project_fy, get_fee_by_platform_fy

@st.cache_resource
def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def format_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}"

def main():
    st.title("Overview")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded. Go to Data Management to upload.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    # Summary Cards
    totals = db.query("""
        SELECT
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy_fcst,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'budget' THEN amount_usd ELSE 0 END) as fy_bud
        FROM fee_income WHERE snapshot = ? AND period = 'FY26'
    """, (selected,))

    if totals:
        t = totals[0]
        fy_fcst = t["fy_fcst"] or 0
        fy_bud = t["fy_bud"] or 0
        variance = fy_fcst - fy_bud
        var_pct = (variance / fy_bud * 100) if fy_bud != 0 else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("FY26 Forecast", f"${format_millions(fy_fcst)}M")
        c2.metric("FY26 Budget", f"${format_millions(fy_bud)}M")
        c3.metric("Variance", f"${format_millions(variance)}M", delta=f"{var_pct:+.1f}%")
        c4.metric("Variance %", f"{var_pct:+.1f}%")

    # Platform Bar Chart
    st.subheader("Fee Income by Platform")
    platform_data = get_fee_by_platform_fy(db, selected)
    project_data = get_fee_by_project_fy(db, selected)

    if platform_data:
        df_plat = pd.DataFrame(platform_data)
        df_chart = pd.DataFrame({
            "Platform": df_plat["platform"].tolist() * 2,
            "Amount (USD M)": [v / 1e6 for v in df_plat["fy26_fcst"]] + [v / 1e6 for v in df_plat["fy26_bud"]],
            "Type": ["FY26 Fcst"] * len(df_plat) + ["FY26 Bud"] * len(df_plat),
        })
        fig = px.bar(df_chart, x="Platform", y="Amount (USD M)", color="Type", barmode="group", height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Fee by Project (FY) Table
    st.subheader("Fee by Project (FY)")
    if project_data:
        df_proj = pd.DataFrame(project_data)
        display_cols = {"platform": "Platform", "project_name": "Project",
            "fy23_act": "FY23 Act", "fy24_act": "FY24 Act", "fy25_act": "FY25 Act",
            "fy26_bud": "FY26 Bud", "fy26_fcst": "FY26 Fcst"}
        df_display = df_proj[list(display_cols.keys())].rename(columns=display_cols)
        for col in ["FY23 Act", "FY24 Act", "FY25 Act", "FY26 Bud", "FY26 Fcst"]:
            df_display[col] = df_display[col].apply(lambda x: round(x / 1e6, 1))
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Fee by Platform Table (collapsible with project detail)
    st.subheader("Fee by Platform (FY)")
    if platform_data and project_data:
        value_cols = ["FY23 Act", "FY24 Act", "FY25 Act", "FY26 Bud", "FY26 Fcst"]
        raw_cols = ["fy23_act", "fy24_act", "fy25_act", "fy26_bud", "fy26_fcst"]
        for plat_row in platform_data:
            plat_name = plat_row["platform"]
            plat_vals = " | ".join(f"{round(plat_row[c] / 1e6, 1)}" for c in raw_cols)
            with st.expander(f"**{plat_name}** — {plat_vals}"):
                plat_projects = [p for p in project_data if p["platform"] == plat_name]
                if plat_projects:
                    df_pp = pd.DataFrame(plat_projects)
                    df_pp_display = df_pp[["project_name"] + raw_cols].rename(
                        columns=dict(zip(["project_name"] + raw_cols, ["Project"] + value_cols)))
                    for col in value_cols:
                        df_pp_display[col] = df_pp_display[col].apply(lambda x: round(x / 1e6, 1))
                    st.dataframe(df_pp_display, use_container_width=True, hide_index=True)

main()
