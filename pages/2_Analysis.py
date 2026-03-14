"""Page 2: Analysis — Fee by Project interactive table with side-by-side comparison."""
import streamlit as st
import pandas as pd
from src.db import FeeIncomeDB
from src.queries import get_snapshot_n_value, PLATFORM_ORDER, sort_by_platform

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

HEADER_COLOR = "#4a5568"


def fv(val_mil):
    """Format value in millions. 0 → '-'."""
    if abs(val_mil) < 0.05:
        return "-"
    return f"{val_mil:.1f}"


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

    # Filter out rows where value is 0
    data = [r for r in data if abs(r["value"]) >= 500]

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
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(val)}</td>
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

    # Filter out rows where both values are 0
    all_projects = [r for r in all_projects if abs(r["val_a"]) >= 500 or abs(r["val_b"]) >= 500]

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
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(a)}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(b)}</td>
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


def query_metric_by_fee_type(db, snapshot, metric_def):
    """Query by project AND fee_type. Returns sorted list of dicts."""
    period_or_type, param = metric_def

    if period_or_type in ("mtd_act", "mtd_bud"):
        n = param
        month = f"2026-{n:02d}"
        pt = "actual" if "act" in period_or_type else "budget"
        rows = db.query("""
            SELECT project_name, platform, fee_type, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period = ? AND period_type = ?
            GROUP BY project_name, platform, fee_type
        """, (snapshot, month, pt))
    elif period_or_type in ("ytd_act", "ytd_bud"):
        n = param
        months = [f"2026-{m:02d}" for m in range(1, n + 1)]
        placeholders = ",".join(["?"] * len(months))
        pt = "actual" if "act" in period_or_type else "budget"
        rows = db.query(f"""
            SELECT project_name, platform, fee_type, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period IN ({placeholders}) AND period_type = ?
            GROUP BY project_name, platform, fee_type
        """, (snapshot, *months, pt))
    else:
        period, period_type = period_or_type, param
        rows = db.query("""
            SELECT project_name, platform, fee_type, SUM(amount_usd) as value
            FROM fee_income
            WHERE snapshot = ? AND period = ? AND period_type = ?
            GROUP BY project_name, platform, fee_type
        """, (snapshot, period, period_type))

    return sort_by_platform(rows)


FEE_TYPE_ORDER = ["Asset Mgmt Fee", "Leasing Fee", "Development Mgmt Fee",
                  "Acq / Div Fee", "Other Fee", "Promote Fee"]


def build_fee_type_comparison_html(data_a, data_b, label_a, label_b, selected_project=None):
    """Build comparison table broken down by Fee Type for selected project(s)."""
    # Filter to selected project if specified
    if selected_project and selected_project != "All Projects":
        data_a = [r for r in data_a if r["project_name"] == selected_project]
        data_b = [r for r in data_b if r["project_name"] == selected_project]

    # Aggregate by project + fee_type
    def agg(data):
        result = {}
        for r in data:
            key = (r["platform"], r["project_name"], r["fee_type"])
            result[key] = result.get(key, 0) + r["value"]
        return result

    agg_a = agg(data_a)
    agg_b = agg(data_b)
    all_keys = sorted(set(agg_a.keys()) | set(agg_b.keys()),
                       key=lambda k: (PLATFORM_ORDER.index(k[0]) if k[0] in PLATFORM_ORDER else 99, k[1],
                                       FEE_TYPE_ORDER.index(k[2]) if k[2] in FEE_TYPE_ORDER else 99))

    # Filter out rows where both values are 0
    all_keys = [k for k in all_keys if abs(agg_a.get(k, 0)) >= 500 or abs(agg_b.get(k, 0)) >= 500]

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
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Fee Type</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_a}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_b}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">Variance</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">%</th>
    </tr></thead><tbody>"""

    total_a = total_b = 0
    prev_plat = prev_proj = None
    for i, key in enumerate(all_keys):
        plat, proj, ft = key
        a = agg_a.get(key, 0) / 1e6
        b = agg_b.get(key, 0) / 1e6
        v = a - b
        pct = f"{(agg_a.get(key, 0) - agg_b.get(key, 0)) / abs(agg_b.get(key, 0)) * 100:+.0f}%" if agg_b.get(key, 0) != 0 else "-"
        total_a += agg_a.get(key, 0)
        total_b += agg_b.get(key, 0)
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"

        plat_display = f"<b>{plat}</b>" if plat != prev_plat else ""
        proj_display = f"<b>{proj}</b>" if proj != prev_proj else ""
        prev_plat, prev_proj = plat, proj

        html += f"""<tr style="background:{bg};">
            <td style="padding:4px 10px; border:1px solid #cbd5e0;">{plat_display}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0;">{proj_display}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0; font-size:11px;">{ft}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(a)}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(b)}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(v)}</td>
            <td style="padding:4px 10px; border:1px solid #cbd5e0; text-align:right;">{pct}</td>
        </tr>"""

    tv = (total_a - total_b) / 1e6
    tpct = f"{(total_a - total_b) / abs(total_b) * 100:+.0f}%" if total_b != 0 else "-"
    html += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        <td style="padding:6px 10px; border:1px solid #cbd5e0;" colspan="3">Grand Total</td>
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
    mode = st.radio("View", ["Single Metric", "Comparison", "Comparison by Fee Type"], horizontal=True)

    if mode == "Single Metric":
        chosen = st.selectbox("Select Metric", option_labels, index=option_labels.index("FY26 Bud"))
        data = query_metric(db, selected, chosen, options[chosen])
        html = build_project_table_html(data, chosen)
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")

    elif mode == "Comparison":
        num_metrics = st.radio("Number of metrics", [2, 3, 4], horizontal=True, key="num_metrics")

        defaults = [f"FY26 Fcst ({selected})", "FY26 Bud", "FY25 Act", "FY24 Act"]
        cols = st.columns(num_metrics)
        labels = []
        for i, c in enumerate(cols):
            with c:
                default_idx = option_labels.index(defaults[i]) if defaults[i] in option_labels else i
                lbl = st.selectbox(f"Metric {i+1}", option_labels, index=default_idx, key=f"cmp_{i}")
                labels.append(lbl)

        # Query all selected metrics
        all_data = {}
        all_projects_set = set()
        for lbl in labels:
            data = query_metric(db, selected, lbl, options[lbl])
            lookup = {}
            for r in data:
                key = (r["platform"], r["project_name"])
                lookup[key] = r["value"]
                all_projects_set.add(key)
            all_data[lbl] = lookup

        # Build sorted project list
        all_proj_list = sort_by_platform([{"platform": k[0], "project_name": k[1]} for k in all_projects_set])
        # Filter: at least one metric has a value
        all_proj_list = [p for p in all_proj_list
                         if any(abs(all_data[lbl].get((p["platform"], p["project_name"]), 0)) >= 500 for lbl in labels)]

        # Build multi-column HTML table
        metric_headers = "".join(
            f'<th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{lbl}</th>' for lbl in labels
        )
        html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Platform</th>
            <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Project</th>
            {metric_headers}
        </tr></thead><tbody>"""

        totals = {lbl: 0 for lbl in labels}
        prev_plat = None
        for i, p in enumerate(all_proj_list):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            key = (p["platform"], p["project_name"])
            plat_display = f"<b>{p['platform']}</b>" if p["platform"] != prev_plat else ""
            prev_plat = p["platform"]

            val_cells = ""
            for lbl in labels:
                v = all_data[lbl].get(key, 0)
                totals[lbl] += v
                val_cells += f'<td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(v / 1e6)}</td>'

            html += f"""<tr style="background:{bg};">
                <td style="padding:5px 10px; border:1px solid #cbd5e0;">{plat_display}</td>
                <td style="padding:5px 10px; border:1px solid #cbd5e0;">{p["project_name"]}</td>
                {val_cells}
            </tr>"""

        total_cells = "".join(
            f'<td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(totals[lbl] / 1e6)}</td>'
            for lbl in labels
        )
        html += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <td style="padding:6px 10px; border:1px solid #cbd5e0;"></td>
            <td style="padding:6px 10px; border:1px solid #cbd5e0;">Grand Total</td>
            {total_cells}
        </tr>"""
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")

    else:  # Comparison by Fee Type
        col1, col2 = st.columns(2)
        with col1:
            label_a = st.selectbox("Left", option_labels,
                                    index=option_labels.index(f"FY26 Fcst ({selected})"),
                                    key="ft_left")
        with col2:
            label_b = st.selectbox("Right", option_labels,
                                    index=option_labels.index("FY26 Bud"),
                                    key="ft_right")

        # Project filter
        all_projects_raw = query_metric(db, selected, label_a, options[label_a])
        project_names = ["All Projects"] + [r["project_name"] for r in all_projects_raw]
        selected_project = st.selectbox("Filter by Project", project_names)

        data_a = query_metric_by_fee_type(db, selected, options[label_a])
        data_b = query_metric_by_fee_type(db, selected, options[label_b])

        html = build_fee_type_comparison_html(data_a, data_b, label_a, label_b, selected_project)
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")


main()
