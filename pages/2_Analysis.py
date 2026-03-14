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


def colored_var(val_raw, note=""):
    """Format variance value with red/blue color. If note exists, show 📝 with tooltip."""
    text = fv(val_raw)
    if text == "-":
        return "-"
    if val_raw > 0.05:
        var_html = f'<span style="color:#c53030;">+{text}</span>'
    elif val_raw < -0.05:
        var_html = f'<span style="color:#2b6cb0;">({text.lstrip("-")})</span>'
    else:
        return "-"
    if note:
        safe_note = note.replace('"', '&quot;').replace("'", "&#39;")
        var_html += (f' <span class="note-icon" title="{safe_note}">'
                     f'📝</span>')
    return var_html


# CSS for note tooltips
NOTE_CSS = """
<style>
.note-icon {
    cursor: help;
    font-size: 11px;
    position: relative;
}
.note-icon:hover::after {
    content: attr(title);
    position: absolute;
    bottom: 120%;
    left: 50%;
    transform: translateX(-50%);
    background: #2d3748;
    color: white;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
    white-space: pre-wrap;
    max-width: 300px;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
</style>
"""


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
    plat_subtotal = 0
    prev_platform = None
    for i, row in enumerate(data):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        val = row["value"] / divisor()
        total += row["value"]
        plat = row["platform"]

        # Insert subtotal when platform changes
        if show_platform and prev_platform is not None and plat != prev_platform:
            html += f"""<tr style="background:#edf2f7; font-weight:bold;">
                <td style="padding:5px 10px; border:1px solid #cbd5e0;" colspan="2">Subtotal — {prev_platform}</td>
                <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(plat_subtotal / divisor())}</td>
            </tr>"""
            plat_subtotal = 0

        plat_subtotal += row["value"]
        prev_platform = plat

        # Show platform name only on first row of each platform group
        if show_platform:
            plat_display = f"<b>{plat}</b>" if plat != (data[i-1]["platform"] if i > 0 else None) else ""
            plat_td = f'<td style="padding:5px 10px; border:1px solid #cbd5e0;">{plat_display}</td>'
        else:
            plat_td = ""

        html += f"""<tr style="background:{bg};">
            {plat_td}
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{row["project_name"]}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(val)}</td>
        </tr>"""

    # Last platform subtotal
    if show_platform and prev_platform is not None:
        html += f"""<tr style="background:#edf2f7; font-weight:bold;">
            <td style="padding:5px 10px; border:1px solid #cbd5e0;" colspan="2">Subtotal — {prev_platform}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(plat_subtotal / divisor())}</td>
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
        return colored_var(v)

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
        return colored_var(v)

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

    st.markdown(NOTE_CSS, unsafe_allow_html=True)

    options = build_metric_options(selected)
    option_labels = list(options.keys())

    # --- View mode ---
    mode = st.radio("View", ["Single Metric", "Fee by Project (FY)", "Monthly Detail"], horizontal=True)

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

    elif mode == "Fee by Project (FY)":
        # Pivoted table: rows = Platform/Project, cols = Fee Type, with two metric blocks side by side
        FT_COLS = ["Asset Mgmt Fee", "Development Mgmt Fee", "Leasing Fee", "Acq / Div Fee", "Promote Fee", "Other Fee"]
        FT_SHORT = {"Asset Mgmt Fee": "AM Fee", "Development Mgmt Fee": "DM Fee",
                     "Leasing Fee": "Leasing Fee", "Acq / Div Fee": "Acq Fee", "Promote Fee": "Promote", "Other Fee": "Other"}

        col1, col2 = st.columns(2)
        with col1:
            label_a = st.selectbox("Metric 1", option_labels,
                                    index=option_labels.index(f"FY26 Fcst ({selected})"), key="ftp_a")
        with col2:
            label_b = st.selectbox("Metric 2", option_labels,
                                    index=option_labels.index("FY26 Bud"), key="ftp_b")

        data_a = query_metric_by_fee_type(db, selected, options[label_a])
        data_b = query_metric_by_fee_type(db, selected, options[label_b])

        # Build lookup: (platform, project) -> {fee_type: value}
        def build_ft_lookup(data):
            lookup = {}
            for r in data:
                key = (r["platform"], r["project_name"])
                if key not in lookup:
                    lookup[key] = {}
                lookup[key][r["fee_type"]] = lookup[key].get(r["fee_type"], 0) + r["value"]
            return lookup

        lookup_a = build_ft_lookup(data_a)
        lookup_b = build_ft_lookup(data_b)
        all_proj_keys = sorted(set(lookup_a.keys()) | set(lookup_b.keys()),
            key=lambda k: (PLATFORM_ORDER.index(k[0]) if k[0] in PLATFORM_ORDER else 99, k[1]))

        # Filter: at least one fee type has value in either metric
        all_proj_keys = [k for k in all_proj_keys
                         if any(abs(lookup_a.get(k, {}).get(ft, 0)) >= 500 or abs(lookup_b.get(k, {}).get(ft, 0)) >= 500 for ft in FT_COLS)]

        d = divisor()
        short_a = label_a.split("(")[0].strip() if "(" in label_a else label_a
        short_b = label_b.split("(")[0].strip() if "(" in label_b else label_b

        # Load saved notes for this metric pair
        ftp_note_key = f"ftp_{label_a}_vs_{label_b}"
        saved_notes = db.get_drivers(selected, ftp_note_key)

        # Highlight threshold: abs variance >= 0.3M (300,000 USD)
        HIGHLIGHT_THRESHOLD = 300_000

        def is_highlighted(val_a, val_b):
            return abs(val_a - val_b) >= HIGHLIGHT_THRESHOLD

        def hl_style(val_a, val_b):
            """Return yellow background if variance >= threshold."""
            if is_highlighted(val_a, val_b):
                return " background:#fff3cd;"
            return ""

        def fmt_var_val(v):
            return colored_var(v / d)

        # Build HTML with two header rows + Variance column
        ft_headers_a = "".join(f'<th style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-size:10px;">{FT_SHORT[ft]}</th>' for ft in FT_COLS)
        ft_headers_b = ft_headers_a

        sty_th = f"background:{HEADER_COLOR}; color:white; position:sticky; z-index:2;"
        # Frozen column styles (sticky left)
        frz0 = f"position:sticky; left:0; z-index:3; background:{HEADER_COLOR}; color:white;"
        frz1 = f"position:sticky; left:100px; z-index:3; background:{HEADER_COLOR}; color:white;"
        frz0_data = "position:sticky; left:0; z-index:1;"
        frz1_data = "position:sticky; left:100px; z-index:1;"

        html = f"""<div style="max-height:70vh; overflow:auto; border:1px solid #cbd5e0;">
        <table style="border-collapse:separate; border-spacing:0; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
        <thead>
        <tr style="font-weight:bold; text-align:center;">
            <th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th} top:0; {frz0} min-width:100px;" rowspan="2">Platform</th>
            <th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th} top:0; {frz1} min-width:120px;" rowspan="2">Project</th>
            <th style="padding:4px 6px; border:1px solid #cbd5e0; {sty_th} top:0;" colspan="{len(FT_COLS) + 1}">{label_a}</th>
            <th style="padding:4px 6px; border:1px solid #cbd5e0; {sty_th} top:0;" colspan="{len(FT_COLS) + 1}">{label_b}</th>
            <th style="padding:4px 6px; border:1px solid #cbd5e0; {sty_th} top:0;" rowspan="2">Variance</th>
            <th style="padding:4px 6px; border:1px solid #cbd5e0; {sty_th} top:0;" rowspan="2">Note</th>
        </tr>
        <tr style="font-weight:bold; font-size:10px; text-align:center;">
            {ft_headers_a.replace('style="', f'style="{sty_th} top:28px; ')}
            <th style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; {sty_th} top:28px;">Total</th>
            {ft_headers_b.replace('style="', f'style="{sty_th} top:28px; ')}
            <th style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; {sty_th} top:28px;">Total</th>
        </tr>
        </thead><tbody>"""

        plat_sub_a = {ft: 0.0 for ft in FT_COLS}
        plat_sub_b = {ft: 0.0 for ft in FT_COLS}
        grand_a = {ft: 0.0 for ft in FT_COLS}
        grand_b = {ft: 0.0 for ft in FT_COLS}
        prev_plat = None

        def render_subtotal_row(label, sub_a, sub_b):
            cells = f'<td style="padding:5px 8px; border:1px solid #cbd5e0; font-weight:bold; background:#edf2f7; {frz0_data} background:#edf2f7;" colspan="2">{label}</td>'
            total_a = sum(sub_a.values())
            for ft in FT_COLS:
                cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(sub_a[ft]/d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(total_a/d)}</td>'
            total_b = sum(sub_b.values())
            for ft in FT_COLS:
                cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(sub_b[ft]/d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(total_b/d)}</td>'
            var = total_a - total_b
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fmt_var_val(var)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; background:#edf2f7;"></td>'
            return f'<tr>{cells}</tr>'

        for idx, key in enumerate(all_proj_keys):
            plat, proj = key
            bg = "#f7fafc" if idx % 2 == 0 else "#ffffff"

            if prev_plat is not None and plat != prev_plat:
                html += render_subtotal_row(f"Subtotal — {prev_plat}", plat_sub_a, plat_sub_b)
                plat_sub_a = {ft: 0.0 for ft in FT_COLS}
                plat_sub_b = {ft: 0.0 for ft in FT_COLS}
            prev_plat = plat

            plat_display = f"<b>{plat}</b>" if plat != (all_proj_keys[idx-1][0] if idx > 0 else None) else ""

            cells = f'<td style="padding:4px 8px; border:1px solid #cbd5e0; {frz0_data} background:{bg}; min-width:100px;">{plat_display}</td>'
            cells += f'<td style="padding:4px 8px; border:1px solid #cbd5e0; {frz1_data} background:{bg}; min-width:120px;">{proj}</td>'

            ft_vals_a = lookup_a.get(key, {})
            ft_vals_b = lookup_b.get(key, {})
            row_total_a = 0
            for ft in FT_COLS:
                va = ft_vals_a.get(ft, 0)
                vb = ft_vals_b.get(ft, 0)
                row_total_a += va
                plat_sub_a[ft] += va
                grand_a[ft] += va
                hl = hl_style(va, vb)
                cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;{hl}">{fv(va/d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold;">{fv(row_total_a/d)}</td>'

            row_total_b = 0
            for ft in FT_COLS:
                va = ft_vals_a.get(ft, 0)
                vb = ft_vals_b.get(ft, 0)
                row_total_b += vb
                plat_sub_b[ft] += vb
                grand_b[ft] += vb
                hl = hl_style(va, vb)
                cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;{hl}">{fv(vb/d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold;">{fv(row_total_b/d)}</td>'

            # Variance column + Note column
            row_var = row_total_a - row_total_b
            row_hl = hl_style(row_total_a, row_total_b)
            proj_note = saved_notes.get(proj, "")
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold;{row_hl}">{colored_var(row_var / d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; font-size:10px; color:#555; min-width:200px;">{proj_note}</td>'

            html += f'<tr style="background:{bg};">{cells}</tr>'

        # Last platform subtotal
        if prev_plat is not None:
            html += render_subtotal_row(f"Subtotal — {prev_plat}", plat_sub_a, plat_sub_b)

        # Grand Total
        gt_cells = f'<td style="padding:6px 8px; border:1px solid #cbd5e0; {frz0_data} background:{HEADER_COLOR};" colspan="2">Grand Total</td>'
        gt_total_a = sum(grand_a.values())
        for ft in FT_COLS:
            gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(grand_a[ft]/d)}</td>'
        gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(gt_total_a/d)}</td>'
        gt_total_b = sum(grand_b.values())
        for ft in FT_COLS:
            gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(grand_b[ft]/d)}</td>'
        gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(gt_total_b/d)}</td>'
        gt_var = gt_total_a - gt_total_b
        gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fmt_var_val(gt_var)}</td>'
        gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0;"></td>'
        html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">{gt_cells}</tr>'

        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption(f"Unit: {unit_label()}")

        # Full HTML view for copy & paste
        full_html = html.replace('max-height:70vh; overflow-y:auto; border:1px solid #cbd5e0;', '')
        full_html = full_html.replace('position:sticky; z-index:2;', '')
        full_html = full_html.replace('border-collapse:separate; border-spacing:0;', 'border-collapse:collapse;')
        with st.expander("Open Full Table (for copy & paste)"):
            st.markdown(full_html, unsafe_allow_html=True)

        # Inline note editor — select project, type note, save
        proj_list = [k[1] for k in all_proj_keys]
        nc1, nc2, nc3 = st.columns([2, 5, 1])
        with nc1:
            note_proj = st.selectbox("Add/edit note for:", [""] + proj_list, key="ftp_note_proj")
        with nc2:
            note_text = st.text_input("Note:", value=saved_notes.get(note_proj, "") if note_proj else "",
                                       key="ftp_note_text", label_visibility="collapsed",
                                       placeholder="Type variance note here...")
        with nc3:
            st.markdown("<div style='padding-top:4px;'></div>", unsafe_allow_html=True)
            if st.button("💾", key="ftp_save_note") and note_proj:
                saved_notes[note_proj] = note_text
                db.save_drivers(selected, ftp_note_key, saved_notes)
                st.rerun()

        # Export
        exp_rows = []
        for key in all_proj_keys:
            plat, proj = key
            row = {"Platform": plat, "Project": proj}
            ft_a = lookup_a.get(key, {})
            ft_b = lookup_b.get(key, {})
            for ft in FT_COLS:
                row[f"{FT_SHORT[ft]} ({short_a})"] = ft_a.get(ft, 0) / d
                row[f"{FT_SHORT[ft]} ({short_b})"] = ft_b.get(ft, 0) / d
            row[f"Total ({short_a})"] = sum(ft_a.get(ft, 0) for ft in FT_COLS) / d
            row[f"Total ({short_b})"] = sum(ft_b.get(ft, 0) for ft in FT_COLS) / d
            row["Note"] = saved_notes.get(proj, "")
            exp_rows.append(row)
        export_button(pd.DataFrame(exp_rows), "fee_by_project_fee_type.xlsx")

    elif mode == "Monthly Detail":
        # Monthly data by Project or Fee Type, with metric selector
        n = get_snapshot_n_value(selected)
        month_names_short = [MONTH_NAMES[m] for m in range(1, 13)]

        view_by = st.radio("View by", ["Project", "Fee Type"], horizontal=True, key="monthly_view")

        metric_options = {
            "Actual": "actual",
            "Budget": "budget",
            "Forecast": "forecast",
        }
        mc1, mc2 = st.columns([2, 3])
        with mc1:
            chosen_metric = st.selectbox("Metric", list(metric_options.keys()), key="monthly_metric")
        with mc2:
            year = st.selectbox("Year", ["2026", "2025", "2024", "2023"], key="monthly_year")

        period_type = metric_options[chosen_metric]

        # Query monthly data
        months = [f"{year}-{m:02d}" for m in range(1, 13)]
        placeholders = ",".join(["?"] * len(months))

        if view_by == "Project":
            rows = db.query(f"""
                SELECT platform, project_name, period, SUM(amount_usd) as value
                FROM fee_income
                WHERE snapshot = ? AND period IN ({placeholders}) AND period_type = ?
                GROUP BY platform, project_name, period
            """, (selected, *months, period_type))

            # Build pivot: (platform, project) -> {month: value}
            pivot = {}
            all_keys_set = set()
            for r in rows:
                key = (r["platform"], r["project_name"])
                if key not in pivot:
                    pivot[key] = {}
                pivot[key][r["period"]] = r["value"]
                all_keys_set.add(key)

            all_keys = sort_by_platform([{"platform": k[0], "project_name": k[1]} for k in all_keys_set])
            all_keys = [(p["platform"], p["project_name"]) for p in all_keys]
            all_keys = [k for k in all_keys if any(abs(pivot.get(k, {}).get(m, 0)) >= 500 for m in months)]

            label_cols = ["Platform", "Project"]
            def get_labels(k): return k
        else:
            # Filter by project first
            all_projects = db.query("""
                SELECT DISTINCT project_name FROM fee_income WHERE snapshot = ? ORDER BY project_name
            """, (selected,))
            proj_names = [r["project_name"] for r in all_projects]
            filter_proj = st.selectbox("Filter by Project", ["All"] + proj_names, key="monthly_proj_filter")

            query_extra = ""
            params = [selected, *months, period_type]
            if filter_proj != "All":
                query_extra = " AND project_name = ?"
                params.append(filter_proj)

            rows = db.query(f"""
                SELECT platform, project_name, fee_type, period, SUM(amount_usd) as value
                FROM fee_income
                WHERE snapshot = ? AND period IN ({placeholders}) AND period_type = ?{query_extra}
                GROUP BY platform, project_name, fee_type, period
            """, tuple(params))

            pivot = {}
            all_keys_set = set()
            for r in rows:
                key = (r["platform"], r["project_name"], r["fee_type"])
                if key not in pivot:
                    pivot[key] = {}
                pivot[key][r["period"]] = r["value"]
                all_keys_set.add(key)

            FT_ORDER = ["Asset Mgmt Fee", "Development Mgmt Fee", "Leasing Fee", "Acq / Div Fee", "Promote Fee", "Other Fee"]
            all_keys = sorted(all_keys_set,
                key=lambda k: (PLATFORM_ORDER.index(k[0]) if k[0] in PLATFORM_ORDER else 99, k[1],
                               FT_ORDER.index(k[2]) if k[2] in FT_ORDER else 99))
            all_keys = [k for k in all_keys if any(abs(pivot.get(k, {}).get(m, 0)) >= 500 for m in months)]

            label_cols = ["Platform", "Project", "Fee Type"]
            def get_labels(k): return k

        d = divisor()

        # Build HTML table
        sty_th = f"background:{HEADER_COLOR}; color:white; position:sticky; z-index:2; top:0;"
        frz0 = f"position:sticky; left:0; z-index:3; background:{HEADER_COLOR}; color:white;"
        frz1 = f"position:sticky; left:100px; z-index:3; background:{HEADER_COLOR}; color:white;"
        frz0_data = "position:sticky; left:0; z-index:1;"
        frz1_data = "position:sticky; left:100px; z-index:1;"

        month_headers = "".join(f'<th style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; {sty_th}">{MONTH_NAMES[m]}</th>' for m in range(1, 13))

        html = f"""<div style="max-height:70vh; overflow:auto; border:1px solid #cbd5e0;">
        <table style="border-collapse:separate; border-spacing:0; width:100%; font-size:11px; font-family:Calibri,sans-serif;">
        <thead><tr style="font-weight:bold; text-align:center;">"""

        for i, col in enumerate(label_cols):
            if i == 0:
                html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th} {frz0} min-width:100px;">{col}</th>'
            elif i == 1:
                html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th} {frz1} min-width:120px;">{col}</th>'
            else:
                html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th}">{col}</th>'

        html += month_headers
        html += f'<th style="padding:6px 8px; border:1px solid #cbd5e0; {sty_th} font-weight:bold;">Total</th>'
        html += "</tr></thead><tbody>"

        grand_totals = {m: 0.0 for m in months}
        prev_plat = None
        plat_totals = {m: 0.0 for m in months}

        for idx, key in enumerate(all_keys):
            bg = "#f7fafc" if idx % 2 == 0 else "#ffffff"
            parts = get_labels(key)
            current_plat = parts[0]

            # Subtotal on platform change
            if prev_plat is not None and current_plat != prev_plat:
                sub_cells = f'<td style="padding:4px 6px; border:1px solid #cbd5e0; font-weight:bold; background:#edf2f7; {frz0_data} background:#edf2f7;" colspan="{len(label_cols)}">Subtotal — {prev_plat}</td>'
                row_sum = 0
                for m in months:
                    v = plat_totals[m]
                    row_sum += v
                    sub_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(v/d)}</td>'
                sub_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(row_sum/d)}</td>'
                html += f'<tr>{sub_cells}</tr>'
                plat_totals = {m: 0.0 for m in months}
            prev_plat = current_plat

            # Label cells
            cells = ""
            for i, part in enumerate(parts):
                if i == 0:
                    plat_display = f"<b>{part}</b>" if part != (all_keys[idx-1][0] if idx > 0 else None) else ""
                    cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; {frz0_data} background:{bg}; min-width:100px;">{plat_display}</td>'
                elif i == 1:
                    proj_display = f"{part}" if len(label_cols) == 2 or part != (all_keys[idx-1][1] if idx > 0 else None) else ""
                    cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; {frz1_data} background:{bg}; min-width:120px;">{proj_display}</td>'
                else:
                    cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; font-size:10px;">{part}</td>'

            # Monthly values
            month_vals = pivot.get(key, {})
            row_total = 0
            for m in months:
                v = month_vals.get(m, 0)
                row_total += v
                plat_totals[m] += v
                grand_totals[m] += v
                cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(v/d)}</td>'
            cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold;">{fv(row_total/d)}</td>'

            html += f'<tr style="background:{bg};">{cells}</tr>'

        # Last subtotal
        if prev_plat is not None:
            sub_cells = f'<td style="padding:4px 6px; border:1px solid #cbd5e0; font-weight:bold; background:#edf2f7; {frz0_data} background:#edf2f7;" colspan="{len(label_cols)}">Subtotal — {prev_plat}</td>'
            row_sum = 0
            for m in months:
                v = plat_totals[m]
                row_sum += v
                sub_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(v/d)}</td>'
            sub_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right; font-weight:bold; background:#edf2f7;">{fv(row_sum/d)}</td>'
            html += f'<tr>{sub_cells}</tr>'

        # Grand Total
        gt_cells = f'<td style="padding:6px 8px; border:1px solid #cbd5e0; {frz0_data} background:{HEADER_COLOR};" colspan="{len(label_cols)}">Grand Total</td>'
        gt_sum = 0
        for m in months:
            v = grand_totals[m]
            gt_sum += v
            gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(v/d)}</td>'
        gt_cells += f'<td style="padding:4px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(gt_sum/d)}</td>'
        html += f'<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">{gt_cells}</tr>'

        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption(f"Unit: {unit_label()} | {chosen_metric} {year}")

        # Full table for copy & paste
        full_html = html.replace('max-height:70vh; overflow:auto; border:1px solid #cbd5e0;', '')
        full_html = full_html.replace('position:sticky;', '').replace('z-index:1;', '').replace('z-index:2;', '').replace('z-index:3;', '')
        full_html = full_html.replace('border-collapse:separate; border-spacing:0;', 'border-collapse:collapse;')
        with st.expander("Open Full Table (for copy & paste)"):
            st.markdown(full_html, unsafe_allow_html=True)

        # Export
        exp_rows = []
        for key in all_keys:
            parts = get_labels(key)
            row = {col: parts[i] for i, col in enumerate(label_cols)}
            month_vals = pivot.get(key, {})
            for m in months:
                row[MONTH_NAMES[int(m.split("-")[1])]] = month_vals.get(m, 0) / d
            row["Total"] = sum(month_vals.get(m, 0) for m in months) / d
            exp_rows.append(row)
        export_button(pd.DataFrame(exp_rows), f"monthly_detail_{chosen_metric}_{year}.xlsx")


main()
