"""Page 2: Analysis — Fee by Project interactive table with side-by-side comparison."""
import streamlit as st
import pandas as pd
from src.db import FeeIncomeDB
from src.queries import get_snapshot_n_value, PLATFORM_ORDER, sort_by_platform

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

HEADER_COLOR = "#4a5568"


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db


def build_metric_options(snapshot):
    """Build list of available metrics based on snapshot."""
    n = get_snapshot_n_value(snapshot)
    month = MONTH_NAMES.get(n, str(n))
    return {
        "FY23 Act": ("FY23", "actual"),
        "FY24 Act": ("FY24", "actual"),
        "FY25 Act": ("FY25", "actual"),
        "FY26 Bud": ("FY26", "budget"),
        f"FY26 Fcst ({snapshot})": ("FY26", "forecast"),
        f"MTD {month} Act": ("mtd_act", n),
        f"MTD {month} Bud": ("mtd_bud", n),
        f"YTD Jan-{month} Act": ("ytd_act", n),
        f"YTD Jan-{month} Bud": ("ytd_bud", n),
    }


def query_metric(db, snapshot, metric_key, metric_def):
    """Query fee by project for a given metric definition. Returns sorted list of dicts."""
    period_or_type, param = metric_def

    if period_or_type in ("mtd_act", "mtd_bud"):
        n = param
        month = f"2026-{n:02d}"
        pt = "actual" if "act" in period_or_type else "budget"
        rows = db.query("""
            SELECT project_name, platform, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period = ? AND period_type = ?
            GROUP BY project_name, platform
        """, (snapshot, month, pt))

    elif period_or_type in ("ytd_act", "ytd_bud"):
        n = param
        months = [f"2026-{m:02d}" for m in range(1, n + 1)]
        placeholders = ",".join(["?"] * len(months))
        pt = "actual" if "act" in period_or_type else "budget"
        rows = db.query(f"""
            SELECT project_name, platform, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period IN ({placeholders}) AND period_type = ?
            GROUP BY project_name, platform
        """, (snapshot, *months, pt))

    else:
        period, period_type = period_or_type, param
        rows = db.query("""
            SELECT project_name, platform, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period = ? AND period_type = ?
            GROUP BY project_name, platform
        """, (snapshot, period, period_type))

    return sort_by_platform(rows)


def build_project_table_html(data, metric_label, show_platform=True):
    """Build styled HTML table for Fee by Project."""
    if not data:
        return "<p>No data</p>"

    platform_col = '<th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Platform</th>' if show_platform else ""
    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        {platform_col}
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Project</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{metric_label}</th>
    </tr></thead><tbody>"""

    total = 0
    prev_platform = None
    for i, row in enumerate(data):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        val = row["value"] / 1e6
        total += row["value"]
        plat = row["platform"]

        # Show platform name only on first row of each platform group
        if show_platform:
            plat_display = f"<b>{plat}</b>" if plat != prev_platform else ""
            prev_platform = plat
            plat_td = f'<td style="padding:5px 10px; border:1px solid #cbd5e0;">{plat_display}</td>'
        else:
            plat_td = ""

        html += f"""<tr style="background:{bg};">
            {plat_td}
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{row["project_name"]}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{val:.1f}</td>
        </tr>"""

    # Grand Total
    plat_td = f'<td style="padding:6px 10px; border:1px solid #cbd5e0;"></td>' if show_platform else ""
    html += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        {plat_td}
        <td style="padding:6px 10px; border:1px solid #cbd5e0;">Grand Total</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{total/1e6:.1f}</td>
    </tr>"""

    html += "</tbody></table>"
    return html


def build_comparison_table_html(data_a, data_b, label_a, label_b):
    """Build side-by-side comparison HTML table with variance."""
    # Merge data by project
    lookup_b = {(r["platform"], r["project_name"]): r["value"] for r in data_b}
    all_projects = []
    seen = set()
    for r in data_a:
        key = (r["platform"], r["project_name"])
        val_a = r["value"]
        val_b = lookup_b.get(key, 0)
        all_projects.append({"platform": r["platform"], "project_name": r["project_name"],
                              "val_a": val_a, "val_b": val_b})
        seen.add(key)
    for r in data_b:
        key = (r["platform"], r["project_name"])
        if key not in seen:
            all_projects.append({"platform": r["platform"], "project_name": r["project_name"],
                                  "val_a": 0, "val_b": r["value"]})

    # Sort by platform order
    all_projects = sort_by_platform(all_projects)

    def fmt_var(v):
        if v < -0.05:
            return f"({abs(v):.1f})"
        elif v > 0.05:
            return f"+{v:.1f}"
        return "-"

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Platform</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Project</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_a}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_b}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">Variance</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">%</th>
    </tr></thead><tbody>"""

    total_a = total_b = 0
    prev_platform = None
    for i, row in enumerate(all_projects):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        a = row["val_a"] / 1e6
        b = row["val_b"] / 1e6
        v = a - b
        pct = f"{(row['val_a'] - row['val_b']) / abs(row['val_b']) * 100:+.0f}%" if row['val_b'] != 0 else "-"
        total_a += row["val_a"]
        total_b += row["val_b"]

        plat = row["platform"]
        plat_display = f"<b>{plat}</b>" if plat != prev_platform else ""
        prev_platform = plat

        html += f"""<tr style="background:{bg};">
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{plat_display}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{row["project_name"]}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{a:.1f}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{b:.1f}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(v)}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{pct}</td>
        </tr>"""

    # Grand Total
    tv = (total_a - total_b) / 1e6
    tpct = f"{(total_a - total_b) / abs(total_b) * 100:+.0f}%" if total_b != 0 else "-"
    html += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        <td style="padding:6px 10px; border:1px solid #cbd5e0;"></td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0;">Grand Total</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{total_a/1e6:.1f}</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{total_b/1e6:.1f}</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(tv)}</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{tpct}</td>
    </tr>"""

    html += "</tbody></table>"
    return html


def main():
    st.title("Fee by Project")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    options = build_metric_options(selected)
    option_labels = list(options.keys())

    # --- View mode ---
    mode = st.radio("View", ["Single Metric", "Comparison (Side by Side)"], horizontal=True)

    if mode == "Single Metric":
        chosen = st.selectbox("Select Metric", option_labels, index=option_labels.index("FY26 Bud"))
        data = query_metric(db, selected, chosen, options[chosen])
        html = build_project_table_html(data, chosen)
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")

    else:
        col1, col2 = st.columns(2)
        with col1:
            label_a = st.selectbox("Left Table", option_labels,
                                    index=option_labels.index(f"FY26 Fcst ({selected})"),
                                    key="left_metric")
        with col2:
            label_b = st.selectbox("Right Table", option_labels,
                                    index=option_labels.index("FY26 Bud"),
                                    key="right_metric")

        data_a = query_metric(db, selected, label_a, options[label_a])
        data_b = query_metric(db, selected, label_b, options[label_b])

        html = build_comparison_table_html(data_a, data_b, label_a, label_b)
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")


main()
