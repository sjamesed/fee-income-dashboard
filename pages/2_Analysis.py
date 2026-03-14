"""Page 2: Analysis — Fee by Project interactive table with side-by-side comparison."""
import streamlit as st
import pandas as pd
import io
from src.db import FeeIncomeDB
from src.queries import get_snapshot_n_value, PLATFORM_ORDER, sort_by_platform

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

HEADER_COLOR = "#4a5568"

# Global state for unit toggle
_use_millions = True


def divisor():
    return 1e6 if _use_millions else 1


def unit_label():
    return "USD millions" if _use_millions else "USD"


def fv(val_raw):
    """Format value. 0 → '-'. val_raw is already divided by divisor."""
    if _use_millions:
        if abs(val_raw) < 0.05:
            return "-"
        return f"{val_raw:.1f}"
    else:
        if abs(val_raw) < 0.5:
            return "-"
        return f"{val_raw:,.0f}"


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
        val = row["value"] / divisor()
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
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(total/divisor())}</td>
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


def build_export_df(all_keys, labels, get_row_labels, get_row_value, row_label_keys):
    """Build a DataFrame for Excel export from the table data."""
    rows = []
    for key in all_keys:
        parts = get_row_labels(key)
        row = {}
        for j, col_name in enumerate(row_label_keys):
            row[col_name] = parts[j]
        base = get_row_value(key, labels[0])
        row[labels[0]] = base / divisor()
        for i in range(1, len(labels)):
            v = get_row_value(key, labels[i])
            row[labels[i]] = v / divisor()
            row[f"Var ({labels[0]} vs {labels[i]})"] = (base - v) / divisor()
        rows.append(row)
    return pd.DataFrame(rows)


def export_button(df, filename="analysis_export.xlsx"):
    """Render an Excel download button."""
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(
        label="Export to Excel",
        data=buf.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def main():
    global _use_millions
    st.title("Fee by Project")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded.")
        return

    latest = db.get_latest_snapshot()

    # Top controls row
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        selected = st.selectbox("Snapshot", snapshots,
            index=snapshots.index(latest) if latest in snapshots else 0)
    with c2:
        unit_choice = st.radio("Unit", ["USD millions", "USD"], horizontal=True, key="unit_toggle")
        _use_millions = (unit_choice == "USD millions")

    options = build_metric_options(selected)
    option_labels = list(options.keys())

    # --- View mode ---
    mode = st.radio("View", ["Single Metric", "Comparison", "Comparison by Fee Type"], horizontal=True)

    if mode == "Single Metric":
        chosen = st.selectbox("Select Metric", option_labels, index=option_labels.index("FY26 Bud"))
        data = query_metric(db, selected, chosen, options[chosen])
        # Filter zero rows
        data = [r for r in data if abs(r["value"]) >= 500]
        html = build_project_table_html(data, chosen)
        st.markdown(html, unsafe_allow_html=True)
        st.caption(f"Unit: {unit_label()}")
        # Export
        if data:
            exp_rows = [{"Platform": r["platform"], "Project": r["project_name"], chosen: r["value"] / divisor()} for r in data]
            export_button(pd.DataFrame(exp_rows), f"fee_by_project_{chosen}.xlsx")

    elif mode in ("Comparison", "Comparison by Fee Type"):
        is_fee_type = mode == "Comparison by Fee Type"
        prefix = "ft" if is_fee_type else "cmp"

        num_metrics = st.radio("Number of metrics", [2, 3, 4], horizontal=True, key=f"{prefix}_num")
        defaults = [f"FY26 Fcst ({selected})", "FY26 Bud", "FY25 Act", "FY24 Act"]
        cols = st.columns(num_metrics)
        labels = []
        for i, c in enumerate(cols):
            with c:
                default_idx = option_labels.index(defaults[i]) if defaults[i] in option_labels else i
                labels.append(st.selectbox(f"Metric {i+1}", option_labels, index=default_idx, key=f"{prefix}_{i}"))

        # Project filter for fee type mode
        selected_project = None
        if is_fee_type:
            all_projects_raw = query_metric(db, selected, labels[0], options[labels[0]])
            project_names = ["All Projects"] + [r["project_name"] for r in all_projects_raw]
            selected_project = st.selectbox("Filter by Project", project_names)

        # Query data
        if is_fee_type:
            all_data = {}
            all_keys_set = set()
            for lbl in labels:
                rows = query_metric_by_fee_type(db, selected, options[lbl])
                if selected_project and selected_project != "All Projects":
                    rows = [r for r in rows if r["project_name"] == selected_project]
                lookup = {}
                for r in rows:
                    key = (r["platform"], r["project_name"], r["fee_type"])
                    lookup[key] = lookup.get(key, 0) + r["value"]
                    all_keys_set.add(key)
                all_data[lbl] = lookup

            all_keys = sorted(all_keys_set,
                key=lambda k: (PLATFORM_ORDER.index(k[0]) if k[0] in PLATFORM_ORDER else 99, k[1],
                               FEE_TYPE_ORDER.index(k[2]) if k[2] in FEE_TYPE_ORDER else 99))
            all_keys = [k for k in all_keys
                        if any(abs(all_data[lbl].get(k, 0)) >= 500 for lbl in labels)]

            row_label_keys = ["Platform", "Project", "Fee Type"]
            def get_row_labels(key):
                return key  # (platform, project, fee_type)
            def get_row_value(key, lbl):
                return all_data[lbl].get(key, 0)
        else:
            all_data = {}
            all_keys_set = set()
            for lbl in labels:
                rows = query_metric(db, selected, lbl, options[lbl])
                lookup = {}
                for r in rows:
                    key = (r["platform"], r["project_name"])
                    lookup[key] = r["value"]
                    all_keys_set.add(key)
                all_data[lbl] = lookup

            all_keys_raw = [{"platform": k[0], "project_name": k[1]} for k in all_keys_set]
            all_keys_raw = sort_by_platform(all_keys_raw)
            all_keys = [(p["platform"], p["project_name"]) for p in all_keys_raw]
            all_keys = [k for k in all_keys
                        if any(abs(all_data[lbl].get(k, 0)) >= 500 for lbl in labels)]

            row_label_keys = ["Platform", "Project"]
            def get_row_labels(key):
                return key  # (platform, project)
            def get_row_value(key, lbl):
                return all_data[lbl].get(key, 0)

        # Build header: for each metric pair (i vs i+1), show Metric_i | Metric_i+1 | Var | %
        # First metric is always shown, then each subsequent metric adds: value | var | %
        header_html = ""
        for col_name in row_label_keys:
            header_html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:left;" rowspan="1">{col_name}</th>'
        header_html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{labels[0]}</th>'
        for i in range(1, len(labels)):
            short_a = labels[0].split("(")[0].strip() if "(" in labels[0] else labels[0]
            short_b = labels[i].split("(")[0].strip() if "(" in labels[i] else labels[i]
            header_html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{labels[i]}</th>'
            header_html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{short_a} vs {short_b}</th>'
            header_html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">%</th>'

        html = f"""<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            {header_html}
        </tr></thead><tbody>"""

        def fmt_var_cell(v):
            if v < -0.05:
                return f"({abs(v):.1f})"
            elif v > 0.05:
                return f"+{v:.1f}"
            return "-"

        totals = {lbl: 0.0 for lbl in labels}
        prev_parts = [None] * len(row_label_keys)

        for idx, key in enumerate(all_keys):
            bg = "#f7fafc" if idx % 2 == 0 else "#ffffff"
            parts = get_row_labels(key)

            # Label cells — show only when value changes (group by platform/project)
            label_cells = ""
            for j, part in enumerate(parts):
                display = f"<b>{part}</b>" if part != prev_parts[j] else ""
                prev_parts[j] = part
                label_cells += f'<td style="padding:4px 8px; border:1px solid #cbd5e0;">{display}</td>'
            # Reset downstream grouping when upstream changes
            for j in range(len(parts)):
                if j > 0 and parts[j-1] != (get_row_labels(all_keys[idx-1])[j-1] if idx > 0 else None):
                    prev_parts[j] = parts[j]
                    label_cells_list = label_cells.split("</td>")
                    # Re-render this cell with value shown
                    # (simpler: just don't group fee_type)

            # Value cells
            d = divisor()
            base_val = get_row_value(key, labels[0])
            totals[labels[0]] += base_val
            val_cells = f'<td style="padding:4px 8px; border:1px solid #cbd5e0; text-align:right;">{fv(base_val / d)}</td>'

            for i in range(1, len(labels)):
                v = get_row_value(key, labels[i])
                totals[labels[i]] += v
                var = (base_val - v) / d
                pct = f"{(base_val - v) / abs(v) * 100:+.0f}%" if v != 0 else "-"
                val_cells += f'<td style="padding:4px 8px; border:1px solid #cbd5e0; text-align:right;">{fv(v / d)}</td>'
                val_cells += f'<td style="padding:4px 8px; border:1px solid #cbd5e0; text-align:right;">{fmt_var_cell(var)}</td>'
                val_cells += f'<td style="padding:4px 8px; border:1px solid #cbd5e0; text-align:right;">{pct}</td>'

            html += f'<tr style="background:{bg};">{label_cells}{val_cells}</tr>'

        # Grand Total row
        d = divisor()
        base_total = totals[labels[0]]
        empty_label_cells = f'<td style="padding:6px 8px; border:1px solid #cbd5e0;" colspan="{len(row_label_keys) - 1}"></td>'
        empty_label_cells += f'<td style="padding:6px 8px; border:1px solid #cbd5e0;">Grand Total</td>'
        total_val_cells = f'<td style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{fv(base_total / d)}</td>'
        for i in range(1, len(labels)):
            t = totals[labels[i]]
            tv = (base_total - t) / d
            tp = f"{(base_total - t) / abs(t) * 100:+.0f}%" if t != 0 else "-"
            total_val_cells += f'<td style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{fv(t / d)}</td>'
            total_val_cells += f'<td style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{fmt_var_cell(tv)}</td>'
            total_val_cells += f'<td style="padding:6px 8px; border:1px solid #cbd5e0; text-align:right;">{tp}</td>'

        html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">{empty_label_cells}{total_val_cells}</tr>'
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption(f"Unit: {unit_label()}")

        # Export button
        exp_df = build_export_df(all_keys, labels, get_row_labels, get_row_value, row_label_keys)
        export_button(exp_df, f"fee_comparison_{mode.replace(' ', '_').lower()}.xlsx")


main()
