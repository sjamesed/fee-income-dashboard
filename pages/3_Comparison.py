"""Page 3: Comparison — variance analysis across different dimensions."""
import streamlit as st
import pandas as pd
from src.db import FeeIncomeDB
from src.queries import (
    get_ytd_comparison, get_fy_comparison,
    get_prior_snapshot_comparison, get_yoy_comparison, get_snapshot_n_value,
)

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def get_db():
    db = FeeIncomeDB()
    db.init_db()
    return db

HEADER_COLOR = "#4a5568"

def fv(val):
    if abs(val) < 0.05:
        return "-"
    return f"{val:.1f}"

def colored_var(val):
    if abs(val) < 0.05:
        return "-"
    if val > 0.05:
        return f'<span style="color:#c53030;">+{val:.1f}</span>'
    return f'<span style="color:#2b6cb0;">({abs(val):.1f})</span>'

def show_comparison_table(data, col_a, col_b, label_a, label_b):
    if not data:
        st.info("No data available for this comparison.")
        return

    sorted_data = sorted(data, key=lambda r: abs(r[col_a] - r[col_b]), reverse=True)

    html = f"""<table style="border-collapse:collapse; width:100%; font-size:12px; font-family:Calibri,sans-serif;">
    <thead><tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Project</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:left;">Platform</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_a}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{label_b}</th>
        <th style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">Variance</th>
    </tr></thead><tbody>"""

    total_a = total_b = 0
    for i, row in enumerate(sorted_data):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        a = row[col_a] / 1e6
        b = row[col_b] / 1e6
        v = a - b
        total_a += row[col_a]
        total_b += row[col_b]
        html += f"""<tr style="background:{bg};">
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{row["project_name"]}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0;">{row["platform"]}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(a)}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(b)}</td>
            <td style="padding:5px 10px; border:1px solid #cbd5e0; text-align:right;">{colored_var(v)}</td>
        </tr>"""

    tv = (total_a - total_b) / 1e6
    html += f"""<tr style="background:{HEADER_COLOR}; color:white; font-weight:bold;">
        <td style="padding:6px 10px; border:1px solid #cbd5e0;">Grand Total</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0;"></td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(total_a/1e6)}</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{fv(total_b/1e6)}</td>
        <td style="padding:6px 10px; border:1px solid #cbd5e0; text-align:right;">{colored_var(tv)}</td>
    </tr>"""

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Unit: USD millions")

def main():
    st.title("Comparison")
    db = get_db()
    snapshots = db.list_snapshots()
    if not snapshots:
        st.warning("No data loaded.")
        return

    latest = db.get_latest_snapshot()
    selected = st.selectbox("Snapshot", snapshots,
        index=snapshots.index(latest) if latest in snapshots else 0)

    n = get_snapshot_n_value(selected)
    month_name = MONTH_NAMES.get(n, str(n))

    mode = st.radio("Comparison Mode", [
        f"YTD {month_name} Act vs YTD {month_name} Bud",
        "FY26 Fcst vs FY26 Bud",
        "FY26 Fcst vs Prior Month Fcst",
        "YoY (FY26 vs FY25)",
    ], horizontal=True)

    if "YTD" in mode:
        data = get_ytd_comparison(db, selected)
        show_comparison_table(data, "ytd_act", "ytd_bud", f"YTD {month_name} Act", f"YTD {month_name} Bud")
    elif "Fcst vs FY26 Bud" in mode:
        data = get_fy_comparison(db, selected)
        show_comparison_table(data, "fy_fcst", "fy_bud", "FY26 Fcst", "FY26 Bud")
    elif "Prior Month" in mode:
        data = get_prior_snapshot_comparison(db, selected)
        if data is None:
            st.warning(f"Prior snapshot not found in database. Need snapshot with N={n-1}.")
        else:
            show_comparison_table(data, "current_fcst", "prior_fcst",
                                  f"Current ({selected})", f"Prior ({n-1}+{13-n})")
    elif "YoY" in mode:
        data = get_yoy_comparison(db, selected)
        show_comparison_table(data, "fy26", "fy25", "FY26 Fcst", "FY25 Act")

main()
