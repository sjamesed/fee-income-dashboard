"""Page 1: Overview — summary cards, charts, FY tables, variance commentary, and watch list."""
import streamlit as st
import pandas as pd
import plotly.express as px
from src.db import FeeIncomeDB
from src.queries import (
    get_fee_by_project_fy, get_fee_by_platform_fy,
    get_mtd_comparison, get_ytd_comparison, get_fy_comparison, get_yoy_comparison,
    get_snapshot_n_value,
)

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

def format_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}"

def fmt_m(value: float) -> str:
    """Format a raw USD value as $X.XM string."""
    return f"${value / 1_000_000:.1f}M"

def add_grand_total(df: pd.DataFrame, label_col: str, numeric_cols: list[str]) -> pd.DataFrame:
    """Append a Grand Total row summing numeric_cols."""
    totals = {label_col: "Grand Total"}
    for col in df.columns:
        if col in numeric_cols:
            totals[col] = round(df[col].sum(), 1)
        elif col != label_col:
            totals[col] = ""
    totals_df = pd.DataFrame([totals])
    return pd.concat([df, totals_df], ignore_index=True)


def render_variance_section(title, items, col_a, col_b, label_a, label_b, use_numbers=True):
    """Render a variance commentary sub-section."""
    if not items:
        st.write("No data available.")
        return
    # Sort by absolute variance descending, take top 5
    sorted_items = sorted(items, key=lambda r: abs(r[col_a] - r[col_b]), reverse=True)[:5]
    markers = ["\u2460", "\u2461", "\u2462", "\u2463", "\u2464"] if use_numbers else ["A.", "B.", "C.", "D.", "E."]
    lines = []
    for i, row in enumerate(sorted_items):
        a_val = row[col_a]
        b_val = row[col_b]
        var = a_val - b_val
        direction = "higher" if var > 0 else "lower"
        name = row.get("project_name", "Unknown")
        lines.append(
            f"{markers[i]} **{name}**: [{label_a} {fmt_m(a_val)} vs {label_b} {fmt_m(b_val)}, "
            f"var {fmt_m(var)}] — fee income {direction} than {label_b.split()[0] if ' ' in label_b else label_b}"
        )
    st.markdown("\n\n".join(lines))


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

    n = get_snapshot_n_value(selected)
    month_name = MONTH_NAMES.get(n, str(n))

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
        value_cols = ["FY23 Act", "FY24 Act", "FY25 Act", "FY26 Bud", "FY26 Fcst"]
        for col in value_cols:
            df_display[col] = df_display[col].apply(lambda x: round(x / 1e6, 1))
        df_display = add_grand_total(df_display, "Project", value_cols)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Fee by Platform Table (collapsible with project detail)
    st.subheader("Fee by Platform (FY)")
    if platform_data and project_data:
        value_col_names = ["FY23 Act", "FY24 Act", "FY25 Act", "FY26 Bud", "FY26 Fcst"]
        raw_cols = ["fy23_act", "fy24_act", "fy25_act", "fy26_bud", "fy26_fcst"]
        for plat_row in platform_data:
            plat_name = plat_row["platform"]
            plat_vals = " | ".join(f"{round(plat_row[c] / 1e6, 1)}" for c in raw_cols)
            with st.expander(f"**{plat_name}** — {plat_vals}"):
                plat_projects = [p for p in project_data if p["platform"] == plat_name]
                if plat_projects:
                    df_pp = pd.DataFrame(plat_projects)
                    df_pp_display = df_pp[["project_name"] + raw_cols].rename(
                        columns=dict(zip(["project_name"] + raw_cols, ["Project"] + value_col_names)))
                    for col in value_col_names:
                        df_pp_display[col] = df_pp_display[col].apply(lambda x: round(x / 1e6, 1))
                    df_pp_display = add_grand_total(df_pp_display, "Project", value_col_names)
                    st.dataframe(df_pp_display, use_container_width=True, hide_index=True)

    # --- Key Variance Commentary ---
    st.markdown("---")
    st.header("Key Variance Commentary")

    mtd_data = get_mtd_comparison(db, selected)
    ytd_data = get_ytd_comparison(db, selected)
    fy_data = get_fy_comparison(db, selected)
    yoy_data = get_yoy_comparison(db, selected)

    st.subheader(f"MTD key variances vs Budget ({month_name})")
    render_variance_section("MTD", mtd_data, "mtd_act", "mtd_bud", "Act", "Bud", use_numbers=True)

    st.subheader(f"YTD key variances vs Budget (Jan-{month_name})")
    render_variance_section("YTD", ytd_data, "ytd_act", "ytd_bud", "YTD Act", "YTD Bud", use_numbers=True)

    st.subheader("Full year key variances vs Budget")
    render_variance_section("FY vs Bud", fy_data, "fy_fcst", "fy_bud", "Fcst", "Bud", use_numbers=False)

    st.subheader("Full year key variances vs FY25")
    render_variance_section("FY vs FY25", yoy_data, "fy26", "fy25", "FY26", "FY25", use_numbers=False)

    # --- Watch List ---
    st.markdown("---")
    st.header("Watch List FY2026")

    watch_items = db.get_watch_list()

    pnl_items = [w for w in watch_items if w.get("category") == "P&L"]
    cf_items = [w for w in watch_items if w.get("category") == "CF"]

    watch_cols = ["fund_project", "impact_mil", "lost_delay", "comment"]
    watch_labels = {"fund_project": "Fund/Project", "impact_mil": "Impact($mil)", "lost_delay": "Lost/Delay", "comment": "Comment"}

    if pnl_items:
        st.subheader("P&L Watch List")
        df_pnl = pd.DataFrame(pnl_items)[watch_cols].rename(columns=watch_labels)
        st.dataframe(df_pnl, use_container_width=True, hide_index=True)
    if cf_items:
        st.subheader("CF Watch List")
        df_cf = pd.DataFrame(cf_items)[watch_cols].rename(columns=watch_labels)
        st.dataframe(df_cf, use_container_width=True, hide_index=True)
    if not pnl_items and not cf_items:
        st.info("No watch list items. Use the editor below to add items.")

    with st.expander("Edit Watch List"):
        if watch_items:
            edit_data = [{"category": w["category"], "fund_project": w["fund_project"],
                          "impact_mil": w.get("impact_mil"), "lost_delay": w.get("lost_delay", ""),
                          "comment": w.get("comment", "")} for w in watch_items]
        else:
            edit_data = [{"category": "P&L", "fund_project": "", "impact_mil": None, "lost_delay": "", "comment": ""}]
        edited_df = st.data_editor(
            pd.DataFrame(edit_data),
            num_rows="dynamic",
            column_config={
                "category": st.column_config.SelectboxColumn("P&L/CF", options=["P&L", "CF"], required=True),
                "fund_project": st.column_config.TextColumn("Fund/Project", required=True),
                "impact_mil": st.column_config.NumberColumn("Impact($mil)"),
                "lost_delay": st.column_config.TextColumn("Lost/Delay"),
                "comment": st.column_config.TextColumn("Comment"),
            },
            use_container_width=True,
            hide_index=True,
            key="watch_list_editor",
        )
        if st.button("Save Watch List"):
            rows_to_save = edited_df.dropna(subset=["fund_project"])
            rows_to_save = rows_to_save[rows_to_save["fund_project"].str.strip() != ""]
            items_to_save = rows_to_save.to_dict("records")
            db.update_watch_list(items_to_save)
            st.success(f"Saved {len(items_to_save)} watch list item(s).")
            st.rerun()

main()
