"""Page 1: Overview — summary cards, FY tables, variance commentary, and watch list."""
import streamlit as st
import pandas as pd
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
    return f"${value / 1_000_000:.1f}M"

def add_grand_total(df: pd.DataFrame, label_col: str, numeric_cols: list[str]) -> pd.DataFrame:
    totals = {label_col: "Grand Total"}
    for col in df.columns:
        if col in numeric_cols:
            totals[col] = round(df[col].sum(), 1)
        elif col != label_col:
            totals[col] = ""
    totals_df = pd.DataFrame([totals])
    return pd.concat([df, totals_df], ignore_index=True)


def render_metric_card(label, actual, budget, color_up="red", color_down="blue"):
    """Render a metric card with colored variance."""
    var = actual - budget
    var_pct = (var / budget * 100) if budget != 0 else 0
    color = color_up if var >= 0 else color_down
    sign = "+" if var >= 0 else ""
    st.markdown(f"""
    <div style="background:#f8f9fa; border-radius:8px; padding:12px; text-align:center; border-left:4px solid {color};">
        <div style="font-size:12px; color:#666;">{label}</div>
        <div style="font-size:18px; font-weight:bold;">${format_millions(actual)}M vs ${format_millions(budget)}M</div>
        <div style="font-size:14px; color:{color}; font-weight:bold;">{sign}{format_millions(var)}M ({sign}{var_pct:.1f}%)</div>
    </div>
    """, unsafe_allow_html=True)


def render_variance_section(title, items, col_a, col_b, label_a, label_b, use_numbers=True):
    if not items:
        st.write("No data available.")
        return
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

    # --- Todo Memo ---
    with st.expander(f"📝 Todo / Memo — {selected}", expanded=False):
        saved_todo = db.get_todo(selected)
        todo_text = st.text_area("", value=saved_todo, height=150, key="todo_memo",
                                  placeholder="Type your notes here... (saved per snapshot)")
        if st.button("Save Memo", key="save_todo"):
            db.save_todo(selected, todo_text)
            st.success("Saved!")

    # --- FY26 Summary Cards ---
    fy_totals = db.query("""
        SELECT
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy_fcst,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'budget' THEN amount_usd ELSE 0 END) as fy_bud,
            SUM(CASE WHEN period = 'FY25' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy25_act
        FROM fee_income WHERE snapshot = ? AND period IN ('FY25', 'FY26')
    """, (selected,))

    # MTD/YTD totals
    mtd_data = get_mtd_comparison(db, selected)
    ytd_data = get_ytd_comparison(db, selected)

    mtd_act_total = sum(r["mtd_act"] for r in mtd_data) if mtd_data else 0
    mtd_bud_total = sum(r["mtd_bud"] for r in mtd_data) if mtd_data else 0
    ytd_act_total = sum(r["ytd_act"] for r in ytd_data) if ytd_data else 0
    ytd_bud_total = sum(r["ytd_bud"] for r in ytd_data) if ytd_data else 0

    fy_fcst = fy_totals[0]["fy_fcst"] or 0 if fy_totals else 0
    fy_bud = fy_totals[0]["fy_bud"] or 0 if fy_totals else 0
    fy25_act = fy_totals[0]["fy25_act"] or 0 if fy_totals else 0

    def metric_row(label, actual, actual_label, budget, budget_label):
        """Render one row as styled cards matching table color tone."""
        var = actual - budget
        var_pct = (var / budget * 100) if budget != 0 else 0
        var_color = "#38a169" if var >= 0 else "#c53030"
        sign = "+" if var >= 0 else ""
        st.markdown(f"""
        <div style="display:flex; gap:12px; margin-bottom:8px;">
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid #4a5568;">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">{actual_label}</div>
                <div style="font-size:22px; font-weight:bold; color:#2d3748;">${format_millions(actual)}M</div>
            </div>
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid #4a5568;">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">{budget_label}</div>
                <div style="font-size:22px; font-weight:bold; color:#2d3748;">${format_millions(budget)}M</div>
            </div>
            <div style="flex:1; background:#f7fafc; border-radius:6px; padding:14px 16px; border-top:3px solid {var_color};">
                <div style="font-size:12px; color:#718096; text-transform:uppercase;">Variance</div>
                <div style="font-size:22px; font-weight:bold; color:{var_color};">{sign}{format_millions(var)}M ({sign}{var_pct:.1f}%)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    fcst_label = f"FY26 Fcst ({selected})"

    # Row 1: FY26 Forecast vs Budget
    st.subheader("FY26 Fee Income")
    metric_row("FY26", fy_fcst, fcst_label, fy_bud, "FY26 Budget")

    # Row 2: MTD Act vs Bud
    st.markdown("")
    metric_row("MTD", mtd_act_total, f"MTD {month_name} Actual", mtd_bud_total, f"MTD {month_name} Budget")

    # Row 3: YTD Act vs Bud
    metric_row("YTD", ytd_act_total, f"YTD Jan-{month_name} Actual", ytd_bud_total, f"YTD Jan-{month_name} Budget")

    # Row 4: FY26 Fcst vs FY25 Act
    metric_row("YoY", fy_fcst, fcst_label, fy25_act, "FY25 Actual")

    # --- Variance Tables (email-style with styled HTML + editable drivers) ---
    st.markdown("---")

    fy_data = get_fy_comparison(db, selected)
    yoy_data = get_yoy_comparison(db, selected)

    HEADER_COLOR = "#4a5568"

    def fmt_var(v):
        """Format variance with color: red for positive, blue for negative."""
        if v < -0.05:
            return f'<span style="color:#c53030;">({abs(v):.1f})</span>'
        elif v > 0.05:
            return f'<span style="color:#38a169;">+{v:.1f}</span>'
        return "-"

    def render_variance_table(title, table_key, data, col_a, col_b, label_a, label_b, top_n=5):
        """Render a styled HTML variance table with editable drivers."""
        st.subheader(title)
        if not data:
            st.info("No data.")
            return

        # Load saved drivers
        saved_drivers = db.get_drivers(selected, table_key)

        for r in data:
            r["_var"] = r[col_a] - r[col_b]
        sorted_data = sorted(data, key=lambda x: abs(x["_var"]), reverse=True)
        # Show items with |variance| >= 0.15M (rounds to 0.2), rest as Other
        key_items = [r for r in sorted_data if round(abs(r["_var"]) / 1e6, 1) >= 0.2]
        other_items = [r for r in sorted_data if round(abs(r["_var"]) / 1e6, 1) < 0.2]

        sub_a = sum(r[col_a] for r in key_items)
        sub_b = sum(r[col_b] for r in key_items)
        other_a = sum(r[col_a] for r in other_items)
        other_b = sum(r[col_b] for r in other_items)
        total_a = sum(r[col_a] for r in data)
        total_b = sum(r[col_b] for r in data)

        # Build HTML table
        html = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif;">
        <thead><tr style="background-color:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Project</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">{label_a}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">{label_b}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">Variance</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Variance Driver</th>
        </tr></thead><tbody>"""

        for i, item in enumerate(key_items):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            name = item["project_name"]
            driver = saved_drivers.get(name, "")
            v = item["_var"] / 1e6
            html += f"""<tr style="background-color:{bg};">
                <td style="padding:6px 12px; border:1px solid #cbd5e0; font-weight:bold;">{name}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{item[col_a]/1e6:.1f}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{item[col_b]/1e6:.1f}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(v)}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; font-size:12px;">{driver}</td>
            </tr>"""

        # Subtotal
        sv = (sub_a - sub_b) / 1e6
        html += f"""<tr style="background-color:#edf2f7; font-weight:bold;">
            <td style="padding:6px 12px; border:1px solid #cbd5e0;">Subtotal (Key Items)</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{sub_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{sub_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(sv)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
        </tr>"""

        # Other
        ov = (other_a - other_b) / 1e6
        html += f"""<tr>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;">Other (net)</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{other_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{other_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(ov)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; font-size:12px;">기타 프로젝트 순합</td>
        </tr>"""

        # Grand Total
        tv = (total_a - total_b) / 1e6
        html += f"""<tr style="background-color:{HEADER_COLOR}; color:white; font-weight:bold;">
            <td style="padding:6px 12px; border:1px solid #cbd5e0;">Grand Total</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{total_a/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{total_b/1e6:.1f}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{fmt_var(tv)}</td>
            <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
        </tr>"""

        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Unit: USD millions")

        # Editable drivers
        with st.expander(f"Edit Variance Drivers — {title}"):
            updated = {}
            for item in key_items:
                name = item["project_name"]
                v = item["_var"] / 1e6
                updated[name] = st.text_area(
                    f"{name} (var {fmt_var(v)}M)",
                    value=saved_drivers.get(name, ""),
                    height=68,
                    key=f"driver_{table_key}_{name}",
                )
            if st.button("Save Drivers", key=f"save_{table_key}"):
                db.save_drivers(selected, table_key, updated)
                st.success("Saved!")
                st.rerun()

    # 4 tables (same order as metric rows: FY26 vs Bud → MTD → YTD → FY26 vs FY25)
    render_variance_table(
        f"{fcst_label} vs FY26 Bud", "fy_bud",
        fy_data, "fy_fcst", "fy_bud", fcst_label, "FY26 Bud")

    render_variance_table(
        f"MTD {month_name} Act vs MTD {month_name} Bud", "mtd",
        mtd_data, "mtd_act", "mtd_bud", "MTD Act", "MTD Bud")

    render_variance_table(
        f"YTD {month_name} Act vs YTD {month_name} Bud", "ytd",
        ytd_data, "ytd_act", "ytd_bud", "YTD Act", "YTD Bud")

    render_variance_table(
        f"{fcst_label} vs FY25 Act", "fy_yoy",
        yoy_data, "fy26", "fy25", fcst_label, "FY25 Act")

    # --- Monthly P&L — Fee Income by Fee Type (PPT Slide 2 table format) ---
    st.markdown("---")
    st.header("Monthly P&L — Fee Income")

    FEE_TYPE_ORDER = [
        "Asset Mgmt Fee",
        "Leasing Fee",
        "Development Mgmt Fee",
        "Acq / Div Fee",
        "Other Fee",
    ]

    def query_fee_by_type(db, snapshot, period_filter, period_type_filter):
        """Sum amount by fee_type for given period/period_type filters."""
        if isinstance(period_filter, list):
            placeholders = ",".join(["?"] * len(period_filter))
            rows = db.query(f"""
                SELECT fee_type, SUM(amount_usd) as total
                FROM fee_income
                WHERE snapshot = ? AND period IN ({placeholders}) AND period_type = ?
                GROUP BY fee_type
            """, (snapshot, *period_filter, period_type_filter))
        else:
            rows = db.query("""
                SELECT fee_type, SUM(amount_usd) as total
                FROM fee_income
                WHERE snapshot = ? AND period = ? AND period_type = ?
                GROUP BY fee_type
            """, (snapshot, period_filter, period_type_filter))
        return {r["fee_type"]: r["total"] for r in rows}

    mtd_month = f"2026-{n:02d}"
    ytd_months = [f"2026-{m:02d}" for m in range(1, n + 1)]

    mtd_act_by_type = query_fee_by_type(db, selected, mtd_month, "actual")
    mtd_bud_by_type = query_fee_by_type(db, selected, mtd_month, "budget")
    ytd_act_by_type = query_fee_by_type(db, selected, ytd_months, "actual")
    ytd_bud_by_type = query_fee_by_type(db, selected, ytd_months, "budget")
    fy_fcst_by_type = query_fee_by_type(db, selected, "FY26", "forecast")
    fy_bud_by_type = query_fee_by_type(db, selected, "FY26", "budget")
    fy25_act_by_type = query_fee_by_type(db, selected, "FY25", "actual")

    def pct(a, b):
        if b == 0:
            return "-"
        v = (a - b) / abs(b) * 100
        return f"{v:+.0f}%"

    def fv(val):
        """Format value in millions."""
        if abs(val) < 500:
            return "-"
        return f"{val/1e6:.1f}"

    # Build HTML table
    hdr = HEADER_COLOR
    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead>
    <tr style="background:{hdr}; color:white; font-weight:bold; text-align:center;">
        <th style="padding:6px 8px; border:1px solid #cbd5e0; text-align:left;" rowspan="2">(in US$'mil)</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;" colspan="4">MTD {month_name}</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;" colspan="4">YTD {month_name}</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;" colspan="4">{fcst_label} vs FY26 Bud</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;" colspan="4">{fcst_label} vs FY25</th>
    </tr>
    <tr style="background:{hdr}; color:white; font-weight:bold; text-align:center; font-size:11px;">
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Actual</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Budget</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Var</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">%Δ</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Actual</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Budget</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Var</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">%Δ</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Fcst</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Budget</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Var</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">%Δ</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Fcst</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">FY25</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">Var</th>
        <th style="padding:4px 6px; border:1px solid #cbd5e0;">%Δ</th>
    </tr>
    </thead><tbody>"""

    # Accumulators for subtotals
    excl_promote = {"mtd_a": 0, "mtd_b": 0, "ytd_a": 0, "ytd_b": 0,
                    "fy_f": 0, "fy_b": 0, "fy25": 0}

    def add_row(label, mtd_a, mtd_b, ytd_a, ytd_b, fy_f, fy_b, fy25, bold=False, bg="#ffffff"):
        fw = "font-weight:bold;" if bold else ""
        style = f"background:{bg}; {fw}"
        mtd_v = mtd_a - mtd_b
        ytd_v = ytd_a - ytd_b
        fy_v = fy_f - fy_b
        yoy_v = fy_f - fy25
        return f"""<tr style="{style}">
            <td style="padding:5px 8px; border:1px solid #cbd5e0;">{label}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(mtd_a)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(mtd_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(mtd_v)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{pct(mtd_a, mtd_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(ytd_a)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(ytd_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(ytd_v)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{pct(ytd_a, ytd_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(fy_f)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(fy_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(fy_v)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{pct(fy_f, fy_b)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(fy_f)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(fy25)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{fv(yoy_v)}</td>
            <td style="padding:5px 6px; border:1px solid #cbd5e0; text-align:right;">{pct(fy_f, fy25)}</td>
        </tr>"""

    for i, ft in enumerate(FEE_TYPE_ORDER):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        ma = mtd_act_by_type.get(ft, 0)
        mb = mtd_bud_by_type.get(ft, 0)
        ya = ytd_act_by_type.get(ft, 0)
        yb = ytd_bud_by_type.get(ft, 0)
        ff = fy_fcst_by_type.get(ft, 0)
        fb = fy_bud_by_type.get(ft, 0)
        f5 = fy25_act_by_type.get(ft, 0)
        html += add_row(ft, ma, mb, ya, yb, ff, fb, f5, bg=bg)
        excl_promote["mtd_a"] += ma
        excl_promote["mtd_b"] += mb
        excl_promote["ytd_a"] += ya
        excl_promote["ytd_b"] += yb
        excl_promote["fy_f"] += ff
        excl_promote["fy_b"] += fb
        excl_promote["fy25"] += f5

    # Fee Income excl. Promote
    html += add_row("Fee Income excl. Promote",
                     excl_promote["mtd_a"], excl_promote["mtd_b"],
                     excl_promote["ytd_a"], excl_promote["ytd_b"],
                     excl_promote["fy_f"], excl_promote["fy_b"],
                     excl_promote["fy25"], bold=True, bg="#edf2f7")

    # Promote Fee
    pm_a = mtd_act_by_type.get("Promote Fee", 0)
    pm_b = mtd_bud_by_type.get("Promote Fee", 0)
    py_a = ytd_act_by_type.get("Promote Fee", 0)
    py_b = ytd_bud_by_type.get("Promote Fee", 0)
    pf_f = fy_fcst_by_type.get("Promote Fee", 0)
    pf_b = fy_bud_by_type.get("Promote Fee", 0)
    pf_5 = fy25_act_by_type.get("Promote Fee", 0)
    html += add_row("Promote Fee", pm_a, pm_b, py_a, py_b, pf_f, pf_b, pf_5)

    # Fee Income (total)
    html += add_row("Fee Income",
                     excl_promote["mtd_a"] + pm_a, excl_promote["mtd_b"] + pm_b,
                     excl_promote["ytd_a"] + py_a, excl_promote["ytd_b"] + py_b,
                     excl_promote["fy_f"] + pf_f, excl_promote["fy_b"] + pf_b,
                     excl_promote["fy25"] + pf_5,
                     bold=True, bg=HEADER_COLOR)

    # Override last row to white text
    html = html.rsplit("<tr", 1)
    html = html[0] + '<tr style="background:' + HEADER_COLOR + '; font-weight:bold; color:white;">' + html[1].split(">", 1)[1]

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")

    # --- Watch List FY2026 (styled HTML table + editable) ---
    st.markdown("---")
    st.header("Watch List FY2026")

    watch_items = db.get_watch_list()
    pnl_items = [w for w in watch_items if w.get("category") == "P&L"]
    cf_items = [w for w in watch_items if w.get("category") == "CF"]

    def render_watch_html(title, items):
        if not items:
            return
        wh = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif; margin-bottom:16px;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">{title}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Fund/Project</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">Impact($mil)</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Lost/Delay</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Comment</th>
        </tr></thead><tbody>"""
        for i, w in enumerate(items):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            impact = w.get("impact_mil")
            impact_str = f"{impact:.1f}" if impact is not None else "-"
            wh += f"""<tr style="background:{bg};">
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("fund_project", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("fund_project", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{impact_str}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("lost_delay", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("comment", "")}</td>
            </tr>"""
        wh += "</tbody></table>"
        st.markdown(wh, unsafe_allow_html=True)

    # Fix: first column should show the P&L line item, not fund_project again
    def render_watch_html_v2(title, items):
        if not items:
            return
        wh = f"""<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Calibri,sans-serif; margin-bottom:16px;">
        <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">{title}</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Fund/Project</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:right;">Impact($mil)</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Lost/Delay</th>
            <th style="padding:8px 12px; border:1px solid #cbd5e0; text-align:left;">Comment</th>
        </tr></thead><tbody>"""
        for i, w in enumerate(items):
            bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
            impact = w.get("impact_mil")
            impact_str = f"{impact:.1f}" if impact is not None else ""
            wh += f"""<tr style="background:{bg};">
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("pnl_item", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("fund_project", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0; text-align:right;">{impact_str}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("lost_delay", "")}</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;">{w.get("comment", "")}</td>
            </tr>"""
        # Empty rows to match PPT style
        for _ in range(max(0, 4 - len(items))):
            wh += f"""<tr><td style="padding:6px 12px; border:1px solid #cbd5e0;">&nbsp;</td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td>
                <td style="padding:6px 12px; border:1px solid #cbd5e0;"></td></tr>"""
        wh += "</tbody></table>"
        st.markdown(wh, unsafe_allow_html=True)

    # Render P&L and CF watch lists
    pnl_display = [{"pnl_item": w.get("pnl_item", ""), "fund_project": w["fund_project"],
                     "impact_mil": w.get("impact_mil"), "lost_delay": w.get("lost_delay", ""),
                     "comment": w.get("comment", "")} for w in pnl_items]
    cf_display = [{"pnl_item": w.get("pnl_item", ""), "fund_project": w["fund_project"],
                    "impact_mil": w.get("impact_mil"), "lost_delay": w.get("lost_delay", ""),
                    "comment": w.get("comment", "")} for w in cf_items]

    render_watch_html_v2("P&L", pnl_display)
    render_watch_html_v2("CF", cf_display)

    if not pnl_items and not cf_items:
        st.info("No watch list items. Use the editor below to add items.")

    with st.expander("Edit Watch List"):
        if watch_items:
            edit_data = [{"category": w["category"],
                          "pnl_item": w.get("pnl_item", ""),
                          "fund_project": w["fund_project"],
                          "impact_mil": w.get("impact_mil"),
                          "lost_delay": w.get("lost_delay", ""),
                          "comment": w.get("comment", "")} for w in watch_items]
        else:
            edit_data = [{"category": "P&L", "pnl_item": "", "fund_project": "",
                          "impact_mil": None, "lost_delay": "", "comment": ""}]
        edited_df = st.data_editor(
            pd.DataFrame(edit_data),
            num_rows="dynamic",
            column_config={
                "category": st.column_config.SelectboxColumn("P&L/CF", options=["P&L", "CF"], required=True),
                "pnl_item": st.column_config.TextColumn("P&L Line Item (e.g. Acq Fee)"),
                "fund_project": st.column_config.TextColumn("Fund/Project", required=True),
                "impact_mil": st.column_config.NumberColumn("Impact($mil)"),
                "lost_delay": st.column_config.SelectboxColumn("Lost/Delay", options=["Lost", "Delay", ""]),
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
